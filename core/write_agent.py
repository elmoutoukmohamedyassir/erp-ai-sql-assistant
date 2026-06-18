"""
core/write_agent.py — orchestrates the WRITE pipeline.

question → LLM (structured JSON) → parse → validate → (preview | execute)

Design decisions
-----------------
* Mirrors core/agent.py's shape and self-correction loop, but operates on
  structured JSON instead of raw SQL text — same retry pattern, different
  payload.
* Two public entry points map 1:1 onto the two new API endpoints:
    - preview(question)        → generate + validate, NEVER executes.
    - execute(action_payload)  → re-validates (defense in depth) and runs.
  Splitting these two steps is the core safety mechanism requested:
  nothing is written to the database without an explicit, separate
  "execute" call on an action that has already been previewed and
  validated.
* execute() re-validates the action from scratch rather than trusting
  that "if it passed preview, it's still fine" — schema can change
  between preview and execute (e.g. someone runs :rebuild), and a
  defense-in-depth re-check costs almost nothing.
* This module does NOT touch core/agent.py, sql/validator.py, or any
  read-path code. It only imports core/db.run_write (newly added,
  additive) and the new sql/write_* modules.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from core.db import run_write
from core.llm import call_llm
from sql.write_models import WriteAction, parse_write_action
from sql.write_prompt_builder import WRITE_SYSTEM_PROMPT, build_write_user_prompt
from sql.write_sql_builder import build_write_sql
from sql.write_validator import WRITABLE_TABLES, WriteValidationResult, validate_write_action
from utils.logger import get_logger

logger = get_logger(__name__)

MAX_CORRECTION_LOOPS = 2


@dataclass
class WritePreviewResult:
    """Result of generating + validating a write action, WITHOUT executing it."""

    question:             str
    requires_confirmation: bool = False
    action:                dict[str, Any] | None = None
    valid:                 bool = False
    errors:                list[str] = field(default_factory=list)
    warnings:              list[str] = field(default_factory=list)
    error:                 str | None = None   # top-level failure (LLM/parse error), distinct from validation errors
    attempts:              int = 0


@dataclass
class WriteExecuteResult:
    """Result of executing a previously validated write action."""

    action:        dict[str, Any]
    executed:       bool = False
    rows_affected:  int = 0
    duration_ms:    int = 0
    error:          str | None = None


def _build_column_hint() -> str:
    """
    Build a short text block of real column names per writable table,
    pulled from the LIVE DB schema, for injection into the write prompt.
    """
    from core.db import get_table_columns_real_case

    lines: list[str] = []
    for table in WRITABLE_TABLES:
        cols = get_table_columns_real_case(table)
        col_list = ", ".join(sorted(cols.values())) if cols else "(unable to load columns)"
        lines.append(f"{table}: {col_list}")
    return "\n".join(lines)


def _extract_json(raw: str) -> dict[str, Any]:
    """
    Strip markdown fences (if any) and parse the LLM output as JSON.
    Raises ValueError with a readable message on failure — callers turn
    this into a correction-loop error rather than letting it crash.
    """
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM output is not valid JSON: {exc}. Raw output: {raw[:200]!r}") from exc


class WriteAgent:
    """Handles the WRITE half of the agent — JSON generation, validation, execution."""

    def preview(self, question: str) -> WritePreviewResult:
        """
        Generate a structured write action for `question` and validate it.
        NEVER executes anything against the database.
        """
        logger.info("Write preview requested: %s", question)
        result = WritePreviewResult(question=question)

        column_hint = _build_column_hint()

        previous_json:  str | None = None
        previous_error: str | None = None

        for attempt in range(1, MAX_CORRECTION_LOOPS + 2):
            result.attempts = attempt

            user_prompt = build_write_user_prompt(
                question=question,
                column_hint=column_hint,
                previous_json=previous_json,
                error_message=previous_error,
            )

            try:
                raw_output = call_llm(WRITE_SYSTEM_PROMPT, user_prompt)
            except Exception as exc:
                result.error = f"LLM call failed: {exc}"
                logger.error("Write LLM error: %s", exc, exc_info=True)
                return result

            logger.info("Raw write LLM output: %s", raw_output[:300])

            try:
                raw_json = _extract_json(raw_output)
            except ValueError as exc:
                if attempt <= MAX_CORRECTION_LOOPS:
                    previous_json = raw_output
                    previous_error = str(exc)
                    continue
                result.error = str(exc)
                return result

            action_type = raw_json.get("action")
            if action_type == "UNSUPPORTED" or action_type == "UNSUPPORTED_RELATIVE_UPDATE":
                if action_type == "UNSUPPORTED_RELATIVE_UPDATE":
                    result.error = (
                        "Relative updates (e.g. 'increase stock by 10') are not yet "
                        "supported — please specify the exact target value instead "
                        "(e.g. 'set stock of X to 50')."
                    )
                else:
                    result.error = (
                        "No writable table/column matches this request. "
                        f"Writable tables: {sorted(WRITABLE_TABLES)}."
                    )
                return result

            # Parse into a typed InsertAction / UpdateAction.
            try:
                parsed_action: WriteAction = parse_write_action(raw_json)
            except Exception as exc:  # pydantic.ValidationError, mainly
                error_msg = f"Structured output validation failed: {exc}"
                logger.warning("Write parse error (attempt %d): %s", attempt, error_msg)
                if attempt <= MAX_CORRECTION_LOOPS:
                    previous_json = json.dumps(raw_json)
                    previous_error = error_msg
                    continue
                result.error = error_msg
                return result

            # Validate against the live DB schema + whitelist.
            validation: WriteValidationResult = validate_write_action(parsed_action)
            result.warnings.extend(validation.warnings)

            if not validation.valid:
                error_msg = "; ".join(validation.errors)
                logger.warning("Write validation failed (attempt %d): %s", attempt, error_msg)
                if attempt <= MAX_CORRECTION_LOOPS:
                    previous_json = json.dumps(raw_json)
                    previous_error = f"Validation error: {error_msg}"
                    continue
                result.action = parsed_action.model_dump()
                result.valid = False
                result.errors = validation.errors
                result.requires_confirmation = False
                return result

            # Success — return the validated action, awaiting confirmation.
            result.action = parsed_action.model_dump()
            result.valid = True
            result.requires_confirmation = True
            logger.info("Write action validated, awaiting confirmation: %s", result.action)
            return result

        result.error = "Unexpected end of write correction loop."
        return result

    def execute(self, action_payload: dict[str, Any]) -> WriteExecuteResult:
        """
        Execute a write action that has already been returned by preview().

        Re-validates from scratch (defense in depth) before building SQL
        and running it. This is the ONLY method in the write pipeline that
        touches the database with a mutating statement.
        """
        logger.info("Write execute requested: %s", action_payload)
        result = WriteExecuteResult(action=action_payload)

        try:
            action: WriteAction = parse_write_action(action_payload)
        except Exception as exc:
            result.error = f"Invalid action payload: {exc}"
            logger.warning("Write execute parse error: %s", exc)
            return result

        validation = validate_write_action(action)
        if not validation.valid:
            result.error = f"Action failed re-validation before execution: {'; '.join(validation.errors)}"
            logger.warning("Write execute blocked by re-validation: %s", validation.errors)
            return result

        built = build_write_sql(action)

        try:
            db_result = run_write(built.sql, built.params)
        except RuntimeError as exc:
            result.error = f"Execution failed: {exc}"
            logger.error("Write execution error: %s", exc, exc_info=True)
            return result

        result.executed = True
        result.rows_affected = db_result["rows_affected"]
        result.duration_ms = db_result["duration_ms"]
        logger.info(
            "Write executed OK — %d row(s) affected in %dms",
            result.rows_affected, result.duration_ms,
        )
        return result
