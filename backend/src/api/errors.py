"""Uniform error envelope (docs/architecture/08-communication-contract.md §6.1).

Routes raise plain HTTPException(status_code, detail="..."), which FastAPI
serializes by default as {"detail": "..."}. The documented contract instead
requires every error response to share one consistent shape:
{"error": {"code", "message", "details", "timestamp"}}. The handler rewrites
the response body only — it does not change status codes, and it never runs
for a 2xx response, so no successful response structure is affected. The
frontend does not inspect error response bodies (it keys off HTTP status
only — see useSimulationPolling.ts), so this is safe to change without a
frontend change.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

STATUS_ERROR_CODES: Dict[int, str] = {
    400: "VALIDATION_ERROR",
    401: "UNAUTHORIZED",
    404: "NOT_FOUND",
    409: "INVALID_STATE_TRANSITION",
    413: "PAYLOAD_TOO_LARGE",
    422: "VALIDATION_ERROR",
    429: "SIMULATION_LIMIT_REACHED",
    500: "INTERNAL_ERROR",
}


def iso_timestamp(epoch_seconds: float) -> str:
    """Formats a Unix timestamp using this API's UTC-Z convention (the same
    as the error envelope's "timestamp" field)."""
    return (
        datetime.fromtimestamp(epoch_seconds, tz=timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    details: Optional[Dict[str, Any]] = None
    if isinstance(exc.detail, str):
        message = exc.detail
    elif isinstance(exc.detail, dict) and isinstance(exc.detail.get("errors"), list):
        # The planning router's {"errors": [...]}: kept as a list a client
        # can show, rather than flattened into a Python repr.
        message = "; ".join(str(e) for e in exc.detail["errors"])
        details = {"errors": [str(e) for e in exc.detail["errors"]]}
    else:
        message = str(exc.detail)
    code = STATUS_ERROR_CODES.get(exc.status_code, "INTERNAL_ERROR")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details,
                "timestamp": datetime.now(timezone.utc)
                .isoformat()
                .replace("+00:00", "Z"),
            }
        },
        headers=exc.headers,
    )
