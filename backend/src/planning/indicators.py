"""Indicator registry: where each reported quantity comes from.

Every indicator is a metric-key path into the comparison output, with a
status. ``unavailable`` is a first-class state (never zero, never a claim):
if a key is not present in the comparison output -- a V1.6 safety measure not
yet wired, an emissions model that does not exist -- the indicator says so.
Wiring a new V1.6 key is a one-line registry edit.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from src.study.validation import _calculate_stats

# direction: which way is favourable for a planner, used only to word a
# per-metric reading; "neutral" never gets a better/worse word.
LOWER, HIGHER, NEUTRAL = "lower_is_better", "higher_is_better", "neutral"


@dataclass(frozen=True)
class Indicator:
    group: str
    key: str
    label: str
    unit: str
    source: str  # "stat": comparison controls stats | "seed": per-seed metric
    path: str
    direction: str = NEUTRAL


@dataclass(frozen=True)
class Unavailable:
    group: str
    key: str
    label: str
    reason: str


REGISTRY: List[Indicator] = [
    Indicator(
        "performance",
        "averageDelay",
        "Mean delay",
        "s/vehicle",
        "stat",
        "averageDelay",
        LOWER,
    ),
    Indicator(
        "performance",
        "averageWaitTime",
        "Mean wait time",
        "s/vehicle",
        "stat",
        "averageWaitTime",
        LOWER,
    ),
    Indicator(
        "performance",
        "throughput",
        "Vehicles served",
        "vehicles",
        "stat",
        "throughput",
        HIGHER,
    ),
    Indicator(
        "performance",
        "averageQueueLength",
        "Mean queue length",
        "vehicles",
        "stat",
        "averageQueueLength",
        LOWER,
    ),
    Indicator(
        "performance",
        "maxQueueLength",
        "Max queue length",
        "vehicles",
        "stat",
        "maxQueueLength",
        LOWER,
    ),
    Indicator(
        "performance",
        "averageStopsPerVehicle",
        "Stops per vehicle",
        "stops",
        "stat",
        "averageStopsPerVehicle",
        LOWER,
    ),
    Indicator(
        "reliability",
        "travelTimeReliability",
        "Travel-time reliability",
        "index",
        "stat",
        "travelTimeReliability",
    ),
    Indicator(
        "safety",
        "collisionCount",
        "Collisions",
        "count",
        "seed",
        "collisionCount",
        LOWER,
    ),
    # Exploratory conflict proxies: present only if the comparison output
    # carries them per seed (V1.6); otherwise reported as unavailable.
    Indicator("safety", "minTTC", "Minimum time-to-collision", "s", "seed", "minTTC"),
    Indicator(
        "safety",
        "ttcEventCount",
        "Time-to-collision events",
        "count",
        "seed",
        "ttcEventCount",
        LOWER,
    ),
    # Environmental proxies: stop-and-go and idling exposure, not emissions.
    Indicator(
        "environmental",
        "averageStopsPerVehicle",
        "Stops per vehicle (stop-and-go proxy)",
        "stops",
        "stat",
        "averageStopsPerVehicle",
        LOWER,
    ),
    Indicator(
        "environmental",
        "averageDelay",
        "Mean delay (idling-exposure proxy)",
        "s/vehicle",
        "stat",
        "averageDelay",
        LOWER,
    ),
]

UNAVAILABLE: List[Unavailable] = [
    Unavailable(
        "environmental",
        "fuelConsumption",
        "Fuel consumption",
        "No emissions model in this build",
    ),
    Unavailable(
        "environmental",
        "co2Emissions",
        "CO2 emissions",
        "No emissions model in this build",
    ),
]

SIGNAL_KEYS = (
    "phaseChanges",
    "averageGreenDuration",
    "unusedGreenSeconds",
    "greenUtilisation",
)

GROUP_ORDER = ("performance", "safety", "environmental", "reliability")
GROUP_STATUS = {
    "performance": "available",
    "reliability": "available",
    "safety": "exploratory",
    "environmental": "proxy",
}
GROUP_NOTE = {
    "safety": "Exploratory: simulated collisions/conflicts are rare-event proxies, "
    "not validated crash predictions.",
    "environmental": "Proxies only (stop-and-go and idling exposure). No emissions "
    "or fuel model exists in this build.",
}


def _block(
    mean: float, std: float, lo: float, hi: float, n: int, half: Optional[float]
) -> Dict[str, Any]:
    return {
        "mean": mean,
        "std": std,
        "min": lo,
        "max": hi,
        "n": n,
        "ciHalfWidth": half,
        "ciLow": round(mean - half, 2) if half is not None else None,
        "ciHigh": round(mean + half, 2) if half is not None else None,
    }


def summarise(values: Sequence[float], confidence: float) -> Dict[str, Any]:
    """Mean, spread and a t-interval for the mean (study.validation stats)."""
    s = _calculate_stats(list(values), confidence)
    n = len(values)
    return _block(
        s["mean"], s["std"], s["min"], s["max"], n, s["ci"] if n > 1 else None
    )


def _seed_values(
    rows: Sequence[Dict[str, Any]], strategy: str, key: str
) -> List[float]:
    out: List[float] = []
    for row in rows:
        v = (row.get(strategy) or {}).get(key)
        if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v):
            out.append(float(v))
    return out


def indicator_values(
    indicator: Indicator,
    stats: Dict[str, Any],
    seed_rows: Sequence[Dict[str, Any]],
    strategy: str,
    confidence: float,
) -> Optional[Dict[str, Any]]:
    """The indicator's summary, or None when the output does not carry it."""
    if indicator.source == "stat":
        s = stats.get(indicator.path)
        if not isinstance(s, dict):
            return None
        n = int(s.get("ciDegreesOfFreedom", 0)) + 1
        return _block(
            s["mean"], s["std"], s["min"], s["max"], n, s.get("ci") if n > 1 else None
        )
    values = _seed_values(seed_rows, strategy, indicator.path)
    return summarise(values, confidence) if values else None


def build_groups(
    comparison_row: Dict[str, Any],
    seed_rows: Sequence[Dict[str, Any]],
    strategy: str,
    confidence: float,
    groups: Sequence[str],
) -> Dict[str, Any]:
    """performance / safety / environmental / reliability for one alt x scale."""
    stats = (comparison_row.get("controls") or {}).get(strategy) or {}
    out: Dict[str, Any] = {}
    for group in GROUP_ORDER:
        if group not in groups:
            continue
        values: Dict[str, Any] = {}
        missing: List[Dict[str, str]] = []
        for ind in (i for i in REGISTRY if i.group == group):
            found = indicator_values(ind, stats, seed_rows, strategy, confidence)
            if found is None:
                missing.append(
                    {
                        "key": ind.key,
                        "label": ind.label,
                        "reason": "not reported by the comparison output",
                    }
                )
            else:
                values[ind.key] = {
                    **found,
                    "label": ind.label,
                    "unit": ind.unit,
                    "direction": ind.direction,
                }
        missing.extend(
            {"key": u.key, "label": u.label, "reason": u.reason}
            for u in UNAVAILABLE
            if u.group == group
        )
        block: Dict[str, Any] = {
            "status": GROUP_STATUS[group] if values else "unavailable",
            "values": values,
            "unavailable": missing,
        }
        if group in GROUP_NOTE:
            block["note"] = GROUP_NOTE[group]
        if group == "reliability":
            delay_ind = next(i for i in REGISTRY if i.key == "averageDelay")
            delay = indicator_values(delay_ind, stats, seed_rows, strategy, confidence)
            if delay:
                mean, std = delay["mean"], delay["std"]
                block["delayAcrossSeeds"] = {
                    "mean": mean,
                    "std": std,
                    "coefficientOfVariation": round(std / mean, 3) if mean else None,
                    "ciLow": delay["ciLow"],
                    "ciHigh": delay["ciHigh"],
                }
        out[group] = block
    return out


def per_approach(seed_rows: Sequence[Dict[str, Any]], strategy: str) -> Dict[str, Any]:
    """Mean over seeds of each approach's exited / delay / queue figures."""
    acc: Dict[str, Dict[str, List[float]]] = {}
    for row in seed_rows:
        breakdown = (row.get(strategy) or {}).get("approachBreakdown") or {}
        for direction, d in breakdown.items():
            slot = acc.setdefault(direction, {})
            for key in (
                "exited",
                "averageDelay",
                "averageQueueLength",
                "maxQueueLength",
            ):
                v = d.get(key)
                if isinstance(v, (int, float)):
                    slot.setdefault(key, []).append(float(v))
    return {
        direction: {
            key: round(max(v), 2)
            if key == "maxQueueLength"
            else round(sum(v) / len(v), 2)
            for key, v in sorted(slot.items())
        }
        for direction, slot in sorted(acc.items())
    }


def per_vehicle_type(
    seed_rows: Sequence[Dict[str, Any]], strategy: str
) -> Dict[str, Any]:
    acc: Dict[str, Dict[str, List[float]]] = {}
    for row in seed_rows:
        breakdown = (row.get(strategy) or {}).get("vehicleTypeBreakdown") or {}
        for vtype, d in breakdown.items():
            slot = acc.setdefault(vtype, {})
            for key in ("exited", "share", "averageDelay"):
                v = d.get(key)
                if isinstance(v, (int, float)):
                    slot.setdefault(key, []).append(float(v))
    return {
        vtype: {key: round(sum(v) / len(v), 3) for key, v in sorted(slot.items())}
        for vtype, slot in sorted(acc.items())
    }


def signal_timing(
    comparison_row: Dict[str, Any], strategy: str
) -> Optional[Dict[str, Any]]:
    """Mean/std of green-time measures; None for a roundabout."""
    stats = (comparison_row.get("controls") or {}).get(strategy) or {}
    found = {
        k: {"mean": stats[k]["mean"], "std": stats[k]["std"]}
        for k in SIGNAL_KEYS
        if isinstance(stats.get(k), dict)
    }
    return found or None
