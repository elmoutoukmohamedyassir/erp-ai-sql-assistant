"""
api/crm/clients.py — Clients CRUD for non-technical CRM users.

Every request/response is a plain business object:
  { "id": "CL000012", "name": "...", "phone": "...", ... }
No table names, SQL, or column names ever leave this layer.
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

router = APIRouter(prefix="/crm/clients", tags=["crm-clients"])


# ── schemas ──────────────────────────────────────────────────────────────────

class ClientIn(BaseModel):
    name: str = Field(..., min_length=1, description="Client name")
    contact: str | None = None
    phone: str | None = None
    mobile: str | None = None
    email: str | None = None
    address: str | None = None
    address2: str | None = None
    postal_code: str | None = None
    city: str | None = None
    country: str | None = None
    tax_number: str | None = None
    notes: str | None = None


class ClientOut(BaseModel):
    id: str
    name: str | None = None
    contact: str | None = None
    phone: str | None = None
    mobile: str | None = None
    email: str | None = None
    address: str | None = None
    address2: str | None = None
    postal_code: str | None = None
    city: str | None = None
    country: str | None = None
    tax_number: str | None = None
    notes: str | None = None


class ClientListResponse(BaseModel):
    items: list[ClientOut]
    total: int
    page: int
    page_size: int


# ── helpers ──────────────────────────────────────────────────────────────────

def _field_map() -> dict[str, str]:
    ensure_table_exists(mapping.CLIENT_TABLE)
    return resolve_field_map(mapping.CLIENT_TABLE, mapping.CLIENT_FIELDS)


def _code_column() -> str:
    real = resolve_column(mapping.CLIENT_TABLE, mapping.CLIENT_CODE_COLUMN)
    if not real:
        raise HTTPException(status_code=500, detail="This feature isn't configured correctly yet.")
    return real


def _type_column() -> str | None:
    return resolve_column(mapping.CLIENT_TABLE, mapping.CLIENT_TYPE_COLUMN)


def _row_to_out(field_map: dict[str, str], code_business_value: str, row: dict[str, Any]) -> ClientOut:
    data = {biz: row.get(biz) for biz in field_map}
    data["id"] = code_business_value
    return ClientOut(**data)


# ── routes ───────────────────────────────────────────────────────────────────

@router.get("", response_model=ClientListResponse)
def list_clients(
    search: str | None = None,
    page: int = 1,
    page_size: int = 25,
    _: TokenData = Depends(require_any),
):
    field_map = _field_map()
    code_col = _code_column()
    type_col = _type_column()

    extra_where = "1=1"
    extra_params: dict[str, Any] = {}
    if type_col:
        extra_where = f"[{type_col}] = :ctype"
        extra_params["ctype"] = mapping.CLIENT_TYPE_VALUE

    full_map = {**field_map, "__code__": code_col}
    try:
        rows, total = list_rows(
            mapping.CLIENT_TABLE,
            full_map,
            search=search,
            search_business_fields=["name", "email", "phone", "city"],
            extra_where=extra_where,
            extra_params=extra_params,
            order_by=f"[{code_col}]",
            page=page,
            page_size=page_size,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=friendly_db_error(exc))

    items = [_row_to_out(field_map, r["__code__"], r) for r in rows]
    return ClientListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{client_id}", response_model=ClientOut)
def get_client(client_id: str, _: TokenData = Depends(require_any)):
    field_map = _field_map()
    code_col = _code_column()
    full_map = {**field_map, "__code__": code_col}
    row = get_one_row(mapping.CLIENT_TABLE, full_map, code_col, client_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return _row_to_out(field_map, row["__code__"], row)


@router.post("", response_model=ClientOut, status_code=201)
def create_client(payload: ClientIn, _: TokenData = Depends(require_any)):
    field_map = _field_map()
    code_col = _code_column()
    type_col = _type_column()

    missing = mapping.CLIENT_REQUIRED_BUSINESS_FIELDS - field_map.keys()
    if missing:
        raise HTTPException(status_code=500, detail="This feature isn't configured correctly yet.")

    values = to_column_values(field_map, payload.model_dump())
    new_code = generate_code(mapping.CLIENT_TABLE, code_col, mapping.CLIENT_CODE_PREFIX)
    values[code_col] = new_code
    if type_col:
        values[type_col] = mapping.CLIENT_TYPE_VALUE

    sql, params = build_insert(mapping.CLIENT_TABLE, values)
    try:
        run_write_many([(sql, params)])
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=friendly_db_error(exc))

    row = get_one_row(mapping.CLIENT_TABLE, {**field_map, "__code__": code_col}, code_col, new_code)
    return _row_to_out(field_map, new_code, row or {})


@router.put("/{client_id}", response_model=ClientOut)
def update_client(client_id: str, payload: ClientIn, _: TokenData = Depends(require_any)):
    field_map = _field_map()
    code_col = _code_column()

    existing = get_one_row(mapping.CLIENT_TABLE, {**field_map, "__code__": code_col}, code_col, client_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Client not found")

    values = to_column_values(field_map, payload.model_dump())
    if not values:
        return _row_to_out(field_map, client_id, existing)

    sql, params = build_update(mapping.CLIENT_TABLE, values, {code_col: client_id})
    try:
        run_write_many([(sql, params)])
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=friendly_db_error(exc))

    row = get_one_row(mapping.CLIENT_TABLE, {**field_map, "__code__": code_col}, code_col, client_id)
    return _row_to_out(field_map, client_id, row or {})


@router.delete("/{client_id}", status_code=204)
def delete_client(client_id: str, _: TokenData = Depends(require_any)):
    code_col = _code_column()
    existing = get_one_row(mapping.CLIENT_TABLE, {"__code__": code_col}, code_col, client_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Client not found")

    sql, params = build_delete(mapping.CLIENT_TABLE, {code_col: client_id})
    try:
        run_write_many([(sql, params)])
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=friendly_db_error(exc))
    return None
