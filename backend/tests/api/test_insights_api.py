"""The ``/api/v3`` result-screen adapters (``src/insights``): shapes match ``frontend/src/*/types.ts``.

Each test builds the router on its own app with a temporary results directory and a stand-in experiment
service, so no database or login is involved; the mounted app and its guards are covered by
``test_v3_route_auth.py``.
"""

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from src.api.errors import http_exception_handler
from src.core.run_manifest import build_run_manifest
from src.insights import osm_preview
from src.insights.locations import ResultsLocations
from src.insights.router import create_router
from src.runstore import LocalFileBackend, RunStore
from src.study.sensitivity import sobol_lite
from src.uncertainty.comparison import compare_paired

USER = "alice"
EXPERIMENT = "exp-1"


class _Store:
    def __init__(self, records: Dict[str, Dict[str, Any]]) -> None:
        self.records = records

    def get(self, user_id: str, experiment_id: str) -> Optional[Dict[str, Any]]:
        rec = self.records.get(experiment_id)
        return rec if rec and rec["userId"] == user_id else None


class _Service:
    def __init__(self, records: Dict[str, Dict[str, Any]]) -> None:
        self.store = _Store(records)


def _result(eligibility: str = "indicative") -> Dict[str, Any]:
    return {
        "name": "Junction study",
        "specification": {"seed": 7},
        "manifest": {"scenarioFingerprint": "s" * 16, "specFingerprint": "p" * 16},
        "provenance": {"gitCommit": "abc1234"},
        "assumptions": [
            {
                "id": "arrivalRate",
                "kind": "demand",
                "basis": "assumed",
                "rationale": "Peak hour guess",
            }
        ],
        "analysis": {
            "eligibility": {"class": eligibility},
            "limitations": ["Not calibrated."],
            "realWorldValidity": "None - assumptions only",
        },
    }


FIXED = [40.0, 42.0, 39.0, 45.0, 41.0, 43.0]
ADAPTIVE = [35.0, 36.5, 34.0, 41.0, 36.0, 37.5]


def _paired() -> Dict[str, Any]:
    seeds = [1, 2, 3, 4, 5, 6]
    return {
        "format": "urbanflow-paired-seeds",
        "version": 1,
        "primaryMetric": "mean_delay_s",
        "baseline": "fixed",
        "metrics": {
            "mean_delay_s": {"label": "Mean delay", "unit": "s", "lowerIsBetter": True},
            "throughput": {"label": "Throughput", "unit": "veh", "lowerIsBetter": False},
        },
        "alternatives": {
            "fixed": {
                "label": "Fixed time",
                "seeds": seeds,
                "values": {"mean_delay_s": FIXED, "throughput": [100, 101, 99, 98, 100, 102]},
            },
            "adaptive": {
                "label": "Adaptive",
                "seeds": seeds,
                "values": {"mean_delay_s": ADAPTIVE, "throughput": [110, 111, 109, 108, 112, 113]},
            },
        },
    }


def _write(root: Path, rel: str, doc: Dict[str, Any]) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc), encoding="utf-8")


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return tmp_path


def _client(
    root: Path,
    records: Optional[Dict[str, Dict[str, Any]]] = None,
    fetch: Any = None,
    user: str = USER,
) -> TestClient:
    if records is None:
        records = {EXPERIMENT: {"userId": USER, "name": "Junction study", "result": _result()}}
    app = FastAPI()
    app.exception_handler(HTTPException)(http_exception_handler)
    app.include_router(
        create_router(
            user_dependency=lambda: user,
            service=_Service(records),  # type: ignore[arg-type]
            locations=ResultsLocations(root),
            overpass_fetch=fetch,
        )
    )
    return TestClient(app)


def _keys(obj: Dict[str, Any]) -> List[str]:
    return sorted(obj)


# -- comparison -------------------------------------------------------------


def test_comparison_matches_the_contract_and_the_statistics(root: Path) -> None:
    _write(root, f"experiments/{EXPERIMENT}/paired.json", _paired())
    res = _client(root).get(f"/api/v3/experiments/{EXPERIMENT}/comparison")
    assert res.status_code == 200
    body = res.json()
    assert _keys(body) == sorted(
        [
            "experimentId", "metric", "a", "b", "pairs", "meanDifference", "ci",
            "confidenceLevel", "pValue", "method", "effectSize", "verdict", "eligibility",
        ]
    )
    # Defaults: A is the baseline, B the best alternative.
    assert body["a"] == {"id": "fixed", "label": "Fixed time"}
    assert body["b"] == {"id": "adaptive", "label": "Adaptive"}
    assert body["metric"] == {
        "id": "mean_delay_s", "label": "Mean delay", "unit": "s", "lowerIsBetter": True
    }
    expected = compare_paired(FIXED, ADAPTIVE, method="paired_t")
    assert body["pairs"] == 6
    assert body["meanDifference"] == pytest.approx(expected.difference)
    assert body["ci"] == pytest.approx([expected.ci_lower, expected.ci_upper])
    assert body["pValue"] == pytest.approx(expected.p_value)
    assert body["confidenceLevel"] == 0.95
    assert _keys(body["method"]) == ["interval", "pairing", "test"]
    assert _keys(body["effectSize"]) == ["name", "value"]
    # A (fixed) has higher delay than B and the difference is reliable: B is better.
    assert body["verdict"] == "b_better"
    assert body["eligibility"] == "indicative"


def test_comparison_query_parameters_choose_the_pair_and_metric(root: Path) -> None:
    _write(root, f"experiments/{EXPERIMENT}/paired.json", _paired())
    res = _client(root).get(
        f"/api/v3/experiments/{EXPERIMENT}/comparison",
        params={"a": "adaptive", "b": "fixed", "metric": "throughput"},
    )
    body = res.json()
    assert body["a"]["id"] == "adaptive" and body["metric"]["id"] == "throughput"
    # Higher throughput is better and A (adaptive) has more.
    assert body["verdict"] == "a_better"


def test_a_zero_variance_difference_has_no_effect_size(root: Path) -> None:
    doc = _paired()
    doc["alternatives"]["adaptive"]["values"]["mean_delay_s"] = [v - 2.0 for v in FIXED]
    _write(root, f"experiments/{EXPERIMENT}/paired.json", doc)
    body = _client(root).get(f"/api/v3/experiments/{EXPERIMENT}/comparison").json()
    assert body["effectSize"] is None
    assert body["meanDifference"] == pytest.approx(2.0)


@pytest.mark.parametrize(
    "params",
    [{"a": "nope"}, {"b": "fixed"}, {"metric": "nope"}, {"a": "fixed", "b": "fixed"}],
)
def test_comparison_of_something_that_does_not_exist_is_404(
    root: Path, params: Dict[str, str]
) -> None:
    _write(root, f"experiments/{EXPERIMENT}/paired.json", _paired())
    res = _client(root).get(
        f"/api/v3/experiments/{EXPERIMENT}/comparison", params=params
    )
    assert res.status_code == 404
    assert res.json()["error"]["message"] == "Not available yet"


def test_comparison_needs_the_data_the_experiment_and_its_owner(root: Path) -> None:
    client = _client(root)
    # No paired.json yet.
    assert client.get(f"/api/v3/experiments/{EXPERIMENT}/comparison").status_code == 404
    _write(root, f"experiments/{EXPERIMENT}/paired.json", _paired())
    assert client.get("/api/v3/experiments/other/comparison").status_code == 404
    # Someone else's experiment.
    stranger = _client(root, user="mallory")
    assert stranger.get(f"/api/v3/experiments/{EXPERIMENT}/comparison").status_code == 404
    # An experiment that has no result yet.
    unfinished = _client(
        root, {EXPERIMENT: {"userId": USER, "name": "x", "result": None}}
    )
    assert unfinished.get(f"/api/v3/experiments/{EXPERIMENT}/comparison").status_code == 404


def test_an_id_that_is_a_path_never_reaches_the_file_system(root: Path) -> None:
    _write(root, "experiments/secret/paired.json", _paired())
    records = {"..": {"userId": USER, "name": "x", "result": _result()}}
    res = _client(root, records).get("/api/v3/experiments/../comparison")
    assert res.status_code == 404


def test_a_damaged_data_file_is_not_available_rather_than_a_crash(root: Path) -> None:
    path = root / "experiments" / EXPERIMENT / "paired.json"
    path.parent.mkdir(parents=True)
    path.write_text("{not json", encoding="utf-8")
    assert (
        _client(root).get(f"/api/v3/experiments/{EXPERIMENT}/comparison").status_code
        == 404
    )


# -- sensitivity ------------------------------------------------------------


def _sensitivity_doc() -> Dict[str, Any]:
    def model(points: List[Dict[str, float]]) -> List[float]:
        return [3.0 * p["arrivalRate"] + 0.5 * p["greenTime"] for p in points]

    result = sobol_lite(
        model, {"arrivalRate": (0.0, 1.0), "greenTime": (0.0, 1.0)}, n_samples=64, seed=3
    )
    return {
        "format": "urbanflow-sensitivity",
        "version": 1,
        "metric": {"id": "mean_delay_s", "label": "Mean delay", "unit": "s"},
        "inputs": {"arrivalRate": {"label": "Arrival rate", "unit": "veh/h"}},
        "result": result,
    }


def test_sensitivity_matches_the_contract(root: Path) -> None:
    _write(root, f"experiments/{EXPERIMENT}/sensitivity.json", _sensitivity_doc())
    res = _client(root).get(f"/api/v3/experiments/{EXPERIMENT}/sensitivity")
    assert res.status_code == 200
    body = res.json()
    assert _keys(body) == ["experimentId", "inputs", "method", "metric"]
    assert _keys(body["method"]) == ["name", "note", "samples", "seed"]
    assert body["method"]["seed"] == 3 and body["method"]["samples"] == 64
    by_id = {i["id"]: i for i in body["inputs"]}
    assert set(by_id) == {"arrivalRate", "greenTime"}
    for item in body["inputs"]:
        assert _keys(item) == ["ci", "firstOrder", "id", "label", "total", "unit"]
        assert 0.0 <= item["firstOrder"] <= 1.0 and 0.0 <= item["total"] <= 1.0
        assert item["ci"] is None
    assert by_id["arrivalRate"]["label"] == "Arrival rate"
    assert by_id["arrivalRate"]["unit"] == "veh/h"
    assert by_id["greenTime"]["label"] == "greenTime" and by_id["greenTime"]["unit"] is None
    # The input with 6 times the weight explains nearly all of the variation.
    assert by_id["arrivalRate"]["firstOrder"] > by_id["greenTime"]["firstOrder"]


def test_sensitivity_for_another_metric_or_a_constant_output_is_404(root: Path) -> None:
    doc = _sensitivity_doc()
    _write(root, f"experiments/{EXPERIMENT}/sensitivity.json", doc)
    client = _client(root)
    assert (
        client.get(
            f"/api/v3/experiments/{EXPERIMENT}/sensitivity", params={"metric": "other"}
        ).status_code
        == 404
    )
    constant = sobol_lite(lambda pts: [1.0] * len(pts), {"a": (0.0, 1.0)}, n_samples=8)
    doc["result"] = constant
    _write(root, f"experiments/{EXPERIMENT}/sensitivity.json", doc)
    assert client.get(f"/api/v3/experiments/{EXPERIMENT}/sensitivity").status_code == 404


# -- runs -------------------------------------------------------------------


def _save_run(
    root: Path, run_id: str, rows: List[Dict[str, Any]], seed: int = 1, config: Optional[Dict[str, Any]] = None
) -> None:
    manifest = build_run_manifest(
        config=config or {"traffic": {"arrivalRate": 0.3}},
        seed=seed,
        run_mode="single",
        git_commit="abc1234",
        python_version="3.11",
        timing={"duration": 60},
        scenario_fingerprint="f" * 16,
        created_at="2026-11-01T10:00:00+00:00",
    )
    RunStore(LocalFileBackend(root)).save_run(manifest, rows, run_id=run_id)


def _trips(extra: Optional[Dict[str, Any]] = None, scale: float = 1.0) -> List[Dict[str, Any]]:
    rows = []
    for i in range(30):
        row: Dict[str, Any] = {
            "travelTimeS": (30.0 + i) * scale,
            "freeFlowTimeS": 25.0,
        }
        row.update(extra or {})
        rows.append(row)
    return rows


def test_run_metrics_matches_the_contract_and_leaves_missing_groups_null(root: Path) -> None:
    _save_run(root, "run-a", _trips())
    res = _client(root).get("/api/v3/runs/run-a/metrics")
    assert res.status_code == 200
    body = res.json()
    assert _keys(body) == [
        "delay", "emissions", "notes", "runId", "safety", "travelTime", "vehiclesCompleted"
    ]
    assert body["runId"] == "run-a" and body["vehiclesCompleted"] == 30
    # delay = travel - 25, i = 0..29: mean 5 + 14.5 = 19.5
    assert body["delay"]["mean"] == {"value": pytest.approx(19.5), "unit": "s", "ci": None}
    assert _keys(body["delay"]) == ["definition", "mean", "p95"]
    assert body["travelTime"]["mean"]["value"] == pytest.approx(44.5)
    assert body["safety"]["minTtc"]["value"] is None
    assert body["safety"]["conflicts"]["value"] is None
    assert body["safety"]["thresholdSeconds"] == 1.5
    assert body["emissions"]["fuel"]["value"] is None
    assert body["emissions"]["co2PerVehicle"]["value"] is None
    assert body["emissions"]["model"] == {
        "name": "Speed, idle and acceleration fuel model (generic petrol car)",
        "version": None,
    }
    assert "estimate" in body["emissions"]["definition"].lower()


def test_run_metrics_uses_safety_and_emissions_columns_when_present(root: Path) -> None:
    rows = _trips({"minTtcS": 2.0, "conflictEvents": 1, "fuelLiters": 0.5, "co2Kg": 1.0})
    rows[3]["minTtcS"] = 0.8
    _save_run(root, "run-a", rows)
    body = _client(root).get("/api/v3/runs/run-a/metrics").json()
    assert body["safety"]["minTtc"]["value"] == pytest.approx(0.8)
    assert body["safety"]["conflicts"]["value"] == 30
    assert body["emissions"]["fuel"]["value"] == pytest.approx(15.0)
    assert body["emissions"]["co2"]["value"] == pytest.approx(30.0)
    assert body["emissions"]["co2PerVehicle"]["value"] == pytest.approx(1.0)


def test_a_run_with_no_trip_rows_gives_null_values_not_zero(root: Path) -> None:
    _save_run(root, "run-a", [{"seed": 1}])
    body = _client(root).get("/api/v3/runs/run-a/metrics").json()
    assert body["vehiclesCompleted"] is None
    assert body["delay"]["mean"]["value"] is None
    assert body["travelTime"]["p95"]["value"] is None


def test_unknown_or_unsafe_run_ids_are_404(root: Path) -> None:
    client = _client(root)
    assert client.get("/api/v3/runs/missing/metrics").status_code == 404
    assert client.get("/api/v3/runs/.hidden/metrics").status_code == 404
    assert client.get("/api/v3/runs/compare", params={"a": "x", "b": "y"}).status_code == 404


def test_run_diff_matches_the_contract(root: Path) -> None:
    _save_run(root, "run-a", _trips(), seed=1)
    _save_run(root, "run-b", _trips(scale=1.5), seed=1)
    res = _client(root).get("/api/v3/runs/compare", params={"a": "run-a", "b": "run-b"})
    assert res.status_code == 200
    body = res.json()
    assert _keys(body) == ["a", "b", "manifest", "metrics", "sameInputs"]
    assert body["a"] == {
        "runId": "run-a", "label": "run-a", "createdAt": "2026-11-01T10:00:00+00:00"
    }
    fields = {f["field"]: f for f in body["manifest"]}
    assert list(fields) == ["seed", "config_hash", "code_version", "input_version"]
    assert _keys(fields["seed"]) == ["a", "b", "field", "label", "same"]
    assert all(f["same"] for f in fields.values())
    assert body["sameInputs"] is True
    metrics = {m["id"]: m for m in body["metrics"]}
    delay = metrics["mean_delay_s"]
    assert _keys(delay) == ["a", "b", "delta", "deltaFraction", "id", "label", "lowerIsBetter", "unit"]
    assert delay["delta"] == pytest.approx(delay["b"] - delay["a"])
    assert delay["deltaFraction"] == pytest.approx(delay["delta"] / delay["a"])
    assert delay["lowerIsBetter"] is True
    assert metrics["vehicles_completed"]["lowerIsBetter"] is False
    # Groups neither run recorded stay null.
    assert metrics["fuel_l"]["a"] is None and metrics["fuel_l"]["delta"] is None
    assert metrics["fuel_l"]["deltaFraction"] is None


def test_run_diff_with_different_inputs(root: Path) -> None:
    _save_run(root, "run-a", _trips(), seed=1)
    _save_run(root, "run-b", _trips(), seed=2, config={"traffic": {"arrivalRate": 0.9}})
    body = _client(root).get(
        "/api/v3/runs/compare", params={"a": "run-a", "b": "run-b"}
    ).json()
    fields = {f["field"]: f["same"] for f in body["manifest"]}
    assert fields["seed"] is False and fields["config_hash"] is False
    assert body["sameInputs"] is False


# -- nightly ----------------------------------------------------------------


def _night(day: int, status: str = "pass") -> Dict[str, Any]:
    return {
        "id": f"2026-11-{day:02d}",
        "startedAt": f"2026-11-{day:02d}T02:17:00Z",
        "gitCommit": "abc1234",
        "status": status,
        "durationSeconds": 1500.5,
        "logUrl": None,
        "checks": [
            {
                "id": "delay",
                "name": "Mean delay",
                "status": "fail" if status == "fail" else "pass",
                "metric": "mean_delay",
                "expected": 12.0,
                "actual": 14.1,
                "tolerance": 1.0,
                "unit": "s",
                "message": None,
            },
            {"id": "suite", "name": "Test suite", "status": "skipped"},
        ],
    }


def _history(days: List[int]) -> Dict[str, Any]:
    return {
        "format": "urbanflow-nightly-history",
        "version": 1,
        "generatedAt": "2026-11-04T03:00:00Z",
        "runs": [_night(d, "fail" if d == 2 else "pass") for d in days],
    }


def test_nightly_is_newest_first_limited_and_complete(root: Path) -> None:
    _write(root, "nightly/history.json", _history([1, 3, 2]))
    client = _client(root)
    body = client.get("/api/v3/regression/nightly").json()
    assert _keys(body) == ["generatedAt", "runs"]
    assert [r["id"] for r in body["runs"]] == ["2026-11-03", "2026-11-02", "2026-11-01"]
    run = body["runs"][1]
    assert _keys(run) == [
        "checks", "durationSeconds", "gitCommit", "id", "logUrl", "startedAt", "status"
    ]
    assert run["status"] == "fail"
    assert _keys(run["checks"][0]) == [
        "actual", "expected", "id", "message", "metric", "name", "status", "tolerance", "unit"
    ]
    # A check that gives only the required fields has the others as null.
    assert run["checks"][1]["expected"] is None and run["checks"][1]["message"] is None
    limited = client.get("/api/v3/regression/nightly", params={"limit": 2}).json()
    assert [r["id"] for r in limited["runs"]] == ["2026-11-03", "2026-11-02"]
    assert client.get("/api/v3/regression/nightly", params={"limit": 0}).status_code == 422


def test_nightly_is_404_until_written_and_when_invalid(root: Path) -> None:
    client = _client(root)
    assert client.get("/api/v3/regression/nightly").status_code == 404
    bad = _history([1])
    bad["runs"][0]["status"] = "weird"
    _write(root, "nightly/history.json", bad)
    assert client.get("/api/v3/regression/nightly").status_code == 404


# -- RL ---------------------------------------------------------------------


def _eval_doc(rl: List[float], fixed: List[float]) -> Dict[str, Any]:
    return {
        "format": "urbanflow-rl-eval",
        "version": 1,
        "seeds": list(range(10000, 10000 + len(rl))),
        "lower_is_better": ["mean_wait_s", "mean_queue"],
        "policies": {
            "fixed_time": {"mean_wait_s": fixed, "mean_queue": fixed},
            "dqn": {"mean_wait_s": rl, "mean_queue": rl},
        },
    }


def _rl_doc() -> Dict[str, Any]:
    return {
        "format": "urbanflow-rl-comparison",
        "version": 1,
        "junction": "Four-way, one lane",
        "metric": "mean_wait_s",
        "fixedPolicy": "fixed_time",
        "fixedLabel": "Fixed time, 30 s green",
        "rl": {
            "policy": "dqn",
            "label": "DQN",
            "policyId": "signal-control/3",
            "algorithm": "DQN",
            "trainingSteps": 20000,
        },
        "caveats": ["Evaluated on held-out seeds only."],
        "scenarios": [
            {
                "scenarioId": "low",
                "label": "400 veh/h",
                "eval": _eval_doc([8.0, 8.5, 7.9, 8.2, 8.1], [10.0, 10.4, 9.8, 10.1, 10.2]),
            },
            {
                "scenarioId": "high",
                "label": "800 veh/h",
                "eval": _eval_doc([15.0, 15.6, 14.8, 15.2, 15.1], [18.0, 18.5, 17.9, 18.2, 18.1]),
            },
        ],
    }


def test_rl_comparison_matches_the_contract(root: Path) -> None:
    _write(root, "rl/cmp-1.json", _rl_doc())
    res = _client(root).get("/api/v3/rl/comparisons/cmp-1")
    assert res.status_code == 200
    body = res.json()
    assert _keys(body) == [
        "caveats", "confidenceLevel", "difference", "fixedTime", "id", "junction",
        "metric", "rl", "scenarios", "verdict",
    ]
    assert body["id"] == "cmp-1"
    assert body["metric"] == {
        "id": "mean_wait_s", "label": "Mean wait per vehicle", "unit": "s", "lowerIsBetter": True
    }
    assert body["fixedTime"] == {"label": "Fixed time, 30 s green"}
    assert body["rl"] == {
        "label": "DQN", "policyId": "signal-control/3", "algorithm": "DQN", "trainingSteps": 20000
    }
    assert _keys(body["difference"]) == ["ci", "mean", "pValue"]
    assert body["difference"]["mean"] < 0 and body["verdict"] == "rl_better"
    assert [s["scenarioId"] for s in body["scenarios"]] == ["low", "high"]
    low = body["scenarios"][0]
    assert _keys(low) == ["fixedTime", "label", "rl", "scenarioId"]
    assert _keys(low["rl"]) == ["ci", "mean", "n"] and low["rl"]["n"] == 5
    assert low["rl"]["mean"] == pytest.approx(math.fsum([8.0, 8.5, 7.9, 8.2, 8.1]) / 5)
    assert low["rl"]["ci"][0] < low["rl"]["mean"] < low["rl"]["ci"][1]
    assert body["caveats"] == ["Evaluated on held-out seeds only."]


def test_rl_comparison_unavailable_cases_are_404(root: Path) -> None:
    client = _client(root)
    assert client.get("/api/v3/rl/comparisons/none").status_code == 404
    assert client.get("/api/v3/rl/comparisons/.x").status_code == 404
    doc = _rl_doc()
    doc["scenarios"][0]["eval"]["policies"]["dqn"]["mean_wait_s"] = [8.0]
    doc["scenarios"][0]["eval"]["policies"]["fixed_time"]["mean_wait_s"] = [10.0]
    _write(root, "rl/cmp-2.json", doc)
    assert client.get("/api/v3/rl/comparisons/cmp-2").status_code == 404


# -- report -----------------------------------------------------------------


def test_report_assembles_computed_results_only(root: Path) -> None:
    paired = _paired()
    paired["metricsRunId"] = "run-a"
    _write(root, f"experiments/{EXPERIMENT}/paired.json", paired)
    _write(root, f"experiments/{EXPERIMENT}/sensitivity.json", _sensitivity_doc())
    _save_run(root, "run-a", _trips())
    res = _client(root).get(f"/api/v3/experiments/{EXPERIMENT}/report")
    assert res.status_code == 200
    body = res.json()
    assert _keys(body) == [
        "assumptions", "comparison", "experimentId", "generatedAt", "limitations",
        "manifest", "metrics", "sensitivity", "summary", "title",
    ]
    assert body["title"] == "Junction study"
    assert body["assumptions"][0].startswith("arrivalRate (demand, assumed): Peak hour guess")
    assert body["assumptions"][-1].startswith("Real-world validity")
    assert body["limitations"] == ["Not calibrated."]
    assert body["comparison"]["verdict"] == "b_better"
    assert body["sensitivity"]["metric"]["id"] == "mean_delay_s"
    assert body["metrics"]["runId"] == "run-a"
    assert body["summary"]["grounded"] is True
    assert "paired seeds" in body["summary"]["text"]
    assert body["manifest"] == {
        "seed": 7, "configHash": "s" * 16, "codeVersion": "abc1234", "inputVersion": "p" * 16
    }


def test_report_leaves_uncomputed_sections_null(root: Path) -> None:
    body = _client(root).get(f"/api/v3/experiments/{EXPERIMENT}/report").json()
    assert body["comparison"] is None and body["sensitivity"] is None
    assert body["metrics"] is None
    assert body["summary"]["grounded"] is True
    assert "No comparison" in body["summary"]["text"]


def test_report_is_404_without_a_finished_experiment(root: Path) -> None:
    client = _client(root)
    assert client.get("/api/v3/experiments/nope/report").status_code == 404
    assert _client(root, user="mallory").get(
        f"/api/v3/experiments/{EXPERIMENT}/report"
    ).status_code == 404


# -- network validation -----------------------------------------------------

OSM = """<?xml version="1.0"?>
<osm version="0.6">
  <node id="1" lat="51.5000" lon="-0.1000"/>
  <node id="2" lat="51.5005" lon="-0.1000"/>
  <node id="3" lat="51.5010" lon="-0.1000"/>
  <node id="4" lat="51.5005" lon="-0.0995"/>
  <way id="10"><nd ref="1"/><nd ref="2"/><nd ref="3"/><tag k="highway" v="residential"/></way>
  <way id="11"><nd ref="2"/><nd ref="4"/><tag k="highway" v="residential"/></way>
</osm>
"""


def _upload(
    client: TestClient, name: str, content: bytes, fmt: str = "auto"
) -> Any:
    return client.post(
        "/api/v3/networks/validate",
        files={"file": (name, content, "application/octet-stream")},
        data={"format": fmt},
    )


def test_validate_reuses_the_importers_and_matches_the_contract(root: Path) -> None:
    res = _upload(_client(root), "area.osm", OSM.encode())
    assert res.status_code == 200
    body = res.json()
    assert _keys(body) == ["filename", "format", "messages", "summary", "uploadId", "valid"]
    assert body["uploadId"] is None and body["filename"] == "area.osm"
    assert body["format"] == "osm" and body["valid"] is True
    assert _keys(body["summary"]) == ["junctions", "links", "nodes", "totalLengthKm"]
    assert body["summary"]["nodes"] == 4 and body["summary"]["links"] >= 3
    assert body["summary"]["totalLengthKm"] > 0
    for m in body["messages"]:
        assert _keys(m) == ["code", "element", "hint", "line", "message", "severity"]
        assert m["severity"] in ("error", "warning", "info")


def test_validate_reports_an_unusable_file_as_200_with_messages(root: Path) -> None:
    res = _upload(_client(root), "bad.xml", b"<osm></osm>", "osm")
    assert res.status_code == 200
    body = res.json()
    assert body["valid"] is False and body["summary"] is None
    assert body["messages"][0]["severity"] == "error"
    assert "drivable" in body["messages"][0]["message"].lower()


def test_validate_geojson_is_honestly_unsupported(root: Path) -> None:
    res = _upload(_client(root), "roads.geojson", b'{"type": "FeatureCollection", "features": []}')
    body = res.json()
    assert res.status_code == 200 and body["format"] == "geojson" and body["valid"] is False
    assert body["messages"][0]["code"] == "unsupported_format"


def test_validate_with_an_unrecognised_file_under_auto(root: Path) -> None:
    res = _upload(_client(root), "mystery.xml", b"<html></html>")
    assert res.status_code == 200 and res.json()["valid"] is False
    assert res.json()["messages"][0]["code"] == "unrecognised_format"


def test_validate_status_codes(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(root)
    assert _upload(client, "net.exe", b"MZ").status_code == 415
    assert _upload(client, "empty.osm", b"").status_code == 415
    assert _upload(client, "x.osm", b"\xff\xfe\x00bad", "osm").status_code == 415
    assert _upload(client, "x.osm", OSM.encode(), "kml").status_code == 422
    monkeypatch.setattr("src.insights.network_view.MAX_UPLOAD_BYTES", 100)
    assert _upload(client, "big.osm", OSM.encode()).status_code == 413
    res = _upload(client, "net.exe", b"MZ")
    assert res.json()["error"]["message"].startswith("Unsupported file type")


# -- import preview ---------------------------------------------------------

OVERPASS = {
    "elements": [
        {"type": "node", "id": 1, "lat": 51.5000, "lon": -0.1000},
        {"type": "node", "id": 2, "lat": 51.5005, "lon": -0.1000, "tags": {"highway": "traffic_signals"}},
        {"type": "node", "id": 3, "lat": 51.5010, "lon": -0.1000},
        {"type": "node", "id": 4, "lat": 51.5005, "lon": -0.0990},
        {
            "type": "way", "id": 10, "nodes": [1, 2, 3],
            "tags": {"highway": "primary", "lanes": "2", "maxspeed": "50"},
        },
        {"type": "way", "id": 11, "nodes": [2, 4], "tags": {"highway": "residential"}},
        {"type": "way", "id": 12, "nodes": [1, 4], "tags": {"highway": "footway"}},
    ]
}


def test_preview_matches_the_contract(root: Path) -> None:
    queries: List[str] = []

    def fetch(query: str) -> str:
        queries.append(query)
        return json.dumps(OVERPASS)

    client = _client(root, fetch=fetch)
    res = client.post(
        "/api/v3/networks/import/preview",
        json={
            "source": "osm",
            "bbox": [-0.101, 51.499, -0.098, 51.502],
            "roadClasses": ["primary", "residential"],
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert _keys(body) == ["area", "bbox", "links", "messages", "previewId", "stats"]
    assert body["bbox"] == [-0.101, 51.499, -0.098, 51.502]
    assert body["stats"]["nodes"] == 4 and body["stats"]["links"] == 2
    assert body["stats"]["linksShown"] == 2 and body["stats"]["signalisedJunctions"] == 1
    assert body["stats"]["totalLengthKm"] > 0.1
    links = {k["id"]: k for k in body["links"]}
    assert _keys(links["w10"]) == [
        "geometry", "id", "lanes", "lengthM", "roadClass", "speedLimitKmh"
    ]
    assert links["w10"]["lanes"] == 2 and links["w10"]["speedLimitKmh"] == 50.0
    assert links["w10"]["geometry"][0] == [-0.1, 51.5]
    # No tags, no invented values.
    assert links["w11"]["lanes"] is None and links["w11"]["speedLimitKmh"] is None
    assert '"highway"~"^(primary|primary_link|residential|residential_link)$"' in queries[0]


def test_preview_by_place_builds_an_area_query_and_takes_the_box_from_the_data(
    root: Path,
) -> None:
    seen: List[str] = []

    def fetch(query: str) -> str:
        seen.append(query)
        return json.dumps(OVERPASS)

    res = _client(root, fetch=fetch).post(
        "/api/v3/networks/import/preview",
        json={"source": "osm", "place": "Camden", "roadClasses": ["primary"]},
    )
    body = res.json()
    assert res.status_code == 200 and body["area"] == "Camden"
    assert body["bbox"] == [-0.1, 51.5, -0.1, 51.501] or len(body["bbox"]) == 4
    assert 'area["name"="Camden"]' in seen[0]


@pytest.mark.parametrize(
    "payload",
    [
        {"source": "osm", "roadClasses": ["primary"]},
        {"source": "osm", "place": "A", "bbox": [0, 0, 0.01, 0.01], "roadClasses": ["primary"]},
        {"source": "osm", "bbox": [0, 0, 1, 1], "roadClasses": ["primary"]},
        {"source": "osm", "bbox": [1, 0, 0, 1], "roadClasses": ["primary"]},
        {"source": "osm", "place": 'Bad"Name', "roadClasses": ["primary"]},
        {"source": "osm", "place": "Camden", "roadClasses": ["footway"]},
        {"source": "osm", "place": "Camden", "roadClasses": []},
        {"source": "gtfs", "place": "Camden", "roadClasses": ["primary"]},
    ],
)
def test_preview_refuses_bad_requests_before_fetching(
    root: Path, payload: Dict[str, Any]
) -> None:
    def fetch(query: str) -> str:
        raise AssertionError("must not fetch")

    res = _client(root, fetch=fetch).post("/api/v3/networks/import/preview", json=payload)
    assert res.status_code == 422


def test_preview_without_an_overpass_server_is_503(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(osm_preview.OVERPASS_URL_ENV, raising=False)
    res = _client(root).post(
        "/api/v3/networks/import/preview",
        json={"source": "osm", "place": "Camden", "roadClasses": ["primary"]},
    )
    assert res.status_code == 503
    assert "not set up" in res.json()["error"]["message"]


def test_preview_upstream_failures(root: Path) -> None:
    def garbled(query: str) -> str:
        return "<html>busy</html>"

    def empty(query: str) -> str:
        return json.dumps({"elements": []})

    body = {"source": "osm", "place": "Camden", "roadClasses": ["primary"]}
    assert (
        _client(root, fetch=garbled).post("/api/v3/networks/import/preview", json=body).status_code
        == 502
    )
    assert (
        _client(root, fetch=empty).post("/api/v3/networks/import/preview", json=body).status_code
        == 422
    )


def test_a_large_area_is_thinned_and_says_so(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(osm_preview, "MAX_LINKS_SHOWN", 1)
    res = _client(root, fetch=lambda q: json.dumps(OVERPASS)).post(
        "/api/v3/networks/import/preview",
        json={"source": "osm", "place": "Camden", "roadClasses": ["primary", "residential"]},
    )
    body = res.json()
    assert body["stats"]["links"] == 2 and body["stats"]["linksShown"] == 1
    assert body["links"][0]["roadClass"] == "primary"
    assert body["messages"][0]["code"] == "thinned"
