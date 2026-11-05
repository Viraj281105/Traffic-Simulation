import json
from pathlib import Path
from typing import Any, Dict, List

import produce_rl_comparison as pr  # noqa: E402
import pytest

from tests.producers import _helpers as h


def _eval(rl: List[float], fixed: List[float]) -> Dict[str, Any]:
    return {
        "format": "urbanflow-rl-eval",
        "version": 1,
        "seeds": list(range(10000, 10000 + len(rl))),
        "lower_is_better": ["mean_wait_s"],
        "policies": {
            "fixed_time": {"mean_wait_s": fixed},
            "rl_dqn": {"mean_wait_s": rl},
        },
    }


def _kwargs(**over: Any) -> Dict[str, Any]:
    base: Dict[str, Any] = dict(
        junction="Four-way, one lane",
        metric="mean_wait_s",
        rl_policy="rl_dqn",
        rl_label="DQN",
        policy_id="signal-control/3",
        algorithm="DQN",
        training_steps=20000,
        scenarios=[
            ("low", "400 veh/h", _eval([8.0, 8.5, 7.9, 8.2], [10.0, 10.4, 9.8, 10.1])),
            (
                "high",
                "800 veh/h",
                _eval([15.0, 15.6, 14.8, 15.2], [18.0, 18.5, 17.9, 18.2]),
            ),
        ],
        caveats=["One simulator."],
    )
    base.update(over)
    return base


def test_build_rl_doc_shape() -> None:
    doc = pr.build_rl_doc(**_kwargs(generated_at="2026-11-04T00:00:00Z"))
    assert (
        doc["format"] == "urbanflow-rl-comparison"
        and doc["fixedPolicy"] == "fixed_time"
    )
    assert doc["rl"] == {
        "policy": "rl_dqn",
        "label": "DQN",
        "policyId": "signal-control/3",
        "algorithm": "DQN",
        "trainingSteps": 20000,
    }
    assert [s["scenarioId"] for s in doc["scenarios"]] == ["low", "high"]
    assert doc["scenarios"][0]["eval"]["format"] == "urbanflow-rl-eval"
    assert doc["caveats"] == ["One simulator."]


def test_build_rl_doc_refuses_bad_input() -> None:
    with pytest.raises(ValueError, match="at least one"):
        pr.build_rl_doc(**_kwargs(scenarios=[]))
    with pytest.raises(ValueError, match="rl_ppo"):
        pr.build_rl_doc(**_kwargs(rl_policy="rl_ppo"))
    with pytest.raises(ValueError, match="at least two"):
        pr.build_rl_doc(**_kwargs(scenarios=[("a", "A", _eval([1.0], [2.0]))]))
    with pytest.raises(ValueError, match="different numbers"):
        pr.build_rl_doc(
            **_kwargs(scenarios=[("a", "A", _eval([1.0, 2.0], [2.0, 3.0, 4.0]))])
        )
    with pytest.raises(ValueError, match="duplicate"):
        s = ("a", "A", _eval([1.0, 2.0], [2.0, 3.0]))
        pr.build_rl_doc(**_kwargs(scenarios=[s, s]))
    with pytest.raises(ValueError, match="urbanflow-rl-eval"):
        pr.build_rl_doc(**_kwargs(scenarios=[("a", "A", {"format": "x"})]))


def test_parse_scenario_reads_the_eval_file(tmp_path: Path) -> None:
    f = tmp_path / "low.json"
    f.write_text(json.dumps(_eval([1.0, 2.0], [2.0, 3.0])), encoding="utf-8")
    sid, label, ev = pr.parse_scenario(f"low=400 veh/h={f}")
    assert (sid, label, ev["format"]) == ("low", "400 veh/h", "urbanflow-rl-eval")
    for bad in ("low", f"low={f}", "low=x=" + str(tmp_path / "missing.json")):
        with pytest.raises(ValueError):
            pr.parse_scenario(bad)


def test_end_to_end_file_passes_the_rl_endpoint(tmp_path: Path) -> None:
    low, high = tmp_path / "low.json", tmp_path / "high.json"
    low.write_text(
        json.dumps(_eval([8.0, 8.5, 7.9, 8.2], [10.0, 10.4, 9.8, 10.1])),
        encoding="utf-8",
    )
    high.write_text(
        json.dumps(_eval([15.0, 15.6, 14.8, 15.2], [18.0, 18.5, 17.9, 18.2])),
        encoding="utf-8",
    )
    out = tmp_path / "results"
    code = pr.main(
        [
            "--id",
            "cmp-1",
            "--junction",
            "Four-way, one lane",
            "--scenario",
            f"low=400 veh/h={low}",
            "--scenario",
            f"high=800 veh/h={high}",
            "--rl-label",
            "DQN",
            "--policy-id",
            "signal-control/3",
            "--algorithm",
            "DQN",
            "--training-steps",
            "20000",
            "--results-dir",
            str(out),
        ]
    )
    assert code == 0 and (out / "rl" / "cmp-1.json").is_file()
    assert b"\r" not in (out / "rl" / "cmp-1.json").read_bytes()
    body = h.client(out).get("/api/v3/rl/comparisons/cmp-1").json()
    assert body["verdict"] == "rl_better" and len(body["scenarios"]) == 2


def test_cli_error_exit_code(tmp_path: Path) -> None:
    code = pr.main(
        [
            "--id",
            "../x",
            "--junction",
            "j",
            "--scenario",
            "a=b=c",
            "--rl-label",
            "l",
            "--policy-id",
            "p",
            "--algorithm",
            "DQN",
            "--training-steps",
            "1",
            "--results-dir",
            str(tmp_path),
        ]
    )
    assert code == 2
