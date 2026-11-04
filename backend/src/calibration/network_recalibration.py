"""Continuous recalibration helper (F14, W43).

Given a rolling window of new counts, re-run the network calibration
warm-started from the previous parameters and report how far they drifted.
Stateless: the caller keeps the previous parameter set (the report's
``parameters.fitted``) and the count history.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence

from src.calibration.network_counts import CountSet
from src.calibration.network_fit import (
    FitOptions,
    SimSettings,
    calibrate_network,
)
from src.networks.graph import RoadGraph
from src.networks.network_sim import Flow

DEFAULT_DRIFT_THRESHOLD = 0.15  # relative change of any parameter that raises a flag


def drift_report(
    previous: Mapping[str, float],
    current: Mapping[str, float],
    threshold: float = DEFAULT_DRIFT_THRESHOLD,
) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    for name in sorted(set(previous) | set(current)):
        old, new = previous.get(name), current.get(name)
        if old is None or new is None:
            rows.append(
                {
                    "name": name,
                    "previous": old,
                    "current": new,
                    "relativeChange": None,
                    "flag": True,
                }
            )
            continue
        change = (new - old) / old if old else None
        rows.append(
            {
                "name": name,
                "previous": old,
                "current": new,
                "relativeChange": round(change, 6) if change is not None else None,
                "flag": change is None or abs(change) > threshold,
            }
        )
    changes = [
        abs(r["relativeChange"]) for r in rows if r["relativeChange"] is not None
    ]
    return {
        "threshold": threshold,
        "maxAbsRelativeChange": round(max(changes), 6) if changes else None,
        "flagged": sorted(r["name"] for r in rows if r["flag"]),
        "drifted": any(r["flag"] for r in rows),
        "parameters": rows,
    }


def recalibrate(
    graph: RoadGraph,
    flows: Sequence[Flow],
    counts: CountSet,
    previous: Mapping[str, float],
    *,
    window_intervals: Optional[int] = None,
    options: FitOptions = FitOptions(budget=80, initial_step=0.1),
    sim: SimSettings = SimSettings(),
    drift_threshold: float = DEFAULT_DRIFT_THRESHOLD,
) -> Dict[str, Any]:
    """Calibrate on the last ``window_intervals`` of ``counts`` (all of it when
    None), starting from ``previous`` parameters. The report is the normal
    calibration report plus ``recalibration``: window, the previous parameters'
    error on the new window ("before" is that), and the drift."""
    window = counts.window(window_intervals) if window_intervals else counts
    report = calibrate_network(graph, flows, window, options, sim, start=previous)
    report["recalibration"] = {
        "windowIntervals": len(window.interval_starts()),
        "windowFirstIntervalStart": window.provenance()["firstIntervalStart"],
        "windowLastIntervalStart": window.provenance()["lastIntervalStart"],
        "warmStartFrom": {k: round(v, 6) for k, v in sorted(previous.items())},
        "previousParametersGCalPassed": report["before"]["gCal"]["passed"],
        "drift": drift_report(
            report["parameters"]["start"],
            report["parameters"]["fitted"],
            drift_threshold,
        ),
    }
    return report
