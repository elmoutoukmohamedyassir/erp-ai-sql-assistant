"""
sql/write_validator.py — validation for structured write actions.

Design decisions
-----------------
* Validation happens on the structured WriteAction (InsertAction /
  UpdateAction), NOT on a SQL string — there is no SQL string yet at this
  point. This is the main safety improvement over the read pipeline's
  regex-based SQL validator: we are validating data, not parsing text.
* Table whitelist is explicit and conservative (`WRITABLE_TABLES` below).
  Even if a table exists in the live DB schema, it is NOT writable unless
  it's been explicitly added to this whitelist. This protects sensitive
  ERP tables (accounting entries, journals, etc.) from being touched by
  this feature until they've been deliberately reviewed and enabled.
* Column existence is checked against the LIVE database schema (same
  ground-truth source the read validator uses: core/db.get_table_columns),
  so the whitelist never drifts from the real DB.
* Primary-key / identity columns are blocked from INSERT values and from
  UPDATE values (you should never let an LLM set AR_Ref's identity column
  by hand) — but they ARE allowed in an UPDATE's `where` clause, since
  that's how you target a specific row.
* Returns a ValidationResult (mirrors sql/validator.py's ValidationResult
  shape) so the rest of the codebase has one consistent validation result
  pattern to work with.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sql.write_models import InsertAction, UpdateAction, WriteAction
from utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Table whitelist — ONLY these tables may be written to.
#
# This is intentionally a short, explicit allowlist rather than "anything
# in the DB schema". Add a table here only after confirming write access
# to it is safe and desired. Keys are uppercase table names; values are a
# short human-readable description (shown back in validation errors).
# ---------------------------------------------------------------------------
WRITABLE_TABLES: dict[str, str] = {
    "F_ARTICLE":  "Articles / products catalog",
    "F_ARTSTOCK": "Stock quantities per warehouse/depot",
    "F_COMPTET":  "Customers / suppliers (third-party accounts)",
}

# Columns that must never be written by an LLM-generated action — typically
# identity / primary-key / system-managed columns. Blocking these at the
# validator level (in addition to whatever constraints exist in SQL Server)
# gives us a clear, fast, in-process rejection with a readable error.
_BLOCKED_COLUMNS: frozenset[str] = frozenset({
    "AR_NO",       # F_ARTICLE internal identity-like column (if present)
    "CT_NO",       # F_COMPTET internal identity-like column (if present)
})


@dataclass
class WriteValidationResult:
    valid:        bool       = True
    errors:       list[str]  = field(default_factory=list)
    warnings:     list[str]  = field(default_factory=list)

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        self.valid = False

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)


def _check_table_whitelisted(table: str, result: WriteValidationResult) -> bool:
    if table not in WRITABLE_TABLES:
        result.add_error(
            f"Table '{table}' is not in the write whitelist. "
            f"Writable tables: {sorted(WRITABLE_TABLES)}."
        )
        return False
    return True


def _check_table_exists(table: str, result: WriteValidationResult) -> bool:
    """Cross-check against the LIVE DB schema (ground truth)."""
    from core.db import get_all_table_names  # lazy import, same pattern as sql/validator.py

    real_tables = get_all_table_names()
    if table not in real_tables:
        result.add_error(f"Table '{table}' does not exist in the database.")
        return False
    return True


def _check_columns(
    table: str,
    columns: dict[str, object],
    result: WriteValidationResult,
    *,
    context: str,
) -> None:
    """
    Verify every column referenced in `columns` exists on `table` (per the
    live DB schema) and is not in the blocked-columns set.
    `context` is "values" or "where", used only for error messages.
    """
    from core.db import get_table_columns  # lazy import, mirrors sql/validator.py

    real_cols = get_table_columns(table)
    if not real_cols:
        result.add_error(f"Could not load column metadata for table '{table}'.")
        return

    for col in columns:
        if col in _BLOCKED_COLUMNS and context == "values":
            result.add_error(
                f"Column '{col}' is a protected/identity column and cannot be "
                f"set directly in {context}."
            )
            continue
        if col not in real_cols:
            result.add_error(
                f"Column '{col}' does not exist on table '{table}' "
                f"(referenced in {context}). Available columns: {sorted(real_cols)[:20]} …"
            )


def _check_no_empty_payload(columns: dict[str, object], result: WriteValidationResult, *, context: str) -> None:
    if not columns:
        result.add_error(f"'{context}' must contain at least one column.")


def validate_insert(action: InsertAction) -> WriteValidationResult:
    result = WriteValidationResult()

    if not _check_table_whitelisted(action.table, result):
        return result
    if not _check_table_exists(action.table, result):
        return result

    _check_no_empty_payload(action.values, result, context="values")
    if not result.valid:
        return result

    _check_columns(action.table, action.values, result, context="values")

    if result.valid:
        logger.info("INSERT action validated OK: table=%s columns=%s", action.table, list(action.values))
    else:
        logger.warning("INSERT action validation failed: %s", result.errors)

    return result


def validate_update(action: UpdateAction) -> WriteValidationResult:
    result = WriteValidationResult()

    if not _check_table_whitelisted(action.table, result):
        return result
    if not _check_table_exists(action.table, result):
        return result

    _check_no_empty_payload(action.where, result, context="where")
    _check_no_empty_payload(action.values, result, context="values")
    if not result.valid:
        return result

    _check_columns(action.table, action.where, result, context="where")
    _check_columns(action.table, action.values, result, context="values")

    # An UPDATE with no WHERE narrowing at all is already impossible here
    # because `where` is required + non-empty by the Pydantic model, but we
    # still warn if the where-clause looks too broad (e.g. only on a
    # non-unique-looking column) — this is advisory, not blocking.
    if result.valid and len(action.where) == 1:
        result.add_warning(
            "UPDATE targets rows using a single WHERE column — "
            "double-check this uniquely identifies the intended row(s)."
        )

    if result.valid:
        logger.info(
            "UPDATE action validated OK: table=%s where=%s columns=%s",
            action.table, list(action.where), list(action.values),
        )
    else:
        logger.warning("UPDATE action validation failed: %s", result.errors)

    return result


def validate_write_action(action: WriteAction) -> WriteValidationResult:
    """Dispatch to the correct validator based on the action's concrete type."""
    if isinstance(action, InsertAction):
        return validate_insert(action)
    if isinstance(action, UpdateAction):
        return validate_update(action)

    # Should be unreachable given the WriteAction discriminated union, but
    # fail safe rather than silently allowing an unrecognized action type.
    result = WriteValidationResult()
    result.add_error(f"Unsupported action type: {type(action).__name__}")
    return result
