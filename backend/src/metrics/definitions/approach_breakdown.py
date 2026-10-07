"""Per-approach breakdown of the headline metrics (V1.4).

A user-configured junction can be deliberately uneven — heavy traffic from
one road, a narrow side street — and a junction-wide average then hides which
approach bears the delay. This reports, per approach the vehicles came from,
the same quantities the aggregate uses: vehicles served after warm-up and
their mean delay (from the same per-vehicle delays as ``averageDelay``, so the
figures reconcile), vehicles still active, and the approach's time-averaged
and maximum queue (the per-direction values ``averageQueueLength`` and
``maxQueueLength`` are built from). No new quantity is introduced.
"""

from __future__ import annotations

from typing import Dict, List, Mapping, Optional, Sequence

from src.core.enums import Direction
from src.vehicles.vehicle import Vehicle

_PREFIX = {"n": "north", "s": "south", "e": "east", "w": "west"}


def origin_of(vehicle: Vehicle) -> Optional[str]:
    """Approach a vehicle entered from (its route's first lane)."""
    route = getattr(vehicle, "route", None)
    if not route:
        return None
    first = route[0]
    approach = getattr(first, "approach", None)
    if isinstance(approach, Direction):
        return approach.value
    lane_id = str(getattr(first, "lane_id", "")).lower()
    return _PREFIX.get(lane_id[:1]) if "_in_" in lane_id else None


def calculate_approach_breakdown(
    post_warmup_exited: Sequence[Vehicle],
    delays: Sequence[float],
    active_vehicles: Sequence[Vehicle],
    average_queue: Mapping[str, float],
    max_queue: Mapping[str, int],
) -> Dict[str, Dict[str, float]]:
    """{approach: {exited, averageDelay, active, averageQueueLength,
    maxQueueLength}} for all four approaches. ``delays`` is aligned with
    ``post_warmup_exited``, exactly the list ``averageDelay`` averages."""
    per_origin: Dict[str, List[float]] = {d.value: [] for d in Direction}
    for vehicle, delay in zip(post_warmup_exited, delays):
        origin = origin_of(vehicle)
        if origin in per_origin:
            per_origin[origin].append(delay)
    active: Dict[str, int] = {d.value: 0 for d in Direction}
    for vehicle in active_vehicles:
        origin = origin_of(vehicle)
        if origin in active:
            active[origin] += 1
    return {
        d.value: {
            "exited": len(per_origin[d.value]),
            "averageDelay": round(
                sum(per_origin[d.value]) / len(per_origin[d.value]), 2
            )
            if per_origin[d.value]
            else 0.0,
            "active": active[d.value],
            "averageQueueLength": round(float(average_queue.get(d.value, 0.0)), 2),
            "maxQueueLength": int(max_queue.get(d.value, 0)),
        }
        for d in Direction
    }
