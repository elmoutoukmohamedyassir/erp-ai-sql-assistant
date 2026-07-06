"""
api/crm/mapping.py — the ONLY place that knows Sage table/column names for CRM.

Every other file in api/crm/ talks purely in business language ("name",
"phone", "quantity", ...). This module is the translation layer that maps
those business fields to real Sage 100 (SQL Server) columns.

WHY "candidate lists" instead of a single column name
-------------------------------------------------------
Sage 100 field names can vary slightly between versions / localizations.
Rather than guessing wrong and hard-failing, each business field maps to
an ordered list of *candidate* column names. At runtime, api/crm/common.py
resolves each candidate against the table's REAL columns (via
core.db.get_table_columns_real_case, the same schema-introspection helper
the Admin Data-Entry pipeline already uses) and keeps the first one that
actually exists. Fields that don't resolve to any real column are simply
dropped for optional business fields, or raise a clear error for fields
marked required.

IMPORTANT — please verify against your real database
-------------------------------------------------------
These candidate lists reflect the standard Sage 100 (Sage Gestion
Commerciale) schema. If your installation differs, use the existing
Admin -> Tables page (admin-only, already built) to inspect the real
column names for F_COMPTET / F_ARTICLE / F_ARTSTOCK / F_DOCENTETE /
F_DOCLIGNE and adjust the lists below — you do not need to touch any
other CRM file to do this.
"""
from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────
# Clients (and, internally, Suppliers share the same Sage table)
# ─────────────────────────────────────────────────────────────────────────
CLIENT_TABLE = "F_COMPTET"
CLIENT_CODE_COLUMN = ["CT_NUM"]          # business "id" / account number (PK)
CLIENT_TYPE_COLUMN = ["CT_TYPE"]         # 0 = client, 1 = supplier (Sage convention)
CLIENT_TYPE_VALUE = 0
CLIENT_CODE_PREFIX = "CL"

CLIENT_FIELDS: dict[str, list[str]] = {
    "name":        ["CT_INTITULE"],
    "contact":     ["CT_CONTACT"],
    "phone":       ["CT_TELEPHONE", "CT_TEL"],
    "mobile":      ["CT_TELECOPIE2", "CT_PORTABLE"],
    "email":       ["CT_EMAIL", "CT_EMAIL1"],
    "address":     ["CT_ADRESSE"],
    "address2":    ["CT_COMPLEMENT"],
    "postal_code": ["CT_CODEPOSTAL"],
    "city":        ["CT_VILLE"],
    "country":     ["CT_PAYS"],
    "tax_number":  ["CT_NUMTVA", "CT_SIRET", "CT_IDENTIFIANT"],
    "notes":       ["CT_OBSERVATIONS", "CT_COMMENTAIRE", "CT_NOTE"],
}
CLIENT_REQUIRED_BUSINESS_FIELDS = {"name"}

# ─────────────────────────────────────────────────────────────────────────
# Products
# ─────────────────────────────────────────────────────────────────────────
PRODUCT_TABLE = "F_ARTICLE"
PRODUCT_CODE_COLUMN = ["AR_REF"]         # business "sku" / reference (PK)
PRODUCT_CODE_PREFIX = "ART"

PRODUCT_FIELDS: dict[str, list[str]] = {
    "name":            ["AR_DESIGN"],
    "description":     ["AR_DESIGNSUPP", "AR_COMMENTAIRE"],
    "category":        ["AR_FAMILLE"],
    "unit":            ["AR_UNITEVEN", "AR_UNITE"],
    "sale_price":      ["AR_PRIXVEN"],
    "purchase_price":  ["AR_PRIXACH"],
    "barcode":         ["AR_CODEBARRE", "AR_CODEABARRES"],
}
PRODUCT_REQUIRED_BUSINESS_FIELDS = {"name"}

# ─────────────────────────────────────────────────────────────────────────
# Stock
# ─────────────────────────────────────────────────────────────────────────
STOCK_TABLE = "F_ARTSTOCK"
STOCK_PRODUCT_REF_COLUMN = ["AR_REF"]        # FK -> F_ARTICLE.AR_REF
STOCK_DEPOT_COLUMN = ["DE_NO", "CO_NO"]      # warehouse/depot number
STOCK_QUANTITY_COLUMN = ["AS_QTESTO"]
DEFAULT_DEPOT = 1                             # single-depot default; adjust if multi-depot

# ─────────────────────────────────────────────────────────────────────────
# Orders (sales orders — "commandes clients")
# ─────────────────────────────────────────────────────────────────────────
ORDER_HEADER_TABLE = "F_DOCENTETE"
ORDER_LINE_TABLE = "F_DOCLIGNE"

ORDER_DOC_TYPE_COLUMN = ["DO_TYPE"]
ORDER_DOC_TYPE_VALUE = 1                      # 1 = "Commande client" (Sales Order) — verify for your version
ORDER_CODE_COLUMN = ["DO_PIECE"]              # business "order number" (PK part)
ORDER_CODE_PREFIX = "CMD"

ORDER_HEADER_FIELDS: dict[str, list[str]] = {
    "customer_code": ["CT_NUM"],
    "date":          ["DO_DATE"],
    "reference":     ["DO_REF"],
    "status":        ["DO_STATUT", "DO_ETAT"],
    "notes":         ["DO_COMMENTAIRE", "DO_OBSERVATIONS"],
    "total":         ["DO_TOTALTTC"],
}

ORDER_LINE_FIELDS: dict[str, list[str]] = {
    "line_no":       ["DL_LIGNE", "DL_NO"],
    "product_ref":   ["AR_REF"],
    "description":   ["DL_DESIGN"],
    "quantity":      ["DL_QTE"],
    "unit_price":    ["DL_PRIXUNITAIRE", "DL_PRIXUTTC"],
    "line_total":    ["DL_MONTANTHT"],
}
