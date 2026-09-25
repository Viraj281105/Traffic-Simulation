from typing import Dict, List, Optional

from src.vehicles.vehicle import Vehicle


def calculate_directional_fairness(
    exited_vehicles: List[Vehicle],
    warmup_baseline_wait: Optional[Dict[str, float]] = None,
) -> float:
    """Computes Jain's Fairness Index across wait times of the 4 approaches.

    ``warmup_baseline_wait`` maps a vehicle id to the wait time it had already
    accumulated when warm-up ended. It is subtracted, exactly as
    ``averageWaitTime`` does, so a vehicle that was already active at the
    warm-up boundary does not contribute its pre-warm-up waiting to the
    post-warm-up index (both figures then describe the same window).

    Returns 1.0 if all wait times are zero.
    """
    baseline = warmup_baseline_wait or {}
    if not exited_vehicles:
        return 1.0

    # Group wait times by direction
    from typing import Dict

    waits: Dict[str, List[float]] = {"north": [], "south": [], "east": [], "west": []}
    # Lane IDs use single-letter direction prefixes (e.g. "n_in_0"); map them to
    # the full direction names used as keys above (same convention as
    # queue_length.py / idle_loss.py).
    mapping = {"n": "north", "s": "south", "e": "east", "w": "west"}

    for v in exited_vehicles:
        # Get start direction from route
        if v.route:
            lane_id = v.route[0].lane_id.lower()
            dir_char = lane_id.split("_")[0]
            direction = mapping.get(dir_char)
            if direction in waits:
                waits[direction].append(
                    max(0.0, v.wait_time - baseline.get(v.vehicle_id, 0.0))
                )

    # Average wait time per approach. An approach with no vehicles has no
    # average wait at all and is left out, with n adjusted to match
    # (docs/architecture/07-metric-contract.md §5.1 edge cases). It used to be
    # entered as a 0.0 s average, so a scenario with traffic on one approach
    # only scored J = 0.25 — "maximally unfair" — for a junction serving its
    # only approach perfectly evenly.
    x = [
        sum(waits[d]) / len(waits[d])
        for d in ["north", "south", "east", "west"]
        if waits[d]
    ]
    if not x:
        return 1.0

    sum_x = sum(x)
    if sum_x <= 0:
        return 1.0

    sum_sq_x = sum(val**2 for val in x)
    n = len(x)
    return float((sum_x**2) / (n * sum_sq_x))
