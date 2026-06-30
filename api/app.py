"""
api/app.py — ERP AI SQL Assistant API with JWT role-based authorization.

Roles:
  admin → /health, /tables, /rebuild, /ask  (full access)
  user  → /ask only
"""
from __future__ import annotations

from typing import Any

try:
    from fastapi import Depends, FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
except ImportError:
    raise ImportError("Run: pip install fastapi uvicorn")

from auth.auth import TokenData, require_admin, require_any
from auth.models import create_tables
from auth.router import router as auth_router
from core.agent import ERPAgent
from utils.logger import get_logger

logger = get_logger(__name__)

# ── create auth DB tables on startup ─────────────────────────────────────────
create_tables()

app = FastAPI(
    title="ERP AI SQL Assistant",
    description="Natural-language SQL queries over Sage 100 / SQL Server",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# mount auth routes (/auth/register, /auth/login, /auth/me)
app.include_router(auth_router)


# ── agent singleton ───────────────────────────────────────────────────────────
_agent: ERPAgent | None = None


def get_agent() -> ERPAgent:
    global _agent
    if _agent is None:
        _agent = ERPAgent()
    return _agent


# ── request / response models ─────────────────────────────────────────────────
class AskRequest(BaseModel):
    question: str
    top_k:    int = 6


class AskResponse(BaseModel):
    question:         str
    sql:              str | None
    columns:          list[str]
    rows:             list[list[Any]]
    error:            str | None
    retrieved_tables: list[str]
    attempts:         int
    warnings:         list[str]
    duration_ms:      int


# ── routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health(_: TokenData = Depends(require_admin)):
    """Admin only — liveness probe."""
    return {"status": "ok"}


@app.get("/tables")
def list_tables(_: TokenData = Depends(require_admin)):
    """Admin only — list indexed tables."""
    tables = get_agent().list_indexed_tables()
    return {"count": len(tables), "tables": tables}


@app.post("/rebuild")
def rebuild(_: TokenData = Depends(require_admin)):
    """Admin only — rebuild FAISS schema index."""
    get_agent().rebuild_schema_index()
    return {"status": "index rebuilt"}


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest, _: TokenData = Depends(require_any)):
    """Admin + user — natural language query."""
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="question cannot be empty")

    agent  = get_agent()
    result = agent.ask(req.question)

    data = result.get("data") or {}
    return AskResponse(
        question         = result["question"],
        sql              = result["sql"],
        columns          = data.get("columns", []),
        rows             = data.get("rows", []),
        error            = result["error"],
        retrieved_tables = result["retrieved_tables"],
        attempts         = result["attempts"],
        warnings         = result["warnings"],
        duration_ms      = data.get("duration_ms", 0),
    )