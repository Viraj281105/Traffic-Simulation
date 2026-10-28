"""Cost controls for the AI Copilot (V3 strategy section 7, sprint plan W5 "Security").

Every route answers with the deterministic fallback, never an error, when the model may not be called:

* ``AI_COPILOT_ENABLED=0`` is the kill switch (read per request);
* at most ``AI_CALLS_PER_CLIENT_PER_DAY`` model calls per client (the address resolved by ``client_key``,
  which honours only a trusted proxy's ``X-Real-IP``) per UTC day;
* at most ``AI_CALLS_PER_DAY`` model calls in total per UTC day (the global spend cap).

The browser proxy attaches the infrastructure API key to every request, so without these caps any visitor
could spend the provider budget. Counters are process-local and reset at UTC midnight (one backend process
is assumed, as for the other in-memory limits).
"""

from __future__ import annotations

import datetime as _dt
import os
import threading
from typing import Dict, Tuple

DEFAULT_CALLS_PER_CLIENT_PER_DAY = 60
DEFAULT_CALLS_PER_DAY = 1000

_lock = threading.Lock()
_day = ""
_per_client: Dict[str, int] = {}
_total = 0


def _int_env(name: str, default: int) -> int:
    try:
        return max(0, int(os.environ.get(name, "").strip() or default))
    except ValueError:
        return default


def enabled() -> bool:
    """False when the operator switched the model off (``AI_COPILOT_ENABLED`` = 0/false/no/off)."""
    return os.environ.get("AI_COPILOT_ENABLED", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def try_spend(client: str) -> Tuple[bool, str]:
    """Reserve one model call for ``client``. ``(False, reason)`` when a cap or the kill switch says no."""
    global _day, _total
    if not enabled():
        return False, "the AI model is switched off on this server"
    today = _dt.datetime.now(_dt.timezone.utc).date().isoformat()
    per_client = _int_env(
        "AI_CALLS_PER_CLIENT_PER_DAY", DEFAULT_CALLS_PER_CLIENT_PER_DAY
    )
    overall = _int_env("AI_CALLS_PER_DAY", DEFAULT_CALLS_PER_DAY)
    with _lock:
        if today != _day:
            _day, _total = today, 0
            _per_client.clear()
        if _total >= overall:
            return False, "the server's daily AI budget is used up"
        if _per_client.get(client, 0) >= per_client:
            return False, "your daily AI budget is used up"
        _per_client[client] = _per_client.get(client, 0) + 1
        _total += 1
        return True, ""


def reset() -> None:
    """Clear the counters. Intended for test fixtures."""
    global _day, _total
    with _lock:
        _day, _total = "", 0
        _per_client.clear()
