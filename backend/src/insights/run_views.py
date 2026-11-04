"""``RunMetrics`` and ``RunDiff`` from the Parquet run store.

A stored run's ``metrics.parquet`` holds one row per vehicle trip. Recognised columns (all optional per
row; a missing value is skipped, never replaced by zero):

* ``travelTimeS`` and ``freeFlowTimeS`` (or ``distanceM`` and ``desiredSpeedMps``): delay and travel time
  (``src.metrics.trip_metrics``);
* ``minTtcS`` and ``conflictEvents``: the safety proxy (``src.metrics.trajectory_metrics``);
* ``fuelLiters`` and ``co2Kg``: the emissions estimate.

A group of columns with no usable row gives ``null`` for every value that needs it. The run's manifest
supplies the reproducibility fields of a diff (``seed``, ``configHash``, ``gitCommit``,
``scenarioFingerprint``) and an optional ``ttcThresholdSeconds`` and ``label``.
"""

from __future__ import annotations

import math
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from src.metrics.trajectory_metrics import (
    DEFAULT_TTC_THRESHOLD_S,
    EMISSIONS_LABEL,
    SAFETY_LABEL,
)
from src.metrics.trip_metrics import summarize_trips
from src.runstore import StoredRun

from .numbers import finite

DELAY_DEFINITION = (
    "Time beyond the free-flow travel time of the same trip, per vehicle, never below zero."
)
TRAVEL_DEFINITION = "Time from entering to leaving the network, per vehicle."
EMISSIONS_MODEL = "Speed, idle and acceleration fuel model (generic petrol car)"


def _value(value: Optional[float], unit: str) -> Dict[str, Any]:
    return {"value": value, "unit": unit, "ci": None}


def _column(rows: Sequence[Mapping[str, Any]], key: str) -> List[float]:
    out: List[float] = []
    for r in rows:
        v = finite(r.get(key))
        if v is not None:
            out.append(v)
    return out


def run_metrics(run: StoredRun) -> Dict[str, Any]:
    rows = run.records
    trips = summarize_trips(rows)
    ttc = _column(rows, "minTtcS")
    conflicts = _column(rows, "conflictEvents")
    fuel, co2 = _column(rows, "fuelLiters"), _column(rows, "co2Kg")
    fuel_total = math.fsum(fuel) if fuel else None
    co2_total = math.fsum(co2) if co2 else None
    threshold = (
        finite(run.manifest.get("ttcThresholdSeconds")) or DEFAULT_TTC_THRESHOLD_S
    )
    notes: List[str] = []
    if trips["n"] and trips["lowSample"]:
        notes.append(
            f"Only {trips['n']} completed trips: the 95th percentiles are unreliable."
        )
    if trips["skipped"]:
        notes.append(
            f"{trips['skipped']} rows without a usable travel time or free-flow time were skipped."
        )
    return {
        "runId": run.run_id,
        "vehiclesCompleted": trips["n"] if trips["n"] else None,
        "delay": {
            "mean": _value(trips["meanDelayS"], "s"),
            "p95": _value(trips["p95DelayS"], "s"),
            "definition": DELAY_DEFINITION,
        },
        "travelTime": {
            "mean": _value(trips["meanTravelTimeS"], "s"),
            "p95": _value(trips["p95TravelTimeS"], "s"),
            "definition": TRAVEL_DEFINITION,
        },
        "safety": {
            "minTtc": _value(min(ttc) if ttc else None, "s"),
            "conflicts": _value(math.fsum(conflicts) if conflicts else None, "count"),
            "thresholdSeconds": threshold,
            "definition": SAFETY_LABEL,
        },
        "emissions": {
            "fuel": _value(fuel_total, "L"),
            "co2": _value(co2_total, "kg"),
            "co2PerVehicle": _value(
                co2_total / len(co2) if co2_total is not None else None, "kg"
            ),
            "model": {"name": EMISSIONS_MODEL, "version": None},
            "definition": EMISSIONS_LABEL,
        },
        "notes": notes,
    }


# (metric id, label, unit, lowerIsBetter, value)
_DiffRow = Tuple[str, str, str, bool, Any]


def _diff_rows(m: Mapping[str, Any]) -> List[_DiffRow]:
    return [
        ("mean_delay_s", "Mean delay", "s", True, m["delay"]["mean"]["value"]),
        ("p95_delay_s", "95th percentile delay", "s", True, m["delay"]["p95"]["value"]),
        (
            "mean_travel_time_s",
            "Mean travel time",
            "s",
            True,
            m["travelTime"]["mean"]["value"],
        ),
        (
            "p95_travel_time_s",
            "95th percentile travel time",
            "s",
            True,
            m["travelTime"]["p95"]["value"],
        ),
        ("vehicles_completed", "Vehicles completed", "vehicles", False, m["vehiclesCompleted"]),
        (
            "min_ttc_s",
            "Smallest time-to-collision",
            "s",
            False,
            m["safety"]["minTtc"]["value"],
        ),
        ("conflicts", "Conflicts", "count", True, m["safety"]["conflicts"]["value"]),
        ("fuel_l", "Fuel (estimate)", "L", True, m["emissions"]["fuel"]["value"]),
        ("co2_kg", "CO2 (estimate)", "kg", True, m["emissions"]["co2"]["value"]),
    ]


def _manifest_fields(
    a: Mapping[str, Any], b: Mapping[str, Any]
) -> List[Dict[str, Any]]:
    def seed(m: Mapping[str, Any]) -> Optional[str]:
        v = m.get("seed") if m.get("seed") is not None else m.get("baseSeed")
        return None if v is None else str(v)

    def text(key: str) -> Callable[[Mapping[str, Any]], Optional[str]]:
        return lambda m: None if m.get(key) is None else str(m[key])

    spec: List[Tuple[str, str, Callable[[Mapping[str, Any]], Optional[str]]]] = [
        ("seed", "Seed", seed),
        ("config_hash", "Configuration hash", text("configHash")),
        ("code_version", "Code version", text("gitCommit")),
        ("input_version", "Input version", text("scenarioFingerprint")),
    ]
    out = []
    for field, label, get in spec:
        va, vb = get(a), get(b)
        out.append(
            {
                "field": field,
                "label": label,
                "a": va,
                "b": vb,
                # Two missing values are not a match: nothing was recorded to compare.
                "same": va is not None and va == vb,
            }
        )
    return out


def _ref(run: StoredRun) -> Dict[str, Any]:
    label = run.manifest.get("label")
    created = run.manifest.get("createdAt")
    return {
        "runId": run.run_id,
        "label": label if isinstance(label, str) and label else run.run_id,
        "createdAt": created if isinstance(created, str) else "",
    }


def run_diff(a: StoredRun, b: StoredRun) -> Dict[str, Any]:
    rows_a, rows_b = _diff_rows(run_metrics(a)), _diff_rows(run_metrics(b))
    manifest = _manifest_fields(a.manifest, b.manifest)
    same = {f["field"]: f["same"] for f in manifest}
    metrics = []
    for (mid, label, unit, lower, va), (_, _, _, _, vb) in zip(rows_a, rows_b):
        fa, fb = finite(va), finite(vb)
        delta = fb - fa if fa is not None and fb is not None else None
        fraction = delta / fa if delta is not None and fa else None
        metrics.append(
            {
                "id": mid,
                "label": label,
                "unit": unit,
                "lowerIsBetter": lower,
                "a": fa,
                "b": fb,
                "delta": delta,
                "deltaFraction": fraction,
            }
        )
    return {
        "a": _ref(a),
        "b": _ref(b),
        "sameInputs": bool(same["seed"] and same["config_hash"] and same["input_version"]),
        "manifest": manifest,
        "metrics": metrics,
    }
