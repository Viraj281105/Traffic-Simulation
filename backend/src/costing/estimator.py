"""Itemised cost estimate: compute, storage, queue. An estimate, not a bill."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .prices import PriceTable

CONFIDENCE = "estimate, not a bill"
BYTES_PER_GB = 1_000_000_000
ROUND_DIGITS = 6


@dataclass(frozen=True)
class CostEstimate:
    compute: float
    storage: float
    queue: float
    total: float
    currency: str
    confidence: str
    assumptions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "items": {
                "compute": self.compute,
                "storage": self.storage,
                "queue": self.queue,
            },
            "total": self.total,
            "currency": self.currency,
            "confidence": self.confidence,
            "assumptions": list(self.assumptions),
        }


def estimate_cost(
    prices: PriceTable,
    *,
    compute_seconds: float,
    vcpu_weight: float = 1.0,
    instance_type: Optional[str] = None,
    spot: bool = False,
    stored_bytes: int = 0,
    queue_requests: int = 0,
    storage_months: float = 1.0,
) -> CostEstimate:
    """Compute = hours x hourly price x (vcpu_weight / instance vCPUs): a job pays for the share of
    the instance it occupies. Storage = GB x per-GB-month x months. Queue = requests / 1e6 x price.

    Raises ``KeyError`` for an unknown instance type and ``ValueError`` for negative or non-finite
    inputs or a weight above the instance vCPUs."""
    for name, value in (
        ("compute_seconds", compute_seconds),
        ("vcpu_weight", vcpu_weight),
        ("stored_bytes", stored_bytes),
        ("queue_requests", queue_requests),
        ("storage_months", storage_months),
    ):
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"{name} must be a non-negative number")
    inst = prices.instance(instance_type)
    if vcpu_weight > inst.vcpus:
        raise ValueError(f"vcpu_weight {vcpu_weight} exceeds {inst.name} vCPUs")
    hourly = inst.spot_hourly if spot else inst.on_demand_hourly
    compute = round(
        compute_seconds / 3600.0 * hourly * (vcpu_weight / inst.vcpus), ROUND_DIGITS
    )
    storage = round(
        stored_bytes / BYTES_PER_GB * prices.s3_per_gb_month * storage_months,
        ROUND_DIGITS,
    )
    queue = round(queue_requests / 1_000_000 * prices.sqs_per_million, ROUND_DIGITS)
    notes = [
        f"{inst.name} {'spot' if spot else 'on-demand'} at {hourly}/h, "
        f"{inst.vcpus} vCPUs, {vcpu_weight} vCPU(s) charged",
        f"prices as of {prices.as_of} for {prices.region}; approximate, from memory",
        f"storage billed for {storage_months} month(s) at S3 standard, decimal GB",
        "no data transfer, request, NAT or idle-node costs are included",
    ]
    return CostEstimate(
        compute=compute,
        storage=storage,
        queue=queue,
        total=round(compute + storage + queue, ROUND_DIGITS),
        currency=prices.currency,
        confidence=CONFIDENCE,
        assumptions=notes,
    )
