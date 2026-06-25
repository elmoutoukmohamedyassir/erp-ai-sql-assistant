from __future__ import annotations
from erp.erp_write_agent import ERPWriteAgent
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

_erp_write_agent: ERPWriteAgent | None = None
def get_erp_write_agent() -> ERPWriteAgent:
    global _erp_write_agent
    if _erp_write_agent is None:
        _erp_write_agent = ERPWriteAgent()
    return _erp_write_agent

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

class ERPWritePreviewRequest(BaseModel):
    conversation_id: str   # client-generated id — keep sending the SAME id across follow-up turns
    question:        str


class ERPWritePreviewResponse(BaseModel):
    conversation_id:            str
    question:                   str
    requires_more_information:  bool
    requires_confirmation:      bool
    entity:                     str | None
    table:                      str | None
    operation:                  str | None
    collected_fields:           dict[str, Any]
    missing_fields:             list[str]
    action:                     dict[str, Any] | None
    valid:                      bool
    errors:                     list[str]
    warnings:                   list[str]
    business_explanation:       str | None
    error:                      str | None
    attempts:                   int


class ERPWriteExecuteRequest(BaseModel):
    conversation_id: str
    action:          dict[str, Any]
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


# ── ERP entity-aware write endpoints ─────────────────────────────────────────
# These sit ALONGSIDE /write/preview and /write/execute above (which keep
# working unchanged for direct table/column requests). Use these two instead
# when you want required-field detection + multi-turn slot-filling — e.g. the
# frontend's "missing information" forms talk to these.

@app.post("/erp/write/preview", response_model=ERPWritePreviewResponse)
def erp_write_preview(req: ERPWritePreviewRequest, _: TokenData = Depends(require_any)):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="question cannot be empty")
    if not req.conversation_id.strip():
        raise HTTPException(status_code=400, detail="conversation_id cannot be empty")

    agent = get_erp_write_agent()
    result = agent.preview(req.conversation_id, req.question)

    return ERPWritePreviewResponse(
        conversation_id            = result.conversation_id,
        question                   = result.question,
        requires_more_information  = result.requires_more_information,
        requires_confirmation      = result.requires_confirmation,
        entity                     = result.entity,
        table                      = result.table,
        operation                  = result.operation,
        collected_fields           = result.collected_fields,
        missing_fields             = result.missing_fields,
        action                     = result.action,
        valid                      = result.valid,
        errors                     = result.errors,
        warnings                   = result.warnings,
        business_explanation       = result.business_explanation,
        error                      = result.error,
        attempts                   = result.attempts,
    )


@app.post("/erp/write/execute", response_model=WriteExecuteResponse)
def erp_write_execute(req: ERPWriteExecuteRequest, _: TokenData = Depends(require_admin)):
    if not req.action:
        raise HTTPException(status_code=400, detail="action cannot be empty")
    if not req.conversation_id.strip():
        raise HTTPException(status_code=400, detail="conversation_id cannot be empty")

    agent = get_erp_write_agent()
    result = agent.execute(req.conversation_id, req.action)

    return WriteExecuteResponse(
        action        = result.action,
        executed      = result.executed,
        rows_affected = result.rows_affected,
        duration_ms   = result.duration_ms,
        error         = result.error,
    )