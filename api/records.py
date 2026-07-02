"""
api/records.py — generic table/column CRUD write endpoints for the
Data-Entry "Create Record" / "Update Record" panel.

Deliberately separate from the entity-aware NL write pipeline in
erp/erp_write_agent.py — this is the raw table+column path that
DataEntryPage.jsx drives directly (no LLM in the loop).

Safety model
------------
* Table name whitelist: must be a real table via core.db.get_all_table_names().
* Column whitelist + real casing: core.db.get_table_columns_real_case().
* SQL is always parameterized (SQLAlchemy bind params for VALUES). Table
  and column identifiers are never taken from user input directly — they
  are only used after being matched against the whitelists above, so an
  attacker-controlled string can never reach the SQL as an identifier
  unless it's already a real table/column name.
* preview() never executes. execute() re-validates from scratch before
  running anything — a client can't skip preview's checks by calling
  execute directly.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from auth.auth import TokenData, require_admin
from core.db import get_all_table_names, get_table_columns_real_case, run_write
from erp.schema_inspector import get_primary_key_columns, get_required_columns
from utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/records", tags=["records"])


# ── request / response models ───────────────────────────────────────────────

class CreateRequest(BaseModel):
    table: str
    values: dict[str, Any]


class UpdateRequest(BaseModel):
    table: str
    where: dict[str, Any]
    values: dict[str, Any]


class ExecuteRequest(BaseModel):
    operation: str          # "INSERT" | "UPDATE"
    table: str
    values: dict[str, Any]
    where: dict[str, Any] | None = None


class PreviewResponse(BaseModel):
    valid: bool
    operation: str
    table: str
    values: dict[str, Any]
    where: dict[str, Any] | None = None
    generated_sql: str | None = None
    errors: list[str] = []
    warnings: list[str] = []


class ExecuteResponse(BaseModel):
    operation: str
    table: str
    executed: bool
    rows_affected: int | None = None
    duration_ms: int | None = None
    error: str | None = None


# ── helpers ──────────────────────────────────────────────────────────────────

def _resolve_table(table: str) -> str | None:
    """Return the table name to use in SQL, or None if it's not a real table."""
    if table.upper() not in get_all_table_names():
        return None
    return table


def _resolve_columns(table: str, values: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Map user-supplied keys to real column casing; collect unknown-column errors."""
    real_cols = get_table_columns_real_case(table)
    resolved: dict[str, Any] = {}
    errors: list[str] = []
    for key, val in values.items():
        real = real_cols.get(key.upper())
        if real is None:
            errors.append(f"Unknown column '{key}' on table '{table}'")
            continue
        resolved[real] = val
    return resolved, errors


def _build_insert(table: str, values: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    param_names = [f"v{i}" for i in range(len(values))]
    columns_sql = ", ".join(f"[{c}]" for c in values)
    values_sql  = ", ".join(f":{p}" for p in param_names)
    sql = f"INSERT INTO [{table}] ({columns_sql}) VALUES ({values_sql})"
    params = dict(zip(param_names, values.values()))
    return sql, params


def _build_update(table: str, values: dict[str, Any], where: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    set_param_names   = [f"s{i}" for i in range(len(values))]
    where_param_names = [f"w{i}" for i in range(len(where))]
    set_sql   = ", ".join(f"[{c}] = :{p}" for c, p in zip(values, set_param_names))
    where_sql = " AND ".join(f"[{c}] = :{p}" for c, p in zip(where, where_param_names))
    sql = f"UPDATE [{table}] SET {set_sql} WHERE {where_sql}"
    params = dict(zip(set_param_names, values.values()))
    params.update(dict(zip(where_param_names, where.values())))
    return sql, params


def _preview(operation: str, table: str, values: dict[str, Any],
             where: dict[str, Any] | None) -> PreviewResponse:
    errors:   list[str] = []
    warnings: list[str] = []

    resolved_table = _resolve_table(table)
    if resolved_table is None:
        return PreviewResponse(valid=False, operation=operation, table=table,
                                values=values, where=where,
                                errors=[f"Unknown table '{table}'"])

    resolved_values, val_errors = _resolve_columns(resolved_table, values)
    errors.extend(val_errors)

    resolved_where: dict[str, Any] | None = None
    if operation == "UPDATE":
        if not where:
            errors.append("UPDATE requires at least one WHERE condition.")
        else:
            resolved_where, where_errors = _resolve_columns(resolved_table, where)
            errors.extend(where_errors)
            pk = get_primary_key_columns(resolved_table)
            if pk and resolved_where and not any(c.upper() in pk for c in resolved_where):
                warnings.append(
                    "WHERE clause doesn't target a primary key column — "
                    "this could match more than one row."
                )

    if operation == "INSERT":
        required = get_required_columns(resolved_table)
        provided_upper = {c.upper() for c in resolved_values}
        missing = sorted(required - provided_upper)
        if missing:
            errors.append(f"Missing required column(s): {', '.join(missing)}")

    if errors:
        return PreviewResponse(valid=False, operation=operation, table=resolved_table,
                                values=resolved_values, where=resolved_where,
                                errors=errors, warnings=warnings)

    if operation == "INSERT":
        sql, _ = _build_insert(resolved_table, resolved_values)
    else:
        sql, _ = _build_update(resolved_table, resolved_values, resolved_where or {})

    return PreviewResponse(valid=True, operation=operation, table=resolved_table,
                            values=resolved_values, where=resolved_where,
                            generated_sql=sql, errors=[], warnings=warnings)


# ── routes ───────────────────────────────────────────────────────────────────

@router.post("/create", response_model=PreviewResponse)
def preview_create(req: CreateRequest, _: TokenData = Depends(require_admin)):
    """Admin only — validate + build (but do not run) an INSERT for review."""
    return _preview("INSERT", req.table, req.values, None)


@router.post("/update", response_model=PreviewResponse)
def preview_update(req: UpdateRequest, _: TokenData = Depends(require_admin)):
    """Admin only — validate + build (but do not run) an UPDATE for review."""
    return _preview("UPDATE", req.table, req.values, req.where)


@router.post("/execute", response_model=ExecuteResponse)
def execute(req: ExecuteRequest, _: TokenData = Depends(require_admin)):
    """
    Admin only — re-validates from scratch, then actually runs the write.
    A client cannot skip preview's validation by calling this directly.
    """
    preview = _preview(req.operation, req.table, req.values, req.where)
    if not preview.valid:
        return ExecuteResponse(operation=req.operation, table=req.table,
                                executed=False, error="; ".join(preview.errors))

    if req.operation == "INSERT":
        sql, params = _build_insert(preview.table, preview.values)
    else:
        sql, params = _build_update(preview.table, preview.values, preview.where or {})

    try:
        result = run_write(sql, params)
    except RuntimeError as exc:
        return ExecuteResponse(operation=req.operation, table=preview.table,
                                executed=False, error=str(exc))

    return ExecuteResponse(
        operation=req.operation, table=preview.table, executed=True,
        rows_affected=result["rows_affected"], duration_ms=result["duration_ms"],
    )