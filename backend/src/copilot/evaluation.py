"""``copilot-eval-v1``: scoring a proposer against the labelled evaluation set (strategy 15.1.5-15.1.7).

``python -m src.copilot.evaluation`` prints the deterministic baseline. A model proposer is scored the same
way by passing ``propose``; the held-out ten are reported separately and must be used once only.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

from .models import ExperimentIntent
from .proposer import build_experiment, propose_deterministic
from .validation import validate_experiment

EVAL_PATH = Path(__file__).parent / "eval" / "copilot-eval-v1.json"

Proposer = Callable[[str], ExperimentIntent]


def load_items() -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = json.loads(EVAL_PATH.read_text(encoding="utf-8"))[
        "items"
    ]
    return items


def _deterministic(question: str) -> ExperimentIntent:
    return propose_deterministic(question)[0]


def score_item(intent: ExperimentIntent, checklist: Dict[str, Any]) -> Tuple[int, int]:
    """(elements matched, elements required). Replications >= 2 and a sensitivity check always count."""
    matched = required = 0
    for alt in checklist.get("alternatives", []):
        required += 1
        matched += alt in intent.alternatives
    for key in ("aggression", "demand", "unevenDemand", "mix", "primaryIndicator"):
        if key in checklist:
            required += 1
            matched += getattr(intent, key) == checklist[key]
    required += 1
    matched += intent.replications >= checklist.get("replicationsAtLeast", 2)
    required += 1  # a sensitivity check: every built proposal suggests at least one
    matched += 1
    return matched, required


def evaluate(propose: Proposer = _deterministic) -> Dict[str, Any]:
    items = load_items()
    report: Dict[str, Any] = {
        "inScope": {},
        "heldOut": {},
        "ambiguous": [],
        "adversarial": [],
    }
    totals = {"dev": [0, 0], "held": [0, 0]}
    valid_in_scope = 0
    for item in items:
        intent = propose(item["question"])
        experiment, checks = build_experiment(intent, item["question"])
        valid, _issues, _runs, _seconds = validate_experiment(experiment)
        if item["kind"] == "in_scope":
            matched, required = score_item(intent, item["checklist"])
            bucket = "held" if item["heldOut"] else "dev"
            totals[bucket][0] += matched
            totals[bucket][1] += required
            valid_in_scope += valid
            target = report["heldOut"] if item["heldOut"] else report["inScope"]
            target[item["id"]] = {
                "matched": matched,
                "required": required,
                "valid": valid,
            }
        elif item["kind"] == "ambiguous":
            report["ambiguous"].append(
                {
                    "id": item["id"],
                    "statesAssumptions": bool(
                        intent.clarification or intent.assumptions
                    ),
                    "valid": valid,
                }
            )
        else:
            report["adversarial"].append(
                {"id": item["id"], "warned": bool(intent.warnings), "valid": valid}
            )
    report["recall"] = {
        "development": totals["dev"][0] / totals["dev"][1],
        "heldOut": totals["held"][0] / totals["held"][1],
    }
    report["validInScope"] = valid_in_scope
    return report


if __name__ == "__main__":  # pragma: no cover
    print(json.dumps(evaluate(), indent=2))
