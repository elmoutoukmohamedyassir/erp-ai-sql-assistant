"""
api/crm/stock.py — Stock view + business operations (Receive / Adjust)
for non-technical CRM users.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth.auth import TokenData, require_any
from api.crm import mapping
from api.crm.common import (
    build_insert,
    build_update,
    ensure_table_exists,
    friendly_db_error,
    get_one_row,
    resolve_column,
    run_query_params_safe,
    run_write_many,
)
from utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/crm/stock", tags=["crm-stock"])


# ── schemas ──────────────────────────────────────────────────────────────────

class StockItemOut(BaseModel):
    product_id: str
    product_name: str | None = None
    quantity: float = 0


class StockListResponse(BaseModel):
    items: list[StockItemOut]
    total: int
    page: int
    page_size: int


class ReceiveStockIn(BaseModel):
    product_id: str = Field(..., description="Product reference")
    quantity: float = Field(..., gt=0, description="Quantity being received (added to current stock)")
    note: str | None = None


class AdjustStockIn(BaseModel):
    product_id: str = Field(..., description="Product reference")
    new_quantity: float = Field(..., ge=0, description="Corrected stock quantity")
    reason: str | None = None


# ── helpers ──────────────────────────────────────────────────────────────────

def _stock_columns() -> tuple[str, str, str | None]:
    ensure_table_exists(mapping.STOCK_TABLE)
    ref_col = resolve_column(mapping.STOCK_TABLE, mapping.STOCK_PRODUCT_REF_COLUMN)
    qty_col = resolve_column(mapping.STOCK_TABLE, mapping.STOCK_QUANTITY_COLUMN)
    depot_col = resolve_column(mapping.STOCK_TABLE, mapping.STOCK_DEPOT_COLUMN)
    if not ref_col or not qty_col:
        raise HTTPException(status_code=500, detail="This feature isn't configured correctly yet.")
    return ref_col, qty_col, depot_col


def _product_name_column() -> str | None:
    return resolve_column(mapping.PRODUCT_TABLE, mapping.PRODUCT_FIELDS["name"])


def _product_exists(product_id: str) -> bool:
    ensure_table_exists(mapping.PRODUCT_TABLE)
    code_col = resolve_column(mapping.PRODUCT_TABLE, mapping.PRODUCT_CODE_COLUMN)
    if not code_col:
        return False
    sql = f"SELECT 1 FROM [{mapping.PRODUCT_TABLE}] WHERE [{code_col}] = :id"
    result = run_query_params_safe(sql, {"id": product_id})
    return bool(result["rows"])


def _get_stock_row(ref_col: str, qty_col: str, depot_col: str | None, product_id: str) -> dict[str, Any] | None:
    where = f"[{ref_col}] = :ref"
    params: dict[str, Any] = {"ref": product_id}
    if depot_col:
        where += f" AND [{depot_col}] = :depot"
        params["depot"] = mapping.DEFAULT_DEPOT
    sql = f"SELECT [{qty_col}] AS qty FROM [{mapping.STOCK_TABLE}] WHERE {where}"
    result = run_query_params_safe(sql, params)
    if not result["rows"]:
        return None
    return {"qty": result["rows"][0][0]}


# ── routes ───────────────────────────────────────────────────────────────────

@router.get("", response_model=StockListResponse)
def list_stock(
    search: str | None = None,
    page: int = 1,
    page_size: int = 25,
    _: TokenData = Depends(require_any),
):
    ensure_table_exists(mapping.PRODUCT_TABLE)
    ref_col, qty_col, depot_col = _stock_columns()
    product_code_col = resolve_column(mapping.PRODUCT_TABLE, mapping.PRODUCT_CODE_COLUMN)
    name_col = _product_name_column()

    if not product_code_col:
        raise HTTPException(status_code=500, detail="This feature isn't configured correctly yet.")

    page = max(1, page)
    page_size = min(max(1, page_size), 200)

    where = "1=1"
    params: dict[str, Any] = {}
    if search and search.strip() and name_col:
        where = f"p.[{name_col}] LIKE :q OR s.[{ref_col}] LIKE :q"
        params["q"] = f"%{search.strip()}%"

    name_select = f"p.[{name_col}]" if name_col else "NULL"
    base = (
        f"FROM [{mapping.STOCK_TABLE}] s "
        f"LEFT JOIN [{mapping.PRODUCT_TABLE}] p ON p.[{product_code_col}] = s.[{ref_col}] "
        f"WHERE {where}"
    )

    count_sql = f"SELECT COUNT(*) {base}"
    count_result = run_query_params_safe(count_sql, params)
    total = int(count_result["rows"][0][0]) if count_result["rows"] else 0

    offset = (page - 1) * page_size
    data_params = dict(params)
    data_params["offset"] = offset
    data_params["limit"] = page_size
    data_sql = (
        f"SELECT s.[{ref_col}] AS product_id, {name_select} AS product_name, s.[{qty_col}] AS quantity "
        f"{base} ORDER BY s.[{ref_col}] OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY"
    )
    data_result = run_query_params_safe(data_sql, data_params)
    items = [
        StockItemOut(product_id=row[0], product_name=row[1], quantity=row[2] or 0)
        for row in data_result["rows"]
    ]
    return StockListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/receive", response_model=StockItemOut)
def receive_stock(payload: ReceiveStockIn, _: TokenData = Depends(require_any)):
    if not _product_exists(payload.product_id):
        raise HTTPException(
            status_code=400,
            detail=f"Product '{payload.product_id}' doesn't exist. Please check the reference and try again.",
        )

    ref_col, qty_col, depot_col = _stock_columns()
    existing = _get_stock_row(ref_col, qty_col, depot_col, payload.product_id)

    if existing is None:
        values: dict[str, Any] = {ref_col: payload.product_id, qty_col: payload.quantity}
        if depot_col:
            values[depot_col] = mapping.DEFAULT_DEPOT
        sql, params = build_insert(mapping.STOCK_TABLE, values)
    else:
        new_qty = (existing["qty"] or 0) + payload.quantity
        where: dict[str, Any] = {ref_col: payload.product_id}
        if depot_col:
            where[depot_col] = mapping.DEFAULT_DEPOT
        sql, params = build_update(mapping.STOCK_TABLE, {qty_col: new_qty}, where)

    try:
        run_write_many([(sql, params)])
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=friendly_db_error(exc))

    row = _get_stock_row(ref_col, qty_col, depot_col, payload.product_id)
    return StockItemOut(product_id=payload.product_id, quantity=(row or {}).get("qty") or 0)


@router.post("/adjust", response_model=StockItemOut)
def adjust_stock(payload: AdjustStockIn, _: TokenData = Depends(require_any)):
    if not _product_exists(payload.product_id):
        raise HTTPException(
            status_code=400,
            detail=f"Product '{payload.product_id}' doesn't exist. Please check the reference and try again.",
        )

    ref_col, qty_col, depot_col = _stock_columns()
    existing = _get_stock_row(ref_col, qty_col, depot_col, payload.product_id)

    if existing is None:
        values: dict[str, Any] = {ref_col: payload.product_id, qty_col: payload.new_quantity}
        if depot_col:
            values[depot_col] = mapping.DEFAULT_DEPOT
        sql, params = build_insert(mapping.STOCK_TABLE, values)
    else:
        where: dict[str, Any] = {ref_col: payload.product_id}
        if depot_col:
            where[depot_col] = mapping.DEFAULT_DEPOT
        sql, params = build_update(mapping.STOCK_TABLE, {qty_col: payload.new_quantity}, where)

    try:
        run_write_many([(sql, params)])
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=friendly_db_error(exc))

    return StockItemOut(product_id=payload.product_id, quantity=payload.new_quantity)