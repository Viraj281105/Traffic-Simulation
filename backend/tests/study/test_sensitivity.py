"""Sensitivity analysis: maths on analytic models, then the API contract."""

from typing import Dict, List

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.study import metrics_router
from src.study.sensitivity import apply_inputs, one_at_a_time, sobol_lite

BOUNDS = {"a": (0.0, 1.0), "b": (0.0, 1.0), "c": (0.0, 1.0)}


def _model(points: List[Dict[str, float]]) -> List[float]:
    # a matters most, b a little, c not at all.
    return [10.0 * p["a"] + 1.0 * p["b"] + 0.0 * p["c"] for p in points]


def test_oat_ranks_the_dominant_input_first() -> None:
    out = one_at_a_time(_model, BOUNDS)
    assert [r["input"] for r in out["ranking"]] == ["a", "b", "c"]
    assert out["ranking"][0]["swing"] == pytest.approx(10.0)
    assert out["ranking"][0]["share"] == pytest.approx(10.0 / 11.0)
    assert out["ranking"][2]["share"] == pytest.approx(0.0)
    assert out["evaluations"] == 7
    assert out["baseline"] == {"a": 0.5, "b": 0.5, "c": 0.5}
    assert out["ranking"][0]["rank"] == 1


def test_oat_custom_baseline_and_flat_model() -> None:
    out = one_at_a_time(lambda ps: [1.0] * len(ps), BOUNDS, {"a": 0.1})
    assert out["baseline"]["a"] == 0.1
    assert all(r["share"] is None for r in out["ranking"])


def test_sobol_matches_analytic_additive_model() -> None:
    # Var = 100/12 + 1/12; S1(a) = 100/101, S1(b) = 1/101, S1(c) = 0.
    out = sobol_lite(_model, BOUNDS, n_samples=2000, seed=3)
    by = {r["input"]: r for r in out["ranking"]}
    assert [r["input"] for r in out["ranking"]] == ["a", "b", "c"]
    assert by["a"]["firstOrder"] == pytest.approx(100 / 101, abs=0.05)
    assert by["a"]["totalOrder"] == pytest.approx(100 / 101, abs=0.05)
    assert by["b"]["totalOrder"] == pytest.approx(1 / 101, abs=0.05)
    assert abs(by["c"]["totalOrder"]) < 0.02
    assert out["evaluations"] == 2000 * 5


def test_sobol_detects_interaction() -> None:
    def product(points: List[Dict[str, float]]) -> List[float]:
        return [p["a"] * p["b"] for p in points]

    out = sobol_lite(product, {"a": (0, 1), "b": (0, 1)}, n_samples=3000, seed=1)
    for r in out["ranking"]:
        assert r["totalOrder"] > r["firstOrder"]


def test_sobol_is_reproducible_from_seed() -> None:
    a = sobol_lite(_model, BOUNDS, 16, seed=7)
    assert a == sobol_lite(_model, BOUNDS, 16, seed=7)
    assert a != sobol_lite(_model, BOUNDS, 16, seed=8)


def test_sobol_constant_model_has_no_indices() -> None:
    out = sobol_lite(lambda ps: [2.0] * len(ps), BOUNDS, 4, seed=0)
    assert all(r["totalOrder"] is None for r in out["ranking"])


def test_bad_ranges_rejected() -> None:
    with pytest.raises(ValueError):
        one_at_a_time(_model, {"a": (1.0, 1.0)})
    with pytest.raises(ValueError):
        sobol_lite(_model, {}, 4)
    with pytest.raises(ValueError):
        sobol_lite(_model, BOUNDS, 1)


def test_apply_inputs_writes_paths_without_mutating() -> None:
    base = {"traffic": {"arrivalRate": 0.2}}
    cfg = apply_inputs(
        base, {"arrivalRate": 0.4, "greenTime": 25.0, "lanesPerApproach": 2.4}
    )
    assert cfg["traffic"]["arrivalRate"] == 0.4
    assert cfg["controller"]["greenTime"] == 25.0
    assert cfg["roads"]["lanesPerApproach"] == {
        "north": 2,
        "south": 2,
        "east": 2,
        "west": 2,
    }
    assert base == {"traffic": {"arrivalRate": 0.2}}
    with pytest.raises(ValueError):
        apply_inputs(base, {"bogus": 1.0})


# -- API ---------------------------------------------------------------------
@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.include_router(metrics_router.router)
    return TestClient(app)


def test_api_trips(client: TestClient) -> None:
    r = client.post(
        "/api/v1/metrics/trips",
        json={"trips": [{"travelTimeS": 20, "freeFlowTimeS": 10}]},
    )
    assert r.status_code == 200
    assert r.json()["meanDelayS"] == 10.0


def test_api_emissions_and_ttc(client: TestClient) -> None:
    r = client.post("/api/v1/metrics/emissions", json={"dt": 1, "speedsMps": [[0, 10]]})
    assert r.status_code == 200 and r.json()["isEstimate"] is True
    r = client.post(
        "/api/v1/metrics/ttc",
        json={
            "dt": 0.1,
            "pairs": [[{"gapM": 5, "followerSpeedMps": 15, "leaderSpeedMps": 5}]],
        },
    )
    assert r.status_code == 200
    assert r.json()["conflictEvents"] == 1 and r.json()["isProxy"] is True
    bad = client.post("/api/v1/metrics/emissions", json={"dt": 0, "speedsMps": []})
    assert bad.status_code == 422


def test_api_sensitivity_validation(client: TestClient) -> None:
    bad = {"ranges": {"nope": {"low": 0, "high": 1}}}
    assert client.post("/api/v1/study/sensitivity", json=bad).status_code == 422
    inverted = {"ranges": {"arrivalRate": {"low": 1, "high": 0.5}}}
    assert client.post("/api/v1/study/sensitivity", json=inverted).status_code == 422
    too_big = {
        "method": "sobol",
        "sobolSamples": 32,
        "numSeeds": 5,
        "ranges": {"arrivalRate": {"low": 0.1, "high": 0.5}},
    }
    assert client.post("/api/v1/study/sensitivity", json=too_big).status_code == 422
    info = client.get("/api/v1/study/sensitivity/inputs").json()
    assert "arrivalRate" in info["inputs"]


def test_api_sensitivity_runs_simulation_and_is_reproducible(
    client: TestClient,
) -> None:
    body = {
        "method": "oat",
        "duration": 12,
        "numSeeds": 1,
        "seed": 4,
        "output": "throughput",
        "ranges": {
            "arrivalRate": {"low": 0.05, "high": 0.6},
            "greenTime": {"low": 15, "high": 40},
        },
    }
    r1 = client.post("/api/v1/study/sensitivity", json=body)
    assert r1.status_code == 200, r1.text
    data = r1.json()
    assert data["evaluations"] == 5 and len(data["ranking"]) == 2
    assert data["ranking"][0]["input"] == "arrivalRate"
    assert client.post("/api/v1/study/sensitivity", json=body).json() == data
