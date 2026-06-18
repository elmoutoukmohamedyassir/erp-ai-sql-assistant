"""
sql/write_sql_builder.py — builds parameterized SQL from validated
write actions.

Design decisions
-----------------
* This module is called ONLY after sql/write_validator.py has confirmed
  the action's table and columns are real and whitelisted. It does not
  re-validate — it trusts its caller (core/write_agent.py) to enforce the
  ordering: validate → build → execute.
* All values are passed as SQLAlchemy bound parameters (:p_0, :p_1, ...),
  NEVER interpolated into the SQL string. Table and column names (which
  SQLAlchemy `text()` cannot parameterize) come ONLY from the validated
  whitelist/schema — never from raw, unchecked user input — so there is
  no injection surface even though identifiers are string-formatted.
* Real-case column names are used (via core.db.get_table_columns_real_case)
  so generated SQL matches the actual DB column casing.
* Returns a small BuiltSql dataclass bundling (sql_text, params) — this
  keeps run_write()'s call site in core/write_agent.py trivial.
"""
from __future__ import annotations

from dataclasses import dataclass

from sql.write_models import InsertAction, UpdateAction
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class BuiltSql:
    sql: str
    params: dict[str, object]


def _quote_ident(name: str) -> str:
    """
    Wrap a table/column identifier in SQL Server square brackets.
    Safe here ONLY because `name` is guaranteed (by the caller) to come
    from the live DB schema / whitelist — never from raw user text.
    """
    return f"[{name}]"


def _real_case_columns(table: str) -> dict[str, str]:
    from core.db import get_table_columns_real_case  # lazy import, avoids import cycle at module load

    return get_table_columns_real_case(table)


def build_insert_sql(action: InsertAction) -> BuiltSql:
    """
    Build a parameterized INSERT statement for an already-validated
    InsertAction.

    Example output:
        INSERT INTO [F_ARTICLE] ([AR_Design], [AR_PrixVen])
        VALUES (:p_0, :p_1)
    """
    real_cols = _real_case_columns(action.table)

    col_names: list[str] = []
    placeholders: list[str] = []
    params: dict[str, object] = {}

    for i, (col_upper, value) in enumerate(action.values.items()):
        real_name = real_cols.get(col_upper, col_upper)  # fall back to as-given if missing
        param_name = f"p_{i}"
        col_names.append(_quote_ident(real_name))
        placeholders.append(f":{param_name}")
        params[param_name] = value

    sql = (
        f"INSERT INTO {_quote_ident(action.table)} "
        f"({', '.join(col_names)}) VALUES ({', '.join(placeholders)})"
    )

    logger.info("Built INSERT SQL for table=%s (%d columns)", action.table, len(col_names))
    return BuiltSql(sql=sql, params=params)


def build_update_sql(action: UpdateAction) -> BuiltSql:
    """
    Build a parameterized UPDATE statement for an already-validated
    UpdateAction.

    Example output:
        UPDATE [F_ARTSTOCK]
        SET [AS_QteSto] = :p_0
        WHERE [AR_Ref] = :p_1
    """
    real_cols = _real_case_columns(action.table)
    params: dict[str, object] = {}

    set_clauses: list[str] = []
    for i, (col_upper, value) in enumerate(action.values.items()):
        real_name = real_cols.get(col_upper, col_upper)
        param_name = f"p_set_{i}"
        set_clauses.append(f"{_quote_ident(real_name)} = :{param_name}")
        params[param_name] = value

    where_clauses: list[str] = []
    for i, (col_upper, value) in enumerate(action.where.items()):
        real_name = real_cols.get(col_upper, col_upper)
        param_name = f"p_where_{i}"
        where_clauses.append(f"{_quote_ident(real_name)} = :{param_name}")
        params[param_name] = value

    sql = (
        f"UPDATE {_quote_ident(action.table)} "
        f"SET {', '.join(set_clauses)} "
        f"WHERE {' AND '.join(where_clauses)}"
    )

    logger.info(
        "Built UPDATE SQL for table=%s (%d set columns, %d where columns)",
        action.table, len(set_clauses), len(where_clauses),
    )
    return BuiltSql(sql=sql, params=params)


def build_write_sql(action: InsertAction | UpdateAction) -> BuiltSql:
    """Dispatch helper — picks the right builder based on action type."""
    if isinstance(action, InsertAction):
        return build_insert_sql(action)
    if isinstance(action, UpdateAction):
        return build_update_sql(action)
    raise TypeError(f"Unsupported action type: {type(action).__name__}")
