"""Eval harness, judge seam, gate script and grounded-summary checker (offline; no real LLM)."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from evals import gate
from src.copilot.eval_harness import (
    DeterministicCopilotClient,
    JudgeVerdict,
    LLMResponse,
    MockJudge,
    MockLLMClient,
    QuestionSetError,
    ToolCall,
    load_question_set,
    run_eval,
)
from src.copilot.grounded_summary import assert_grounded, check_grounded_summary

BACKEND = Path(__file__).resolve().parents[2]
QUESTIONS = gate.DEFAULT_QUESTIONS


@pytest.fixture(scope="module")
def qset():
    return load_question_set(QUESTIONS)


def _tiny(items):
    return {
        "format": "urbanflow-copilot-eval-questions",
        "version": 1,
        "name": "t",
        "items": items,
    }


PROPOSAL = {
    "id": "x",
    "kind": "proposal",
    "question": "q",
    "expected": {
        "toolCalls": [
            {
                "name": "propose_experiment",
                "arguments": {"alternatives": ["adaptive"], "demand": "peak"},
            }
        ]
    },
}


# ---- question set


def test_question_set_loads_and_is_versioned(qset):
    assert qset["version"] == 1 and len(qset["items"]) >= 10
    assert len({i["id"] for i in qset["items"]}) == len(qset["items"])


@pytest.mark.parametrize(
    "mutate,msg",
    [
        (lambda d: d.update(format="other"), "not a"),
        (lambda d: d.update(version=2), "unsupported"),
        (lambda d: d.update(items=[]), "no items"),
        (lambda d: d["items"].append(dict(d["items"][0])), "duplicate"),
        (lambda d: d["items"][0].update(kind="chat"), "unknown kind"),
        (lambda d: d["items"][0].pop("expected"), "missing"),
    ],
)
def test_invalid_question_sets_rejected(tmp_path, mutate, msg):
    data = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    mutate(data)
    path = tmp_path / "q.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(QuestionSetError, match=msg):
        load_question_set(path)


def test_summary_item_requires_numbers(tmp_path):
    path = tmp_path / "q.json"
    item = {"id": "s", "kind": "summary", "question": "q", "expected": {}}
    path.write_text(json.dumps(_tiny([item])))
    with pytest.raises(QuestionSetError, match="context.numbers"):
        load_question_set(path)


# ---- harness


def test_deterministic_offline_client_passes_whole_set(qset):
    report = run_eval(qset, DeterministicCopilotClient(), MockJudge())
    assert report.pass_rate == 1.0, report.to_dict()["failures"]
    assert report.total == len(qset["items"])


def test_deterministic_client_is_repeatable(qset):
    a = run_eval(qset, DeterministicCopilotClient()).to_dict()
    b = run_eval(qset, DeterministicCopilotClient()).to_dict()
    assert a == b


def test_mock_client_scripted_pass_and_fail():
    def tc(name, **args):
        return LLMResponse(tool_calls=(ToolCall(name, args),))

    cases = [
        (
            tc(
                "propose_experiment",
                alternatives=["adaptive", "fixed_time"],
                demand="peak",
            ),
            True,
        ),
        (tc("propose_experiment", alternatives=["adaptive"], demand="light"), False),
        (tc("run_simulation", alternatives=["adaptive"], demand="peak"), False),
        (LLMResponse(), False),
    ]
    for resp, ok in cases:
        report = run_eval(_tiny([PROPOSAL]), MockLLMClient({"x": resp}))
        assert (report.pass_rate == 1.0) is ok
    assert "missing tool call" in report.results[0].failures[0]


def test_facts_and_forbidden_checked_case_insensitively():
    item = {
        "id": "f",
        "kind": "proposal",
        "question": "q",
        "expected": {"facts": ["Cannot Prove"], "forbidden": ["guaranteed"]},
    }
    ok = run_eval(
        _tiny([item]), MockLLMClient({"f": LLMResponse("It cannot prove this.")})
    )
    assert ok.pass_rate == 1.0
    bad = run_eval(
        _tiny([item]), MockLLMClient({"f": LLMResponse("cannot prove; GUARANTEED")})
    )
    assert "forbidden" in bad.results[0].failures[0]


def test_unscripted_item_and_client_crash_fail_the_item_not_the_run():
    def boom(_req):
        raise RuntimeError("provider down")

    report = run_eval(
        _tiny([PROPOSAL, dict(PROPOSAL, id="y")]), MockLLMClient({"x": boom})
    )
    assert report.total == 2 and report.passed == 0
    assert "provider down" in report.results[0].failures[0]
    assert "no scripted answer" in report.results[1].failures[0]


def test_summary_item_grounding_in_harness(qset):
    item = next(i for i in qset["items"] if i["id"] == "s-01")
    one = _tiny([item])
    assert (
        run_eval(
            one, MockLLMClient({"s-01": LLMResponse("Adaptive signal 24.8")})
        ).pass_rate
        == 0.0
    )
    full = "Adaptive signal: 24.8 s; difference -6.6 s; 144 runs. "
    assert run_eval(one, MockLLMClient({"s-01": LLMResponse(full)})).pass_rate == 1.0
    bad = run_eval(
        one, MockLLMClient({"s-01": LLMResponse(full + "A 37% improvement.")})
    )
    assert bad.pass_rate == 0.0 and "37%" in bad.results[0].failures[0]


def test_report_by_category_and_dict(qset):
    d = run_eval(qset, DeterministicCopilotClient()).to_dict()
    assert d["passed"] == d["total"] and d["failures"] == []
    assert sum(c["total"] for c in d["byCategory"].values()) == d["total"]


def test_unknown_kind_from_deterministic_client():
    with pytest.raises(ValueError):
        from src.copilot.eval_harness import LLMRequest

        DeterministicCopilotClient().respond(LLMRequest("a", "chat", "q"))


# ---- judge


RUBRIC_ITEM = {
    "id": "j",
    "kind": "proposal",
    "question": "q",
    "expected": {"rubric": "mention: baseline | interval"},
}


def test_mock_judge_keyword_scoring():
    client = MockLLMClient({"j": LLMResponse("compared with the baseline")})
    assert (
        run_eval(_tiny([RUBRIC_ITEM]), client, MockJudge(threshold=0.5)).pass_rate
        == 1.0
    )
    strict = run_eval(_tiny([RUBRIC_ITEM]), client, MockJudge(threshold=1.0))
    assert strict.pass_rate == 0.0 and "judge rejected" in strict.results[0].failures[0]


def test_judge_called_only_for_rubric_items_that_pass_structure():
    calls = []

    class Spy:
        def judge(self, req, resp, rubric):
            calls.append(req.question_id)
            return JudgeVerdict(0.0, False, "spy no")

    no_rubric = {"id": "n", "kind": "proposal", "question": "q", "expected": {}}
    struct_fail = {
        "id": "s",
        "kind": "proposal",
        "question": "q",
        "expected": {"facts": ["zzz"], "rubric": "mention: a"},
    }
    client = MockLLMClient({}, default=LLMResponse("a"))
    report = run_eval(_tiny([no_rubric, struct_fail, RUBRIC_ITEM]), client, Spy())
    assert calls == ["j"]
    assert [r.passed for r in report.results] == [True, False, False]
    override = MockJudge({"j": JudgeVerdict(1.0, True, "forced")}, threshold=1.0)
    assert run_eval(_tiny([RUBRIC_ITEM]), client, override).pass_rate == 1.0


def test_no_judge_skips_rubric():
    assert (
        run_eval(_tiny([RUBRIC_ITEM]), MockLLMClient({"j": LLMResponse("")})).pass_rate
        == 1.0
    )


def test_empty_rubric_passes():
    item = dict(RUBRIC_ITEM, expected={"rubric": "mention:"})
    assert (
        run_eval(
            _tiny([item]), MockLLMClient({"j": LLMResponse("")}), MockJudge()
        ).pass_rate
        == 1.0
    )


# ---- grounded-summary checker


NUMBERS = {
    "delay": {"fixed": 31.4, "adaptive": 24.84},
    "diff": -6.6,
    "share": 0.75,
    "runs": 144,
    "ci": [-9.1, -4.2],
    "note": "n=240 sampled",
    "flag": True,
    "none": None,
}


@pytest.mark.parametrize(
    "text",
    [
        "Adaptive delay was 24.84 s.",
        "Adaptive delay was 24.8 s.",
        "Adaptive delay was 25 s.",
        "Delay fell by 6.6 s.",
        "It was preferred in 75% of conditions.",
        "Interval -9.1 to -4.2 over 144 runs.",
        "Sampled 240 conditions.",
        "Uses p95 delay on A2 at v3.",
        "No numbers here.",
    ],
)
def test_grounded_texts(text):
    assert check_grounded_summary(text, NUMBERS).ok


@pytest.mark.parametrize(
    "text,bad",
    [
        ("Delay fell 37%.", ["37%"]),
        ("Adaptive delay was 24.9 s.", ["24.9"]),
        ("There were 145 runs.", ["145"]),
        ("Preferred in 76% of cases and 3 sites.", ["76%", "3"]),
        ("The flag counts as 1 run.", ["1"]),
    ],
)
def test_ungrounded_numbers_flagged(text, bad):
    report = check_grounded_summary(text, NUMBERS)
    assert not report.ok and report.ungrounded_tokens == bad


def test_exact_mode_disables_rounding():
    assert check_grounded_summary("24.8", NUMBERS, rounding=True).ok
    assert not check_grounded_summary("24.8", NUMBERS, rounding=False).ok
    assert check_grounded_summary("24.84", NUMBERS, rounding=False).ok


def test_allowed_numbers_and_sources():
    assert not check_grounded_summary("a 95% interval", NUMBERS).ok
    report = check_grounded_summary(
        "a 95% interval, 144 runs", NUMBERS, allowed_numbers=[95]
    )
    assert report.ok
    assert {f.source for f in report.grounded} == {"allowed", "$.runs"}


def test_assert_grounded_raises_with_numbers():
    assert_grounded("144 runs", NUMBERS)
    with pytest.raises(AssertionError, match="999"):
        assert_grounded("999 runs", NUMBERS)


def test_template_summary_is_grounded(qset):
    from src.copilot.interpretation import template_summary

    for item in (i for i in qset["items"] if i["kind"] == "summary"):
        ctx = item["context"]
        text = template_summary(ctx["numbers"], ctx["preferred"])
        assert check_grounded_summary(text, ctx["numbers"], allowed_numbers=[95]).ok, (
            text
        )


# ---- gate


def test_grounding_self_check_ok():
    assert gate.grounding_self_check() is None


def test_gate_passes_offline_and_writes_report(tmp_path, capsys):
    out = tmp_path / "r.json"
    assert gate.main(["--report", str(out)]) == 0
    report = json.loads(out.read_text())
    assert report["gate"] == "pass" and report["passRate"] == 1.0
    assert "GATE PASS" in capsys.readouterr().out


BAD_CLIENT = (
    "from src.copilot.eval_harness import LLMResponse\n"
    "class C:\n"
    "    def respond(self, r):\n"
    "        return LLMResponse('nothing useful')\n"
    "def make():\n"
    "    return C()\n"
)

ONE_WRONG_CLIENT = (
    "from src.copilot.eval_harness import DeterministicCopilotClient, LLMResponse\n"
    "class C(DeterministicCopilotClient):\n"
    "    def respond(self, r):\n"
    "        if r.question_id == 'p-01':\n"
    "            return LLMResponse('x')\n"
    "        return super().respond(r)\n"
    "def make():\n"
    "    return C()\n"
)


def test_gate_fails_below_threshold(tmp_path, monkeypatch, capsys):
    monkeypatch.syspath_prepend(str(tmp_path))
    (tmp_path / "badclient.py").write_text(BAD_CLIENT)
    assert gate.main(["--client", "badclient:make"]) == 1
    assert "GATE FAIL" in capsys.readouterr().out
    assert gate.main(["--client", "badclient:make", "--threshold", "0"]) == 0


def test_gate_threshold_boundary(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(tmp_path))
    (tmp_path / "onewrong.py").write_text(ONE_WRONG_CLIENT)
    # 10 of 11 items pass (0.909)
    assert gate.main(["--client", "onewrong:make", "--threshold", "0.9"]) == 0
    assert gate.main(["--client", "onewrong:make", "--threshold", "0.95"]) == 1


def test_gate_bad_input_exit_2(tmp_path):
    assert gate.main(["--threshold", "1.5"]) == 2
    assert gate.main(["--questions", str(tmp_path / "missing.json")]) == 2
    assert gate.main(["--client", "no_such_module:f"]) == 2
    assert gate.main(["--client", "nocolon"]) == 2
    bad = tmp_path / "bad.json"
    bad.write_text("{}")
    assert gate.main(["--questions", str(bad)]) == 2


def test_gate_fails_when_checker_is_broken(monkeypatch):
    monkeypatch.setattr(gate, "grounding_self_check", lambda: "checker broken")
    assert gate.main([]) == 1


def test_gate_runs_as_module_from_backend_dir():
    proc = subprocess.run(
        [sys.executable, "-m", "evals.gate"],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "GATE PASS" in proc.stdout
