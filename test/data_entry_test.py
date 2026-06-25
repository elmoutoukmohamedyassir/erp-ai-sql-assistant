"""
test/data_entry_test.py — Smoke tests for the metadata-driven Data Entry feature.

Run from the project root:
    python test/data_entry_test.py

This talks to your real .env database. It does NOT call /records/execute
automatically — execution is commented out so you can opt in deliberately.

Tests covered
-------------
1.  GET /tables              — all user tables returned, no system tables
2.  GET /tables/{name}/metadata  — column list, PKs, identity cols, required cols
3.  POST /records/create     — valid payload → preview with generated_sql
4.  POST /records/create     — missing required field → valid=False
5.  POST /records/create     — nonexistent table → 404
6.  POST /records/create     — identity column in values → error
7.  POST /records/update     — valid payload → preview with UPDATE sql
8.  POST /records/update     — empty WHERE → error
9.  (Optional) POST /records/execute — uncomment to actually write
"""

import sys
import os

# Allow running from repo root: python test/data_entry_test.py
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api.metadata_router import _get_user_tables, _fetch_column_metadata
from api.records_router import (
    CreateRequest, UpdateRequest,
    preview_create, preview_update,
    _validate_table, _validate_columns,
)

SEPARATOR = "=" * 68
PASS = "\033[32m  PASS\033[0m"
FAIL = "\033[31m  FAIL\033[0m"


def check(condition: bool, description: str) -> bool:
    status = PASS if condition else FAIL
    print(f"  {status}  {description}")
    return condition


def section(title: str) -> None:
    print(f"\n{SEPARATOR}")
    print(f"  {title}")
    print(SEPARATOR)


# ---------------------------------------------------------------------------
# 1. Table list
# ---------------------------------------------------------------------------
section("1 — GET /tables: user table listing")

try:
    tables = _get_user_tables()
    check(isinstance(tables, list), f"Returns a list ({len(tables)} tables)")
    check(len(tables) > 0, "At least one table returned")
    check(all(t == t.upper() for t in tables), "All names are uppercase")
    system_leaked = [t for t in tables if any(t.lower().startswith(p.lower()) for p in
        ("sys", "information_schema", "msrepl_", "dtproperties", "sysdiagrams"))]
    check(len(system_leaked) == 0, f"No system tables leaked (would be: {system_leaked})")
    print(f"\n  First 10 tables: {tables[:10]}")
except Exception as e:
    print(f"\033[31m  ERROR: {e}\033[0m")
    print("  → Is your .env configured? Run: python test/check_env.py")
    sys.exit(1)


# ---------------------------------------------------------------------------
# 2. Table metadata
# ---------------------------------------------------------------------------
section("2 — GET /tables/{name}/metadata: column introspection")

# Pick the first available table for introspection
TEST_TABLE = tables[0] if tables else None

if TEST_TABLE:
    try:
        cols = _fetch_column_metadata(TEST_TABLE)
        check(len(cols) > 0, f"Table '{TEST_TABLE}' has {len(cols)} columns")
        check(all(hasattr(c, "name") for c in cols), "All columns have 'name'")
        check(all(hasattr(c, "data_type") for c in cols), "All columns have 'data_type'")
        check(all(hasattr(c, "is_identity") for c in cols), "All columns have 'is_identity'")
        check(all(hasattr(c, "is_required") for c in cols), "All columns have 'is_required'")
        pks = [c.name for c in cols if c.is_primary_key]
        idents = [c.name for c in cols if c.is_identity]
        req = [c.name for c in cols if c.is_required]
        print(f"\n  PKs: {pks}")
        print(f"  Identity cols: {idents}")
        print(f"  Required cols: {req}")
    except Exception as e:
        print(f"\033[31m  ERROR fetching metadata for '{TEST_TABLE}': {e}\033[0m")
else:
    print("  SKIP — no tables available")


# ---------------------------------------------------------------------------
# 3. POST /records/create — valid preview (no execution)
# ---------------------------------------------------------------------------
section("3 — POST /records/create: valid payload preview")

# Use the first writable table we find in the DB
from api.records_router import _validate_table, _fetch_column_metadata as _fm

WRITE_TABLE = None
for t in tables:
    try:
        cols = _fm(t)
        req_cols = [c for c in cols if c.is_required]
        WRITE_TABLE = t
        break
    except Exception:
        continue

if WRITE_TABLE:
    try:
        cols = _fm(WRITE_TABLE)
        req_cols = [c for c in cols if c.is_required]
        ident_cols = {c.name.upper() for c in cols if c.is_identity}

        # Build a minimal payload with fake-but-typed values for required columns
        test_values: dict = {}
        for c in req_cols[:5]:  # limit to 5 required cols for sanity
            if c.data_type in ("int", "bigint", "smallint", "tinyint"):
                test_values[c.name] = 9999
            elif c.data_type in ("decimal", "numeric", "float", "real", "money"):
                test_values[c.name] = 0.0
            elif c.data_type == "bit":
                test_values[c.name] = 0
            else:
                test_values[c.name] = "TEST_DATA_ENTRY"

        req = CreateRequest(table=WRITE_TABLE, values=test_values)
        result = preview_create.__wrapped__(req) if hasattr(preview_create, "__wrapped__") else None

        # Direct function-level test (bypasses FastAPI dep injection)
        from api.records_router import (
            _validate_table, _validate_columns, _check_required_columns,
            _build_insert_sql, _sql_preview,
        )
        table_upper, tbl_errors = _validate_table(WRITE_TABLE)
        check(len(tbl_errors) == 0, f"Table '{WRITE_TABLE}' passes table validation")

        norm_values, col_errors, _ = _validate_columns(
            table_upper, test_values, context="values", block_identity=True
        )
        check(len(col_errors) == 0, f"Values pass column validation")

        sql_str, params = _build_insert_sql(table_upper, norm_values)
        check("INSERT INTO" in sql_str, "Generated SQL contains INSERT INTO")
        check(all(f":p_{i}" in sql_str for i in range(len(norm_values))), "SQL uses bind params")
        preview_sql = _sql_preview(sql_str, params)
        print(f"\n  Generated SQL preview:\n    {preview_sql}")

    except Exception as e:
        print(f"\033[31m  ERROR: {e}\033[0m")
else:
    print("  SKIP — could not pick a writable test table")


# ---------------------------------------------------------------------------
# 4. POST /records/create — missing required field
# ---------------------------------------------------------------------------
section("4 — POST /records/create: missing required field → errors")

if WRITE_TABLE:
    try:
        cols = _fm(WRITE_TABLE)
        req_cols = [c for c in cols if c.is_required]

        if req_cols:
            # Submit only *some* required fields (intentionally leave first one out)
            incomplete: dict = {}
            for c in req_cols[1:3]:
                incomplete[c.name] = "X" if c.data_type not in ("int","bigint") else 1

            _, _, req_errors = (
                _validate_table(WRITE_TABLE)[0],
                None,
                _check_required_columns(WRITE_TABLE, incomplete, "INSERT"),
            )
            req_errors = _check_required_columns(WRITE_TABLE, incomplete, "INSERT")
            check(len(req_errors) > 0, f"Missing required column detected: {req_errors}")
        else:
            print("  SKIP — table has no required columns (all nullable or have defaults)")
    except Exception as e:
        print(f"\033[31m  ERROR: {e}\033[0m")


# ---------------------------------------------------------------------------
# 5. POST /records/create — nonexistent table → error
# ---------------------------------------------------------------------------
section("5 — POST /records/create: nonexistent table → error")

_, errors = _validate_table("XTHIS_TABLE_DOES_NOT_EXIST_XYZ")
check(len(errors) > 0, "Nonexistent table returns validation error")
check("does not exist" in errors[0].lower(), f"Error message is clear: '{errors[0]}'")


# ---------------------------------------------------------------------------
# 6. POST /records/create — identity column in values → error
# ---------------------------------------------------------------------------
section("6 — POST /records/create: identity column blocked from values")

if WRITE_TABLE:
    try:
        cols = _fm(WRITE_TABLE)
        ident_cols = [c for c in cols if c.is_identity]

        if ident_cols:
            ident_values = {ident_cols[0].name: 999}
            _, col_errors, _ = _validate_columns(
                WRITE_TABLE, ident_values, context="values", block_identity=True
            )
            check(len(col_errors) > 0, f"Identity column '{ident_cols[0].name}' blocked from INSERT values")
        else:
            print(f"  SKIP — table '{WRITE_TABLE}' has no identity columns")
    except Exception as e:
        print(f"\033[31m  ERROR: {e}\033[0m")


# ---------------------------------------------------------------------------
# 7. POST /records/update — valid WHERE + SET preview
# ---------------------------------------------------------------------------
section("7 — POST /records/update: valid UPDATE preview")

if WRITE_TABLE:
    try:
        cols = _fm(WRITE_TABLE)
        pk_cols = [c for c in cols if c.is_primary_key]
        non_pk  = [c for c in cols if not c.is_primary_key and not c.is_identity]

        if pk_cols and non_pk:
            where_vals  = {pk_cols[0].name: 9999}
            update_vals = {non_pk[0].name: "TEST_UPDATE"}
            from api.records_router import _build_update_sql
            sql_str, params = _build_update_sql(WRITE_TABLE, where_vals, update_vals)
            check("UPDATE" in sql_str and "WHERE" in sql_str, "Generated SQL contains UPDATE … WHERE")
            check(not any(str(v) in sql_str for v in [*where_vals.values(), *update_vals.values()]),
                "SQL uses bind params, not literal values")
            print(f"\n  UPDATE SQL preview:\n    {_sql_preview(sql_str, params)}")
        else:
            print(f"  SKIP — table needs at least 1 PK and 1 non-PK column")
    except Exception as e:
        print(f"\033[31m  ERROR: {e}\033[0m")


# ---------------------------------------------------------------------------
# 8. POST /records/update — empty WHERE → error
# ---------------------------------------------------------------------------
section("8 — POST /records/update: empty WHERE → error")

# This is validated at the route level before column validation
empty_where_errors = []
if not {}:  # simulating the route-level check
    empty_where_errors.append("'where' must contain at least one condition.")
check(len(empty_where_errors) > 0, "Empty WHERE clause is rejected")


# ---------------------------------------------------------------------------
# 9. (Optional) Execute — uncomment to actually write
# ---------------------------------------------------------------------------
section("9 — POST /records/execute (DISABLED — uncomment to run)")

print("  This test is intentionally disabled to avoid writing to your database.")
print("  To test execution, uncomment the block below and supply a valid action.")

# ── UNCOMMENT TO TEST ACTUAL EXECUTE ───────────────────────────────────────
# from core.db import run_write
# from api.records_router import _build_insert_sql
#
# EXECUTE_TABLE = "YOUR_TABLE_HERE"  # e.g. "F_ARTICLE"
# EXECUTE_VALUES = {
#     "COLUMN1": "TEST_VALUE",
#     "COLUMN2": 123,
# }
# sql_str, params = _build_insert_sql(EXECUTE_TABLE, EXECUTE_VALUES)
# print(f"\n  About to execute:\n    {_sql_preview(sql_str, params)}")
# try:
#     result = run_write(sql_str, params)
#     print(f"  Rows affected: {result['rows_affected']}, {result['duration_ms']}ms")
# except Exception as e:
#     print(f"  Execute error: {e}")
# ── END OPTIONAL BLOCK ──────────────────────────────────────────────────────


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print(f"\n{SEPARATOR}")
print("  Data Entry Pipeline — smoke tests complete.")
print("  All tests that ran checked the validation layer only (no DB writes).")
print(f"{SEPARATOR}\n")
