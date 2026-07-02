from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from sqlalchemy import inspect, text

from core.db import get_engine
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class ColumnMetadata:
    name: str
    data_type: str
    max_length: int | None
    nullable: bool
    default: str | None
    is_identity: bool
    is_computed: bool
    is_primary_key: bool

    @property
    def is_required_for_insert(self) -> bool:
        """
        True only if SQL Server will NOT auto-fill this column — i.e. the
        caller must supply a value for INSERT to succeed.
        """
        if self.is_identity or self.is_computed:
            return False
        if self.nullable:
            return False
        if self.default is not None:
            return False
        return True


@lru_cache(maxsize=256)
def get_primary_key_columns(table_name: str) -> frozenset[str]:
    """Return the UPPERCASE primary-key column names for `table_name`."""
    engine = get_engine()
    try:
        pk_info = inspect(engine).get_pk_constraint(table_name)
        return frozenset(c.upper() for c in (pk_info.get("constrained_columns") or []))
    except Exception as exc:
        logger.warning("Could not read primary key for '%s': %s", table_name, exc)
        return frozenset()


@lru_cache(maxsize=256)
def get_table_metadata(table_name: str) -> tuple[ColumnMetadata, ...]:
    """
    Fetch full column metadata for `table_name` from SQL Server metadata
    views. Returns an empty tuple (with a warning logged) if the table
    can't be introspected — callers should treat that as "unknown
    requirements" rather than crash.
    """
    engine = get_engine()

    query = text(
        """
        SELECT
            c.COLUMN_NAME                                                       AS column_name,
            c.DATA_TYPE                                                         AS data_type,
            c.CHARACTER_MAXIMUM_LENGTH                                          AS max_length,
            c.IS_NULLABLE                                                       AS is_nullable,
            c.COLUMN_DEFAULT                                                    AS column_default,
            COLUMNPROPERTY(OBJECT_ID(:table_name), c.COLUMN_NAME, 'IsIdentity') AS is_identity,
            COLUMNPROPERTY(OBJECT_ID(:table_name), c.COLUMN_NAME, 'IsComputed') AS is_computed
        FROM INFORMATION_SCHEMA.COLUMNS c
        WHERE c.TABLE_NAME = :table_name
        ORDER BY c.ORDINAL_POSITION
        """
    )

    try:
        with engine.connect() as conn:
            rows = conn.execute(query, {"table_name": table_name}).mappings().all()
    except Exception as exc:
        logger.error("Schema inspection failed for table '%s': %s", table_name, exc)
        return tuple()

    if not rows:
        logger.warning("No metadata found for table '%s' — does it exist?", table_name)
        return tuple()

    pk_columns = get_primary_key_columns(table_name)

    return tuple(
        ColumnMetadata(
            name=row["column_name"],
            data_type=row["data_type"],
            max_length=row["max_length"],
            nullable=(row["is_nullable"] == "YES"),
            default=row["column_default"],
            is_identity=bool(row["is_identity"]),
            is_computed=bool(row["is_computed"]),
            is_primary_key=row["column_name"].upper() in pk_columns,
        )
        for row in rows
    )


def get_required_columns(table_name: str) -> frozenset[str]:
    """
    Return the set of UPPERCASE column names that MUST be supplied to
    successfully INSERT a row into `table_name` (NOT NULL, no default,
    not identity/computed).
    """
    metadata = get_table_metadata(table_name)
    return frozenset(col.name.upper() for col in metadata if col.is_required_for_insert)


def clear_metadata_cache() -> None:
    """Call after a schema change (e.g. :rebuild) to drop cached metadata."""
    get_table_metadata.cache_clear()
    get_primary_key_columns.cache_clear()
    logger.info("ERP schema metadata cache cleared")