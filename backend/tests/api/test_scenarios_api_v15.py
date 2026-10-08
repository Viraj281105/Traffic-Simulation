"""V1.5 real-world junctions through the API: validate, compile, run, the
live side-by-side comparison and the controlled comparison study."""

from typing import Any, Dict

from fastapi.testclient import TestClient

from src.core.enums import Direction
from src.main import _compile_dashboard_config, app
from src.snapshot.dual_orchestrator import DualSimulationOrchestrator

client = TestClient(app)

T_JUNCTION: Dict[str, Any] = {
    "format": "urbanflow-scenario",
    "version": 1,
    "name": "T-junction",
    "junction": {"type": "fixed_time_signal"},
    "approaches": {
        "north": None,
        "south": {
            "lanes": 1,
            "vehiclesPerHour": 300,
            "turning": {"left": 0.5, "straight": 0, "right": 0.5},
        },
        "east": {
            "lanes": 1,
            "vehiclesPerHour": 400,
            "bearing": 80,
            "turning": {"left": 0.3, "straight": 0.7, "right": 0},
        },
        "west": {
            "lanes": 1,
            "vehiclesPerHour": 400,
            "laneWidth": 3.2,
            "turning": {"left": 0, "straight": 0.7, "right": 0.3},
        },
    },
    "simulation": {"duration": 40, "warmup": 10, "seed": 7},
}


def test_validate_returns_the_laid_out_geometry() -> None:
    body = client.post(
        "/api/v1/scenarios/validate",
        json={"scenario": T_JUNCTION, "strategies": ["fixed_time", "roundabout"]},
    ).json()
    assert body["valid"], body["errors"]
    geometry = body["design"]["fixed_time"]["geometry"]
    assert set(geometry) == {"south", "east", "west"}
    assert geometry["east"]["bearing"] == 80
    assert geometry["west"]["laneWidth"] == 3.2


def test_validate_explains_an_impossible_movement() -> None:
    bad = {**T_JUNCTION, "approaches": dict(T_JUNCTION["approaches"])}
    bad["approaches"]["south"] = {
        **T_JUNCTION["approaches"]["south"],
        "turning": {"left": 0.4, "straight": 0.2, "right": 0.4},
    }
    body = client.post("/api/v1/scenarios/validate", json={"scenario": bad}).json()
    assert body["valid"] is False
    assert any("into a slot this junction has no arm in" in e for e in body["errors"])


def test_compile_and_run_a_three_arm_junction() -> None:
    compiled = client.post(
        "/api/v1/scenarios/compile",
        json={"scenario": T_JUNCTION, "strategy": "roundabout"},
    ).json()["config"]
    assert compiled["geometry"]["arms"] == ["south", "east", "west"]
    response = client.post(
        "/api/v1/simulations", json={"scenario": T_JUNCTION, "strategy": "fixed_time"}
    )
    assert response.status_code == 201, response.text
    client.delete(f"/api/v1/simulations/{response.json()['simulationId']}")


def test_the_live_comparison_builds_both_designs_without_the_missing_arm() -> None:
    config = _compile_dashboard_config(
        {"intersectionType": "fixed_time_signal", "scenario": T_JUNCTION}, 1
    )
    orch = DualSimulationOrchestrator(config)
    for engine in (orch.engine_signal, orch.engine_roundabout):
        assert engine.network.lane_count(Direction.NORTH) == 0
        assert set(engine.network.geometry.arms) == {
            Direction.SOUTH,
            Direction.EAST,
            Direction.WEST,
        }


def test_the_comparison_study_reports_only_the_arms_that_exist() -> None:
    response = client.post(
        "/api/v1/study/control-comparison/run",
        json={
            "scenario": T_JUNCTION,
            "strategies": ["fixed_time", "adaptive", "roundabout"],
            "numSeeds": 2,
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()
    configs = result["compiledConfigs"]
    assert configs["fixed_time"]["traffic"] == configs["roundabout"]["traffic"]
    assert configs["fixed_time"]["roads"] == configs["adaptive"]["roads"]
    for row in result["perSeed"]:
        for strategy in ("fixed_time", "adaptive", "roundabout"):
            assert set(row[strategy]["approachBreakdown"]) == {"south", "east", "west"}
            assert row[strategy]["collisionCount"] == 0
