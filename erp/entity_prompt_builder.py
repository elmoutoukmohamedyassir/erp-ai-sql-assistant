"""
erp/entity_prompt_builder.py — prompts that make the LLM emit
{"entity", "operation", "fields"} instead of raw table/column writes.

Design decisions
-----------------
* Mirrors sql/write_prompt_builder.py's shape — same self-correction
  contract (previous_json / error_message), same "never output SQL" rule.
* The LLM works at the ENTITY level (Customer, Article, ...), never at the
  table/column level directly. erp/erp_write_agent.py is what maps entity
  fields -> real table/columns afterwards, via erp/entities.py. This keeps
  the LLM's job (and its failure surface) limited to "what business thing
  is this and what values did the user give", not "which physical table".
* Already-collected fields from a prior turn are injected into the prompt
  (<already_collected>) so the LLM only needs to extract NEW information
  from the latest message rather than re-deriving everything from scratch
  every turn — this is what makes multi-turn slot-filling work.
"""
from __future__ import annotations

from typing import Any

from erp.entities import list_writable_entities

ENTITY_SYSTEM_PROMPT = """\
You are an ERP copilot that converts natural-language requests into a
SINGLE structured JSON object describing a business entity action. You
NEVER output SQL. You NEVER output explanations. You output ONLY raw
JSON — no markdown fences, no comments.

<strict_rules>
1. Output ONLY one JSON object. No markdown backticks, no prose.
2. The JSON must match this shape exactly:
   {"entity": "<ENTITY>", "operation": "CREATE"|"UPDATE", "fields": {"<FIELD>": <VALUE>, ...}}
3. <ENTITY> must be one of the entities listed in <available_entities> below
   (use the exact entity= value shown, e.g. "CUSTOMER").
4. Use ONLY field names listed for that entity in <available_entities>.
   NEVER invent a field name.
5. Extract ONLY information present in <already_collected> + the latest
   <request>. Do not guess values the user never gave.
6. If the request gives a RELATIVE change with no current value available
   ("increase stock by 10"), output exactly: {"entity": "UNSUPPORTED_RELATIVE_UPDATE"}
7. If the request doesn't map to any entity below, output exactly:
   {"entity": "UNSUPPORTED"}
</strict_rules>

<available_entities>
{entities_block}
</available_entities>
"""


def _build_entities_block() -> str:
    lines: list[str] = []
    for entity in list_writable_entities():
        fields = sorted(set(entity.field_aliases.values()) | entity.additional_required_fields)
        lines.append(f'- {entity.name} (entity="{entity.name.upper()}"): fields = {fields}. {entity.description}')
    return "\n".join(lines)


ENTITY_SYSTEM_PROMPT = ENTITY_SYSTEM_PROMPT.replace("{entities_block}", _build_entities_block())


def build_entity_user_prompt(
    question: str,
    already_collected: dict[str, Any],
    missing_fields: list[str] | None = None,
    previous_json: str | None = None,
    error_message: str | None = None,
) -> str:
    parts: list[str] = []

    if already_collected:
        parts.append(f"<already_collected>\n{already_collected}\n</already_collected>")

    if missing_fields:
        parts.append(
            "<still_needed>\n"
            f"The user still needs to supply: {missing_fields}\n"
            "If the latest request provides any of these, include them in `fields`.\n"
            "</still_needed>"
        )

    if previous_json and error_message:
        parts.append(
            "<correction>\n"
            "Your previous JSON failed validation. Fix it.\n\n"
            f"Previous JSON:\n{previous_json}\n\n"
            f"Error:\n{error_message}\n\n"
            "Output ONLY the corrected raw JSON — nothing else.\n"
            "</correction>"
        )

    parts.append(f"<request>\n{question}\n</request>")
    parts.append("Output ONLY the raw JSON object now — no markdown, no explanation.")

    return "\n\n".join(parts)