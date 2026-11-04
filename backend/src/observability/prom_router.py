"""``GET /metrics/prom``: run/API metrics for Prometheus (package 1D).

The existing ``GET /metrics`` (``observability/router.py``) already owns that
path, so this router serves the richer set (``urbanflow_runs_*``,
``urbanflow_run_duration_seconds``, ``urbanflow_queue_depth``,
``urbanflow_api_latency_seconds`` and, appended, everything ``/metrics``
serves) one segment lower. Same access rule as ``/metrics``: bearer
``METRICS_TOKEN`` when set, otherwise loopback only.

Register in ``src/main.py``::

    from src.observability import prom_router
    app.include_router(prom_router.router)
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse

from .prom_metrics import CONTENT_TYPE, render
from .router import _authorised

router = APIRouter()


@router.get("/metrics/prom", include_in_schema=False)
def metrics_prom(request: Request) -> PlainTextResponse:
    if not _authorised(request):
        raise HTTPException(status_code=403, detail="Metrics are restricted")
    return PlainTextResponse(render(), media_type=CONTENT_TYPE)
