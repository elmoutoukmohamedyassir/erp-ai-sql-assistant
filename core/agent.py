from __future__ import annotations

from typing import Any

from core.db import run_query, clear_schema_cache
from core.llm import call_llm
from schema.indexer import SchemaRetriever, build_index
from sql.prompt_builder import SYSTEM_PROMPT, build_user_prompt
from sql.validator import validate_sql
from utils.logger import get_logger

logger = get_logger(__name__)

MAX_CORRECTION_LOOPS = 2   

class ERPAgent:
    

    def __init__(self, top_k: int = 8):
        self._retriever = SchemaRetriever(top_k=top_k)

    

    def ask(self, question: str) -> dict[str, Any]:
        
        logger.info("Question: %s", question)

        result: dict[str, Any] = {
            "question":         question,
            "sql":              None,
            "data":             None,
            "error":            None,
            "retrieved_tables": [],
            "attempts":         0,
            "warnings":         [],
        }

        
        try:
            retrieved = self._retriever.retrieve(question)
        except Exception as exc:
            result["error"] = f"Schema retrieval failed: {exc}"
            logger.error("Schema retrieval error: %s", exc, exc_info=True)
            return result

        result["retrieved_tables"] = [r["table"] for r in retrieved]
        schema_context = self._retriever.get_schema_context(question)

        logger.info("Retrieved tables for prompt: %s", result["retrieved_tables"])

         
        previous_sql:   str | None = None
        previous_error: str | None = None

        for attempt in range(1, MAX_CORRECTION_LOOPS + 2):
            result["attempts"] = attempt
            logger.info("Attempt %d / %d", attempt, MAX_CORRECTION_LOOPS + 1)

            
            user_prompt = build_user_prompt(
                question       = question,
                schema_context = schema_context,
                previous_sql   = previous_sql,
                error_message  = previous_error,
            )

            
            try:
                raw_sql = call_llm(SYSTEM_PROMPT, user_prompt)
            except Exception as exc:
                result["error"] = f"LLM call failed: {exc}"
                logger.error("LLM error: %s", exc, exc_info=True)
                return result

            logger.info("Raw LLM output: %s", raw_sql[:300])

            
            if "UNSUPPORTED_QUESTION" in raw_sql.upper():
                result["error"] = (
                    "No relevant table found for this question. "
                    "Try rephrasing, or check :schema to see what's indexed."
                )
                return result

            
            validation = validate_sql(raw_sql, retrieved_tables=retrieved)
            result["warnings"].extend(validation.warnings)

            if not validation.valid:
                error_msg = "; ".join(validation.errors)
                logger.warning("Validation failed (attempt %d): %s", attempt, error_msg)

                if attempt <= MAX_CORRECTION_LOOPS:
                    previous_sql   = validation.cleaned_sql or raw_sql
                    previous_error = f"Validation error: {error_msg}"
                    continue
                else:
                    result["sql"]   = validation.cleaned_sql or raw_sql
                    result["error"] = f"SQL validation failed after {attempt} attempts: {error_msg}"
                    return result

            clean = validation.cleaned_sql
            result["sql"] = clean
            logger.info("Validated SQL: %s", clean)

            
            try:
                data = run_query(clean)
                result["data"]  = data
                result["error"] = None
                logger.info(
                    "Success — %d rows in %dms",
                    len(data["rows"]),
                    data.get("duration_ms", 0),
                )
                return result

            except RuntimeError as exc:
                error_msg = str(exc)
                logger.warning("Execution error (attempt %d): %s", attempt, error_msg)

                if attempt <= MAX_CORRECTION_LOOPS:
                    previous_sql   = clean
                    previous_error = error_msg
                    
                else:
                    result["error"] = (
                        f"Query execution failed after {attempt} attempts: {error_msg}"
                    )
                    return result

        result["error"] = "Unexpected end of correction loop."
        return result


    def rebuild_schema_index(self) -> None:
        """Force full re-introspection and FAISS index rebuild."""
        build_index(force=True)
        clear_schema_cache()                          
        self._retriever = SchemaRetriever(top_k=self._retriever.top_k)
        logger.info("Schema index and DB cache rebuilt.")

    def list_indexed_tables(self) -> list[str]:
        return sorted(self._retriever.list_all_tables())