"""``/api/v2/costing``: prices, estimates, per-run cost and a per-tenant daily summary.

Register in main.py (the integrator does this)::

    from src.costing.router import create_router as build_costing_router
    app.include_router(build_costing_router(dependencies=[Depends(require_api_key)]))

Everything returned is an estimate, not a bill. Run data is read from the results directory the
insights routes use (``URBANFLOW_RESULTS_DIR``), through the run store backend.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional, Sequence

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.insights.locations import ResultsLocations, safe_id
from src.runstore import LocalFileBackend, StorageBackend

from .estimator import estimate_cost
from .prices import PriceTable, load_prices
from .runcost import (
    JobRecordNotFoundError,
    job_record_run_ids,
    read_run_cost,
    summarise_tenant_day,
)

PREFIX = "/api/v2/costing"
MAX_SUMMARY_RUNS = 5000


class EstimateRequest(BaseModel):
    computeSeconds: float = Field(ge=0, le=31_536_000)
    vcpuWeight: float = Field(default=1.0, gt=0, le=1024)
    instanceType: Optional[str] = Field(default=None, max_length=40)
    spot: bool = False
    storedBytes: int = Field(default=0, ge=0, le=10**15)
    queueRequests: int = Field(default=0, ge=0, le=10**12)
    storageMonths: float = Field(default=1.0, ge=0, le=120)


def create_router(
    dependencies: Sequence[Any] = (),
    locations: Optional[ResultsLocations] = None,
    prices: Optional[PriceTable] = None,
    backend: Optional[StorageBackend] = None,
) -> APIRouter:
    router = APIRouter(
        prefix=PREFIX, tags=["costing-v2"], dependencies=list(dependencies)
    )
    table = prices or load_prices()
    where = locations or ResultsLocations()
    store = backend or LocalFileBackend(where.root)

    def _error(status: int, message: str) -> HTTPException:
        return HTTPException(status_code=status, detail=message)

    @router.get("/prices")
    def get_prices() -> Dict[str, Any]:
        return table.to_dict()

    @router.post("/estimate")
    def post_estimate(body: EstimateRequest) -> Dict[str, Any]:
        try:
            est = estimate_cost(
                table,
                compute_seconds=body.computeSeconds,
                vcpu_weight=body.vcpuWeight,
                instance_type=body.instanceType,
                spot=body.spot,
                stored_bytes=body.storedBytes,
                queue_requests=body.queueRequests,
                storage_months=body.storageMonths,
            )
        except KeyError:
            raise _error(422, f"unknown instance type {body.instanceType!r}") from None
        except ValueError as exc:
            raise _error(422, str(exc)) from None
        return est.to_dict()

    @router.get("/runs/{run_id}")
    def get_run_cost(
        run_id: str,
        instance_type: Optional[str] = Query(
            default=None, alias="instanceType", max_length=40
        ),
        spot: bool = False,
    ) -> Dict[str, Any]:
        rid = safe_id(run_id)
        if rid is None:
            raise _error(404, "run not found")
        try:
            return read_run_cost(
                store, table, rid, instance_type=instance_type, spot=spot
            ).to_dict()
        except JobRecordNotFoundError as exc:
            raise _error(404, str(exc)) from None
        except KeyError:
            raise _error(422, f"unknown instance type {instance_type!r}") from None

    @router.get("/tenants/{tenant}/summary")
    def get_tenant_summary(
        tenant: str,
        day: str = Query(min_length=10, max_length=10),
    ) -> Dict[str, Any]:
        if safe_id(tenant) is None:
            raise _error(404, "tenant not found")
        try:
            date.fromisoformat(day)
        except ValueError:
            raise _error(422, "day must be YYYY-MM-DD") from None
        costs = []
        for rid in job_record_run_ids(store)[:MAX_SUMMARY_RUNS]:
            try:
                costs.append(read_run_cost(store, table, rid))
            except JobRecordNotFoundError:
                continue
        return summarise_tenant_day(
            costs, tenant, day, currency=table.currency
        ).to_dict()

    return router
