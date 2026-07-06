"""
api/crm/router.py — combines all CRM sub-routers.

Mounted once from api/app.py alongside (not instead of) the existing
auth_router and records_router. Every CRM route requires an authenticated
user with role "admin" OR "user" (auth.auth.require_any, unmodified) —
so normal, non-admin CRM staff can use it, while Admin-only routes
(/health, /tables, /rebuild, /records/*) remain admin-only exactly as
they already were.
"""
from __future__ import annotations

from fastapi import APIRouter

from api.crm.clients import router as clients_router
from api.crm.orders import router as orders_router
from api.crm.products import router as products_router
from api.crm.stock import router as stock_router

router = APIRouter()
router.include_router(clients_router)
router.include_router(orders_router)
router.include_router(products_router)
router.include_router(stock_router)
