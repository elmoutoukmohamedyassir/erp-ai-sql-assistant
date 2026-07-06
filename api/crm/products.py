"""
api/crm/products.py — Products CRUD for non-technical CRM users.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth.auth import TokenData, require_any
from api.crm import mapping
from api.crm.common import (
    build_delete,
    build_insert,
    build_update,
    ensure_table_exists,
    friendly_db_error,
    generate_code,
    get_one_row,
    list_rows,
    resolve_column,
    resolve_field_map,
    run_write_many,
    to_column_values,
)
from utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/crm/products", tags=["crm-products"])


# ── schemas ──────────────────────────────────────────────────────────────────

class ProductIn(BaseModel):
    name: str = Field(..., min_length=1, description="Product name")
    sku: str | None = Field(None, description="Optional product reference; auto-generated if left blank")
    description: str | None = None
    category: str | None = None
    unit: str | None = None
    sale_price: float | None = None
    purchase_price: float | None = None
    barcode: str | None = None


class ProductOut(BaseModel):
    id: str
    sku: str
    name: str | None = None
    description: str | None = None
    category: str | None = None
    unit: str | None = None
    sale_price: float | None = None
    purchase_price: float | None = None
    barcode: str | None = None


class ProductListResponse(BaseModel):
    items: list[ProductOut]
    total: int
    page: int
    page_size: int


# ── helpers ──────────────────────────────────────────────────────────────────

def _field_map() -> dict[str, str]:
    ensure_table_exists(mapping.PRODUCT_TABLE)
    return resolve_field_map(mapping.PRODUCT_TABLE, mapping.PRODUCT_FIELDS)


def _code_column() -> str:
    real = resolve_column(mapping.PRODUCT_TABLE, mapping.PRODUCT_CODE_COLUMN)
    if not real:
        raise HTTPException(status_code=500, detail="This feature isn't configured correctly yet.")
    return real


def _row_to_out(field_map: dict[str, str], code_value: str, row: dict[str, Any]) -> ProductOut:
    data = {biz: row.get(biz) for biz in field_map}
    data["id"] = code_value
    data["sku"] = code_value
    return ProductOut(**data)


# ── routes ───────────────────────────────────────────────────────────────────

@router.get("", response_model=ProductListResponse)
def list_products(
    search: str | None = None,
    page: int = 1,
    page_size: int = 25,
    _: TokenData = Depends(require_any),
):
    field_map = _field_map()
    code_col = _code_column()
    full_map = {**field_map, "__code__": code_col}

    try:
        rows, total = list_rows(
            mapping.PRODUCT_TABLE,
            full_map,
            search=search,
            search_business_fields=["name", "description", "category"],
            order_by=f"[{code_col}]",
            page=page,
            page_size=page_size,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=friendly_db_error(exc))

    items = [_row_to_out(field_map, r["__code__"], r) for r in rows]
    return ProductListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: str, _: TokenData = Depends(require_any)):
    field_map = _field_map()
    code_col = _code_column()
    row = get_one_row(mapping.PRODUCT_TABLE, {**field_map, "__code__": code_col}, code_col, product_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return _row_to_out(field_map, row["__code__"], row)


@router.post("", response_model=ProductOut, status_code=201)
def create_product(payload: ProductIn, _: TokenData = Depends(require_any)):
    field_map = _field_map()
    code_col = _code_column()

    missing = mapping.PRODUCT_REQUIRED_BUSINESS_FIELDS - field_map.keys()
    if missing:
        raise HTTPException(status_code=500, detail="This feature isn't configured correctly yet.")

    values = to_column_values(field_map, payload.model_dump(exclude={"sku"}))
    code_value = (payload.sku or "").strip() or generate_code(
        mapping.PRODUCT_TABLE, code_col, mapping.PRODUCT_CODE_PREFIX
    )
    values[code_col] = code_value

    sql, params = build_insert(mapping.PRODUCT_TABLE, values)
    try:
        run_write_many([(sql, params)])
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=friendly_db_error(exc))

    row = get_one_row(mapping.PRODUCT_TABLE, {**field_map, "__code__": code_col}, code_col, code_value)
    return _row_to_out(field_map, code_value, row or {})


@router.put("/{product_id}", response_model=ProductOut)
def update_product(product_id: str, payload: ProductIn, _: TokenData = Depends(require_any)):
    field_map = _field_map()
    code_col = _code_column()

    existing = get_one_row(mapping.PRODUCT_TABLE, {**field_map, "__code__": code_col}, code_col, product_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Product not found")

    values = to_column_values(field_map, payload.model_dump(exclude={"sku"}))
    if not values:
        return _row_to_out(field_map, product_id, existing)

    sql, params = build_update(mapping.PRODUCT_TABLE, values, {code_col: product_id})
    try:
        run_write_many([(sql, params)])
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=friendly_db_error(exc))

    row = get_one_row(mapping.PRODUCT_TABLE, {**field_map, "__code__": code_col}, code_col, product_id)
    return _row_to_out(field_map, product_id, row or {})


@router.delete("/{product_id}", status_code=204)
def delete_product(product_id: str, _: TokenData = Depends(require_any)):
    code_col = _code_column()
    existing = get_one_row(mapping.PRODUCT_TABLE, {"__code__": code_col}, code_col, product_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Product not found")

    sql, params = build_delete(mapping.PRODUCT_TABLE, {code_col: product_id})
    try:
        run_write_many([(sql, params)])
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=friendly_db_error(exc))
    return None
