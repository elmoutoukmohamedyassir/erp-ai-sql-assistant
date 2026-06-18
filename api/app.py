from __future__ import annotations

from typing import Any

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
except ImportError:
    raise ImportError("Run: pip install fastapi uvicorn")

from core.agent import ERPAgent
from core.write_agent import WriteAgent
from intent.classifier import Intent, detect_intent
from utils.logger import get_logger

logger = get_logger(__name__)

app = FastAPI(
    title="ERP AI SQL Assistant",
    description="Natural-language SQL queries over Sage 100 / SQL Server",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   
    allow_methods=["*"],
    allow_headers=["*"],
)

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


# ---------------------------------------------------------------------------
# WRITE pipeline models — separate from the read AskRequest/AskResponse
# pair above so the read contract is never touched by this feature.
# ---------------------------------------------------------------------------

class IntentResponse(BaseModel):
    """Lets the frontend ask 'is this a READ or WRITE request?' before deciding which flow to call."""
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
    # The frontend sends back exactly the `action` object it received
    # from /write/preview — this is what gets re-validated and executed.
    action: dict[str, Any]


class WriteExecuteResponse(BaseModel):
    action:         dict[str, Any]
    executed:       bool
    rows_affected:  int
    duration_ms:    int
    error:          str | None




@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/tables")
def list_tables():
    tables = get_agent().list_indexed_tables()
    return {"count": len(tables), "tables": tables}


@app.post("/rebuild")
def rebuild():
    get_agent().rebuild_schema_index()
    return {"status": "index rebuilt"}


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
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


# ---------------------------------------------------------------------------
# WRITE pipeline endpoints
#
# /intent          — optional helper so the frontend can route a question
#                     to the read or write flow before calling either one.
# /write/preview   — generates + validates a write action. NEVER executes.
# /write/execute   — executes a previously-previewed, already-validated
#                     action. This is the ONLY endpoint that mutates data.
# ---------------------------------------------------------------------------

@app.post("/intent", response_model=IntentResponse)
def classify_intent(req: AskRequest):
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
def write_preview(req: WritePreviewRequest):
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
def write_execute(req: WriteExecuteRequest):
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