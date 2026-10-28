"""Which browser pages may open the simulation WebSockets.

CORS does not apply to WebSockets: any page a visitor has open can connect to
``/ws/...`` on this host, and the browser attaches the visitor's cookies --
including the live-session cookie that selects *their* simulation. Without a
check, a page on another site could watch a visitor's live run
(cross-site WebSocket hijacking). Browsers always send ``Origin`` on a
WebSocket handshake, so the server checks it:

* the page's host is this server's host (same site, as served through nginx,
  which forwards ``Host`` without the port, so ports are not compared); or
* the page's origin is one of ``CORS_ORIGINS`` (the Vite dev server, whose
  proxy rewrites ``Host``); or
* there is no ``Origin`` at all -- not a browser (scripts, tests), and a
  browser cannot be made to omit it.
"""

from __future__ import annotations

from typing import Optional, Sequence
from urllib.parse import urlsplit


def _hostname(value: str) -> Optional[str]:
    """Hostname of an origin (``https://a.b:8080``) or a Host header
    (``a.b:8080``, ``[::1]:80``), lower-cased; None if there is none."""
    candidate = value if "://" in value else f"//{value}"
    try:
        host = urlsplit(candidate).hostname
    except ValueError:
        return None
    return host.lower() if host else None


def origin_allowed(
    origin: Optional[str], host: Optional[str], allowed_origins: Sequence[str]
) -> bool:
    if origin is None:
        return True
    origin = origin.strip()
    if "*" in allowed_origins or origin.rstrip("/") in {
        o.rstrip("/") for o in allowed_origins
    }:
        return True
    origin_host = _hostname(origin)
    return origin_host is not None and origin_host == _hostname(host or "")
