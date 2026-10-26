"""Groq API client wrapper.

Key contract
────────────
* The API key is read once from the ``GROQ_API_KEY`` environment variable.
* It is NEVER logged, returned in any response, or stored anywhere else.
* All calls carry a 30-second timeout.
* A single 429 (rate-limit) triggers one retry after 2 seconds; after that
  the caller falls back to the deterministic answers in fallback.py.
* Any other Groq error is caught, logged at WARNING level (without the key),
  and re-raised so the router can return the fallback instead of a 500.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Lazy import so the app starts even if groq is not installed yet ──────────


def _groq() -> Any:
    """Return the groq module, raising ImportError with a helpful message."""
    try:
        import groq as _g

        return _g
    except ImportError as exc:
        raise ImportError(
            "The 'groq' package is not installed. Run: pip install groq>=0.28.0"
        ) from exc


# ── Configuration ────────────────────────────────────────────────────────────

# These are read once at module load time, before any request is handled.
_GROQ_API_KEY: Optional[str] = os.environ.get("GROQ_API_KEY")
_MODEL: str = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")

# Hard caps applied to every call, regardless of what the caller requests.
_MAX_INPUT_CHARS = 8_000  # ~2 K tokens of metrics JSON (generous budget)
_MAX_OUTPUT_TOKENS = 900  # enough for any of our three use-cases
_TIMEOUT_SECONDS = 30
_RATE_LIMIT_RETRY_SECONDS = 2


def _client() -> Any:
    """Build a Groq client from the environment key."""
    if not _GROQ_API_KEY:
        raise EnvironmentError(
            "GROQ_API_KEY is not set. Add it to backend/.env and restart."
        )
    g = _groq()
    return g.Groq(api_key=_GROQ_API_KEY, timeout=_TIMEOUT_SECONDS)


def is_configured() -> bool:
    """True when GROQ_API_KEY is present in the environment."""
    return bool(_GROQ_API_KEY)


# ── Core call ────────────────────────────────────────────────────────────────


def _call(
    messages: List[Dict[str, str]],
    *,
    max_tokens: int = _MAX_OUTPUT_TOKENS,
    response_format: Optional[Dict[str, Any]] = None,
) -> str:
    """Make one Groq chat-completion call and return the content string.

    Retries once on 429 (rate-limit).  Every other error propagates.
    """
    g = _groq()
    client = _client()
    kwargs: Dict[str, Any] = {
        "model": _MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.2,  # low temperature for factual / deterministic output
    }
    if response_format:
        kwargs["response_format"] = response_format

    for attempt in range(2):
        try:
            resp = client.chat.completions.create(**kwargs)
            return resp.choices[0].message.content or ""
        except g.RateLimitError:
            if attempt == 0:
                logger.warning(
                    "Groq rate-limit hit; retrying after %ss", _RATE_LIMIT_RETRY_SECONDS
                )
                time.sleep(_RATE_LIMIT_RETRY_SECONDS)
            else:
                raise
        except g.APIConnectionError as exc:
            logger.warning("Groq connection error: %s", type(exc).__name__)
            raise
        except g.APIStatusError as exc:
            logger.warning("Groq API error %s: %s", exc.status_code, type(exc).__name__)
            raise

    return ""  # unreachable, but satisfies type checkers


# ── Public helpers ───────────────────────────────────────────────────────────


def complete(
    system: str,
    user: str,
    *,
    history: Optional[List[Dict[str, str]]] = None,
    max_tokens: int = _MAX_OUTPUT_TOKENS,
) -> str:
    """Plain text completion (summary, Q&A)."""
    # Truncate the user message to guard against oversized metrics blobs.
    user = user[:_MAX_INPUT_CHARS]
    messages: List[Dict[str, str]] = [{"role": "system", "content": system}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user})
    return _call(messages, max_tokens=max_tokens)


def complete_json(
    system: str,
    user: str,
    schema: Optional[Dict[str, Any]] = None,
    *,
    max_tokens: int = _MAX_OUTPUT_TOKENS,
) -> Dict[str, Any]:
    """Structured-output completion that guarantees a valid JSON object.

    Uses Groq's ``json_object`` mode which guarantees JSON output without
    requiring strict schema definitions where every partial patch field would
    have to be mandatory.
    """
    user = user[:_MAX_INPUT_CHARS]
    system_with_instruction = (
        f"{system}\n\nIMPORTANT: You MUST respond ONLY with a valid JSON object."
    )
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": system_with_instruction},
        {"role": "user", "content": user},
    ]
    response_format: Dict[str, Any] = {"type": "json_object"}
    raw = _call(messages, max_tokens=max_tokens, response_format=response_format)
    try:
        return _as_object(json.loads(raw))
    except json.JSONDecodeError:
        # Extract markdown json block if wrapped
        if "```" in raw:
            parts = raw.split("```")
            for part in parts:
                cleaned = part.strip()
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:].strip()
                try:
                    return _as_object(json.loads(cleaned))
                except Exception:
                    continue
        # Model output is not logged or echoed: it may contain the user's data.
        logger.warning("Groq returned non-JSON despite json_object format")
        raise ValueError("Model returned non-JSON output")


def _as_object(parsed: Any) -> Dict[str, Any]:
    if not isinstance(parsed, dict):
        raise ValueError("Model returned JSON that is not an object")
    return parsed
