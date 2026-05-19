from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from utils.logger import get_logger

logger = get_logger(__name__)


_DANGEROUS = re.compile(
    r"\bDROP\b"
    r"|\bDELETE\b"
    r"|\bTRUNCATE\b"
    r"|\bINSERT\b"
    r"|\bUPDATE\b"
    r"|\bALTER\b"
    r"|\bCREATE\b"
    r"|\bEXEC\b(?!UTE)"   
    r"|\bEXECUTE\b"
    r"|\bXP_\w+"
    r"|\bSP_\w+"
    r"|\bOPENROWSET\b"
    r"|\bOPENQUERY\b"
    r"|\bBULK\s+INSERT\b"
    r"|--"                
    r"|/\*"               
    r"|;\s*\w",            
    re.IGNORECASE,
)

_SELECT_START = re.compile(
    r"^\s*(WITH\b.+?)\s*SELECT\b|^\s*SELECT\b",
    re.IGNORECASE | re.DOTALL,
)

@dataclass
class ValidationResult:
    valid:       bool       = True
    errors:      list[str]  = field(default_factory=list)
    warnings:    list[str]  = field(default_factory=list)
    cleaned_sql: str        = ""

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        self.valid = False

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)




def clean_sql(raw: str) -> str:
    """
    Remove markdown fences, keep only the SELECT statement,
    strip trailing semicolons.
    """
    if not raw:
        return ""
    
    sql = re.sub(r"```sql\s*|```", "", raw).strip()
    
    match = re.search(
        r"((?:WITH\b.+?AS\s*\(.+?\)\s*)?SELECT\b.*)",
        sql,
        re.IGNORECASE | re.DOTALL,
    )
    sql = match.group(1).strip() if match else sql
    
    return sql.rstrip(";").strip()




_FROM_JOIN = re.compile(
    r"(?:FROM|JOIN)\s+"           
    r"([A-Za-z_][A-Za-z0-9_]*)"  
    r"(?:\s+(?:AS\s+)?([A-Za-z_][A-Za-z0-9_]*))?",  
    re.IGNORECASE,
)

_SQL_KEYWORDS = frozenset({
    "SELECT", "WHERE", "ON", "AND", "OR", "NOT", "IN", "IS",
    "NULL", "AS", "BY", "GROUP", "ORDER", "HAVING", "LIMIT",
    "TOP", "INNER", "LEFT", "RIGHT", "OUTER", "CROSS", "FULL",
    "WITH", "UNION", "EXCEPT", "INTERSECT", "DISTINCT", "INTO",
})


def _extract_table_refs(sql: str) -> list[tuple[str, str | None]]:
    """
    Returns list of (table_name_upper, alias_upper_or_None).
    Skips matches where the 'table name' is actually a SQL keyword.
    """
    refs = []
    for m in _FROM_JOIN.finditer(sql):
        tbl   = m.group(1).upper()
        alias = m.group(2).upper() if m.group(2) else None
        if tbl in _SQL_KEYWORDS:
            continue
        refs.append((tbl, alias))
    return refs



_COL_REF = re.compile(
    r"(?:^|[\s,=(+\-*/])([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)",
    re.MULTILINE,
)


def _extract_col_refs(sql: str) -> list[tuple[str, str]]:
    """
    Returns list of (prefix_upper, column_upper) for qualified references
    like  c.CT_Num  or  F_COMPTET.CT_Num.
    prefix may be either a table name or an alias.
    """
    return [
        (m.group(1).upper(), m.group(2).upper())
        for m in _COL_REF.finditer(sql)
    ]



def _check_static(sql: str, result: ValidationResult) -> None:
    if not sql:
        result.add_error("Empty SQL string.")
        return

    if not _SELECT_START.match(sql):
        result.add_error(
            f"Query must start with SELECT (or WITH … SELECT). Got: {sql[:100]!r}"
        )

    danger = _DANGEROUS.search(sql)
    if danger:
        result.add_error(
            f"Dangerous keyword/pattern detected: {danger.group()!r}. "
            "Only SELECT queries are allowed."
        )

    if not re.search(r"\bWHERE\b|\bTOP\b|\bLIMIT\b", sql, re.IGNORECASE):
        result.add_warning(
            "No WHERE / TOP / LIMIT clause — may return a very large result set."
        )

    if re.search(r"SELECT\s+\*", sql, re.IGNORECASE):
        result.add_warning(
            "SELECT * detected — prefer explicit column names for performance."
        )



def _check_schema(sql: str, result: ValidationResult) -> None:
    """
    Validates table and column names against the LIVE database schema.
    Imports db helpers here (not at module top) to avoid circular imports
    and to keep the import lazy (no DB connection until needed).
    """
    from core.db import get_all_table_names, get_table_columns

    real_tables: frozenset[str] = get_all_table_names()  # uppercase frozenset
    table_refs  = _extract_table_refs(sql)

    if not table_refs:
        result.add_warning("No FROM/JOIN table references found in query.")
        return

    
    alias_map: dict[str, str] = {}   

    for tbl_upper, alias in table_refs:
        if tbl_upper not in real_tables:
            result.add_error(
                f"Table '{tbl_upper}' does not exist in the database. "
                "Use only tables that appear in the schema context provided."
            )
        else:
            if alias:
                alias_map[alias] = tbl_upper
            alias_map[tbl_upper] = tbl_upper  

    if not result.valid:
        return   
    
    col_refs = _extract_col_refs(sql)
    for prefix, col in col_refs:
        if prefix in _SQL_KEYWORDS:
            continue
        real_table = alias_map.get(prefix)
        if real_table is None:
            
            continue
        real_cols = get_table_columns(real_table)
        if real_cols and col not in real_cols:
            result.add_error(
                f"Column '{col}' does not exist in table '{real_table}'. "
                f"Available columns: {sorted(real_cols)[:15]} …"
            )



def validate_sql(
    raw_sql: str,
    retrieved_tables: list[dict[str, Any]] | None = None, 
) -> ValidationResult:
    
    result = ValidationResult()

    cleaned = clean_sql(raw_sql)
    result.cleaned_sql = cleaned

    _check_static(cleaned, result)
    if not result.valid:
        logger.warning("Static validation failed: %s", result.errors)
        return result

    _check_schema(cleaned, result)

    if result.errors:
        logger.warning("Schema validation errors: %s", result.errors)
    if result.warnings:
        logger.debug("Validation warnings: %s", result.warnings)

    return result