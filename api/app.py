from __future__ import annotations

from typing import Any

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
except ImportError:
    raise ImportError("Run: pip install fastapi uvicorn")

from core.agent import ERPAgent
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


def get_agent() -> ERPAgent:
    global _agent
    if _agent is None:
        _agent = ERPAgent()
    return _agent




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