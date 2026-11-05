"""Enumerates every route of the real app, including routers nested by ``include_router``.

FastAPI 0.141 keeps an included router as one opaque ``_IncludedRouter`` entry in
``app.routes`` and flattens it lazily through ``effective_route_contexts()``. This helper walks
both shapes (that one, and the classic ``.routes`` container) so a future FastAPI upgrade that
changes the layout still enumerates everything. ``assert_inventory_sane`` guards against the
walker silently returning nothing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterator, List, Optional, Tuple

from src.main import app

_SKIPPED_METHODS = frozenset({"HEAD", "OPTIONS"})


@dataclass(frozen=True)
class RouteInfo:
    kind: str  # "http" or "websocket"
    method: str  # "GET", ... or "WS"
    path: str  # template, e.g. /api/v1/replays/{replay_id}
    dependant: Any = None

    @property
    def key(self) -> Tuple[str, str]:
        return (self.method, self.path)

    @property
    def concrete_path(self) -> str:
        return re.sub(r"\{[^}]+\}", "x", self.path)

    @property
    def label(self) -> str:
        return f"{self.method} {self.path}"


def _walk(routes: Any) -> Iterator[Any]:
    for route in routes:
        contexts = getattr(route, "effective_route_contexts", None)
        if callable(contexts):
            yield from _walk(contexts())
            continue
        nested = getattr(route, "routes", None)
        if nested is not None and not getattr(route, "methods", None):
            yield from _walk(nested)
            continue
        yield route


def _describe(route: Any) -> List[RouteInfo]:
    inner: Optional[Any] = getattr(route, "starlette_route", None)
    methods = getattr(route, "methods", None)
    path = getattr(route, "path", "") or getattr(inner, "path", "") or ""
    if not methods:
        ws_path = getattr(inner, "path", None) or path
        dependant = getattr(inner, "dependant", None) or getattr(
            route, "dependant", None
        )
        return [RouteInfo("websocket", "WS", str(ws_path), dependant)]
    dependant = getattr(route, "dependant", None)
    return [
        RouteInfo("http", m, str(path), dependant)
        for m in sorted(set(methods) - _SKIPPED_METHODS)
    ]


def all_routes() -> List[RouteInfo]:
    found: List[RouteInfo] = []
    for route in _walk(app.routes):
        found.extend(_describe(route))
    return sorted(found, key=lambda r: (r.path, r.method))


def assert_inventory_sane(routes: List[RouteInfo]) -> None:
    assert len(routes) >= 100, f"route walker found only {len(routes)} routes"
    assert any(r.kind == "websocket" for r in routes), "no websocket route found"
    assert all(r.path.startswith("/") for r in routes), "route without a path"
