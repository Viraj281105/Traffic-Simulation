"""Which browser origins may call the API and open its WebSockets.

Origins are environment-driven (CORS_ORIGINS, comma-separated), never
hardcoded to a specific machine/domain. The local-dev default covers the
Vite dev server's default port. A bare "*" is never combined with
allow_credentials=True (browsers reject that combination anyway, and it
amounts to an unrestricted, credentialed CORS policy) — CORS_ORIGINS="*"
instead explicitly disables credentials for that case.

The same list decides WebSocket handshakes (src/api/ws_origin.py), and the two
stream helpers every WebSocket route uses live here with it.
"""

import logging
import os

from fastapi import WebSocket

from src.api.ws_origin import origin_allowed

logger = logging.getLogger(__name__)

_DEFAULT_DEV_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"
_cors_origins_raw = os.environ.get("CORS_ORIGINS", _DEFAULT_DEV_ORIGINS).strip()
if _cors_origins_raw == "*":
    CORS_ORIGINS = ["*"]
    CORS_ALLOW_CREDENTIALS = False
else:
    CORS_ORIGINS = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]
    CORS_ALLOW_CREDENTIALS = True


async def refuse_foreign_origin(websocket: WebSocket) -> bool:
    """Close a handshake from another site's page before accepting it
    (src/api/ws_origin.py); True when refused."""
    origin = websocket.headers.get("origin")
    if origin_allowed(origin, websocket.headers.get("host"), CORS_ORIGINS):
        return False
    logger.warning("Refused WebSocket from origin %r", origin)
    await websocket.close(code=1008)
    return True


async def close_after_stream_error(websocket: WebSocket) -> None:
    """Closes a stream that failed server-side; never raises.

    The reason is generic on purpose. The handlers used to send str(exc),
    which put internal error text on the wire — and a close reason longer
    than the protocol's 123-byte limit made close() itself raise, out of the
    handler. The exception is logged by the caller instead.
    """
    try:
        await websocket.close(code=1011, reason="Internal server error")
    except Exception:
        pass
