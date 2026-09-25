"""The reliability check repeats the dashboard's own scenario.

The comparison view's "How reliable is this?" step sends its scenario payload
(the same body it posts to /api/simulation/config) to the Monte Carlo
endpoint. These tests pin that the study then runs that scenario — its
duration, geometry, demand and timings — rather than the endpoint's fixed
study defaults, and that a malformed scenario is rejected like the live
dashboard would reject it.
"""

from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient

import src.main as main
from src.main import app

client = TestClient(app)

SCENARIO: Dict[str, Any] = {
    "intersectionSize": 11.0,
    "laneWidth": 3.5,
    "lanesNorth": 1,
    "lanesSouth": 1,
    "lanesEast": 1,
    "lanesWest": 1,
    "arrivalRate": 0.2,
    "duration": 40,
    "randomSeed": 42,
    "greenDuration": 20,
    "yellowDuration": 3,
    "allRedDuration": 2,
    "criticalGap": 4.5,
    "followUpTime": 2.8,
}


@pytest.fixture
def captured(monkeypatch) -> List[Dict[str, Any]]:
    """Records what the endpoint asks the study to run, without running it."""
    calls: List[Dict[str, Any]] = []

    def fake_validation(
        config=None,
        num_seeds=5,
        duration=30.0,
        time_step=0.1,
        confidence_level=0.95,
    ):
        calls.append(
            {
                "config": config,
                "num_seeds": num_seeds,
                "duration": duration,
                "confidence_level": confidence_level,
            }
        )
        return {"numSeeds": num_seeds, "duration": duration}

    monkeypatch.setattr(main, "run_statistical_validation", fake_validation)
    return calls


def test_scenario_runs_with_its_own_settings(captured) -> None:
    res = client.post(
        "/api/v1/study/validate/monte-carlo",
        json={"numSeeds": 3, "scenario": SCENARIO},
    )
    assert res.status_code == 200
    (call,) = captured
    config = call["config"]
    # The scenario's duration wins over the request's study default (30 s).
    assert call["duration"] == 40.0
    assert call["num_seeds"] == 3
    assert config["simulation"]["duration"] == 40.0
    # Same warm-up the live comparison uses.
    assert (
        config["simulation"]["warmupTime"]
        == main.DEFAULT_CONFIG["simulation"]["warmupTime"]
    )
    assert config["roads"]["lanesPerApproach"] == {
        "north": 1,
        "south": 1,
        "east": 1,
        "west": 1,
    }
    assert config["traffic"]["arrivalRate"] == 0.2
    # Both controls get the scenario's parameters: the signal its timings,
    # the roundabout its gap acceptance.
    assert config["controller"]["straightRightDuration"] == 20.0
    assert (
        config["controller"]["phaseSequence"]
        == main.DEFAULT_CONFIG["controller"]["phaseSequence"]
    )
    assert config["roundaboutController"] == {
        "criticalGap": 4.5,
        "followUpTime": 2.8,
    }


def test_scenario_keeps_split_corridor_greens(captured) -> None:
    res = client.post(
        "/api/v1/study/validate/monte-carlo",
        json={"scenario": {**SCENARIO, "nsGreenDuration": 30, "ewGreenDuration": 15}},
    )
    assert res.status_code == 200
    controller = captured[0]["config"]["controller"]
    assert controller["nsGreenDuration"] == 30.0
    assert controller["ewGreenDuration"] == 15.0


def test_invalid_scenario_is_rejected(captured) -> None:
    res = client.post(
        "/api/v1/study/validate/monte-carlo",
        json={"scenario": {**SCENARIO, "lanesNorth": 0}},
    )
    assert res.status_code == 400
    assert captured == []


def test_scenario_and_custom_config_are_exclusive(captured) -> None:
    res = client.post(
        "/api/v1/study/validate/monte-carlo",
        json={"scenario": SCENARIO, "customConfig": {"traffic": {}}},
    )
    assert res.status_code == 422
    assert captured == []


def test_scenario_study_really_runs_both_controls() -> None:
    """End to end on a short scenario: both controls, one result per seed."""
    res = client.post(
        "/api/v1/study/validate/monte-carlo",
        json={"numSeeds": 2, "scenario": {**SCENARIO, "duration": 12}},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["numSeeds"] == 2
    assert body["duration"] == 12.0
    assert len(body["seedRuns"]) == 2
    for key in ("delay", "throughput", "queue"):
        assert key in body["comparison"]
