"""
erp/entities.py — ERP business-entity definitions.

Design decisions
-----------------
* An ERPEntity is a thin, declarative description of a business concept
  ("Customer") mapped onto a physical table ("F_COMPTET") that is ALREADY
  in sql/write_validator.WRITABLE_TABLES. This module never bypasses that
  whitelist — it's a friendlier layer ON TOP of it, not a replacement.
  Adding a new entity here does nothing unless its table is also
  deliberately whitelisted in sql/write_validator.py (see is_entity_writable).
* `field_aliases` maps friendly/LLM-facing field names -> real DB column
  names (uppercase), so prompts and API responses can use names a
  non-technical user (or an LLM) would naturally produce ("name" ->
  "CT_INTITULE") without hardcoding column casing everywhere.
* `additional_required_fields` covers BUSINESS rules the DB schema itself
  doesn't enforce (e.g. CT_Type may be nullable in SQL Server, but a
  customer record without a type is meaningless). These are merged with
  the DB-derived required columns from erp/schema_inspector.py.
* Entities for tables NOT YET in WRITABLE_TABLES (Invoice, Payment) are
  defined with enabled=False, so the system gives a clear "not enabled
  yet" message instead of silently failing — or worse, an LLM inventing a
  write path that routes around the whitelist.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sql.write_validator import WRITABLE_TABLES
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class ERPEntity:
    name: str                                       # "Customer" — used in API/LLM-facing responses
    table: str                                       # "F_COMPTET" — must be in WRITABLE_TABLES if enabled
    key_field: str                                    # column used as WHERE target for UPDATE, e.g. "CT_NUM"
    field_aliases: dict[str, str] = field(default_factory=dict)        # friendly name (lowercase) -> COLUMN
    additional_required_fields: frozenset[str] = frozenset()           # business-required, uppercase columns
    description: str = ""
    enabled: bool = True

    def resolve_column(self, field_name: str) -> str:
        """
        Map a friendly/LLM field name (or an already-real column name) to
        the real uppercase column name. Unknown names are simply
        uppercased and passed through — sql/write_validator.py will
        reject them if they don't actually exist on the table, so this
        is safe to be permissive about.
        """
        return self.field_aliases.get(field_name.strip().lower(), field_name.strip().upper())


# ---------------------------------------------------------------------------
# Entity registry
# ---------------------------------------------------------------------------
ENTITY_REGISTRY: dict[str, ERPEntity] = {
    "CUSTOMER": ERPEntity(
        name="Customer",
        table="F_COMPTET",
        key_field="CT_NUM",
        field_aliases={
            "code": "CT_NUM", "customer code": "CT_NUM", "ref": "CT_NUM",
            "name": "CT_INTITULE", "customer name": "CT_INTITULE", "intitule": "CT_INTITULE",
            "type": "CT_TYPE", "customer type": "CT_TYPE",
        },
        additional_required_fields=frozenset({"CT_NUM", "CT_TYPE"}),
        description="A customer / third-party account (F_COMPTET).",
    ),
    "SUPPLIER": ERPEntity(
        name="Supplier",
        table="F_COMPTET",
        key_field="CT_NUM",
        field_aliases={
            "code": "CT_NUM", "supplier code": "CT_NUM",
            "name": "CT_INTITULE", "supplier name": "CT_INTITULE",
            "type": "CT_TYPE", "supplier type": "CT_TYPE",
        },
        additional_required_fields=frozenset({"CT_NUM", "CT_TYPE"}),
        description="A supplier / third-party account (F_COMPTET).",
    ),
    "ARTICLE": ERPEntity(
        name="Article",
        table="F_ARTICLE",
        key_field="AR_REF",
        field_aliases={
            "ref": "AR_REF", "reference": "AR_REF", "code": "AR_REF",
            "name": "AR_DESIGN", "designation": "AR_DESIGN", "label": "AR_DESIGN",
            "price": "AR_PRIXVEN", "selling price": "AR_PRIXVEN",
        },
        additional_required_fields=frozenset({"AR_REF"}),
        description="A product / article in the catalog (F_ARTICLE).",
    ),
    "STOCKITEM": ERPEntity(
        name="StockItem",
        table="F_ARTSTOCK",
        key_field="AR_REF",
        field_aliases={
            "ref": "AR_REF", "article": "AR_REF", "article ref": "AR_REF",
            "quantity": "AS_QTESTO", "stock": "AS_QTESTO", "qty": "AS_QTESTO",
        },
        additional_required_fields=frozenset({"AR_REF"}),
        description="A stock quantity record per article/depot (F_ARTSTOCK).",
    ),
    # --- NOT YET ENABLED -----------------------------------------------------
    # Defined for forward-compatibility / discoverability only. Their tables
    # are NOT in WRITABLE_TABLES, so even if something upstream slipped past
    # entity resolution, sql/write_validator.py would still reject them.
    # Enabling one of these is a deliberate TWO-step action:
    #   1. add the table to sql/write_validator.WRITABLE_TABLES
    #   2. flip enabled=True here and fill in real field_aliases
    "INVOICE": ERPEntity(
        name="Invoice", table="F_DOCENTETE", key_field="DO_PIECE",
        description="Sales invoice header — NOT YET ENABLED for writes.",
        enabled=False,
    ),
    "PAYMENT": ERPEntity(
        name="Payment", table="F_ECHEANCE", key_field="DO_PIECE",
        description="Payment / settlement record — NOT YET ENABLED for writes.",
        enabled=False,
    ),
}


def get_entity(name: str) -> ERPEntity | None:
    """Look up an entity by name, case-insensitively. Returns None if unknown."""
    if not name:
        return None
    return ENTITY_REGISTRY.get(name.strip().upper())


def is_entity_writable(entity: ERPEntity) -> bool:
    """An entity is actually usable only if it's enabled AND its table is whitelisted."""
    return entity.enabled and entity.table in WRITABLE_TABLES


def list_writable_entities() -> list[ERPEntity]:
    return [e for e in ENTITY_REGISTRY.values() if is_entity_writable(e)]


def get_required_fields(entity: ERPEntity) -> frozenset[str]:
    """
    Merge DB-derived required columns (NOT NULL, no default, not
    identity/computed — from erp/schema_inspector.py) with this entity's
    business-required fields. DB introspection failures don't crash this;
    they just fall back to the business-declared set so the system stays
    usable even if metadata lookup has a transient issue.
    """
    from erp.schema_inspector import get_required_columns  # lazy import: avoids import cycle at module load

    try:
        db_required = get_required_columns(entity.table)
    except Exception as exc:
        logger.warning("Could not introspect required columns for %s: %s", entity.table, exc)
        db_required = frozenset()

    return frozenset(db_required | entity.additional_required_fields)