from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from core.llm import call_llm
from core.write_agent import WriteAgent, WriteExecuteResult
from erp.conversation_store import clear_conversation, get_conversation, merge_conversation
from erp.entities import ERPEntity, get_entity, get_required_fields, is_entity_writable
from erp.entity_prompt_builder import ENTITY_SYSTEM_PROMPT, build_entity_user_prompt
from sql.write_models import parse_write_action
from sql.write_validator import validate_write_action
from utils.logger import get_logger

logger = get_logger(__name__)

MAX_CORRECTION_LOOPS = 2


@dataclass
class ERPPreviewResult:
    conversation_id:            str
    question:                   str
    requires_more_information:  bool = False
    requires_confirmation:      bool = False
    entity:                     str | None = None
    table:                      str | None = None
    operation:                  str | None = None
    collected_fields:           dict[str, Any] = field(default_factory=dict)
    missing_fields:             list[str] = field(default_factory=list)
    action:                     dict[str, Any] | None = None  # InsertAction/UpdateAction-shaped, ready for execute()
    valid:                      bool = False
    errors:                     list[str] = field(default_factory=list)
    warnings:                   list[str] = field(default_factory=list)
    business_explanation:       str | None = None
    error:                      str | None = None
    attempts:                   int = 0


def _extract_json(raw: str) -> dict[str, Any]:
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


def _build_action_payload(entity: ERPEntity, operation: str, fields: dict[str, Any]) -> dict[str, Any]:
    """
    Translate entity-level fields into the exact InsertAction/UpdateAction
    JSON shape that sql/write_models.py already parses and validates.
    """
    if operation == "CREATE":
        return {"action": "INSERT", "table": entity.table, "values": dict(fields)}

    # UPDATE — the entity's key field becomes the WHERE target; everything
    # else becomes the SET values.
    key = entity.key_field
    if key not in fields:
        raise ValueError(f"Missing key field '{key}' required to target an UPDATE for {entity.name}.")
    where = {key: fields[key]}
    values = {k: v for k, v in fields.items() if k != key}
    if not values:
        raise ValueError(f"UPDATE for {entity.name} has no fields to set besides the key field.")
    return {"action": "UPDATE", "table": entity.table, "where": where, "values": values}


class ERPWriteAgent:
    """Entity-aware write orchestrator — sits in front of core.write_agent.WriteAgent."""

    def __init__(self) -> None:
        self._write_agent = WriteAgent()

    def preview(self, conversation_id: str, question: str) -> ERPPreviewResult:
        logger.info("ERP write preview [%s]: %s", conversation_id, question)
        result = ERPPreviewResult(conversation_id=conversation_id, question=question)

        existing = get_conversation(conversation_id)
        already_collected = dict(existing.collected_fields) if existing else {}
        known_entity_name = existing.entity_name if existing else None
        known_operation = existing.operation if existing else None

        previous_json:  str | None = None
        previous_error: str | None = None

        for attempt in range(1, MAX_CORRECTION_LOOPS + 2):
            result.attempts = attempt

            user_prompt = build_entity_user_prompt(
                question=question,
                already_collected=already_collected,
                previous_json=previous_json,
                error_message=previous_error,
            )

            try:
                raw_output = call_llm(ENTITY_SYSTEM_PROMPT, user_prompt)
            except Exception as exc:
                result.error = f"LLM call failed: {exc}"
                logger.error("ERP LLM error: %s", exc, exc_info=True)
                return result

            logger.info("Raw ERP LLM output: %s", raw_output[:300])

            try:
                raw_json = _extract_json(raw_output)
            except ValueError as exc:
                if attempt <= MAX_CORRECTION_LOOPS:
                    previous_json, previous_error = raw_output, str(exc)
                    continue
                result.error = str(exc)
                return result

            entity_key = raw_json.get("entity")
            if entity_key in ("UNSUPPORTED", "UNSUPPORTED_RELATIVE_UPDATE"):
                if entity_key == "UNSUPPORTED_RELATIVE_UPDATE":
                    result.error = (
                        "Relative updates (e.g. 'increase stock by 10') aren't supported yet — "
                        "please give the exact target value instead."
                    )
                else:
                    result.error = "No matching ERP entity found for this request."
                return result

            entity = get_entity(entity_key or known_entity_name or "")
            if entity is None:
                result.error = f"Unknown entity '{entity_key}'."
                return result
            if not is_entity_writable(entity):
                result.error = (
                    f"Entity '{entity.name}' is not yet enabled for write operations "
                    f"(table '{entity.table}' is not in the write whitelist)."
                )
                return result

            operation = raw_json.get("operation") or known_operation
            if operation not in ("CREATE", "UPDATE"):
                result.error = f"Unsupported or missing operation '{operation}'."
                return result

            raw_fields = raw_json.get("fields") or {}
            # Resolve friendly field names -> real uppercase columns.
            resolved_fields = {entity.resolve_column(k): v for k, v in raw_fields.items()}

            state = merge_conversation(
                conversation_id,
                entity_name=entity.name,
                operation=operation,
                new_fields=resolved_fields,
            )
            result.entity = entity.name
            result.table = entity.table
            result.operation = operation
            result.collected_fields = dict(state.collected_fields)

            required = get_required_fields(entity)
            missing = sorted(required - state.collected_fields.keys())

            if missing:
                result.requires_more_information = True
                result.missing_fields = missing
                result.business_explanation = f"Need {', '.join(missing)} to create this {entity.name.lower()}."
                logger.info("ERP write needs more info [%s]: missing=%s", conversation_id, missing)
                return result

            # All required fields present — translate to the existing
            # InsertAction/UpdateAction shape and run it through the SAME
            # validator the table/column write pipeline already uses.
            try:
                action_payload = _build_action_payload(entity, operation, state.collected_fields)
                parsed_action = parse_write_action(action_payload)
            except Exception as exc:
                error_msg = f"Could not build a valid action: {exc}"
                if attempt <= MAX_CORRECTION_LOOPS:
                    previous_json, previous_error = json.dumps(raw_json), error_msg
                    continue
                result.error = error_msg
                return result

            validation = validate_write_action(parsed_action)
            result.warnings.extend(validation.warnings)

            if not validation.valid:
                error_msg = "; ".join(validation.errors)
                logger.warning("ERP write validation failed (attempt %d): %s", attempt, error_msg)
                if attempt <= MAX_CORRECTION_LOOPS:
                    previous_json, previous_error = json.dumps(raw_json), f"Validation error: {error_msg}"
                    continue
                result.action = parsed_action.model_dump()
                result.errors = validation.errors
                return result

            result.action = parsed_action.model_dump()
            result.valid = True
            result.requires_confirmation = True
            verb = "create a new" if operation == "CREATE" else "update the"
            result.business_explanation = f"Ready to {verb} {entity.name.lower()} with: {state.collected_fields}."
            logger.info("ERP write ready for confirmation [%s]: %s", conversation_id, result.action)
            return result

        result.error = "Unexpected end of ERP correction loop."
        return result

    def execute(self, conversation_id: str, action_payload: dict[str, Any]) -> WriteExecuteResult:
        """
        Delegate execution to the existing, already-tested
        core.write_agent.WriteAgent — zero new execution logic here.
        Clears the conversation on success so a follow-up message starts
        a fresh slot-filling exchange instead of re-merging stale fields.
        """
        result = self._write_agent.execute(action_payload)
        if result.executed:
            clear_conversation(conversation_id)
        return result