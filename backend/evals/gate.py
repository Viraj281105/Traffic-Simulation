"""Copilot eval gate: run the question set, compare the pass rate with a threshold, exit non-zero on failure.

    python -m evals.gate                      # offline, deterministic: the CI mode (run from backend/)
    python -m evals.gate --threshold 0.9 --report copilot-eval-gate.json
    python -m evals.gate --client mypkg.mod:make_client --judge mypkg.mod:make_judge   # caller-supplied (live)

Exit codes: 0 pass; 1 pass rate below the threshold, or the grounding self-check failed; 2 bad input
(missing or invalid question set, bad factory). The default client is the deterministic offline one, so
the gate needs no network and no API key. A live client is never built here: ``--client`` imports a
factory the caller provides.

The grounding self-check feeds a deliberately hallucinated summary to the checker and requires it to be
flagged, so a broken checker cannot turn the gate green (F8: a hallucinated-number test fails the build).
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import Any, Callable, List, Optional

from src.copilot.eval_harness import (
    DeterministicCopilotClient,
    Judge,
    LLMClient,
    MockJudge,
    QuestionSetError,
    load_question_set,
    run_eval,
)
from src.copilot.grounded_summary import check_grounded_summary

DEFAULT_QUESTIONS = Path(__file__).with_name("copilot_questions_v1.json")
DEFAULT_THRESHOLD = 1.0


def grounding_self_check() -> Optional[str]:
    """None when the checker behaves; otherwise a reason."""
    numbers = {"meanDelay": 24.8, "runs": 144, "share": 0.75}
    good = check_grounded_summary("Mean delay was 24.8 s over 144 runs; preferred in 75% of cases.", numbers)
    if not good.ok:
        return f"grounded summary was flagged: {good.ungrounded_tokens}"
    bad = check_grounded_summary("Mean delay was 24.8 s; the adaptive signal cut delay by 37% over 144 runs.", numbers)
    if bad.ungrounded_tokens != ["37%"]:
        return f"hallucinated number not flagged exactly: {bad.ungrounded_tokens}"
    return None


def _factory(spec: str) -> Callable[[], Any]:
    module, _, attr = spec.partition(":")
    if not module or not attr:
        raise ValueError(f"expected 'package.module:factory', got {spec!r}")
    return getattr(importlib.import_module(module), attr)  # type: ignore[no-any-return]


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="evals.gate", description=__doc__.split("\n")[0])
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD,
                        help="minimum pass rate in [0, 1] (default 1.0: every item)")
    parser.add_argument("--report", type=Path, help="write the JSON report here")
    parser.add_argument("--client", help="package.module:factory returning an LLMClient (default: offline deterministic)")
    parser.add_argument("--judge", help="package.module:factory returning a Judge (default: MockJudge)")
    args = parser.parse_args(argv)

    if not 0.0 <= args.threshold <= 1.0:
        print("error: --threshold must be within [0, 1]", file=sys.stderr)
        return 2
    try:
        questions = load_question_set(args.questions)
        client: LLMClient = _factory(args.client)() if args.client else DeterministicCopilotClient()
        judge: Judge = _factory(args.judge)() if args.judge else MockJudge()
    except (QuestionSetError, OSError, ValueError, ImportError, AttributeError) as err:
        print(f"error: {err}", file=sys.stderr)
        return 2

    report = run_eval(questions, client, judge)
    self_check = grounding_self_check()
    ok = report.pass_rate >= args.threshold and self_check is None

    out = report.to_dict()
    out.update({"threshold": args.threshold, "groundingSelfCheck": self_check or "ok", "gate": "pass" if ok else "fail"})
    if args.report:
        args.report.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")

    print(f"Copilot eval {report.name} v{report.version}: {report.passed}/{report.total} passed "
          f"(pass rate {report.pass_rate:.3f}, threshold {args.threshold:.3f})")
    for cat, c in sorted(report.by_category().items()):
        print(f"  {cat}: {c['passed']}/{c['total']}")
    for f in out["failures"]:
        print(f"  FAIL {f['id']}: " + "; ".join(f["failures"]))
    if self_check:
        print(f"  FAIL grounding self-check: {self_check}")
    print("GATE " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
