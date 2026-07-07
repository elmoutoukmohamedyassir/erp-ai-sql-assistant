"""
api/crm/orders.py — Orders for non-technical CRM users.

An order is a business object:
  {
    "order_number": "CMD000045",
    "customer_id": "CL000012",
    "customer_name": "Acme Corp",
    "reference": "...",
    "status": "...",
    "lines": [ { "product_id": "ART000003", "product_name": "Widget",
                 "quantity": 4, "unit_price": 12.5, "line_total": 50.0 } ],
    "total": 50.0
  }

Internally this writes to the Sage document header + line tables
(F_DOCENTETE / F_DOCLIGNE by default — see api/crm/mapping.py), reusing
the same parameterized-write approach as the rest of the CRM module.
Never exposes SQL, table names, or column names to the client.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth.auth import TokenData, require_any
from api.crm import mapping
from api.crm.common import (
    build_delete,
    ensure_table_exists,
    friendly_db_error,
    generate_code,
    resolve_column,
    resolve_field_map,
    run_query_params_safe,
    run_write_many,
)
from utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/crm/orders", tags=["crm-orders"])


# ── schemas ──────────────────────────────────────────────────────────────────

class OrderLineIn(BaseModel):
    product_id: str
    quantity: float = Field(..., gt=0)
    unit_price: float | None = Field(None, description="Defaults to the product's sale price if omitted")


class OrderIn(BaseModel):
    customer_id: str
    reference: str | None = None
    notes: str | None = None
    lines: list[OrderLineIn] = Field(..., min_length=1)


class OrderLineOut(BaseModel):
    product_id: str
    product_name: str | None = None
    quantity: float
    unit_price: float
    line_total: float


class OrderOut(BaseModel):
    order_number: str
    customer_id: str | None = None
    customer_name: str | None = None
    date: str | None = None
    reference: str | None = None
    status: str | None = None
    notes: str | None = None
    lines: list[OrderLineOut] = []
    total: float = 0


class OrderListItem(BaseModel):
    order_number: str
    customer_id: str | None = None
    customer_name: str | None = None
    date: str | None = None
    status: str | None = None
    total: float = 0


class OrderListResponse(BaseModel):
    items: list[OrderListItem]
    total: int
    page: int
    page_size: int


# ── helpers ──────────────────────────────────────────────────────────────────

def _header_setup():
    ensure_table_exists(mapping.ORDER_HEADER_TABLE)
    ensure_table_exists(mapping.ORDER_LINE_TABLE)
    header_map = resolve_field_map(mapping.ORDER_HEADER_TABLE, mapping.ORDER_HEADER_FIELDS)
    line_map = resolve_field_map(mapping.ORDER_LINE_TABLE, mapping.ORDER_LINE_FIELDS)
    order_code_col = resolve_column(mapping.ORDER_HEADER_TABLE, mapping.ORDER_CODE_COLUMN)
    doc_type_col = resolve_column(mapping.ORDER_HEADER_TABLE, mapping.ORDER_DOC_TYPE_COLUMN)
    line_doc_code_col = resolve_column(mapping.ORDER_LINE_TABLE, mapping.ORDER_CODE_COLUMN)
    line_doc_type_col = resolve_column(mapping.ORDER_LINE_TABLE, mapping.ORDER_DOC_TYPE_COLUMN)

    if not order_code_col or "customer_code" not in header_map:
        logger.error(
            "Orders misconfigured — header_table=%s order_code_col=%s "
            "resolved_header_fields=%s (need 'customer_code')",
            mapping.ORDER_HEADER_TABLE, order_code_col, sorted(header_map.keys()),
        )
        raise HTTPException(status_code=500, detail="This feature isn't configured correctly yet.")
    if "product_ref" not in line_map or "quantity" not in line_map:
        logger.error(
            "Orders misconfigured — line_table=%s resolved_line_fields=%s "
            "(need 'product_ref' and 'quantity')",
            mapping.ORDER_LINE_TABLE, sorted(line_map.keys()),
        )
        raise HTTPException(status_code=500, detail="This feature isn't configured correctly yet.")

    return {
        "header_map": header_map,
        "line_map": line_map,
        "order_code_col": order_code_col,
        "doc_type_col": doc_type_col,
        "line_doc_code_col": line_doc_code_col,
        "line_doc_type_col": line_doc_type_col,
    }


def _customer_name_column() -> str | None:
    ensure_table_exists(mapping.CLIENT_TABLE)
    return resolve_column(mapping.CLIENT_TABLE, mapping.CLIENT_FIELDS["name"])


def _customer_code_column() -> str | None:
    return resolve_column(mapping.CLIENT_TABLE, mapping.CLIENT_CODE_COLUMN)


def _product_name_column() -> str | None:
    ensure_table_exists(mapping.PRODUCT_TABLE)
    return resolve_column(mapping.PRODUCT_TABLE, mapping.PRODUCT_FIELDS["name"])


def _product_sale_price(product_id: str) -> float:
    price_col = resolve_column(mapping.PRODUCT_TABLE, mapping.PRODUCT_FIELDS["sale_price"])
    code_col = resolve_column(mapping.PRODUCT_TABLE, mapping.PRODUCT_CODE_COLUMN)
    if not price_col or not code_col:
        return 0.0
    sql = f"SELECT [{price_col}] FROM [{mapping.PRODUCT_TABLE}] WHERE [{code_col}] = :ref"
    result = run_query_params_safe(sql, {"ref": product_id})
    if not result["rows"] or result["rows"][0][0] is None:
        return 0.0
    return float(result["rows"][0][0])


def _customer_exists(customer_id: str) -> bool:
    code_col = _customer_code_column()
    if not code_col:
        return False
    sql = f"SELECT 1 FROM [{mapping.CLIENT_TABLE}] WHERE [{code_col}] = :id"
    result = run_query_params_safe(sql, {"id": customer_id})
    return bool(result["rows"])


def _product_exists(product_id: str) -> bool:
    code_col = resolve_column(mapping.PRODUCT_TABLE, mapping.PRODUCT_CODE_COLUMN)
    if not code_col:
        return False
    sql = f"SELECT 1 FROM [{mapping.PRODUCT_TABLE}] WHERE [{code_col}] = :id"
    result = run_query_params_safe(sql, {"id": product_id})
    return bool(result["rows"])


def _build_order_statements(setup: dict, order_number: str, payload: OrderIn) -> tuple[list[tuple[str, dict]], float]:
    header_map = setup["header_map"]
    line_map = setup["line_map"]
    statements: list[tuple[str, dict[str, Any]]] = []

    header_values: dict[str, Any] = {setup["order_code_col"]: order_number}
    if setup["doc_type_col"]:
        header_values[setup["doc_type_col"]] = mapping.ORDER_DOC_TYPE_VALUE
    header_values[header_map["customer_code"]] = payload.customer_id
    if "date" in header_map:
        header_values[header_map["date"]] = date.today().isoformat()
    if payload.reference and "reference" in header_map:
        header_values[header_map["reference"]] = payload.reference
    if payload.notes and "notes" in header_map:
        header_values[header_map["notes"]] = payload.notes

    resolved_lines: list[tuple[str, float, float]] = []  # (product_id, qty, unit_price)
    grand_total = 0.0
    for idx, line in enumerate(payload.lines, start=1):
        unit_price = line.unit_price if line.unit_price is not None else _product_sale_price(line.product_id)
        line_total = round(unit_price * line.quantity, 2)
        grand_total += line_total
        resolved_lines.append((line.product_id, line.quantity, unit_price))

        line_values: dict[str, Any] = {}
        if setup["line_doc_code_col"]:
            line_values[setup["line_doc_code_col"]] = order_number
        if setup["line_doc_type_col"]:
            line_values[setup["line_doc_type_col"]] = mapping.ORDER_DOC_TYPE_VALUE
        line_values[line_map["product_ref"]] = line.product_id
        line_values[line_map["quantity"]] = line.quantity
        if "unit_price" in line_map:
            line_values[line_map["unit_price"]] = unit_price
        if "line_total" in line_map:
            line_values[line_map["line_total"]] = line_total
        if "line_no" in line_map:
            line_values[line_map["line_no"]] = idx

        cols = ", ".join(f"[{c}]" for c in line_values)
        param_names = [f"lp{idx}_{i}" for i in range(len(line_values))]
        vals_sql = ", ".join(f":{p}" for p in param_names)
        statements.append((
            f"INSERT INTO [{mapping.ORDER_LINE_TABLE}] ({cols}) VALUES ({vals_sql})",
            dict(zip(param_names, line_values.values())),
        ))

    if "total" in header_map:
        header_values[header_map["total"]] = grand_total

    header_cols = ", ".join(f"[{c}]" for c in header_values)
    header_param_names = [f"h{i}" for i in range(len(header_values))]
    header_vals_sql = ", ".join(f":{p}" for p in header_param_names)
    header_stmt = (
        f"INSERT INTO [{mapping.ORDER_HEADER_TABLE}] ({header_cols}) VALUES ({header_vals_sql})",
        dict(zip(header_param_names, header_values.values())),
    )

    return [header_stmt, *statements], grand_total


def _load_order(setup: dict, order_number: str) -> OrderOut | None:
    header_map = setup["header_map"]
    order_code_col = setup["order_code_col"]

    select_cols = ", ".join(f"h.[{real}] AS [{biz}]" for biz, real in header_map.items())
    sql = f"SELECT {select_cols} FROM [{mapping.ORDER_HEADER_TABLE}] h WHERE h.[{order_code_col}] = :code"
    result = run_query_params_safe(sql, {"code": order_number})
    if not result["rows"]:
        return None
    header_row = dict(zip(result["columns"], result["rows"][0]))

    customer_name = None
    name_col = _customer_name_column()
    customer_code_col = _customer_code_column()
    if name_col and customer_code_col and header_row.get("customer_code"):
        sql2 = f"SELECT [{name_col}] FROM [{mapping.CLIENT_TABLE}] WHERE [{customer_code_col}] = :id"
        r2 = run_query_params_safe(sql2, {"id": header_row["customer_code"]})
        if r2["rows"]:
            customer_name = r2["rows"][0][0]

    line_map = setup["line_map"]
    line_select = ", ".join(f"l.[{real}] AS [{biz}]" for biz, real in line_map.items())
    line_where = "1=1"
    line_params: dict[str, Any] = {}
    if setup["line_doc_code_col"]:
        line_where = f"l.[{setup['line_doc_code_col']}] = :code"
        line_params["code"] = order_number
    line_sql = f"SELECT {line_select} FROM [{mapping.ORDER_LINE_TABLE}] l WHERE {line_where}"
    line_result = run_query_params_safe(line_sql, line_params)

    name_col_product = _product_name_column()
    product_code_col = resolve_column(mapping.PRODUCT_TABLE, mapping.PRODUCT_CODE_COLUMN)
    lines: list[OrderLineOut] = []
    for row in line_result["rows"]:
        row_dict = dict(zip(line_result["columns"], row))
        product_id = row_dict.get("product_ref")
        product_name = None
        if name_col_product and product_code_col and product_id:
            r3 = run_query_params_safe(
                f"SELECT [{name_col_product}] FROM [{mapping.PRODUCT_TABLE}] WHERE [{product_code_col}] = :id",
                {"id": product_id},
            )
            if r3["rows"]:
                product_name = r3["rows"][0][0]
        lines.append(OrderLineOut(
            product_id=product_id,
            product_name=product_name,
            quantity=row_dict.get("quantity") or 0,
            unit_price=row_dict.get("unit_price") or 0,
            line_total=row_dict.get("line_total") or ((row_dict.get("quantity") or 0) * (row_dict.get("unit_price") or 0)),
        ))

    return OrderOut(
        order_number=order_number,
        customer_id=header_row.get("customer_code"),
        customer_name=customer_name,
        date=str(header_row.get("date")) if header_row.get("date") else None,
        reference=header_row.get("reference"),
        status=header_row.get("status"),
        notes=header_row.get("notes"),
        lines=lines,
        total=header_row.get("total") or sum(l.line_total for l in lines),
    )


# ── routes ───────────────────────────────────────────────────────────────────

@router.get("", response_model=OrderListResponse)
def list_orders(
    search: str | None = None,
    page: int = 1,
    page_size: int = 25,
    _: TokenData = Depends(require_any),
):
    setup = _header_setup()
    header_map = setup["header_map"]
    order_code_col = setup["order_code_col"]
    name_col = _customer_name_column()
    customer_code_col = _customer_code_column()

    page = max(1, page)
    page_size = min(max(1, page_size), 200)

    where = "1=1"
    params: dict[str, Any] = {}
    if setup["doc_type_col"]:
        where = f"h.[{setup['doc_type_col']}] = :dtype"
        params["dtype"] = mapping.ORDER_DOC_TYPE_VALUE

    join = ""
    if name_col and customer_code_col:
        join = f"LEFT JOIN [{mapping.CLIENT_TABLE}] c ON c.[{customer_code_col}] = h.[{header_map['customer_code']}]"
        if search and search.strip():
            where += f" AND (c.[{name_col}] LIKE :q OR h.[{order_code_col}] LIKE :q)"
            params["q"] = f"%{search.strip()}%"

    base = f"FROM [{mapping.ORDER_HEADER_TABLE}] h {join} WHERE {where}"
    count_result = run_query_params_safe(f"SELECT COUNT(*) {base}", params)
    total = int(count_result["rows"][0][0]) if count_result["rows"] else 0

    offset = (page - 1) * page_size
    data_params = dict(params)
    data_params["offset"] = offset
    data_params["limit"] = page_size

    name_select = f"c.[{name_col}]" if name_col and customer_code_col else "NULL"
    status_select = f"h.[{header_map['status']}]" if "status" in header_map else "NULL"
    total_select = f"h.[{header_map['total']}]" if "total" in header_map else "NULL"
    date_select = f"h.[{header_map['date']}]" if "date" in header_map else "NULL"

    data_sql = (
        f"SELECT h.[{order_code_col}] AS order_number, h.[{header_map['customer_code']}] AS customer_id, "
        f"{name_select} AS customer_name, {date_select} AS order_date, {status_select} AS status, {total_select} AS order_total "
        f"{base} ORDER BY h.[{order_code_col}] DESC OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY"
    )
    data_result = run_query_params_safe(data_sql, data_params)
    items = [
        OrderListItem(
            order_number=row[0], customer_id=row[1], customer_name=row[2],
            date=str(row[3]) if row[3] else None, status=row[4], total=row[5] or 0,
        )
        for row in data_result["rows"]
    ]
    return OrderListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{order_number}", response_model=OrderOut)
def get_order(order_number: str, _: TokenData = Depends(require_any)):
    setup = _header_setup()
    order = _load_order(setup, order_number)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.post("", response_model=OrderOut, status_code=201)
def create_order(payload: OrderIn, _: TokenData = Depends(require_any)):
    setup = _header_setup()

    if not _customer_exists(payload.customer_id):
        raise HTTPException(status_code=400, detail="That customer doesn't exist. Please pick a customer from the list.")
    for line in payload.lines:
        if not _product_exists(line.product_id):
            raise HTTPException(status_code=400, detail=f"Product '{line.product_id}' doesn't exist.")

    order_number = generate_code(mapping.ORDER_HEADER_TABLE, setup["order_code_col"], mapping.ORDER_CODE_PREFIX)
    statements, _total = _build_order_statements(setup, order_number, payload)

    try:
        run_write_many(statements)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=friendly_db_error(exc))

    order = _load_order(setup, order_number)
    if order is None:
        raise HTTPException(status_code=500, detail="Order was created but could not be reloaded.")
    return order


@router.put("/{order_number}", response_model=OrderOut)
def update_order(order_number: str, payload: OrderIn, _: TokenData = Depends(require_any)):
    setup = _header_setup()
    existing = _load_order(setup, order_number)
    if existing is None:
        raise HTTPException(status_code=404, detail="Order not found")

    if not _customer_exists(payload.customer_id):
        raise HTTPException(status_code=400, detail="That customer doesn't exist. Please pick a customer from the list.")
    for line in payload.lines:
        if not _product_exists(line.product_id):
            raise HTTPException(status_code=400, detail=f"Product '{line.product_id}' doesn't exist.")

    header_map = setup["header_map"]
    header_values: dict[str, Any] = {header_map["customer_code"]: payload.customer_id}
    if payload.reference is not None and "reference" in header_map:
        header_values[header_map["reference"]] = payload.reference
    if payload.notes is not None and "notes" in header_map:
        header_values[header_map["notes"]] = payload.notes

    header_where = {setup["order_code_col"]: order_number}
    set_names = [f"s{i}" for i in range(len(header_values))]
    where_names = [f"w{i}" for i in range(len(header_where))]
    set_sql = ", ".join(f"[{c}] = :{p}" for c, p in zip(header_values, set_names))
    where_sql = " AND ".join(f"[{c}] = :{p}" for c, p in zip(header_where, where_names))
    header_params = dict(zip(set_names, header_values.values()))
    header_params.update(dict(zip(where_names, header_where.values())))
    statements = [(f"UPDATE [{mapping.ORDER_HEADER_TABLE}] SET {set_sql} WHERE {where_sql}", header_params)]

    # replace all lines atomically (delete + reinsert) so quantities/products stay consistent
    line_delete_where: dict[str, Any] = {}
    if setup["line_doc_code_col"]:
        line_delete_where[setup["line_doc_code_col"]] = order_number
    if setup["line_doc_type_col"]:
        line_delete_where[setup["line_doc_type_col"]] = mapping.ORDER_DOC_TYPE_VALUE
    if line_delete_where:
        statements.append(build_delete(mapping.ORDER_LINE_TABLE, line_delete_where))

    line_map = setup["line_map"]
    grand_total = 0.0
    for idx, line in enumerate(payload.lines, start=1):
        unit_price = line.unit_price if line.unit_price is not None else _product_sale_price(line.product_id)
        line_total = round(unit_price * line.quantity, 2)
        grand_total += line_total

        line_values: dict[str, Any] = {}
        if setup["line_doc_code_col"]:
            line_values[setup["line_doc_code_col"]] = order_number
        if setup["line_doc_type_col"]:
            line_values[setup["line_doc_type_col"]] = mapping.ORDER_DOC_TYPE_VALUE
        line_values[line_map["product_ref"]] = line.product_id
        line_values[line_map["quantity"]] = line.quantity
        if "unit_price" in line_map:
            line_values[line_map["unit_price"]] = unit_price
        if "line_total" in line_map:
            line_values[line_map["line_total"]] = line_total
        if "line_no" in line_map:
            line_values[line_map["line_no"]] = idx

        cols = ", ".join(f"[{c}]" for c in line_values)
        param_names = [f"lp{idx}_{i}" for i in range(len(line_values))]
        vals_sql = ", ".join(f":{p}" for p in param_names)
        statements.append((
            f"INSERT INTO [{mapping.ORDER_LINE_TABLE}] ({cols}) VALUES ({vals_sql})",
            dict(zip(param_names, line_values.values())),
        ))

    if "total" in header_map:
        statements.append((
            f"UPDATE [{mapping.ORDER_HEADER_TABLE}] SET [{header_map['total']}] = :t WHERE [{setup['order_code_col']}] = :code",
            {"t": grand_total, "code": order_number},
        ))

    try:
        run_write_many(statements)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=friendly_db_error(exc))

    order = _load_order(setup, order_number)
    if order is None:
        raise HTTPException(status_code=500, detail="Order was updated but could not be reloaded.")
    return order