"""
api/records_router.py — Metadata-driven record creation and update endpoints.

Workflow
--------
1.  Client POSTs to /records/create   → validate, return preview + generated SQL.
    No data is written yet.
2.  Client reviews the preview, confirms.
3.  Client POSTs to /records/execute  → run the parameterized SQL.
    The server re-validates the action before executing (never trust a round-tripped payload blindly).

Similarly for /records/update → /records/execute (same execute endpoint, action.action discriminates).

Security
--------
* /records/create  requires `require_any`   (authenticated user can preview)
* /records/update  requires `require_any`
* /records/execute requires `require_admin` (only admin can write to DB)
* All table and column names are validated against the LIVE DB schema.
* System tables are blocked.
* Values are ALWAYS passed as SQLAlchemy bind parameters — no string concatenation.
* Identity columns are blocked from INSERT/UPDATE values.
"""
from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth.auth import TokenData, require_admin, require_any
from core.db import get_all_table_names, get_engine, run_write
from utils.logger import get_logger
from api.metadata_router import _is_system_table, _fetch_column_metadata

logger = get_logger(__name__)

router = APIRouter(prefix="/records", tags=["records"])

# ---------------------------------------------------------------------------
# Scalar value type (mirrors sql/write_models.WriteValue)
# ---------------------------------------------------------------------------
WriteValue = str | int | float | bool | None


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class CreateRequest(BaseModel):
    table: str
    values: dict[str, WriteValue]


class UpdateRequest(BaseModel):
    table: str
    where: dict[str, WriteValue]
    values: dict[str, WriteValue]


class PreviewResponse(BaseModel):
    valid: bool
    table: str
    operation: str              # "INSERT" | "UPDATE"
    values: dict[str, Any]
    where: dict[str, Any] | None
    generated_sql: str
    requires_confirmation: bool
    errors: list[str]
    warnings: list[str]


class ExecuteRequest(BaseModel):
    table: str
    operation: str              # "INSERT" | "UPDATE"
    values: dict[str, WriteValue]
    where: dict[str, WriteValue] | None = None


class ExecuteResponse(BaseModel):
    executed: bool
    table: str
    operation: str
    rows_affected: int
    duration_ms: int
    error: str | None


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _validate_table(table: str) -> tuple[str, list[str]]:
    """
    Normalise to UPPER, check it's not a system table, check it exists.
    Returns (normalised_name, errors_list).
    """
    upper = table.strip().upper()
    errors: list[str] = []

    if _is_system_table(upper):
        errors.append(f"Table '{upper}' is a system table and cannot be modified.")
        return upper, errors

    all_tables = get_all_table_names()
    if upper not in all_tables:
        errors.append(f"Table '{upper}' does not exist in the database.")

    return upper, errors


def _validate_columns(
    table: str,
    columns: dict[str, WriteValue],
    *,
    context: str,
    block_identity: bool,
) -> tuple[dict[str, WriteValue], list[str], list[str]]:
    """
    Validate column names against live schema metadata.
    Returns (normalised_columns, errors, warnings).
    """
    errors: list[str] = []
    warnings: list[str] = []

    try:
        col_meta = _fetch_column_metadata(table)
    except HTTPException as exc:
        return columns, [str(exc.detail)], []

    col_map = {c.name.upper(): c for c in col_meta}
    normalised: dict[str, WriteValue] = {}

    for raw_key, val in columns.items():
        upper_key = raw_key.strip().upper()

        if upper_key not in col_map:
            errors.append(
                f"Column '{raw_key}' does not exist on table '{table}' "
                f"(referenced in {context})."
            )
            continue

        meta = col_map[upper_key]

        if block_identity and (meta.is_identity or meta.is_computed):
            errors.append(
                f"Column '{meta.name}' is an identity/computed column and "
                f"cannot be set in {context}."
            )
            continue

        # Type coercion warnings (non-blocking)
        if val is not None:
            numeric_types = {"int", "bigint", "smallint", "tinyint", "decimal", "numeric", "float", "real", "money", "smallmoney"}
            if meta.data_type in numeric_types:
                try:
                    float(str(val))
                except ValueError:
                    warnings.append(
                        f"Column '{meta.name}' expects a numeric value but got '{val}'."
                    )

        normalised[meta.name] = val   # use real casing from DB

    return normalised, errors, warnings


def _check_required_columns(
    table: str,
    provided: dict[str, WriteValue],
    operation: str,
) -> list[str]:
    """Return errors for required columns that are missing from `provided`."""
    if operation != "INSERT":
        return []

    try:
        col_meta = _fetch_column_metadata(table)
    except HTTPException:
        return []

    provided_upper = {k.upper() for k in provided}
    missing = [
        c.name
        for c in col_meta
        if c.is_required and c.name.upper() not in provided_upper
    ]
    if missing:
        return [f"Required column(s) missing from INSERT values: {missing}"]
    return []


def _build_insert_sql(table: str, values: dict[str, WriteValue]) -> tuple[str, dict]:
    """
    Build a parameterized INSERT statement.
    Returns (sql_string, params_dict).
    Column names are bracketed to handle reserved-word names safely.
    """
    cols = list(values.keys())
    params = {f"p_{i}": v for i, v in enumerate(values.values())}
    placeholders = ", ".join(f":p_{i}" for i in range(len(cols)))
    col_list = ", ".join(f"[{c}]" for c in cols)
    sql = f"INSERT INTO [{table}] ({col_list}) VALUES ({placeholders})"
    return sql, params


def _build_update_sql(
    table: str,
    where: dict[str, WriteValue],
    values: dict[str, WriteValue],
) -> tuple[str, dict]:
    """
    Build a parameterized UPDATE statement.
    Returns (sql_string, params_dict).
    """
    params: dict[str, Any] = {}
    set_parts: list[str] = []
    for i, (col, val) in enumerate(values.items()):
        key = f"s_{i}"
        set_parts.append(f"[{col}] = :{key}")
        params[key] = val

    where_parts: list[str] = []
    for i, (col, val) in enumerate(where.items()):
        key = f"w_{i}"
        where_parts.append(f"[{col}] = :{key}")
        params[key] = val

    set_clause   = ", ".join(set_parts)
    where_clause = " AND ".join(where_parts)
    sql = f"UPDATE [{table}] SET {set_clause} WHERE {where_clause}"
    return sql, params


def _sql_preview(sql: str, params: dict) -> str:
    """
    Return a human-readable SQL preview with literal param values shown.
    Used only for display — execution always uses bind params.
    """
    preview = sql
    for key, val in params.items():
        display = f"'{val}'" if isinstance(val, str) else str(val) if val is not None else "NULL"
        preview = preview.replace(f":{key}", display)
    return preview


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/create", response_model=PreviewResponse)
def preview_create(req: CreateRequest, _: TokenData = Depends(require_any)):
    """
    Validate a CREATE (INSERT) payload and return a preview with generated SQL.
    Nothing is written to the database at this stage.
    """
    errors: list[str] = []
    warnings: list[str] = []

    table, tbl_errors = _validate_table(req.table)
    errors.extend(tbl_errors)

    if not req.values:
        errors.append("'values' must contain at least one column.")

    if errors:
        return PreviewResponse(
            valid=False, table=table, operation="INSERT",
            values=req.values, where=None,
            generated_sql="", requires_confirmation=False,
            errors=errors, warnings=warnings,
        )

    norm_values, col_errors, col_warnings = _validate_columns(
        table, req.values, context="values", block_identity=True
    )
    errors.extend(col_errors)
    warnings.extend(col_warnings)

    req_errors = _check_required_columns(table, norm_values, "INSERT")
    errors.extend(req_errors)

    valid = len(errors) == 0
    sql_preview = ""
    if valid:
        sql_str, params = _build_insert_sql(table, norm_values)
        sql_preview = _sql_preview(sql_str, params)

    return PreviewResponse(
        valid=valid, table=table, operation="INSERT",
        values=norm_values, where=None,
        generated_sql=sql_preview, requires_confirmation=valid,
        errors=errors, warnings=warnings,
    )


@router.post("/update", response_model=PreviewResponse)
def preview_update(req: UpdateRequest, _: TokenData = Depends(require_any)):
    """
    Validate an UPDATE payload and return a preview with generated SQL.
    Nothing is written to the database at this stage.
    """
    errors: list[str] = []
    warnings: list[str] = []

    table, tbl_errors = _validate_table(req.table)
    errors.extend(tbl_errors)

    if not req.where:
        errors.append("'where' must contain at least one condition.")
    if not req.values:
        errors.append("'values' must contain at least one column to update.")

    if errors:
        return PreviewResponse(
            valid=False, table=table, operation="UPDATE",
            values=req.values, where=req.where,
            generated_sql="", requires_confirmation=False,
            errors=errors, warnings=warnings,
        )

    norm_where, where_errors, where_warnings = _validate_columns(
        table, req.where, context="where", block_identity=False
    )
    norm_values, val_errors, val_warnings = _validate_columns(
        table, req.values, context="values", block_identity=True
    )

    errors.extend(where_errors)
    errors.extend(val_errors)
    warnings.extend(where_warnings)
    warnings.extend(val_warnings)

    if len(norm_where) == 1:
        warnings.append(
            "UPDATE uses a single WHERE condition — confirm this uniquely identifies the intended row(s)."
        )

    valid = len(errors) == 0
    sql_preview = ""
    if valid:
        sql_str, params = _build_update_sql(table, norm_where, norm_values)
        sql_preview = _sql_preview(sql_str, params)

    return PreviewResponse(
        valid=valid, table=table, operation="UPDATE",
        values=norm_values, where=norm_where,
        generated_sql=sql_preview, requires_confirmation=valid,
        errors=errors, warnings=warnings,
    )


@router.post("/execute", response_model=ExecuteResponse)
def execute_record(req: ExecuteRequest, _: TokenData = Depends(require_admin)):
    """
    Execute a previously previewed INSERT or UPDATE.

    The server re-validates the round-tripped action before writing —
    client-side tampering is rejected here rather than silently trusted.
    Raw SQL from the client is NEVER accepted; only the structured action
    payload is used to re-build parameterized SQL server-side.
    """
    errors: list[str] = []

    operation = req.operation.strip().upper()
    if operation not in ("INSERT", "UPDATE"):
        raise HTTPException(status_code=400, detail=f"Unsupported operation: '{operation}'")

    table, tbl_errors = _validate_table(req.table)
    errors.extend(tbl_errors)

    if not req.values:
        errors.append("'values' cannot be empty.")

    if operation == "UPDATE" and not req.where:
        errors.append("UPDATE requires a non-empty 'where' condition.")

    if errors:
        raise HTTPException(status_code=422, detail="; ".join(errors))

    # Re-validate columns (server-side, not trusting round-tripped payload)
    norm_values, val_errors, _ = _validate_columns(
        table, req.values, context="values", block_identity=True
    )
    if val_errors:
        raise HTTPException(status_code=422, detail="; ".join(val_errors))

    if operation == "INSERT":
        req_errors = _check_required_columns(table, norm_values, "INSERT")
        if req_errors:
            raise HTTPException(status_code=422, detail="; ".join(req_errors))
        sql_str, params = _build_insert_sql(table, norm_values)

    else:  # UPDATE
        norm_where, where_errors, _ = _validate_columns(
            table, req.where or {}, context="where", block_identity=False
        )
        if where_errors:
            raise HTTPException(status_code=422, detail="; ".join(where_errors))
        sql_str, params = _build_update_sql(table, norm_where, norm_values)

    # Execute via the safe run_write() — uses engine.begin() transaction
    try:
        result = run_write(sql_str, params)
    except RuntimeError as exc:
        logger.error("Execute failed for %s on %s: %s", operation, table, exc)
        return ExecuteResponse(
            executed=False, table=table, operation=operation,
            rows_affected=0, duration_ms=0, error=str(exc),
        )

    return ExecuteResponse(
        executed=True, table=table, operation=operation,
        rows_affected=result["rows_affected"],
        duration_ms=result["duration_ms"],
        error=None,
    )
