"""
api/metadata_router.py — Table metadata endpoints for the Data-Entry UI.

Endpoints
---------
GET  /tables                        — list all real, non-system tables (whitelisted)
GET  /tables/{table_name}/metadata  — column definitions, PK, identity flags

Security
--------
* Only tables that exist in the live DB schema are returned.
* System tables (sys*, information_schema, etc.) are blocked.
* Uses INFORMATION_SCHEMA + COLUMNPROPERTY — same source as erp/schema_inspector.py.
* Requires at minimum `require_any` (any authenticated user) to read metadata.
  Write endpoints in records_router.py require `require_admin`.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from auth.auth import TokenData, require_any
from core.db import get_engine, get_all_table_names
from utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/tables", tags=["metadata"])

# ---------------------------------------------------------------------------
# System-table prefix / name blocklist — we never expose these to the UI.
# ---------------------------------------------------------------------------
_SYSTEM_PREFIXES = (
    "sys",
    "information_schema",
    "msrepl_",
    "mspeer_",
    "MSmerge_",
    "MSsub_",
    "MSarticle",
    "MSdistrib",
    "MSlogreader",
    "MSreplication",
    "MSsnapshot",
    "dtproperties",
    "sysdiagrams",
)


def _is_system_table(name: str) -> bool:
    lower = name.lower()
    return any(lower.startswith(p.lower()) for p in _SYSTEM_PREFIXES)


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class ColumnInfo(BaseModel):
    name: str
    data_type: str
    max_length: int | None
    nullable: bool
    default: str | None
    is_identity: bool
    is_computed: bool
    is_primary_key: bool
    is_required: bool   # True → must be supplied on INSERT (not nullable, no default, not identity/computed)


class TableMetadataResponse(BaseModel):
    table: str
    columns: list[ColumnInfo]
    primary_keys: list[str]
    identity_columns: list[str]
    required_columns: list[str]   # subset of columns the form must mark as required


class TablesListResponse(BaseModel):
    count: int
    tables: list[str]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_user_tables() -> list[str]:
    """
    Return all real, non-system table names from the live DB, sorted.
    Uses the LRU-cached get_all_table_names() — same ground truth the
    write validator uses.
    """
    all_tables = get_all_table_names()   # frozenset[str], upper-cased
    return sorted(t for t in all_tables if not _is_system_table(t))


def _fetch_column_metadata(table_name: str) -> list[ColumnInfo]:
    """
    Query INFORMATION_SCHEMA + COLUMNPROPERTY for the given table.
    Raises HTTPException(404) if the table doesn't exist.
    """
    engine = get_engine()

    pk_query = text("""
        SELECT c.COLUMN_NAME
        FROM   INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
        JOIN   INFORMATION_SCHEMA.CONSTRAINT_COLUMN_USAGE c
               ON  c.TABLE_NAME       = tc.TABLE_NAME
               AND c.CONSTRAINT_NAME  = tc.CONSTRAINT_NAME
        WHERE  tc.TABLE_NAME         = :table_name
          AND  tc.CONSTRAINT_TYPE    = 'PRIMARY KEY'
    """)

    col_query = text("""
        SELECT
            c.COLUMN_NAME,
            c.DATA_TYPE,
            c.CHARACTER_MAXIMUM_LENGTH   AS max_length,
            c.IS_NULLABLE,
            c.COLUMN_DEFAULT,
            COLUMNPROPERTY(OBJECT_ID(:table_name), c.COLUMN_NAME, 'IsIdentity')  AS is_identity,
            COLUMNPROPERTY(OBJECT_ID(:table_name), c.COLUMN_NAME, 'IsComputed')  AS is_computed
        FROM INFORMATION_SCHEMA.COLUMNS c
        WHERE c.TABLE_NAME = :table_name
        ORDER BY c.ORDINAL_POSITION
    """)

    try:
        with engine.connect() as conn:
            pk_rows = conn.execute(pk_query, {"table_name": table_name}).fetchall()
            col_rows = conn.execute(col_query, {"table_name": table_name}).mappings().all()
    except Exception as exc:
        logger.error("Metadata fetch failed for '%s': %s", table_name, exc)
        raise HTTPException(status_code=500, detail=f"Could not fetch metadata: {exc}")

    if not col_rows:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found or has no columns.")

    pk_set = {r[0].upper() for r in pk_rows}

    columns: list[ColumnInfo] = []
    for row in col_rows:
        nullable    = (row["IS_NULLABLE"] == "YES")
        is_identity = bool(row["is_identity"])
        is_computed = bool(row["is_computed"])
        default_val = row["COLUMN_DEFAULT"]

        # A column is "required" if SQL Server won't auto-populate it
        is_required = (
            not nullable
            and not is_identity
            and not is_computed
            and default_val is None
        )

        columns.append(ColumnInfo(
            name          = row["COLUMN_NAME"],
            data_type     = row["DATA_TYPE"],
            max_length    = row["max_length"],
            nullable      = nullable,
            default       = default_val,
            is_identity   = is_identity,
            is_computed   = is_computed,
            is_primary_key= row["COLUMN_NAME"].upper() in pk_set,
            is_required   = is_required,
        ))

    return columns


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("", response_model=TablesListResponse)
def list_tables(_: TokenData = Depends(require_any)):
    """
    Return all user (non-system) tables in the database, sorted alphabetically.
    This is the source of truth for the table selector in the Data-Entry UI.
    """
    tables = _get_user_tables()
    return TablesListResponse(count=len(tables), tables=tables)


@router.get("/{table_name}/metadata", response_model=TableMetadataResponse)
def get_table_metadata(table_name: str, _: TokenData = Depends(require_any)):
    """
    Return full column metadata for a single table:
    column names, data types, nullable status, PK/identity flags,
    and which columns are required on INSERT.

    The frontend uses this to build the dynamic form.
    """
    # Normalize
    table_upper = table_name.strip().upper()

    # Block system tables explicitly (belt-and-suspenders on top of the
    # schema whitelist — a curious user could probe /tables/sysobjects)
    if _is_system_table(table_upper):
        raise HTTPException(status_code=403, detail="System tables are not accessible.")

    # Verify the table actually exists in the live DB
    all_tables = get_all_table_names()
    if table_upper not in all_tables:
        raise HTTPException(status_code=404, detail=f"Table '{table_upper}' does not exist.")

    columns = _fetch_column_metadata(table_upper)

    primary_keys     = [c.name for c in columns if c.is_primary_key]
    identity_columns = [c.name for c in columns if c.is_identity]
    required_columns = [c.name for c in columns if c.is_required]

    return TableMetadataResponse(
        table            = table_upper,
        columns          = columns,
        primary_keys     = primary_keys,
        identity_columns = identity_columns,
        required_columns = required_columns,
    )
