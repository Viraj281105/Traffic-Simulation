"""Per-run cost from the worker job record (runs/<id>/job.json) and per-tenant-per-day totals."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional

from src.jobs.worker import JOB_RECORD_NAME
from src.runstore import KeyNotFoundError, StorageBackend

from .estimator import CONFIDENCE, CostEstimate, estimate_cost
from .prices import PriceTable

# Send, receive and delete: one message's life on the queue.
QUEUE_REQUESTS_PER_JOB = 3


class JobRecordNotFoundError(LookupError):
    """No usable job record is stored for the run."""


@dataclass(frozen=True)
class RunCost:
    run_id: str
    tenant: str
    day: Optional[str]
    compute_seconds: float
    tags: Dict[str, str]
    estimate: CostEstimate

    def to_dict(self) -> Dict[str, Any]:
        return {
            "runId": self.run_id,
            "tenant": self.tenant,
            "day": self.day,
            "computeSeconds": self.compute_seconds,
            "costTags": self.tags,
            **self.estimate.to_dict(),
        }


def _day_of(
    backend: StorageBackend, run_id: str, record: Mapping[str, Any]
) -> Optional[str]:
    """The record own date, else the manifest createdAt (its first 10 characters)."""
    stamp = record.get("finishedAt")
    if not isinstance(stamp, str):
        try:
            manifest = json.loads(backend.get(f"runs/{run_id}/manifest.json"))
            stamp = manifest.get("createdAt")
        except (KeyNotFoundError, ValueError, AttributeError):
            stamp = None
    return stamp[:10] if isinstance(stamp, str) and len(stamp) >= 10 else None


def read_run_cost(
    backend: StorageBackend,
    prices: PriceTable,
    run_id: str,
    *,
    instance_type: Optional[str] = None,
    spot: bool = False,
) -> RunCost:
    """Estimate one run from its job record. Raises ``JobRecordNotFoundError`` when absent."""
    try:
        record = json.loads(backend.get(f"runs/{run_id}/{JOB_RECORD_NAME}"))
    except KeyNotFoundError:
        raise JobRecordNotFoundError(f"no job record for run {run_id}") from None
    except ValueError:
        raise JobRecordNotFoundError(
            f"job record for run {run_id} is unreadable"
        ) from None
    if not isinstance(record, dict):
        raise JobRecordNotFoundError(f"job record for run {run_id} is unreadable")
    seconds = record.get("computeSeconds")
    if (
        isinstance(seconds, bool)
        or not isinstance(seconds, (int, float))
        or seconds < 0
    ):
        raise JobRecordNotFoundError(
            f"job record for run {run_id} has no computeSeconds"
        )
    raw_tags = record.get("costTags")
    tags = (
        {str(k): str(v) for k, v in raw_tags.items()}
        if isinstance(raw_tags, dict)
        else {}
    )
    estimate = estimate_cost(
        prices,
        compute_seconds=float(seconds),
        instance_type=instance_type,
        spot=spot,
        queue_requests=QUEUE_REQUESTS_PER_JOB,
    )
    return RunCost(
        run_id=run_id,
        tenant=str(record.get("tenant") or tags.get("tenant") or ""),
        day=_day_of(backend, run_id, record),
        compute_seconds=float(seconds),
        tags=tags,
        estimate=estimate,
    )


@dataclass
class TenantDaySummary:
    tenant: str
    day: str
    runs: int = 0
    compute_seconds: float = 0.0
    total: float = 0.0
    currency: str = "USD"
    by_tag: Dict[str, Dict[str, float]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tenant": self.tenant,
            "day": self.day,
            "runs": self.runs,
            "computeSeconds": round(self.compute_seconds, 3),
            "total": round(self.total, 6),
            "currency": self.currency,
            "byTag": {
                k: {v: round(c, 6) for v, c in sorted(vals.items())}
                for k, vals in sorted(self.by_tag.items())
            },
            "confidence": CONFIDENCE,
        }


def summarise_tenant_day(
    costs: Iterable[RunCost], tenant: str, day: str, currency: str = "USD"
) -> TenantDaySummary:
    """Add up one tenant day, with the cost split by the project and env cost tags."""
    out = TenantDaySummary(tenant=tenant, day=day, currency=currency)
    for cost in costs:
        if cost.tenant != tenant or cost.day != day:
            continue
        out.runs += 1
        out.compute_seconds += cost.compute_seconds
        out.total += cost.estimate.total
        for key in ("project", "env"):
            value = cost.tags.get(key)
            if value:
                bucket = out.by_tag.setdefault(key, {})
                bucket[value] = bucket.get(value, 0.0) + cost.estimate.total
    return out


def job_record_run_ids(backend: StorageBackend) -> List[str]:
    """Ids of the runs that have a job record."""
    ids = set()
    for key in backend.list("runs/"):
        parts = key.split("/")
        if len(parts) == 3 and parts[2] == JOB_RECORD_NAME:
            ids.add(parts[1])
    return sorted(ids)
