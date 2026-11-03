"""Request id, request metrics and the request log line (pure ASGI).

Each HTTP request gets a request id: the caller's ``X-Request-ID`` when it is
a short, safe token (so a proxy's id carries through), otherwise a new one.
It is set for the duration of the request (every log line written meanwhile
carries it) and returned in the ``X-Request-ID`` response header.

Metrics use the matched route's **template** (``/api/v3/experiments/{id}``),
never the raw path, and ``unmatched`` for a path no route serves, so ids in
URLs cannot grow the number of series. Health and metrics scrapes are counted
but logged only at DEBUG, so they do not flood the log.
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from typing import Any, Awaitable, Callable, Dict, MutableMapping, Optional, Sequence

from starlette.routing import Match

from .logging_setup import request_id_var
from .metrics import HTTP_LATENCY, HTTP_REQUESTS, HTTP_UNHANDLED, LIMIT_EVENTS

logger = logging.getLogger("urbanflow.request")

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]

_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_QUIET_PATHS = frozenset({"/health", "/metrics"})


def _request_id(scope: Scope) -> str:
    for name, value in scope.get("headers") or ():
        if name == b"x-request-id":
            try:
                candidate: str = bytes(value).decode("ascii")
            except UnicodeDecodeError:
                break
            if _SAFE_ID.match(candidate):
                return candidate
            break
    return uuid.uuid4().hex


def _template(route: Any) -> Optional[str]:
    path = getattr(route, "path", None)
    return path if isinstance(path, str) and path else None


def _find(routes: Sequence[Any], scope: Scope, depth: int) -> Optional[str]:
    """The template of the route in ``routes`` that serves ``scope``, looking
    inside included routers; None when none does."""
    if depth > 4:
        return None
    for route in routes:
        inner = getattr(route, "original_router", None)
        if inner is not None:
            found = _find(getattr(inner, "routes", ()), scope, depth + 1)
            if found is not None:
                return found
            continue
        try:
            match, _ = route.matches(scope)
        except Exception:  # noqa: BLE001 - naming a route must never fail a request
            continue
        if match == Match.FULL:
            return _template(route)
    return None


class ObservabilityMiddleware:
    """``routes``: the application's route table (``app.routes``), used to
    name the route of a request refused before routing ran (a body-size
    413, for example). Without it such requests are ``unmatched``."""

    def __init__(self, app: ASGIApp, routes: Optional[Sequence[Any]] = None) -> None:
        self.app = app
        self.routes = routes

    def _route(self, scope: Scope) -> str:
        matched = _template(scope.get("route"))
        if matched is not None:
            return matched
        return _find(self.routes or (), scope, depth=0) or "unmatched"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        rid = _request_id(scope)
        token = request_id_var.set(rid)
        status: Dict[str, int] = {"code": 500}
        started = time.perf_counter()

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                status["code"] = int(message["status"])
                headers = list(message.get("headers") or [])
                headers.append((b"x-request-id", rid.encode("ascii")))
                message["headers"] = headers
            await send(message)

        method = str(scope.get("method", "GET"))
        try:
            await self.app(scope, receive, send_with_id)
        except Exception:
            HTTP_UNHANDLED.inc(self._route(scope))
            logger.exception(
                "request failed",
                extra={"method": method, "route": self._route(scope), "status": 500},
            )
            raise
        finally:
            elapsed = time.perf_counter() - started
            route = self._route(scope)
            code = status["code"]
            HTTP_REQUESTS.inc(method, route, f"{code // 100}xx")
            HTTP_LATENCY.observe(elapsed, method, route)
            if code in (413, 429):
                LIMIT_EVENTS.inc(str(code), route)
            level = (
                logging.DEBUG
                if scope.get("path") in _QUIET_PATHS
                else logging.WARNING
                if code >= 500
                else logging.INFO
            )
            logger.log(
                level,
                "%s %s %d",
                method,
                route,
                code,
                extra={
                    "method": method,
                    "route": route,
                    "status": code,
                    "duration_ms": round(elapsed * 1000.0, 1),
                },
            )
            request_id_var.reset(token)
