"""``ReportDocument``: an experiment's report, assembled from results that were already computed.

Nothing new is calculated. Assumptions and limitations come from the stored experiment result; the
comparison, sensitivity and metrics blocks are the ones the other endpoints serve (a block that is not
available is ``null``); the summary sentences are filled from those blocks only, and ``grounded`` is the
outcome of ``src.copilot.grounded_summary.check_grounded_summary`` run over the finished text against the
same blocks, so a number that traces to nothing makes it false.

Manifest mapping: ``seed`` is the experiment's sampling seed, ``configHash`` its scenario fingerprint,
``inputVersion`` its specification fingerprint (the declared uncertainty inputs), ``codeVersion`` the git
commit recorded in its provenance.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional

from src.copilot.grounded_summary import check_grounded_summary

_VERDICT_WORDS = {
    "a_better": "A is better than B",
    "b_better": "B is better than A",
    "no_clear_difference": "there is no clear difference between A and B",
}


def _assumptions(result: Mapping[str, Any]) -> List[str]:
    out: List[str] = []
    for a in result.get("assumptions") or []:
        if not isinstance(a, dict):
            continue
        basis = a.get("basis")
        rationale = a.get("rationale")
        line = f"{a.get('id')} ({a.get('kind')}, {basis})"
        if isinstance(rationale, str) and rationale:
            line += f": {rationale}"
        out.append(line)
    analysis = result.get("analysis")
    validity = analysis.get("realWorldValidity") if isinstance(analysis, dict) else None
    if isinstance(validity, str) and validity:
        out.append(f"Real-world validity: {validity}")
    return out


def _limitations(result: Mapping[str, Any]) -> List[str]:
    analysis = result.get("analysis")
    items = analysis.get("limitations") if isinstance(analysis, dict) else None
    return [x for x in items if isinstance(x, str)] if isinstance(items, list) else []


def _summary_text(
    comparison: Optional[Mapping[str, Any]], sensitivity: Optional[Mapping[str, Any]]
) -> str:
    sentences: List[str] = []
    if comparison is not None:
        metric = comparison["metric"]
        low, high = comparison["ci"]
        pct = round(comparison["confidenceLevel"] * 100)
        sentences.append(
            f"On {metric['label']}, {_VERDICT_WORDS[comparison['verdict']]} "
            f"({comparison['a']['label']} minus {comparison['b']['label']}: "
            f"{comparison['meanDifference']:.3g} {metric['unit']}, "
            f"{pct}% interval {low:.3g} to {high:.3g}, p = {comparison['pValue']:.3g}, "
            f"{comparison['pairs']} paired seeds)."
        )
    if sensitivity is not None and sensitivity["inputs"]:
        top = max(sensitivity["inputs"], key=lambda i: (i["total"], i["firstOrder"]))
        sentences.append(
            f"The input with the largest total effect on {sensitivity['metric']['label']} "
            f"is {top['label']} (total index {top['total']:.2f}, first-order {top['firstOrder']:.2f})."
        )
    if not sentences:
        return "No comparison or sensitivity result is available for this experiment yet."
    return " ".join(sentences)


def build_report(
    experiment_id: str,
    name: str,
    result: Mapping[str, Any],
    comparison: Optional[Dict[str, Any]],
    sensitivity: Optional[Dict[str, Any]],
    metrics: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    text = _summary_text(comparison, sensitivity)
    grounded = check_grounded_summary(
        text, {"comparison": comparison, "sensitivity": sensitivity}
    ).ok
    spec = result.get("specification")
    manifest = result.get("manifest")
    provenance = result.get("provenance")
    seed = spec.get("seed") if isinstance(spec, dict) else None
    return {
        "experimentId": experiment_id,
        "title": name,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "assumptions": _assumptions(result),
        "limitations": _limitations(result),
        "summary": {"text": text, "grounded": grounded},
        "comparison": comparison,
        "sensitivity": sensitivity,
        "metrics": metrics,
        "manifest": {
            "seed": seed if isinstance(seed, int) else None,
            "configHash": _str(manifest, "scenarioFingerprint"),
            "codeVersion": _str(provenance, "gitCommit"),
            "inputVersion": _str(manifest, "specFingerprint"),
        },
    }


def _str(source: Any, key: str) -> Optional[str]:
    value = source.get(key) if isinstance(source, dict) else None
    return value if isinstance(value, str) else None
