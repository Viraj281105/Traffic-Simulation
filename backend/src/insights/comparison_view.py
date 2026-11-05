"""``ComparisonResult``: "does A beat B" for one experiment, from per-seed paired values.

Source: ``experiments/<id>/paired.json`` (format ``urbanflow-paired-seeds`` v1)::

    {"format": "urbanflow-paired-seeds", "version": 1,
     "primaryMetric": "mean_delay_s", "baseline": "fixed",
     "metrics": {"mean_delay_s": {"label": "Mean delay", "unit": "s", "lowerIsBetter": true}},
     "alternatives": {"fixed": {"label": "Fixed time", "seeds": [1, 2, 3],
                                "values": {"mean_delay_s": [41.2, 39.8, 44.0]}}, ...},
     "metricsRunId": "optional run id in the run store, used by the report"}

A and B are paired by seed (only seeds present in both count). The interval, p-value and direction come from
``src.uncertainty.comparison.compare_paired`` (paired t); the eligibility label is the experiment's own
(``analysis.eligibility.class``), so a comparison without a finished experiment is not available.
Defaults: A is the baseline, B the alternative with the best mean on the metric.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Mapping, Optional, Tuple

from src.uncertainty.comparison import DEFAULT_CONFIDENCE, compare_paired

from .numbers import finite_list

PAIRED_FORMAT = "urbanflow-paired-seeds"
ELIGIBILITY = ("eligible", "indicative", "exploratory")


def _metric_info(doc: Mapping[str, Any], metric_id: str) -> Optional[Dict[str, Any]]:
    info = (doc.get("metrics") or {}).get(metric_id)
    if not isinstance(info, dict):
        return None
    label, unit = info.get("label"), info.get("unit")
    lower = info.get("lowerIsBetter")
    if (
        not isinstance(label, str)
        or not isinstance(unit, str)
        or not isinstance(lower, bool)
    ):
        return None
    return {"id": metric_id, "label": label, "unit": unit, "lowerIsBetter": lower}


def _series(
    doc: Mapping[str, Any], alt: str, metric_id: str
) -> Optional[Dict[int, float]]:
    entry = (doc.get("alternatives") or {}).get(alt)
    if not isinstance(entry, dict):
        return None
    seeds = entry.get("seeds")
    values = finite_list((entry.get("values") or {}).get(metric_id))
    if not isinstance(seeds, list) or values is None or len(seeds) != len(values):
        return None
    if not all(isinstance(s, int) and not isinstance(s, bool) for s in seeds):
        return None
    if len(set(seeds)) != len(seeds):
        return None
    return dict(zip(seeds, values))


def alternative_label(doc: Mapping[str, Any], alt: str) -> str:
    entry = (doc.get("alternatives") or {}).get(alt)
    label = entry.get("label") if isinstance(entry, dict) else None
    return label if isinstance(label, str) and label else alt


def choose_pair(
    doc: Mapping[str, Any], a: Optional[str], b: Optional[str], metric: Dict[str, Any]
) -> Optional[Tuple[str, str]]:
    alts = doc.get("alternatives")
    if not isinstance(alts, dict) or len(alts) < 2:
        return None
    names = list(alts)
    baseline = doc.get("baseline")
    a_id: str = a or (
        baseline if isinstance(baseline, str) and baseline in alts else names[0]
    )
    if a_id not in alts:
        return None
    if b is None:
        means: List[Tuple[float, str]] = []
        for name in names:
            if name == a_id:
                continue
            s = _series(doc, name, metric["id"])
            if s:
                means.append((math.fsum(s.values()) / len(s), name))
        if not means:
            return None
        means.sort(key=lambda m: m[0] if metric["lowerIsBetter"] else -m[0])
        b_id = means[0][1]
    else:
        b_id = b
    if b_id not in alts or b_id == a_id:
        return None
    return a_id, b_id


def _verdict(direction: str, lower_is_better: bool) -> str:
    if direction == "none":
        return "no_clear_difference"
    a_wins = (direction == "a_lower") == lower_is_better
    return "a_better" if a_wins else "b_better"


def build_comparison(
    experiment_id: str,
    doc: Mapping[str, Any],
    eligibility: Optional[str],
    a: Optional[str] = None,
    b: Optional[str] = None,
    metric: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """The contract object, or None when this comparison cannot be made from the stored data."""
    if doc.get("format") != PAIRED_FORMAT or eligibility not in ELIGIBILITY:
        return None
    metric_id = metric or doc.get("primaryMetric")
    if not isinstance(metric_id, str):
        return None
    info = _metric_info(doc, metric_id)
    if info is None:
        return None
    pair = choose_pair(doc, a, b, info)
    if pair is None:
        return None
    a_id, b_id = pair
    sa, sb = _series(doc, a_id, metric_id), _series(doc, b_id, metric_id)
    if sa is None or sb is None:
        return None
    shared = sorted(set(sa) & set(sb))
    if len(shared) < 2:
        return None
    xs, ys = [sa[s] for s in shared], [sb[s] for s in shared]
    result = compare_paired(xs, ys, method="paired_t", confidence=DEFAULT_CONFIDENCE)
    diffs = [x - y for x, y in zip(xs, ys)]
    mean_d = math.fsum(diffs) / len(diffs)
    sd = math.sqrt(math.fsum((d - mean_d) ** 2 for d in diffs) / (len(diffs) - 1))
    effect = {"name": "Cohen's d (paired)", "value": mean_d / sd} if sd > 0.0 else None
    pct = round(result.confidence * 100)
    return {
        "experimentId": experiment_id,
        "metric": info,
        "a": {"id": a_id, "label": alternative_label(doc, a_id)},
        "b": {"id": b_id, "label": alternative_label(doc, b_id)},
        "pairs": result.n_pairs,
        "meanDifference": result.difference,
        "ci": [result.ci_lower, result.ci_upper],
        "confidenceLevel": result.confidence,
        "pValue": result.p_value,
        "method": {
            "test": "Paired t-test",
            "interval": f"Student t interval, {pct}%, {result.n_pairs - 1} degrees of freedom",
            "pairing": f"Paired by seed: {result.n_pairs} seeds run under both A and B",
        },
        "effectSize": effect,
        "verdict": _verdict(result.direction, info["lowerIsBetter"]),
        "eligibility": eligibility,
    }
