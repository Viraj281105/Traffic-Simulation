"""``GET /metrics``: the registry in the Prometheus text format.

Access:

* ``METRICS_TOKEN`` set: the request must carry ``Authorization: Bearer
  <METRICS_TOKEN>`` (compared in constant time). This is the deployed setup:
  a scraper inside the Docker network presents the token.
* ``METRICS_TOKEN`` unset: only a loopback client (127.0.0.1, ::1) is
  answered, which covers local development; anything else gets 403. The
  production nginx does not proxy ``/metrics`` either, so it is not public.

Gauges read cheap in-memory state at scrape time (job counts, registered
simulations, live sessions); nothing here touches a running simulation.
"""

from __future__ import annotations

import hmac
import os
from typing import Iterator, Tuple

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse

from .metrics import REGISTRY, LabelValues

router = APIRouter()

_LOOPBACK = frozenset({"127.0.0.1", "::1", "localhost"})
CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"


def _registered_simulations() -> Iterator[Tuple[LabelValues, float]]:
    from src.simulations.registry import simulations_db, simulations_lock

    counts: dict[str, int] = {}
    with simulations_lock:
        for entry in simulations_db.values():
            engine = entry.get("engine")
            status = getattr(getattr(engine, "status", None), "value", "unknown")
            key = str(status).lower()
            counts[key] = counts.get(key, 0) + 1
    for status, n in sorted(counts.items()):
        yield (status,), float(n)


def _live_sessions() -> Iterator[Tuple[LabelValues, float]]:
    from src.live.sessions import live_sessions, live_sessions_lock

    with live_sessions_lock:
        n = len(live_sessions)
    yield (), float(n)


def _active_jobs() -> Iterator[Tuple[LabelValues, float]]:
    from src.study.jobs import active_jobs_by_kind

    yield from active_jobs_by_kind()


REGISTRY.gauge(
    "urbanflow_jobs_active",
    "Background jobs queued or running, by kind.",
    _active_jobs,
    ("kind",),
)
REGISTRY.gauge(
    "urbanflow_simulations_registered",
    "Simulations held in the /api/v1/simulations registry, by engine status.",
    _registered_simulations,
    ("status",),
)
REGISTRY.gauge(
    "urbanflow_live_sessions",
    "Live dashboard sessions held in memory.",
    _live_sessions,
)


def _authorised(request: Request) -> bool:
    token = os.getenv("METRICS_TOKEN", "")
    if token:
        header = request.headers.get("authorization", "")
        scheme, _, presented = header.partition(" ")
        return scheme.lower() == "bearer" and hmac.compare_digest(
            presented.strip().encode(), token.encode()
        )
    host = request.client.host if request.client else ""
    return host in _LOOPBACK


@router.get("/metrics", include_in_schema=False)
def metrics(request: Request) -> PlainTextResponse:
    if not _authorised(request):
        raise HTTPException(status_code=403, detail="Metrics are restricted")
    return PlainTextResponse(REGISTRY.render(), media_type=CONTENT_TYPE)
