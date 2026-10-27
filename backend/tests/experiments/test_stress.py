"""Stress lab and breakpoint explorer (W8)."""

from __future__ import annotations

import time
from typing import Any, Dict, List

import pytest
from fastapi import FastAPI, Header, HTTPException
from fastapi.testclient import TestClient

from src.experiments import limits
from src.scenario.documents import validate_scenario
from src.stress.classify import classify
from src.stress.generator import FAMILIES, generate, generate_one, suite_fingerprint
from src.stress.lab import run_breakpoints, run_suite
from src.stress.router import create_router as create_stress_router
from src.stress.service import StressService, default_scenario

from .conftest import as_user

ALICE, BOB = "alice", "bob"


def metrics_for(task: Any) -> Dict[str, Any]:
    """A stand-in engine: delay depends on the strategy and the demand, so preferences can be planted."""
    strategy = task.config["scenario"]["strategy"]
    rate = task.config["traffic"]["arrivalRate"]
    delay = {"fixed_time": 10 + 100 * rate, "adaptive": 12 + 90 * rate}.get(
        strategy, 30 + 20 * rate
    )
    return {
        "metrics": {
            "averageDelay": delay,
            "throughput": 50,
            "totalVehiclesSpawned": 60,
            "maxQueueLength": 30 if rate > 1.0 else 5,
            "collisionCount": 0,
            "directionalFairnessIndex": 0.9,
        }
    }


def fake_executor(tasks: List[Any], progress: Any = None) -> List[Any]:
    return [metrics_for(t) for t in tasks]


# ---- generator --------------------------------------------------------------------------------------


def test_generation_is_reproducible_from_version_seed_and_index():
    assert generate(7, 10) == generate(7, 10)
    assert generate(7, 10) != generate(8, 10)
    assert generate_one(7, 3) == generate(7, 10)[3]
    assert suite_fingerprint(generate(7, 10)) == suite_fingerprint(generate(7, 10))
    with pytest.raises(ValueError):
        generate(1, 31)


def test_every_generated_scenario_passes_the_validators():
    families = set()
    for item in generate(11, 24):
        families.add(item["family"])
        result = validate_scenario(
            item["scenario"], ["fixed_time", "adaptive", "roundabout"]
        )
        assert result["valid"], (item["family"], result["errors"])
    assert families == set(FAMILIES)


# ---- classification ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "metrics,expected",
    [
        (
            {"collisionCount": 1, "throughput": 10, "totalVehiclesSpawned": 20},
            {"collision"},
        ),
        ({"throughput": 0, "totalVehiclesSpawned": 40}, {"gridlock"}),
        (
            {"vehicleLimitReached": True, "throughput": 30, "totalVehiclesSpawned": 40},
            {"vehicle_limit"},
        ),
        (
            {
                "directionalFairnessIndex": 0.1,
                "throughput": 30,
                "totalVehiclesSpawned": 40,
            },
            {"starvation"},
        ),
        (
            {"maxQueueLength": 22, "throughput": 30, "totalVehiclesSpawned": 40},
            {"excessive_queue"},
        ),
        (
            {"maxQueueLength": 27, "throughput": 30, "totalVehiclesSpawned": 40},
            {"excessive_queue", "spillback"},
        ),
        (
            {
                "maxQueueLength": 3,
                "throughput": 30,
                "totalVehiclesSpawned": 40,
                "directionalFairnessIndex": 0.95,
            },
            set(),
        ),
    ],
)
def test_planted_failures_are_classified(metrics, expected):
    assert set(classify(metrics, 200.0)) == expected


# ---- suites -----------------------------------------------------------------------------------------


def test_suite_counts_failures_per_strategy_and_skips_what_does_not_apply():
    result = run_suite(
        3,
        16,
        ["fixed_time", "roundabout", "signalised_roundabout"],
        1,
        120.0,
        fake_executor,
    )
    assert len(result["scenarios"]) == 16
    three_arm = [r for r in result["scenarios"] if r["family"] == "three_arm"]
    assert three_arm and all(
        r["results"]["signalised_roundabout"] == {"skipped": "not_applicable"}
        for r in three_arm
    )
    assert set(result["failureTotals"]) == {
        "fixed_time",
        "roundabout",
        "signalised_roundabout",
    }
    assert (
        result["failureTotals"]["fixed_time"]["excessive_queue"] >= 1
    )  # the over-capacity family
    assert result["generator"] == "stress-v1" and result["rules"]


# ---- breakpoints ------------------------------------------------------------------------------------


def test_a_planted_flip_is_recovered_between_the_right_levels():
    # 4 arms x 500 veh/h = 2000 veh/h = 0.556 veh/s. Fixed-time wins below rate 0.25, the roundabout above.
    levels = [0.2, 0.3, 0.4, 0.6, 0.8]
    result = run_breakpoints(
        default_scenario(),
        "demand_scale",
        levels,
        ["fixed_time", "roundabout"],
        1,
        3,
        fake_executor,
    )
    assert [row["preferred"] for row in result["table"]] == [
        "fixed_time",
        "fixed_time",
        "fixed_time",
        "roundabout",
        "roundabout",
    ]
    assert result["breakpoints"] == [
        {
            "between": [0.4, 0.6],
            "from": "fixed_time",
            "to": "roundabout",
            "confidence": 1.0,
        }
    ]
    assert result["tooFewToAssess"] is None


def test_too_few_levels_or_seeds_are_said_so():
    result = run_breakpoints(
        default_scenario(),
        "demand_scale",
        [0.5, 1.0],
        ["fixed_time", "roundabout"],
        1,
        1,
        fake_executor,
    )
    assert result["tooFewToAssess"] == [
        "fewer than 3 levels",
        "fewer than 2 seeds per level",
    ]


def test_aggression_is_a_factor_too():
    result = run_breakpoints(
        default_scenario(),
        "aggression",
        ["standard", "moderate", "high"],
        ["fixed_time", "adaptive"],
        2,
        2,
        fake_executor,
    )
    assert [row["level"] for row in result["table"]] == ["standard", "moderate", "high"]


def test_real_engine_suite_runs(monkeypatch):
    monkeypatch.setenv("STUDY_WORKERS", "0")
    result = run_suite(5, 2, ["fixed_time"], 1, 60.0)
    assert all(
        isinstance(r["results"]["fixed_time"].get("meanDelay"), float)
        for r in result["scenarios"]
    )


# ---- API ---------------------------------------------------------------------------------------------


@pytest.fixture
def api(make_service):
    service = make_service()
    lab = StressService(service, executor=fake_executor)
    app = FastAPI()

    def user(x_user: str = Header(default="")) -> str:
        if not x_user:
            raise HTTPException(status_code=401, detail="no user")
        return x_user

    app.include_router(create_stress_router(user_dependency=user, service=lab))
    return TestClient(app), service


def wait(client: TestClient, job: str) -> Dict[str, Any]:
    for _ in range(500):
        st = client.get(f"/api/v3/stress/jobs/{job}", headers=as_user(ALICE)).json()
        if st["status"] not in ("queued", "running"):
            return st
        time.sleep(0.02)
    raise AssertionError("job never finished")


def test_suite_and_breakpoint_jobs_through_the_api(api):
    client, service = api
    cat = client.get("/api/v3/stress/catalogue", headers=as_user(ALICE)).json()
    assert cat["maxScenarios"] == 30 and "spillback" in cat["failureRules"]
    job = client.post(
        "/api/v3/stress/suites",
        json={"count": 4, "seedsPerRun": 1},
        headers=as_user(ALICE),
    )
    assert job.status_code == 202
    jid = job.json()["id"]
    assert wait(client, jid)["status"] == "completed"
    assert (
        client.get(f"/api/v3/stress/jobs/{jid}/result", headers=as_user(ALICE)).json()[
            "format"
        ]
        == "urbanflow-stress-suite"
    )
    assert (
        client.get(f"/api/v3/stress/jobs/{jid}", headers=as_user(BOB)).status_code
        == 404
    )
    assert service.usage.used(ALICE) == pytest.approx(4 * 4 * 1 * 120)

    bp = client.post(
        "/api/v3/stress/breakpoints",
        json={"levels": [0.2, 0.4, 0.6], "strategies": ["fixed_time", "roundabout"]},
        headers=as_user(ALICE),
    )
    assert bp.status_code == 202
    assert wait(client, bp.json()["id"])["status"] == "completed"


def test_requests_are_bounded(api, monkeypatch):
    client, _service = api
    assert (
        client.post(
            "/api/v3/stress/suites", json={"count": 31}, headers=as_user(ALICE)
        ).status_code
        == 422
    )
    bad = client.post(
        "/api/v3/stress/breakpoints",
        json={"factor": "aggression", "levels": [1.0]},
        headers=as_user(ALICE),
    )
    assert bad.status_code == 422
    monkeypatch.setattr(limits, "MAX_DAILY_SIMULATED_SECONDS_PER_USER", 100)
    over = client.post(
        "/api/v3/stress/suites", json={"count": 4}, headers=as_user(ALICE)
    )
    assert (
        over.status_code == 429
        and "maxDailySimulatedSecondsPerUser" in over.json()["detail"]
    )
