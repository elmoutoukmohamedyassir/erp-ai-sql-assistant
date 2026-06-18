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
from core.write_agent import WriteAgent
from intent.classifier import Intent, detect_intent
from utils.logger import get_logger

logger = get_logger(__name__)

# create auth DB tables on startup
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

_agent: ERPAgent | None = None
_write_agent: WriteAgent | None = None


def get_agent() -> ERPAgent:
    global _agent
    if _agent is None:
        _agent = ERPAgent()
    return _agent


def get_write_agent() -> WriteAgent:
    global _write_agent
    if _write_agent is None:
        _write_agent = WriteAgent()
    return _write_agent


class AskRequest(BaseModel):
    question: str
    top_k:    int = 6


class AskResponse(BaseModel):
    question:          str
    sql:               str | None
    columns:           list[str]
    rows:              list[list[Any]]
    error:             str | None
    retrieved_tables:  list[str]
    attempts:          int
    warnings:          list[str]
    duration_ms:       int


class IntentResponse(BaseModel):
    question:        str
    intent:          str
    matched_keyword: str | None
    confidence:      float


class WritePreviewRequest(BaseModel):
    question: str


class WritePreviewResponse(BaseModel):
    question:              str
    requires_confirmation: bool
    action:                dict[str, Any] | None
    valid:                 bool
    errors:                list[str]
    warnings:              list[str]
    error:                 str | None
    attempts:              int


class WriteExecuteRequest(BaseModel):
    action: dict[str, Any]


class WriteExecuteResponse(BaseModel):
    action:         dict[str, Any]
    executed:       bool
    rows_affected:  int
    duration_ms:    int
    error:          str | None


# ── routes ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health(_: TokenData = Depends(require_admin)):
    return {"status": "ok"}


@app.get("/tables")
def list_tables(_: TokenData = Depends(require_admin)):
    tables = get_agent().list_indexed_tables()
    return {"count": len(tables), "tables": tables}


@app.post("/rebuild")
def rebuild(_: TokenData = Depends(require_admin)):
    get_agent().rebuild_schema_index()
    return {"status": "index rebuilt"}


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest, _: TokenData = Depends(require_any)):
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


@app.post("/intent", response_model=IntentResponse)
def classify_intent(req: AskRequest, _: TokenData = Depends(require_any)):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="question cannot be empty")

    result = detect_intent(req.question)
    return IntentResponse(
        question        = req.question,
        intent          = result.intent.value,
        matched_keyword = result.matched_keyword,
        confidence      = result.confidence,
    )


@app.post("/write/preview", response_model=WritePreviewResponse)
def write_preview(req: WritePreviewRequest, _: TokenData = Depends(require_any)):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="question cannot be empty")

    write_agent = get_write_agent()
    result = write_agent.preview(req.question)

    return WritePreviewResponse(
        question              = result.question,
        requires_confirmation = result.requires_confirmation,
        action                = result.action,
        valid                 = result.valid,
        errors                = result.errors,
        warnings              = result.warnings,
        error                 = result.error,
        attempts              = result.attempts,
    )


@app.post("/write/execute", response_model=WriteExecuteResponse)
def write_execute(req: WriteExecuteRequest, _: TokenData = Depends(require_admin)):
    if not req.action:
        raise HTTPException(status_code=400, detail="action cannot be empty")

    write_agent = get_write_agent()
    result = write_agent.execute(req.action)

    return WriteExecuteResponse(
        action        = result.action,
        executed      = result.executed,
        rows_affected = result.rows_affected,
        duration_ms   = result.duration_ms,
        error         = result.error,
    )