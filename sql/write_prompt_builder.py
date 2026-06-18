"""
sql/write_prompt_builder.py — prompts that make the LLM emit structured
JSON write actions instead of raw SQL.

Design decisions
-----------------
* Mirrors sql/prompt_builder.py's shape (SYSTEM_PROMPT + build_user_prompt)
  so the two prompt builders stay consistent and easy to maintain side by
  side.
* The system prompt explicitly forbids the LLM from ever emitting SQL —
  only JSON matching InsertAction / UpdateAction. This is the prompt-level
  half of the "no LLM-generated SQL" guarantee; the structural half is
  enforced by sql/write_models.py + sql/write_validator.py regardless of
  what the LLM actually outputs.
* Domain mappings (table/column names) are intentionally limited to the
  WRITABLE_TABLES whitelist from sql/write_validator.py, so the LLM is
  never even prompted with write-capable instructions for tables it isn't
  allowed to touch.
"""
from __future__ import annotations

from sql.write_validator import WRITABLE_TABLES

WRITE_SYSTEM_PROMPT = """\
You are an assistant that converts natural-language ERP write requests
into a SINGLE structured JSON object describing an INSERT or UPDATE
action. You NEVER output SQL. You NEVER output explanations. You output
ONLY raw JSON — no markdown fences, no comments.

<strict_rules>
1. Output ONLY one JSON object. No markdown backticks, no prose.
2. The JSON must match exactly one of these two shapes:

   INSERT:
   {"action": "INSERT", "table": "<TABLE>", "values": {"<COL>": <VALUE>, ...}}

   UPDATE:
   {"action": "UPDATE", "table": "<TABLE>", "where": {"<COL>": <VALUE>, ...}, "values": {"<COL>": <VALUE>, ...}}

3. Use ONLY tables and columns listed in <writable_schema> below.
4. NEVER invent column names. If unsure which column to use, pick the
   closest documented one from <writable_schema>.
5. For UPDATE actions, "where" must contain enough columns to uniquely
   identify the row (prefer the documented key column, e.g. AR_Ref for
   F_ARTICLE / F_ARTSTOCK, CT_Num for F_COMPTET).
6. Some requests are RELATIVE ("increase stock by 10", "decrease price by
   5"). You do not have access to the current stored value, so for this
   phase you cannot compute the new absolute value yourself. If the
   request is relative rather than an explicit target value, output
   exactly: {"action": "UNSUPPORTED_RELATIVE_UPDATE"}
   Only generate a normal UPDATE when the user gives (or implies) an
   explicit target value, e.g. "set stock of X to 50" or "update price of
   Y to 1000".
7. If the request does not map to any writable table/column, output
   exactly: {"action": "UNSUPPORTED"}
8. Never include any column not present in <writable_schema>.
</strict_rules>

<writable_schema>
{schema_block}
</writable_schema>
"""


def _build_schema_block() -> str:
    """
    Render the writable-tables whitelist (and their human description)
    into a short text block for the system prompt. Kept intentionally
    compact — full column lists are injected per-request in the user
    prompt via `column_hint`, since they come from the live DB schema.
    """
    lines = []
    for table, desc in WRITABLE_TABLES.items():
        lines.append(f"- {table}: {desc}")
    return "\n".join(lines)


WRITE_SYSTEM_PROMPT = WRITE_SYSTEM_PROMPT.replace("{schema_block}", _build_schema_block())


def build_write_user_prompt(
    question: str,
    column_hint: str,
    previous_json: str | None = None,
    error_message: str | None = None,
) -> str:
    """
    Compose the user-turn prompt for write-intent requests.

    `column_hint` is a short text block listing real column names per
    writable table (populated by core/write_agent.py from the live DB
    schema via core.db.get_table_columns_real_case), so the LLM has
    accurate, current column names without us hardcoding them here.
    """
    parts: list[str] = []

    parts.append(f"<available_columns>\n{column_hint}\n</available_columns>")

    if previous_json and error_message:
        parts.append(
            "<correction>\n"
            "Your previous JSON failed validation. Fix it.\n\n"
            f"Previous JSON:\n{previous_json}\n\n"
            f"Validation error:\n{error_message}\n\n"
            "Output ONLY the corrected raw JSON — nothing else.\n"
            "</correction>"
        )

    parts.append(f"<request>\n{question}\n</request>")

    if previous_json:
        parts.append("Output ONLY the corrected JSON object. No explanation.")
    else:
        parts.append(
            "Generate the JSON write action now. "
            "Output ONLY the raw JSON object — no markdown, no explanation."
        )

    return "\n\n".join(parts)
