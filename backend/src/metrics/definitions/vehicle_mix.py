"""Per-vehicle-class breakdown of the headline metrics (V1.1).

With heterogeneous traffic the existing aggregates stay valid — throughput is
still vehicles served, delay is still each vehicle's travel time over its own
free-flow time (a bus's free-flow time uses the bus's own desired speed) — but
an average over a mix hides who bears the delay. This breakdown reports the
same quantities per class, from the same per-vehicle delays the aggregate
uses, so the class figures always reconcile with the overall ones.
"""

from __future__ import annotations

from typing import Dict, List, Sequence

from src.vehicles.vehicle import LEGACY_VEHICLE_TYPE, Vehicle


def _type_of(vehicle: Vehicle) -> str:
    return str(getattr(vehicle, "vehicle_type", LEGACY_VEHICLE_TYPE))


def calculate_vehicle_type_breakdown(
    post_warmup_exited: Sequence[Vehicle],
    delays: Sequence[float],
    active_vehicles: Sequence[Vehicle],
) -> Dict[str, Dict[str, float]]:
    """{class: {exited, share, averageDelay, active}} for every class present.

    ``delays`` must be aligned with ``post_warmup_exited`` (one delay per
    exited vehicle, in the same order) — exactly the list the collector
    averages for ``averageDelay``.
    """
    per_type: Dict[str, List[float]] = {}
    for vehicle, delay in zip(post_warmup_exited, delays):
        per_type.setdefault(_type_of(vehicle), []).append(delay)

    active: Dict[str, int] = {}
    for vehicle in active_vehicles:
        type_id = _type_of(vehicle)
        active[type_id] = active.get(type_id, 0) + 1

    total_exited = sum(len(v) for v in per_type.values())
    breakdown: Dict[str, Dict[str, float]] = {}
    for type_id in sorted(set(per_type) | set(active)):
        type_delays = per_type.get(type_id, [])
        breakdown[type_id] = {
            "exited": len(type_delays),
            "share": round(len(type_delays) / total_exited, 3) if total_exited else 0.0,
            "averageDelay": round(sum(type_delays) / len(type_delays), 2)
            if type_delays
            else 0.0,
            "active": active.get(type_id, 0),
        }
    return breakdown
