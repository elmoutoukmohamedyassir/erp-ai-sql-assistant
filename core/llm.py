from __future__ import annotations

import os
import time
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq, APIError, APIConnectionError, RateLimitError

from utils.logger import get_logger

load_dotenv(Path(__file__).parent.parent / ".env", override=True)

logger = get_logger(__name__)

_CLIENT: Groq | None = None


MODEL       = "llama-3.3-70b-versatile"
TEMPERATURE = 0.0       
MAX_TOKENS  = 1024
MAX_RETRIES = 3
RETRY_DELAY = 2.0   


def _get_client() -> Groq:
    global _CLIENT
    if _CLIENT is None:
        api_key = os.getenv("GROQ_API_KEY", "").strip()
        if not api_key:
            raise EnvironmentError("GROQ_API_KEY is not set in .env")
        _CLIENT = Groq(api_key=api_key)
    return _CLIENT


def call_llm(system_prompt: str, user_prompt: str) -> str:
    
    client  = _get_client()
    delay   = RETRY_DELAY
    last_ex = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            t0       = time.perf_counter()
            response = client.chat.completions.create(
                model=MODEL,
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ],
            )
            elapsed = time.perf_counter() - t0

            usage = response.usage
            logger.debug(
                "LLM call OK (attempt %d, %.1fs) — prompt=%d tokens, completion=%d tokens",
                attempt, elapsed,
                usage.prompt_tokens if usage else -1,
                usage.completion_tokens if usage else -1,
            )
            return response.choices[0].message.content or ""

        except RateLimitError as exc:
            logger.warning("Rate limit hit (attempt %d) — waiting %.0fs…", attempt, delay)
            last_ex = exc
            time.sleep(delay)
            delay *= 2

        except (APIConnectionError, APIError) as exc:
            logger.warning("LLM API error (attempt %d): %s", attempt, exc)
            last_ex = exc
            if attempt < MAX_RETRIES:
                time.sleep(delay)
                delay *= 2

    raise RuntimeError(f"LLM call failed after {MAX_RETRIES} attempts: {last_ex}") from last_ex