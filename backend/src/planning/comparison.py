"""Paired alternative-vs-baseline comparison over shared seeds.

Mean delay reuses ``study.control_comparison._paired_delay`` (the V1.3 rule:
Student-t interval on per-seed differences, the shared tie tolerance). The
other measures use the same rule with their own absolute tolerance. Readings
are per metric and per demand scale: ``better`` / ``worse`` mean the interval
excludes zero *and* the gap exceeds the tie tolerance; ``tie`` means the means
are within it; otherwise ``inconclusive``. No overall winner is ever computed.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence

from src.planning.indicators import HIGHER, LOWER
from src.study.control_comparison import _paired_delay
from src.study.tolerances import tie_tolerance
from src.study.validation import _t_critical

# key, label, direction, absolute tie tolerance (in the metric's own unit)
COMPARED = (
    ("averageDelay", "Mean delay", LOWER, None),  # None -> study.tolerances rule
    ("throughput", "Vehicles served", HIGHER, 2.0),
    ("averageQueueLength", "Mean queue length", LOWER, 0.5),
    ("collisionCount", "Collisions", LOWER, 0.5),
)


def _fmt(x: Optional[float]) -> Optional[float]:
    return round(x, 2) if x is not None and math.isfinite(x) else None


def paired_metric(
    key: str,
    direction: str,
    abs_tol: Optional[float],
    alt: Sequence[float],
    base: Sequence[float],
    confidence: float,
) -> Dict[str, Any]:
    n = min(len(alt), len(base))
    if n == 0:
        return {
            "metric": key,
            "n": 0,
            "verdict": "unavailable",
            "reading": "unavailable",
        }
    a, b = list(alt)[:n], list(base)[:n]
    mean_a, mean_b = sum(a) / n, sum(b) / n
    if key == "averageDelay":
        paired = _paired_delay(a, b, confidence)
        delta, lo, hi = paired["meanDifference"], paired["ciLow"], paired["ciHigh"]
        reading = paired["reading"]  # lower | higher | tie | inconclusive
    else:
        diffs = [x - y for x, y in zip(a, b)]
        delta = sum(diffs) / n
        if n > 1:
            sd = math.sqrt(sum((d - delta) ** 2 for d in diffs) / (n - 1))
            half = _t_critical(n - 1, confidence) * sd / math.sqrt(n)
            lo, hi = delta - half, delta + half
        else:
            lo = hi = None
        gap = abs(mean_a - mean_b)
        larger = max(abs(mean_a), abs(mean_b))
        tied = gap <= (abs_tol or 0.0) + 1e-9 or (
            larger > 0 and gap / larger <= tie_tolerance()["relative"] + 1e-9
        )
        if tied:
            reading = "tie"
        elif lo is not None and (hi < 0 or lo > 0):
            reading = "lower" if delta < 0 else "higher"
        else:
            reading = "inconclusive"
    if reading in ("tie", "inconclusive"):
        verdict = reading
    else:
        favourable = (reading == "lower") == (direction == LOWER)
        verdict = "better" if favourable else "worse"
    return {
        "metric": key,
        "direction": direction,
        "baselineMean": _fmt(mean_b),
        "alternativeMean": _fmt(mean_a),
        "delta": _fmt(delta),
        "deltaPct": _fmt(100.0 * (mean_a - mean_b) / mean_b) if mean_b else None,
        "ciLow": _fmt(lo),
        "ciHigh": _fmt(hi),
        "n": n,
        "reading": reading,
        "verdict": verdict,
    }


def vs_baseline(
    rows: List[Dict[str, Any]],
    baseline_id: str,
    confidence: float,
) -> List[Dict[str, Any]]:
    """``rows`` are result rows ({alternativeId, demandScale, seriesBySeed}).

    ``seriesBySeed[metric]`` is a list of per-seed values in seed order.
    """
    index = {(r["alternativeId"], r["demandScale"]): r for r in rows}
    out: List[Dict[str, Any]] = []
    for r in rows:
        if r["alternativeId"] == baseline_id:
            continue
        base = index.get((baseline_id, r["demandScale"]))
        if base is None:
            continue
        for key, _label, direction, abs_tol in COMPARED:
            cmp_ = paired_metric(
                key,
                direction,
                abs_tol,
                r["seriesBySeed"].get(key, []),
                base["seriesBySeed"].get(key, []),
                confidence,
            )
            out.append(
                {
                    "alternativeId": r["alternativeId"],
                    "baselineId": baseline_id,
                    "demandScale": r["demandScale"],
                    **cmp_,
                }
            )
    return out
