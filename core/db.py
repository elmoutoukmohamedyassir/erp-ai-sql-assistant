"""
core/db.py — database layer.

Key design decisions
--------------------
* Singleton engine — created once, reused across the process lifetime.
* Two schema helpers exposed to other modules:
    - get_all_table_names()  → set[str]   used by the VALIDATOR
    - get_table_columns()    → dict       used by the VALIDATOR
  These are the ground-truth references. The FAISS index is only used
  to pick which tables go into the LLM prompt — it is NEVER used for
  validation.
* load_full_schema() is used by the schema indexer at build time.
* run_query() executes only pre-validated SELECT statements.
"""
from __future__ import annotations

import os
import time
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from utils.logger import get_logger

load_dotenv(Path(__file__).parent.parent / ".env", override=True)

logger = get_logger(__name__)

_engine: Engine | None = None



def get_engine() -> Engine:
    global _engine
    if _engine is not None:
        return _engine

    server   = os.getenv("DB_SERVER", "").strip()
    database = os.getenv("DB_NAME",   "").strip()
    username = os.getenv("DB_USER",   "").strip()
    password = os.getenv("DB_PASSWORD","").strip()

    if not server or not database:
        raise EnvironmentError("DB_SERVER and DB_NAME must be set in .env")

    if username and password:
        conn_str = (
            f"mssql+pyodbc://{username}:{password}@{server}/{database}"
            "?driver=ODBC+Driver+17+for+SQL+Server&TrustServerCertificate=yes"
        )
        logger.info("DB engine: SQL Server auth as '%s'", username)
    else:
        conn_str = (
            f"mssql+pyodbc://@{server}/{database}"
            "?driver=ODBC+Driver+17+for+SQL+Server"
            "&TrustServerCertificate=yes&Trusted_Connection=yes"
        )
        logger.info("DB engine: Windows trusted auth")

    _engine = create_engine(
        conn_str,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
    )
    return _engine



@lru_cache(maxsize=1)
def get_all_table_names() -> frozenset[str]:
    
    engine    = get_engine()
    inspector = inspect(engine)
    names     = frozenset(t.upper() for t in inspector.get_table_names())
    logger.info("Loaded %d real table names from DB", len(names))
    return names


@lru_cache(maxsize=512)
def get_table_columns(table_name: str) -> frozenset[str]:
    
    engine    = get_engine()
    inspector = inspect(engine)
    try:
        cols = inspector.get_columns(table_name)
        return frozenset(c["name"].upper() for c in cols)
    except Exception:
        return frozenset()


@lru_cache(maxsize=512)
def get_table_columns_real_case(table_name: str) -> dict[str, str]:
    """
    Like get_table_columns(), but returns a mapping of
    UPPERCASE_NAME -> RealCaseName instead of a flat uppercase set.

    The write SQL builder needs the real column casing to build valid
    INSERT/UPDATE statements (SQL Server is usually case-insensitive for
    identifiers, but preserving real casing avoids surprises on
    case-sensitive collations and keeps generated SQL readable in logs).

    Added for the write pipeline — get_table_columns() above remains
    untouched and is still what the READ validator uses.
    """
    engine    = get_engine()
    inspector = inspect(engine)
    try:
        cols = inspector.get_columns(table_name)
        return {c["name"].upper(): c["name"] for c in cols}
    except Exception:
        return {}


def clear_schema_cache() -> None:
    """Call this after rebuild_index to reset the LRU caches."""
    get_all_table_names.cache_clear()
    get_table_columns.cache_clear()
    get_table_columns_real_case.cache_clear()
    logger.info("Schema cache cleared")



def load_full_schema() -> dict[str, dict]:
    
    engine    = get_engine()
    inspector = inspect(engine)
    schema: dict[str, dict] = {}

    table_names = inspector.get_table_names()
    logger.info("Introspecting %d tables for schema index…", len(table_names))

    for table in table_names:
        try:
            raw_cols = inspector.get_columns(table)
            pk_info  = inspector.get_pk_constraint(table)
            fk_info  = inspector.get_foreign_keys(table)

            columns = [
                {
                    "name":     c["name"],
                    "type":     str(c["type"]),
                    "nullable": c.get("nullable", True),
                    "default":  str(c.get("default")) if c.get("default") else None,
                }
                for c in raw_cols
            ]

            schema[table] = {
                "columns":      columns,
                "primary_keys": pk_info.get("constrained_columns", []),
                "foreign_keys": [
                    {
                        "column":     fk["constrained_columns"][0] if fk["constrained_columns"] else "",
                        "ref_table":  fk["referred_table"],
                        "ref_column": fk["referred_columns"][0]    if fk["referred_columns"]    else "",
                    }
                    for fk in fk_info
                ],
            }
        except Exception as exc:
            logger.warning("Could not introspect '%s': %s", table, exc)

    logger.info("Schema loaded: %d tables", len(schema))
    return schema



def run_write(sql: str, params: dict[str, Any], timeout_seconds: int = 30) -> dict[str, Any]:
    """
    Execute a parameterized INSERT/UPDATE statement built by
    sql/write_sql_builder.py.

    Deliberately separate from run_query():
    * run_query()  → read-only, executes raw validated SELECT text.
    * run_write()  → write-only, ALWAYS takes a separate `params` dict for
                     bound parameters (never string-concatenated values),
                     and runs inside an explicit transaction so a failed
                     write never partially commits.

    `sql` must already be a parameterized statement (e.g. built with
    SQLAlchemy `text()` and named bind parameters like :p_0, :p_1, ...).
    `params` must contain exactly the bind values referenced by `sql`.
    """
    engine = get_engine()
    t0 = time.perf_counter()

    try:
        with engine.begin() as conn:  # engine.begin() = transaction, auto-commit/rollback
            result = conn.execute(
                text(sql).execution_options(timeout=timeout_seconds),
                params,
            )
            row_count = result.rowcount

        ms = int((time.perf_counter() - t0) * 1000)
        logger.info("Write OK — %d row(s) affected in %dms", row_count, ms)
        return {"rows_affected": row_count, "duration_ms": ms}

    except SQLAlchemyError as exc:
        ms = int((time.perf_counter() - t0) * 1000)
        logger.error("Write failed (%dms): %s", ms, exc)
        raise RuntimeError(str(exc)) from exc


def run_query(sql: str, timeout_seconds: int = 30) -> dict[str, Any]:

    engine = get_engine()
    t0 = time.perf_counter()

    try:
        with engine.connect() as conn:
            result  = conn.execute(
                text(sql).execution_options(timeout=timeout_seconds)
            )
            columns = list(result.keys())
            rows    = [list(row) for row in result.fetchall()]

        ms = int((time.perf_counter() - t0) * 1000)
        logger.info("Query OK — %d rows in %dms", len(rows), ms)
        return {"columns": columns, "rows": rows, "duration_ms": ms}

    except SQLAlchemyError as exc:
        ms = int((time.perf_counter() - t0) * 1000)
        logger.error("Query failed (%dms): %s", ms, exc)
        raise RuntimeError(str(exc)) from exc