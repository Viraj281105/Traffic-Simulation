"""Build the observed-vs-simulated rows from per-seed tallies.

Pure functions over plain dicts (no engine), so they are fast to test and the
same inputs always give the same rows. Simulated values are means over the
seeds; ``simulatedStd`` and ``n`` say how much they varied.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence

from src.calibration.models import ObservationSet
from src.calibration.rating import geh, percent_error, rate


def _stats(values: Sequence[float]) -> Optional[Dict[str, float]]:
    if not values:
        return None
    n = len(values)
    mean = sum(values) / n
    std = math.sqrt(sum((x - mean) ** 2 for x in values) / (n - 1)) if n > 1 else 0.0
    return {"mean": mean, "std": std, "n": n}


def _row(
    kind: str,
    metric: str,
    approach: Optional[str],
    movement: Optional[str],
    vehicle_class: Optional[str],
    observed: float,
    values: Sequence[float],
    unit_geh: bool = False,
    input_fitted: bool = False,
) -> Dict[str, Any]:
    stats = _stats(values)
    row: Dict[str, Any] = {
        "metric": metric,
        "kind": kind,
        "location": {
            "approach": approach,
            "movement": movement,
            "vehicleClass": vehicle_class,
        },
        "observed": round(observed, 4),
        "simulated": None,
        "simulatedStd": None,
        "seedsWithData": 0,
        "absoluteError": None,
        "percentError": None,
        "geh": None,
        "rating": None,
        "inputWasFitted": input_fitted,
    }
    if stats is None:
        row["note"] = "Not compared: no simulated vehicles supplied this measurement."
        return row
    error = stats["mean"] - observed
    pct = percent_error(kind, observed, error)
    row.update(
        simulated=round(stats["mean"], 4),
        simulatedStd=round(stats["std"], 4),
        seedsWithData=int(stats["n"]),
        absoluteError=round(error, 4),
        percentError=None if pct is None else round(pct, 2),
        rating=rate(kind, observed, error),
    )
    if unit_geh:
        row["geh"] = round(geh(stats["mean"], observed), 3)
    if pct is None:
        row["note"] = (
            "Observed value is below the minimum for a percentage; rated on "
            "absolute error only."
        )
    return row


def build_rows(
    obs: ObservationSet,
    tallies: Sequence[Dict[str, Any]],
    strategy: str,
    fitted: Sequence[str],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    # Approach flow: vehicles that left the junction in the measured window.
    for approach, observed in obs.flow_vph().items():
        values = [
            t["flowCount"].get(approach, 0) * 3600.0 / t["measuredSeconds"]
            for t in tallies
            if t["measuredSeconds"] > 0
        ]
        rows.append(
            _row(
                "flow",
                "approachFlow",
                approach,
                None,
                None,
                observed,
                values,
                unit_geh=True,
                input_fitted="demand" in fitted,
            )
        )

    # Turning proportions, over the movements the user supplied.
    for approach, shares in obs.turning_shares().items():
        for move, observed in shares.items():
            values = []
            for t in tallies:
                counts = t["movementCount"].get(approach, {})
                denom = sum(counts.get(m, 0) for m in shares)
                if denom > 0:
                    values.append(counts.get(move, 0) / denom)
            rows.append(
                _row(
                    "turning",
                    "turningShare",
                    approach,
                    move,
                    None,
                    observed,
                    values,
                    input_fitted="turning" in fitted,
                )
            )

    # Vehicle mix: share of all exited vehicles, for the classes supplied.
    for cls, observed in obs.mix_shares().items():
        values = [
            t["classCount"].get(cls, 0) / t["exited"]
            for t in tallies
            if t["exited"] > 0
        ]
        rows.append(
            _row(
                "mix",
                "vehicleClassShare",
                None,
                None,
                cls,
                observed,
                values,
                input_fitted="mix" in fitted,
            )
        )

    # Queues, as the metric collector defines them (vehicles below the wait
    # speed threshold, per approach).
    for q in obs.queues:
        for field, metric, key in (
            ("meanVehicles", "meanQueueLength", "averageQueueLength"),
            ("maxVehicles", "maxQueueLength", "maxQueueLength"),
        ):
            observed_q = getattr(q, field)
            if observed_q is None:
                continue
            values = [
                float(t["metrics"]["approachBreakdown"][q.approach][key])
                for t in tallies
                if key in (t["metrics"]["approachBreakdown"].get(q.approach) or {})
            ]
            rows.append(
                _row("queue", metric, q.approach, None, None, observed_q, values)
            )

    # Travel time: entry onto the approach to leaving the junction.
    for tt in obs.travelTimes:
        if tt.movement is None:
            samples = [
                sum(t["travelTimes"][tt.approach]) / len(t["travelTimes"][tt.approach])
                for t in tallies
                if t["travelTimes"].get(tt.approach)
            ]
        else:
            samples = [
                sum(lst) / len(lst)
                for t in tallies
                for lst in [
                    t["movementTravelTimes"].get(tt.approach, {}).get(tt.movement)
                ]
                if lst
            ]
        rows.append(
            _row(
                "travelTime",
                "meanTravelTime",
                tt.approach,
                tt.movement,
                None,
                tt.meanSeconds,
                samples,
            )
        )

    # Signal timing (signal strategies only).
    if obs.signal is not None and strategy != "roundabout":
        values = [
            float(t["metrics"]["signalTiming"]["averageGreenDuration"])
            for t in tallies
            if isinstance(
                t["metrics"]["signalTiming"].get("averageGreenDuration"), (int, float)
            )
        ]
        rows.append(
            _row(
                "signal",
                "averageGreenDuration",
                None,
                None,
                None,
                obs.signal.averageGreenSeconds,
                values,
            )
        )
    return rows
