"""Copilot eval harness: runs a versioned question set against a pluggable LLM client.

* ``LLMClient`` is the seam: ``respond(request) -> LLMResponse`` (text plus structured tool calls).
  Tests and CI use ``MockLLMClient`` (scripted) or ``DeterministicCopilotClient`` (the real
  deterministic proposer and template summary); a live client is supplied by the caller and is never
  constructed here, so nothing in this module can reach the network.
* ``Judge`` is the LLM-judge seam: ``judge(request, response, rubric) -> JudgeVerdict``. ``MockJudge``
  is deterministic. A judge is consulted only for items that carry a ``rubric``.
* Each item is checked structurally first (expected tool calls, expected facts, forbidden strings,
  grounded numbers); the judge adds a quality verdict on top. An item passes only if all of them pass.

Question set format (``urbanflow-copilot-eval-questions`` v1): see ``backend/evals/copilot_questions_v1.json``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Protocol, Sequence

from .grounded_summary import check_grounded_summary

QUESTION_SET_FORMAT = "urbanflow-copilot-eval-questions"
SUPPORTED_VERSION = 1
KINDS = ("proposal", "summary")


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LLMRequest:
    question_id: str
    kind: str
    question: str
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LLMResponse:
    text: str = ""
    tool_calls: Sequence[ToolCall] = ()


class LLMClient(Protocol):
    def respond(self, request: LLMRequest) -> LLMResponse: ...


@dataclass(frozen=True)
class JudgeVerdict:
    score: float  # 0..1
    passed: bool
    rationale: str = ""


class Judge(Protocol):
    def judge(
        self, request: LLMRequest, response: LLMResponse, rubric: str
    ) -> JudgeVerdict: ...


# ---------------------------------------------------------------- offline clients and judge


class MockLLMClient:
    """Scripted client: ``script`` maps question id to an ``LLMResponse`` (or a callable of the request).
    An unscripted id raises ``KeyError`` so a test cannot silently pass on an empty answer."""

    def __init__(
        self, script: Mapping[str, Any], default: Optional[LLMResponse] = None
    ) -> None:
        self._script = dict(script)
        self._default = default
        self.calls: List[LLMRequest] = []

    def respond(self, request: LLMRequest) -> LLMResponse:
        self.calls.append(request)
        entry = self._script.get(request.question_id, self._default)
        if entry is None:
            raise KeyError(f"no scripted answer for {request.question_id!r}")
        return entry(request) if callable(entry) else entry  # type: ignore[no-any-return]


class DeterministicCopilotClient:
    """Offline client backed by the shipped deterministic proposer and template summary. No network,
    no key, same answer every time: the CI default."""

    def respond(self, request: LLMRequest) -> LLMResponse:
        from .interpretation import template_summary
        from .proposer import propose_deterministic

        if request.kind == "proposal":
            intent, _ = propose_deterministic(request.question)
            return LLMResponse(
                text=" ".join(intent.assumptions + intent.warnings),
                tool_calls=(ToolCall("propose_experiment", intent.model_dump()),),
            )
        if request.kind == "summary":
            ctx = request.context
            return LLMResponse(
                text=template_summary(ctx["numbers"], ctx.get("preferred"))
            )
        raise ValueError(f"unknown kind {request.kind!r}")


class MockJudge:
    """Deterministic judge. The rubric is ``"mention: a | b"``; the score is the share of those keywords
    present in the answer text (case-insensitive). ``verdicts`` overrides per question id."""

    def __init__(
        self,
        verdicts: Optional[Mapping[str, JudgeVerdict]] = None,
        threshold: float = 0.5,
    ) -> None:
        self._verdicts = dict(verdicts or {})
        self._threshold = threshold

    def judge(
        self, request: LLMRequest, response: LLMResponse, rubric: str
    ) -> JudgeVerdict:
        if request.question_id in self._verdicts:
            return self._verdicts[request.question_id]
        keywords = [
            k.strip().lower() for k in rubric.split(":", 1)[-1].split("|") if k.strip()
        ]
        if not keywords:
            return JudgeVerdict(1.0, True, "empty rubric")
        text = response.text.lower()
        hit = [k for k in keywords if k in text]
        score = len(hit) / len(keywords)
        return JudgeVerdict(score, score >= self._threshold, f"matched {hit}")


# ---------------------------------------------------------------- question set


class QuestionSetError(ValueError):
    pass


def load_question_set(path: Path) -> Dict[str, Any]:
    data: Dict[str, Any] = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("format") != QUESTION_SET_FORMAT:
        raise QuestionSetError(f"{path}: not a {QUESTION_SET_FORMAT} file")
    if data.get("version") != SUPPORTED_VERSION:
        raise QuestionSetError(f"{path}: unsupported version {data.get('version')!r}")
    if not data.get("items"):
        raise QuestionSetError(f"{path}: no items")
    seen = set()
    for item in data["items"]:
        for key in ("id", "kind", "question", "expected"):
            if key not in item:
                raise QuestionSetError(f"item missing {key!r}: {item.get('id')}")
        if item["kind"] not in KINDS:
            raise QuestionSetError(f"{item['id']}: unknown kind {item['kind']!r}")
        if item["id"] in seen:
            raise QuestionSetError(f"duplicate id {item['id']}")
        seen.add(item["id"])
        if item["kind"] == "summary" and "numbers" not in item.get("context", {}):
            raise QuestionSetError(f"{item['id']}: summary items need context.numbers")
    return data


# ---------------------------------------------------------------- checks


def _arg_matches(expected: Any, actual: Any) -> bool:
    if isinstance(expected, list):
        return isinstance(actual, list) and all(e in actual for e in expected)
    return bool(expected == actual)


def _tool_call_failures(
    expected: Sequence[Mapping[str, Any]], actual: Sequence[ToolCall]
) -> List[str]:
    failures = []
    for want in expected:
        wanted_args = want.get("arguments", {})
        found = any(
            call.name == want["name"]
            and all(
                k in call.arguments and _arg_matches(v, call.arguments[k])
                for k, v in wanted_args.items()
            )
            for call in actual
        )
        if not found:
            failures.append(f"missing tool call {want['name']} {wanted_args}")
    return failures


def check_item(
    item: Mapping[str, Any],
    response: LLMResponse,
    allowed_numbers: Sequence[float] = (95,),
) -> List[str]:
    """Structural failures of one response; an empty list means it satisfied the item."""
    expected = item["expected"]
    low = response.text.lower()
    failures = _tool_call_failures(expected.get("toolCalls", []), response.tool_calls)
    failures += [
        f"missing fact {f!r}" for f in expected.get("facts", []) if f.lower() not in low
    ]
    failures += [
        f"contains forbidden {s!r}"
        for s in expected.get("forbidden", [])
        if s.lower() in low
    ]
    if expected.get("grounded"):
        report = check_grounded_summary(
            response.text, item["context"]["numbers"], allowed_numbers=allowed_numbers
        )
        if not report.ok:
            failures.append(
                "ungrounded numbers: " + ", ".join(report.ungrounded_tokens)
            )
    return failures


# ---------------------------------------------------------------- runner


@dataclass
class ItemResult:
    id: str
    kind: str
    category: str
    passed: bool
    failures: List[str]
    judge: Optional[JudgeVerdict] = None


@dataclass
class EvalReport:
    name: str
    version: int
    results: List[ItemResult]

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed(self) -> int:
        return sum(r.passed for r in self.results)

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 0.0

    def by_category(self) -> Dict[str, Dict[str, int]]:
        out: Dict[str, Dict[str, int]] = {}
        for r in self.results:
            slot = out.setdefault(r.category, {"passed": 0, "total": 0})
            slot["total"] += 1
            slot["passed"] += int(r.passed)
        return out

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "total": self.total,
            "passed": self.passed,
            "passRate": round(self.pass_rate, 6),
            "byCategory": self.by_category(),
            "failures": [
                {
                    "id": r.id,
                    "failures": r.failures,
                    "judge": None if r.judge is None else r.judge.rationale,
                }
                for r in self.results
                if not r.passed
            ],
        }


def run_eval(
    question_set: Mapping[str, Any],
    client: LLMClient,
    judge: Optional[Judge] = None,
    *,
    allowed_numbers: Sequence[float] = (95,),
    on_item: Optional[Callable[[ItemResult], None]] = None,
) -> EvalReport:
    results: List[ItemResult] = []
    for item in question_set["items"]:
        request = LLMRequest(
            item["id"], item["kind"], item["question"], dict(item.get("context", {}))
        )
        response = LLMResponse()
        try:
            response = client.respond(request)
            failures = check_item(item, response, allowed_numbers)
        except Exception as err:  # noqa: BLE001 - a client crash fails the item, not the harness
            failures = [f"client error: {type(err).__name__}: {err}"]
        verdict: Optional[JudgeVerdict] = None
        rubric = item["expected"].get("rubric")
        if judge is not None and rubric and not failures:
            verdict = judge.judge(request, response, rubric)
            if not verdict.passed:
                failures.append(
                    f"judge rejected (score {verdict.score:.2f}): {verdict.rationale}"
                )
        result = ItemResult(
            item["id"],
            item["kind"],
            item.get("category", item["kind"]),
            not failures,
            failures,
            verdict,
        )
        results.append(result)
        if on_item:
            on_item(result)
    return EvalReport(
        question_set.get("name", "unnamed"), question_set["version"], results
    )
