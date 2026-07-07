"""
api/crm/common.py — shared, table-agnostic helpers for the CRM module.

Everything here operates on business dicts (friendly-field -> value) and
resolves them against real Sage columns via mapping.py + core.db's
existing schema-introspection helpers. Nothing here is specific to
Clients/Orders/Products/Stock — those modules just call into this one.

Reuses (does not modify):
  * core.db.get_engine                  — singleton engine
  * core.db.get_table_columns_real_case — real column casing lookup
  * core.db.get_all_table_names         — table existence check
  * core.db.run_query_params            — parameterized SELECT (added
    additively in core/db.py alongside the untouched run_query/run_write)
"""
from __future__ import annotations

import time
from typing import Any

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from core.db import (
    get_all_table_names,
    get_engine,
    get_table_columns_real_case,
    run_query_params,
)
from utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 200


# ── table / column resolution ───────────────────────────────────────────────

def ensure_table_exists(table: str) -> None:
    if table.upper() not in get_all_table_names():
        # This is an internal configuration problem (mapping.py points at a
        # table that doesn't exist in this database), never a user error.
        logger.error("CRM mapping error — table '%s' not found in database", table)
        raise HTTPException(
            status_code=500,
            detail="This feature isn't configured correctly yet. Please contact your administrator.",
        )


def resolve_column(table: str, candidates: list[str]) -> str | None:
    """Return the first candidate that's a real column on `table`, else None."""
    real_cols = get_table_columns_real_case(table)
    for candidate in candidates:
        real = real_cols.get(candidate.upper())
        if real:
            return real
    return None


def resolve_field_map(table: str, business_fields: dict[str, list[str]]) -> dict[str, str]:
    """
    business_field -> real column name, for whichever business fields
    actually have a matching column on this table. Fields with no match
    are silently dropped here (callers check required fields separately).
    """
    resolved: dict[str, str] = {}
    for business_name, candidates in business_fields.items():
        real = resolve_column(table, candidates)
        if real:
            resolved[business_name] = real
    return resolved


def to_business_dict(field_map: dict[str, str], row: dict[str, Any]) -> dict[str, Any]:
    """Real-column row -> business-field dict, using only resolved fields."""
    return {business: row.get(real) for business, real in field_map.items()}


def to_column_values(field_map: dict[str, str], business_values: dict[str, Any]) -> dict[str, Any]:
    """business-field values -> {real_column: value}, ignoring unknown/unmapped keys."""
    out: dict[str, Any] = {}
    for business_name, value in business_values.items():
        real = field_map.get(business_name)
        if real is not None and value is not None:
            out[real] = value
    return out


# ── code / reference number generation ──────────────────────────────────────

def generate_code(table: str, code_column: str, prefix: str, width: int = 6) -> str:
    """
    Generate the next business code like 'CL000123'.

    Pulls back every existing code starting with `prefix` and computes the
    highest numeric suffix in Python (rather than SQL MAX()), because some
    Sage installations store these columns as fixed-width/padded CHAR with
    collations that make MAX()/ORDER BY behave unreliably on string data.
    Doing the comparison in Python sidesteps that entirely.

    Simple approach — good enough for a low-concurrency CRM front end. For
    a live multi-user, high-volume deployment, wire this up to Sage's own
    counter mechanism instead.
    """
    sql = f"SELECT [{code_column}] FROM [{table}] WHERE [{code_column}] LIKE :prefix"
    result = run_query_params(sql, {"prefix": f"{prefix}%"})

    max_n = 0
    for row in result["rows"]:
        raw = row[0]
        if not raw:
            continue
        code = str(raw).strip()
        if not code.upper().startswith(prefix.upper()):
            continue
        digits = "".join(ch for ch in code[len(prefix):] if ch.isdigit())
        if digits:
            max_n = max(max_n, int(digits))

    return f"{prefix}{max_n + 1:0{width}d}"


# ── search + pagination ──────────────────────────────────────────────────────

def search_clause(columns: list[str], param_name: str = "q") -> str:
    if not columns:
        return "1=1"
    parts = [f"[{c}] LIKE :{param_name}" for c in columns]
    return "(" + " OR ".join(parts) + ")"


def list_rows(
    table: str,
    field_map: dict[str, str],
    *,
    search: str | None,
    search_business_fields: list[str],
    extra_where: str = "1=1",
    extra_params: dict[str, Any] | None = None,
    order_by: str,
    page: int,
    page_size: int,
) -> tuple[list[dict[str, Any]], int]:
    """Generic paginated + searchable SELECT over a mapped business table."""
    page = max(1, page)
    page_size = min(max(1, page_size), MAX_PAGE_SIZE)

    real_cols = [field_map[f] for f in search_business_fields if f in field_map]
    params: dict[str, Any] = dict(extra_params or {})

    where = extra_where
    if search and search.strip() and real_cols:
        where = f"{extra_where} AND {search_clause(real_cols)}"
        params["q"] = f"%{search.strip()}%"

    select_cols = ", ".join(f"[{real}] AS [{business}]" for business, real in field_map.items())

    count_sql = f"SELECT COUNT(*) AS cnt FROM [{table}] WHERE {where}"
    count_result = run_query_params(count_sql, params)
    total = int(count_result["rows"][0][0]) if count_result["rows"] else 0

    offset = (page - 1) * page_size
    data_sql = (
        f"SELECT {select_cols} FROM [{table}] WHERE {where} "
        f"ORDER BY {order_by} OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY"
    )
    data_params = dict(params)
    data_params["offset"] = offset
    data_params["limit"] = page_size
    data_result = run_query_params(data_sql, data_params)

    rows = [dict(zip(data_result["columns"], r)) for r in data_result["rows"]]
    return rows, total


def run_query_params_safe(sql: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """run_query_params, but converts DB errors into a friendly HTTPException."""
    try:
        return run_query_params(sql, params)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=friendly_db_error(exc))


def get_one_row(
    table: str,
    field_map: dict[str, str],
    where_column: str,
    where_value: Any,
    extra_where: str = "1=1",
    extra_params: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    select_cols = ", ".join(f"[{real}] AS [{business}]" for business, real in field_map.items())
    params: dict[str, Any] = dict(extra_params or {})
    params["where_value"] = where_value
    sql = (
        f"SELECT {select_cols} FROM [{table}] "
        f"WHERE [{where_column}] = :where_value AND {extra_where}"
    )
    result = run_query_params(sql, params)
    if not result["rows"]:
        return None
    return dict(zip(result["columns"], result["rows"][0]))


# ── writes (parameterized, transactional) ────────────────────────────────────

def run_write_many(statements: list[tuple[str, dict[str, Any]]]) -> int:
    """
    Execute several parameterized statements in ONE transaction — all
    succeed or all roll back. Used for multi-row operations (order header
    + lines) that core.db.run_write (single-statement) doesn't cover.
    Built on the same shared engine core.db already manages.
    """
    engine = get_engine()
    t0 = time.perf_counter()
    total_affected = 0
    try:
        with engine.begin() as conn:
            for sql, params in statements:
                result = conn.execute(text(sql), params)
                total_affected += result.rowcount if result.rowcount and result.rowcount > 0 else 0
        ms = int((time.perf_counter() - t0) * 1000)
        logger.info("CRM multi-write OK — %d statement(s), %dms", len(statements), ms)
        return total_affected
    except SQLAlchemyError as exc:
        ms = int((time.perf_counter() - t0) * 1000)
        logger.error("CRM multi-write failed (%dms): %s", ms, exc)
        raise RuntimeError(str(exc)) from exc


def build_insert(table: str, values: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    param_names = [f"v{i}" for i in range(len(values))]
    columns_sql = ", ".join(f"[{c}]" for c in values)
    values_sql = ", ".join(f":{p}" for p in param_names)
    sql = f"INSERT INTO [{table}] ({columns_sql}) VALUES ({values_sql})"
    return sql, dict(zip(param_names, values.values()))


def build_update(table: str, values: dict[str, Any], where: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    set_names = [f"s{i}" for i in range(len(values))]
    where_names = [f"w{i}" for i in range(len(where))]
    set_sql = ", ".join(f"[{c}] = :{p}" for c, p in zip(values, set_names))
    where_sql = " AND ".join(f"[{c}] = :{p}" for c, p in zip(where, where_names))
    sql = f"UPDATE [{table}] SET {set_sql} WHERE {where_sql}"
    params = dict(zip(set_names, values.values()))
    params.update(dict(zip(where_names, where.values())))
    return sql, params


def build_delete(table: str, where: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    where_names = [f"w{i}" for i in range(len(where))]
    where_sql = " AND ".join(f"[{c}] = :{p}" for c, p in zip(where, where_names))
    sql = f"DELETE FROM [{table}] WHERE {where_sql}"
    return sql, dict(zip(where_names, where.values()))


def friendly_db_error(exc: Exception) -> str:
    """Never surface raw SQL/driver errors to non-technical CRM users."""
    logger.error("CRM DB error: %s", exc)
    return "Something went wrong saving this record. Please try again or contact your administrator."