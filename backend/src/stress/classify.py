"""Failure classification of one simulation run (stress-v1 rules).

Rules are deliberately simple, stated, and applied to the run's own metrics; a run can carry several
failures. Thresholds are assumptions of this lab, not engineering standards.
"""

from __future__ import annotations

from typing import Any, Dict, List

FAILURES = (
    "collision",
    "gridlock",
    "vehicle_limit",
    "starvation",
    "excessive_queue",
    "spillback",
)

EXCESSIVE_QUEUE_VEHICLES = 20  # longest queue seen on any approach
STARVATION_FAIRNESS = 0.3  # Jain's directional fairness index below this
VEHICLE_SPACING_M = 7.5  # stopped-vehicle footprint used to turn a queue into metres
GRIDLOCK_MIN_THROUGHPUT_SHARE = 0.05  # vehicles that finished / vehicles spawned


def classify(metrics: Dict[str, Any], approach_length_m: float = 200.0) -> List[str]:
    found: List[str] = []
    spawned = float(metrics.get("totalVehiclesSpawned") or 0)
    throughput = float(metrics.get("throughput") or 0)
    max_queue = float(metrics.get("maxQueueLength") or 0)
    if (metrics.get("collisionCount") or 0) > 0:
        found.append("collision")
    if spawned >= 10 and throughput / spawned < GRIDLOCK_MIN_THROUGHPUT_SHARE:
        found.append("gridlock")
    if metrics.get("vehicleLimitReached"):
        found.append("vehicle_limit")
    fairness = metrics.get("directionalFairnessIndex")
    if (
        isinstance(fairness, (int, float))
        and not isinstance(fairness, bool)
        and throughput > 0
        and fairness < STARVATION_FAIRNESS
    ):
        found.append("starvation")
    if max_queue >= EXCESSIVE_QUEUE_VEHICLES:
        found.append("excessive_queue")
    if max_queue * VEHICLE_SPACING_M >= approach_length_m:
        found.append("spillback")
    return found


def rules() -> Dict[str, str]:
    return {
        "collision": "any collision in the run",
        "gridlock": f"fewer than {GRIDLOCK_MIN_THROUGHPUT_SHARE:.0%} of spawned vehicles finished (at least 10 spawned)",
        "vehicle_limit": "the run hit the engine's vehicle limit",
        "starvation": f"directional fairness index below {STARVATION_FAIRNESS}",
        "excessive_queue": f"a queue of {EXCESSIVE_QUEUE_VEHICLES} or more vehicles on some approach",
        "spillback": f"the longest queue ({VEHICLE_SPACING_M} m per vehicle) reached the approach length",
    }
