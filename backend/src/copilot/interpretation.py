"""Evidence object, template summary and the grounding check (strategy section 15.1.2, C5 and C6).

The evidence object is taken from the caller's own completed result. The template summary is always
built; a model-written text is shown only if every numeral in it traces to the evidence, and the
mandatory sections (eligibility, sample sizes, validity, limitations and every unfavourable finding for
the preferred alternative) are appended deterministically whatever the model wrote.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple

from src.uncertainty.analysis import REAL_WORLD_VALIDITY

_NUMBER = re.compile(r"(?<![A-Za-z0-9_])-?\d+(?:[.,]\d+)*(?:\.\d+)?%?")


def build_evidence(result: Dict[str, Any]) -> Dict[str, Any]:
    """The facts an interpretation may use, from an ``urbanflow-experiment-result``."""
    analysis = result.get("analysis") or {}
    counts = analysis.get("counts") or {}
    alternatives: Dict[str, Any] = {}
    for alt in result.get("alternatives") or []:
        block = (analysis.get("alternatives") or {}).get(alt["id"]) or {}
        comparison = block.get("comparison") or None
        entry: Dict[str, Any] = {
            "label": alt.get("label") or alt["id"],
            "strategy": alt.get("strategy"),
            "isBaseline": bool(alt.get("isBaseline")),
            "meanOutcome": block.get("meanOutcome"),
            "preferenceShare": block.get("preferenceShare"),
            "meanRegret": (block.get("regret") or {}).get("mean"),
        }
        if comparison:
            difference = (comparison.get("difference") or {}).get("mean") or {}
            entry["versusBaseline"] = {
                "win": comparison["win"]["p"],
                "tie": comparison["tie"]["p"],
                "loss": comparison["loss"]["p"],
                "meanDifference": difference.get("value"),
                "meanDifferenceCi": difference.get("ci"),
            }
        alternatives[alt["id"]] = entry
    eligibility = analysis.get("eligibility") or {}
    return {
        "experimentId": result.get("experimentId"),
        "name": result.get("name"),
        "primaryIndicator": analysis.get("primaryIndicator"),
        "unit": "seconds",
        "baseline": result.get("baseline"),
        "counts": {
            "conditions": counts.get("conditions"),
            "validConditions": counts.get("validConditions"),
            "replications": counts.get("replications"),
            "totalRuns": counts.get("totalRuns"),
        },
        "eligibilityClass": eligibility.get("class"),
        "excludedShare": (analysis.get("exclusions") or {}).get("overallShare"),
        "alternatives": alternatives,
        "realWorldValidity": analysis.get("realWorldValidity", REAL_WORLD_VALIDITY),
        "limitations": list(analysis.get("limitations") or []),
        "resultFingerprint": result.get("resultFingerprint"),
    }


def _fmt(value: Any) -> str:
    if value is None:
        return "n/a"
    # Numbers are written exactly as the evidence holds them, so the summary passes its own grounding check.
    return str(value)


def unfavourable_findings(
    evidence: Dict[str, Any], preferred: Optional[str]
) -> List[str]:
    """Every measured way the preferred alternative did worse. Empty when there is none or no preference."""
    if not preferred or preferred not in evidence["alternatives"]:
        return []
    findings: List[str] = []
    alts = evidence["alternatives"]
    mine = alts[preferred]
    baseline = evidence["baseline"]
    if preferred != baseline and "versusBaseline" in mine:
        vs = mine["versusBaseline"]
        if (vs["meanDifference"] or 0) > 0:
            findings.append(
                f"{mine['label']} had a higher mean {evidence['primaryIndicator']} than the baseline "
                f"(mean difference {_fmt(vs['meanDifference'])} s)."
            )
        if vs["loss"] and vs["loss"] > 0:
            findings.append(
                f"{mine['label']} lost to the baseline in a share of {_fmt(vs['loss'])} of the valid conditions."
            )
    for other_id, other in alts.items():
        if other_id == preferred:
            continue
        a, b = mine.get("meanOutcome"), other.get("meanOutcome")
        if isinstance(a, (int, float)) and isinstance(b, (int, float)) and b < a:
            findings.append(
                f"{other['label']} had a lower mean outcome ({_fmt(b)} s) than {mine['label']} ({_fmt(a)} s)."
            )
    share = mine.get("preferenceShare")
    if isinstance(share, (int, float)) and share < 0.5:
        findings.append(
            f"{mine['label']} was the preferred (lowest-delay) option in a share of only {_fmt(share)} of conditions."
        )
    return findings


def mandatory_sections(evidence: Dict[str, Any], preferred: Optional[str]) -> List[str]:
    c = evidence["counts"]
    lines = [
        f"Eligibility: {evidence['eligibilityClass']}.",
        f"Sample: {_fmt(c['conditions'])} sampled conditions ({_fmt(c['validConditions'])} valid), "
        f"{_fmt(c['replications'])} replications per condition, {_fmt(c['totalRuns'])} runs in total.",
        f"Real-world validity: {evidence['realWorldValidity']}.",
    ]
    limitations = evidence.get("limitations") or []
    if limitations:
        lines.append("Limitations: " + " ".join(str(item) for item in limitations))
    unfavourable = unfavourable_findings(evidence, preferred)
    if unfavourable:
        lines.append(
            "Unfavourable for the preferred alternative: " + " ".join(unfavourable)
        )
    elif preferred:
        lines.append(
            "No measured finding was unfavourable to the preferred alternative."
        )
    return lines


def template_summary(evidence: Dict[str, Any], preferred: Optional[str]) -> str:
    alts = evidence["alternatives"]
    baseline = evidence["baseline"]
    lines = [
        f"Primary indicator: {evidence['primaryIndicator']} (lower is better), compared with the "
        f"baseline {alts.get(baseline, {}).get('label', baseline)}."
    ]
    for alt_id, alt in alts.items():
        part = f"{alt['label']}: mean outcome {_fmt(alt.get('meanOutcome'))} s, preferred in a share of {_fmt(alt.get('preferenceShare'))} of conditions"
        vs = alt.get("versusBaseline")
        if vs:
            part += (
                f"; against the baseline it won {_fmt(vs['win'])}, tied {_fmt(vs['tie'])} and lost "
                f"{_fmt(vs['loss'])} of conditions (mean difference {_fmt(vs['meanDifference'])} s, "
                f"95% interval {_fmt((vs.get('meanDifferenceCi') or [None, None])[0])} to "
                f"{_fmt((vs.get('meanDifferenceCi') or [None, None])[1])})"
            )
        lines.append(part + ".")
    lines.extend(mandatory_sections(evidence, preferred))
    return "\n".join(lines)


def _evidence_numbers(value: Any, out: Set[float]) -> None:
    if isinstance(value, bool):
        return
    if isinstance(value, (int, float)):
        out.add(round(float(value), 6))
        out.add(round(float(value) * 100, 6))  # a proportion written as a percentage
    elif isinstance(value, dict):
        for v in value.values():
            _evidence_numbers(v, out)
    elif isinstance(value, (list, tuple)):
        for v in value:
            _evidence_numbers(v, out)
    elif isinstance(value, str):
        for token in _NUMBER.findall(value):
            parsed = _parse(token)
            if parsed is not None:
                out.add(round(parsed, 6))


def _parse(token: str) -> Optional[float]:
    cleaned = token.rstrip("%").replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


# Small counting words a summary may use without them being measurements ("95%" belongs to the evidence
# through the interval label; 1 and 2 appear in ordinary prose).
_ALWAYS_ALLOWED = {0.0, 1.0, 2.0, 95.0, 100.0}


def grounding_check(text: str, evidence: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Every numeral in ``text`` must be a number of the evidence. Returns ``(ok, ungrounded numerals)``."""
    allowed: Set[float] = set(_ALWAYS_ALLOWED)
    _evidence_numbers(evidence, allowed)
    ungrounded = []
    for token in _NUMBER.findall(text):
        value = _parse(token)
        if value is None:
            continue
        if round(value, 6) not in allowed:
            ungrounded.append(token)
    return not ungrounded, ungrounded
