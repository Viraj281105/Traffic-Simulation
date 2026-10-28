"""Deterministic fallback answers when Groq is unavailable.

Every public function here produces a response object of the same shape as the
LLM path so the router can return either without branching.  Nothing here
fabricates metrics; every number comes from the metrics dict passed in.
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Dict, List, Optional

from src.ai.schemas import ChatResponse, ConfigPatch, SummaryResponse

# ── Helpers ──────────────────────────────────────────────────────────────────


def _v(metrics: Dict[str, Any], key: str) -> Optional[float]:
    """Return a metric value as float, or None."""
    val = metrics.get(key)
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _fmt(value: Optional[float], unit: str = "", decimals: int = 1) -> str:
    if value is None:
        return "not yet measured"
    return f"{value:.{decimals}f}{(' ' + unit) if unit else ''}"


# ── Summary fallback ─────────────────────────────────────────────────────────


def summary_fallback(
    metrics: Dict[str, Any],
    config: Dict[str, Any],
    geometry: str,
    elapsed: Optional[float] = None,
) -> SummaryResponse:
    delay = _v(metrics, "averageDelay")
    throughput = _v(metrics, "throughput")
    max_q = _v(metrics, "maxQueueLength")
    collisions = _v(metrics, "collisionCount")
    active = _v(metrics, "activeVehicleCount")

    if geometry == "comparison":
        geom_label = "comparison (Signal vs Roundabout)"
    elif geometry == "roundabout":
        geom_label = "roundabout"
    else:
        geom_label = "traffic signal"
    elapsed_str = f" after {elapsed:.0f} s" if elapsed else ""

    summary_parts = []
    if delay is not None:
        summary_parts.append(f"avg delay {_fmt(delay, 's')}")
    if throughput is not None:
        summary_parts.append(f"{throughput:.0f} vehicles served")
    if max_q is not None:
        summary_parts.append(f"max queue {max_q:.0f} veh")

    summary = (
        f"{geom_label.capitalize()} run{elapsed_str}: "
        + (
            ", ".join(summary_parts)
            if summary_parts
            else "comparative metrics recorded"
        )
        + "."
    )

    bullets: List[str] = []
    if delay is not None:
        bullets.append(f"Average delay: {_fmt(delay, 's')} per driver.")
    if throughput is not None:
        bullets.append(f"Vehicles served (after warm-up): {throughput:.0f}.")
    if max_q is not None:
        bullets.append(f"Longest queue seen: {max_q:.0f} vehicle(s).")
    fairness = _v(metrics, "directionalFairnessIndex")
    if fairness is not None:
        bullets.append(
            f"Directional fairness index: {fairness:.2f} (1.0 = perfectly even)."
        )
    if not bullets:
        bullets.append("No metrics are available yet — start or complete a run first.")

    warnings: List[str] = []
    if collisions and collisions > 0:
        warnings.append(
            f"The model recorded {collisions:.0f} vehicle overlap(s). "
            "This is a model-integrity signal, not a crash prediction."
        )
    if active and throughput and active > throughput * 2:
        warnings.append(
            "Many vehicles are still in the network; the junction may be oversaturated."
        )

    return SummaryResponse(
        summary=summary[:600],
        bullets=bullets,
        warnings=warnings,
        fallback=True,
    )


# ── Chat fallback ─────────────────────────────────────────────────────────────

_KEYWORD_ANSWERS: List[tuple[str, str, str]] = [
    (
        r"delay|wait|time lost",
        "averageDelay",
        "Average delay (time lost per driver vs driving through an empty junction)",
    ),
    (
        r"throughput|served|through|exited",
        "throughput",
        "Throughput (vehicles that exited after the warm-up)",
    ),
    (
        r"queue|backlog|congestion",
        "maxQueueLength",
        "Maximum queue length seen on any approach",
    ),
    (
        r"fair|balance|even|direction",
        "directionalFairnessIndex",
        "Directional fairness index (Jain's, 1.0 = perfectly even across approaches)",
    ),
    (
        r"collision|overlap|crash",
        "collisionCount",
        "Collision count (vehicle overlaps, a model-integrity signal)",
    ),
]

# Separate tuples to avoid unpacking issues
_KEYWORD_PATTERNS = [
    (
        r"delay|wait|time lost",
        "averageDelay",
        "Average delay (time lost per driver vs driving through an empty junction)",
    ),
    (
        r"throughput|served|through|exited",
        "throughput",
        "Throughput (vehicles that exited after the warm-up)",
    ),
    (
        r"queue|backlog|congestion",
        "maxQueueLength",
        "Maximum queue length seen on any approach",
    ),
    (
        r"fair|balance|even|direction",
        "directionalFairnessIndex",
        "Directional fairness index (Jain's, 1.0 = perfectly even across approaches)",
    ),
    (
        r"collision|overlap|crash",
        "collisionCount",
        "Collision count (vehicle overlaps, a model-integrity signal)",
    ),
]


def chat_fallback(
    question: str,
    metrics: Dict[str, Any],
    config: Dict[str, Any],
) -> ChatResponse:
    q_lower = question.lower()

    for pattern, key, label in _KEYWORD_PATTERNS:
        if re.search(pattern, q_lower):
            val = _v(metrics, key)
            if val is not None:
                unit = "s" if "delay" in key.lower() or "wait" in key.lower() else ""
                answer = (
                    f"{label}: {_fmt(val, unit)}. "
                    "(AI is temporarily unavailable; this is directly from the simulation metrics.)"
                )
            else:
                answer = (
                    f"{label} has not been measured yet — "
                    "start or complete a run first. "
                    "(AI is temporarily unavailable.)"
                )
            return ChatResponse(answer=answer, fallback=True)

    # Generic fallback
    lines = ["AI is temporarily unavailable. Here is a quick summary from the metrics:"]
    for key, label, unit in [
        ("averageDelay", "Average delay", "s"),
        ("throughput", "Throughput", "veh"),
        ("maxQueueLength", "Max queue", "veh"),
    ]:
        val = _v(metrics, key)
        if val is not None:
            lines.append(f"• {label}: {_fmt(val, unit)}")
    if len(lines) == 1:
        lines.append("No metrics available yet.")

    return ChatResponse(answer=" ".join(lines), fallback=True)


# ── Config-patch fallback ─────────────────────────────────────────────────────

# Keyword → config patch mappings for the most common Indian / general requests.
_PATCH_RULES: List[tuple[str, Dict[str, Any], List[str], List[str]]] = [
    (
        r"pune|mumbai|delhi|bengaluru|bangalore|peak.?hour|rush.?hour",
        {
            "arrivalRate": 0.85,
            "unstructuredTraffic": True,
            "aggressiveTwoWheelers": True,
            "duration": 300,
        },
        [
            "Set arrival rate to 0.85 veh/s (≈3 060 veh/h) — typical Indian metro peak-hour.",
            "Enabled unstructured traffic and aggressive two-wheelers.",
        ],
        ["High demand may cause queue growth throughout the run."],
    ),
    (
        r"aggressive.?driver|aggressive",
        {
            "aggressiveTwoWheelers": True,
            "unstructuredTraffic": True,
        },
        ["Enabled aggressive two-wheelers and unstructured traffic patterns."],
        [],
    ),
    (
        r"light.?traffic|low.?demand|quiet|off.?peak",
        {
            "arrivalRate": 0.15,
            "unstructuredTraffic": False,
            "aggressiveTwoWheelers": False,
        },
        ["Set arrival rate to 0.15 veh/s (≈540 veh/h) — light off-peak traffic."],
        [],
    ),
    (
        r"heavy.?traffic|busy|high.?demand|congested",
        {"arrivalRate": 0.9},
        ["Set arrival rate to 0.9 veh/s (≈3 240 veh/h) — heavy demand."],
        ["Queue lengths may grow continuously at this demand level."],
    ),
    (
        r"longer.?run|more.?time|extend",
        {"duration": 600},
        ["Extended simulation duration to 600 s (10 minutes) for steadier statistics."],
        [],
    ),
    (
        r"short.?run|quick|fast",
        {"duration": 120},
        ["Set simulation duration to 120 s — a quick preview."],
        ["Short runs produce less stable statistics."],
    ),
    (
        r"adaptive.?signal|adaptive",
        {"signalControl": "adaptive"},
        ["Switched signal control to adaptive (vehicle-actuated)."],
        [],
    ),
    (
        r"fixed.?time|fixed",
        {"signalControl": "fixed_time"},
        ["Switched signal control to fixed-time."],
        [],
    ),
    (
        r"mixed.?traffic|vehicle.?mix|bus|truck",
        {
            "vehicleMix": {
                "car": 0.6,
                "motorcycle": 0.2,
                "bus": 0.1,
                "truck": 0.05,
                "suv": 0.05,
            }
        },
        [
            "Applied a mixed-traffic vehicle mix (60% cars, 20% motorcycles, "
            "10% buses, 5% trucks, 5% SUVs)."
        ],
        [
            "Mixed traffic has not been calibrated against real observations; results are indicative."
        ],
    ),
]


def patch_fallback(
    instruction: str,
    current_config: Dict[str, Any],
) -> ConfigPatch:
    instr_lower = instruction.lower()

    for pattern, patch_dict, assumptions, warnings in _PATCH_RULES:
        if re.search(pattern, instr_lower):
            merged = deepcopy(current_config)
            merged.update(patch_dict)
            return ConfigPatch(
                patch=patch_dict,
                merged=merged,
                assumptions=assumptions,
                warnings=warnings
                + [
                    "AI is temporarily unavailable; this patch was generated by rule-based fallback."
                ],
                clarification=None,
                fallback=True,
            )

    # No rule matched — ask for clarification
    return ConfigPatch(
        patch={},
        merged=deepcopy(current_config),
        assumptions=[],
        warnings=["AI is temporarily unavailable."],
        clarification=(
            "AI is temporarily unavailable and your instruction did not match any "
            "known pattern. Please try again shortly, or use the Scenario settings "
            "panel to adjust the configuration manually."
        ),
        fallback=True,
    )
