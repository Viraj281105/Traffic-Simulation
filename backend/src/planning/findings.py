"""Rule-based findings: structured statements, each citing its evidence.

There is deliberately no ranking, no scoring and no overall "best": a finding
describes one alternative against the baseline on one metric at one demand
scale, in this scenario only. ``unavailable`` indicators produce no claim.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

MIN_SEEDS_ADEQUATE = 5
MIN_SEEDS_ANY = 3

_PHRASE = {
    "averageDelay": {
        "better": "had lower mean delay",
        "worse": "had higher mean delay",
        "tie": "had a similar mean delay",
        "inconclusive": "showed an inconclusive difference in mean delay",
        "unit": "s",
    },
    "throughput": {
        "better": "served more vehicles",
        "worse": "served fewer vehicles",
        "tie": "served a similar number of vehicles",
        "inconclusive": "showed an inconclusive difference in vehicles served",
        "unit": "vehicles",
    },
    "averageQueueLength": {
        "better": "had shorter average queues",
        "worse": "had longer average queues",
        "tie": "had similar average queues",
        "inconclusive": "showed an inconclusive difference in average queue length",
        "unit": "vehicles",
    },
    "collisionCount": {
        "better": "had fewer simulated collisions",
        "worse": "had more simulated collisions",
        "tie": "had similar safety indicators (simulated collisions)",
        "inconclusive": "showed an inconclusive difference in simulated collisions",
        "unit": "collisions",
    },
}
_METRIC_LABEL = {
    "averageDelay": "mean delay",
    "throughput": "vehicles served",
}
_KIND = {
    "averageDelay": "delay",
    "throughput": "throughput",
    "averageQueueLength": "queue",
    "collisionCount": "safety",
}


def confidence_of(verdict: str, n: int) -> str:
    if n < MIN_SEEDS_ANY or verdict == "inconclusive":
        return "low"
    if verdict in ("better", "worse") and n >= MIN_SEEDS_ADEQUATE:
        return "high"
    return "moderate"


def _scale(s: float) -> str:
    return f"x{s:g} demand"


def generate_findings(
    alternatives: Sequence[Dict[str, Any]],
    results: Sequence[Dict[str, Any]],
    vs_baseline: Sequence[Dict[str, Any]],
    seeds: Sequence[int],
    validity: Dict[str, Any],
    indicator_groups: Sequence[str],
) -> List[Dict[str, Any]]:
    labels = {a["id"]: a["label"] for a in alternatives}
    baseline = next((a["id"] for a in alternatives if a["isBaseline"]), None)
    result_index = {
        (r["alternativeId"], r["demandScale"]): i for i, r in enumerate(results)
    }
    findings: List[Dict[str, Any]] = []

    def add(
        kind: str,
        statement: str,
        confidence: str,
        evidence: List[str],
        caveats: List[str],
    ) -> None:
        findings.append(
            {
                "id": f"F{len(findings) + 1}",
                "kind": kind,
                "statement": statement,
                "confidence": confidence,
                "evidence": [{"path": p} for p in evidence],
                "caveats": caveats,
            }
        )

    exploratory = [c for c in validity.get("caveats", [])]
    n = len(seeds)

    if len(alternatives) < 2:
        add(
            "note",
            "Only the baseline was run, so there is nothing to compare it with.",
            "high",
            [],
            [],
        )

    for j, c in enumerate(vs_baseline):
        metric = c["metric"]
        if metric not in _PHRASE or c.get("verdict") == "unavailable":
            continue
        if metric == "collisionCount" and "safety" not in indicator_groups:
            continue
        if metric != "collisionCount" and "performance" not in indicator_groups:
            continue
        verdict = c["verdict"]
        alt, scale = c["alternativeId"], c["demandScale"]
        phrase = _PHRASE[metric]
        detail = ""
        if verdict in ("better", "worse") and c.get("delta") is not None:
            lo, hi = c.get("ciLow"), c.get("ciHigh")
            ci = f", CI {lo:g} to {hi:g}" if lo is not None and hi is not None else ""
            detail = f" ({c['delta']:+g} {phrase['unit']} vs baseline{ci})"
        elif verdict == "inconclusive":
            detail = f" ({n} seeds could not separate them)"
        statement = (
            f"{labels[alt]} {phrase[verdict]} than {labels[baseline]}"
            if verdict in ("better", "worse")
            else f"{labels[alt]} {phrase[verdict]} compared with {labels[baseline]}"
        )
        statement += f" at {_scale(scale)}{detail}."
        caveats = list(exploratory)
        if metric == "collisionCount":
            caveats.append("Exploratory: simulated collisions are a rare-event proxy.")
        evidence = [f"comparison.vsBaseline[{j}]"]
        for aid in (alt, baseline):
            i = result_index.get((aid, scale))
            if i is not None:
                evidence.append(
                    f"results[{i}].{'safety' if metric == 'collisionCount' else 'performance'}.values.{metric}"
                )
        add(_KIND[metric], statement, confidence_of(verdict, c["n"]), evidence, caveats)

    # Sensitivity: does the reading for an alternative change with demand?
    by_alt_metric: Dict[Tuple[str, str], List[Tuple[float, str, int]]] = {}
    for j, c in enumerate(vs_baseline):
        if (
            c["metric"] in ("averageDelay", "throughput")
            and c.get("verdict") != "unavailable"
        ):
            by_alt_metric.setdefault((c["alternativeId"], c["metric"]), []).append(
                (c["demandScale"], c["verdict"], j)
            )
    for (alt, metric), entries in by_alt_metric.items():
        if len({v for _, v, _ in entries}) > 1:
            readings = "; ".join(f"{_scale(s)}: {v}" for s, v, _ in sorted(entries))
            add(
                "demand_sensitivity",
                f"The result for {labels[alt]} on {_METRIC_LABEL[metric]} "
                f"depends on demand ({readings}). It should not be read as holding "
                "outside the tested demand levels.",
                "moderate",
                [f"comparison.vsBaseline[{j}]" for _, _, j in sorted(entries)],
                exploratory,
            )

    if n < MIN_SEEDS_ANY:
        add(
            "reliability",
            f"Only {n} repetition(s) were run; differences cannot be reliably "
            "separated from seed-to-seed variation.",
            "high",
            ["reliability"],
            [],
        )
    elif n < MIN_SEEDS_ADEQUATE:
        add(
            "reliability",
            f"{n} repetitions were run; intervals are wide and readings should be "
            "treated as indicative.",
            "moderate",
            ["reliability"],
            [],
        )
    if validity.get("vehicleLimitReached"):
        add(
            "reliability",
            "The vehicle limit was reached in at least one run, so throughput and "
            "delay may be truncated.",
            "high",
            ["validity.vehicleLimitReached"],
            [],
        )
    if "environmental" in indicator_groups:
        add(
            "note",
            "No emissions or fuel model is available; environmental indicators are "
            "stop-and-go and idling proxies only, and no environmental claim is made.",
            "high",
            ["results[0].environmental"] if results else [],
            [],
        )
    return findings


def resolve_path(root: Any, path: str) -> Optional[Any]:
    """Resolve ``a.b[2].c`` against nested dicts/lists; None if absent."""
    cur: Any = root
    for part in path.replace("]", "").replace("[", ".").split("."):
        if part == "":
            continue
        if isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                return None
        elif isinstance(cur, dict):
            if part not in cur:
                return None
            cur = cur[part]
        else:
            return None
    return cur
