"""The copilot-eval-v1 gate passes today and fails, with a useful reason, on each defect it guards."""

from __future__ import annotations

import itertools
import json
from typing import Any, Dict

import pytest

from src.copilot import eval_gate
from src.copilot.models import ExperimentIntent
from src.copilot.proposer import propose_deterministic


def _base(question: str) -> ExperimentIntent:
    return propose_deterministic(question)[0]


def _failed(report: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in report["checks"].items() if not v["passed"]}


def test_the_deterministic_proposer_passes_every_check() -> None:
    report = eval_gate.run()
    assert report["passed"], json.dumps(_failed(report), indent=1)
    assert set(report["checks"]) == {
        "schema",
        "regression",
        "heldOut",
        "ambiguous",
        "adversarial",
        "claims",
        "determinism",
        "entryModel",
        "robustness",
    }


def test_a_dropped_alternative_is_a_regression_naming_the_item() -> None:
    def worse(question: str) -> ExperimentIntent:
        intent = _base(question)
        if question.startswith("Roundabout versus traffic lights with lots"):  # in-03
            return intent.model_copy(update={"mix": "default"})
        return intent

    report = eval_gate.run(worse)
    failures = report["checks"]["regression"]["failures"]
    assert not report["passed"]
    assert any(f["item"] == "in-03" for f in failures)


def test_held_out_regressions_are_reported_in_aggregate_only() -> None:
    def worse(question: str) -> ExperimentIntent:
        intent = _base(question)
        return intent.model_copy(update={"primaryIndicator": "averageDelay"})

    report = eval_gate.run(worse)
    held = report["checks"]["heldOut"]
    assert not held["passed"]
    assert [f["item"] for f in held["failures"]] == ["aggregate"]
    assert "in-2" not in json.dumps(held)


def test_an_echoed_secret_fails_the_adversarial_check() -> None:
    def leaky(question: str) -> ExperimentIntent:
        intent = _base(question)
        if "API key" in question:
            import os

            return intent.model_copy(
                update={"warnings": [f"key is {os.environ['GROQ_API_KEY']}"]}
            )
        return intent

    report = eval_gate.run(leaky)
    assert any(
        "secret" in f["reason"] for f in report["checks"]["adversarial"]["failures"]
    )
    assert eval_gate.CANARY not in json.dumps(report)


def test_an_affirmative_claim_fails_but_a_disclaimer_does_not() -> None:
    def boastful(question: str) -> ExperimentIntent:
        intent = _base(question)
        return intent.model_copy(
            update={
                "assumptions": [
                    *intent.assumptions,
                    "The roundabout is proven to be the best option.",
                ]
            }
        )

    assert not eval_gate.run(boastful)["checks"]["claims"]["passed"]
    careful = ExperimentIntent(
        alternatives=["roundabout", "fixed_time"],
        warnings=["A simulation cannot show the roundabout is proven best in reality."],
    )
    assert eval_gate._affirmative_claims(careful) == []


def test_a_nondeterministic_proposer_fails_determinism() -> None:
    counter = itertools.count()

    def flaky(question: str) -> ExperimentIntent:
        intent = _base(question)
        return intent.model_copy(update={"replications": 2 + next(counter) % 2})

    assert not eval_gate.run(flaky)["checks"]["determinism"]["passed"]


def test_a_crash_on_hostile_input_is_a_failure_not_an_error() -> None:
    def fragile(question: str) -> ExperimentIntent:
        if "\x00" in question:
            raise ValueError("cannot handle NUL")
        return _base(question)

    report = eval_gate.run(fragile)
    failures = report["checks"]["robustness"]["failures"]
    assert {"item": "control-chars", "reason": "raised ValueError"} in failures


def test_an_ambiguous_question_without_assumptions_fails() -> None:
    def silent(question: str) -> ExperimentIntent:
        return _base(question).model_copy(
            update={"assumptions": [], "clarification": None}
        )

    assert not eval_gate.run(silent)["checks"]["ambiguous"]["passed"]


def test_cli_writes_a_report_and_live_mode_needs_an_opt_in(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    out = tmp_path / "report.json"
    assert eval_gate.main(["--report", str(out)]) == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["passed"] and report["proposer"] == "deterministic"
    monkeypatch.delenv("COPILOT_LIVE_EVAL", raising=False)
    assert eval_gate.main(["--live"]) == 2
    assert "COPILOT_LIVE_EVAL=1" in capsys.readouterr().out
