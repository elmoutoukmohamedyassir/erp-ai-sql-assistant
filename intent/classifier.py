from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from utils.logger import get_logger

logger = get_logger(__name__)


class Intent(str, Enum):
    READ = "READ"
    WRITE = "WRITE"


@dataclass
class IntentResult:
    intent: Intent
    matched_keyword: str | None = None
    confidence: float = 1.0


# ---------------------------------------------------------------------------
# WRITE trigger vocabulary
# ---------------------------------------------------------------------------
# Verbs / phrasings that strongly imply a mutation (INSERT or UPDATE).
# Kept as whole-word regexes to avoid matching inside unrelated words
# (e.g. "create" inside "created_at" mentioned in a read question).
_WRITE_PATTERNS: list[str] = [
    r"\badd\b",
    r"\bcreate\b",
    r"\bcreer\b",          # French, no accent (user input may be unaccented)
    r"\bcr[eé]er\b",
    r"\bajouter\b",
    r"\bajoute\b",
    r"\binsert\b",
    r"\bnew\s+(customer|article|product|invoice|supplier)\b",
    r"\bupdate\b",
    r"\bmodify\b",
    r"\bmodifier\b",
    r"\bedit\b",
    r"\bchange\b",
    r"\bset\b.+\bto\b",
    r"\bincrease\b",
    r"\baugmenter\b",
    r"\bdecrease\b",
    r"\breduce\b",
    r"\breduire\b",
    r"\badjust\b",
    r"\brename\b",
]

_WRITE_REGEX = re.compile("|".join(_WRITE_PATTERNS), re.IGNORECASE)

# Words that, if present, strongly confirm READ even if a write-ish verb
# appears elsewhere (e.g. "show me how to update prices" — informational).
_READ_OVERRIDE_PATTERNS: list[str] = [
    r"^\s*(show|list|display|get|find|how many|what is|what are)\b",
]
_READ_OVERRIDE_REGEX = re.compile("|".join(_READ_OVERRIDE_PATTERNS), re.IGNORECASE)


def detect_intent(question: str) -> IntentResult:
    """
    Classify a natural-language question as READ or WRITE.

    This is a pure function — no DB / LLM access — so it can run on every
    request with negligible cost.
    """
    q = question.strip()

    if not q:
        return IntentResult(intent=Intent.READ, matched_keyword=None, confidence=0.0)

    # An explicit read-style opener (e.g. "show me...", "list...") wins
    # even if a write verb appears later in the sentence.
    if _READ_OVERRIDE_REGEX.search(q):
        logger.debug("Intent=READ (read-override phrasing): %s", q[:80])
        return IntentResult(intent=Intent.READ, matched_keyword=None, confidence=0.9)

    match = _WRITE_REGEX.search(q)
    if match:
        logger.debug("Intent=WRITE (matched %r): %s", match.group(), q[:80])
        return IntentResult(intent=Intent.WRITE, matched_keyword=match.group(), confidence=0.85)

    logger.debug("Intent=READ (default, no write keyword): %s", q[:80])
    return IntentResult(intent=Intent.READ, matched_keyword=None, confidence=0.6)
