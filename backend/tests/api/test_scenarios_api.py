"""V1.4 scenario documents through the API: validate, compile, run, the live
side-by-side comparison and the controlled comparison study."""

import copy
from typing import Any, Dict

from fastapi.testclient import TestClient

from src.main import _compile_dashboard_config, app
from src.snapshot.dual_orchestrator import DualSimulationOrchestrator

client = TestClient(app)


def _arm(lanes: int, vph: float) -> Dict[str, Any]:
    return {
        "lanes": lanes,
        "vehiclesPerHour": vph,
        "turning": {"left": 0.2, "straight": 0.6, "right": 0.2},
    }


SCENARIO: Dict[str, Any] = {
    "format": "urbanflow-scenario",
    "version": 1,
    "name": "API test",
    "junction": {"type": "fixed_time_signal"},
    "approaches": {
        "north": _arm(2, 300),
        "south": _arm(2, 200),
        "east": _arm(1, 120),
        "west": _arm(1, 120),
    },
    "vehicles": {"mix": {"car": 0.8, "bus": 0.1, "motorcycle": 0.1}},
    "roundabout": {"circulatingLanes": 2, "innerRadius": 12, "outerRadius": 22},
    "simulation": {"duration": 40, "warmup": 10, "seed": 11},
}


def test_validate_reports_validity_warnings_and_the_resolved_design() -> None:
    body = client.post(
        "/api/v1/scenarios/validate",
        json={"scenario": SCENARIO, "strategies": ["fixed_time", "roundabout"]},
    ).json()
    assert body["valid"], body["errors"]
    assert body["fingerprint"]
    assert any("exploratory" in w for w in body["warnings"])
    design = body["design"]["roundabout"]
    assert design["circulatingLanes"] == 2
    north = design["ringAssignment"]["north"]
    # Left inner (1), right outer (2), straight on the entry lane's own.
    assert {(r["lane"], r["movement"]): r["ringLane"] for r in north} == {
        (1, "left"): 1,
        (1, "straight"): 1,
        (2, "straight"): 2,
        (2, "right"): 2,
    }


def test_validate_explains_an_invalid_scenario_without_failing() -> None:
    bad = copy.deepcopy(SCENARIO)
    bad["vehicles"]["mix"] = {"car": 0.5, "bus": 0.1}
    response = client.post("/api/v1/scenarios/validate", json={"scenario": bad})
    assert response.status_code == 200
    body = response.json()
    assert not body["valid"]
    assert any("sum to 1.0" in e for e in body["errors"])


def test_compile_returns_the_exact_engine_configuration() -> None:
    body = client.post(
        "/api/v1/scenarios/compile",
        json={"scenario": SCENARIO, "strategy": "roundabout"},
    ).json()
    config = body["config"]
    assert config["geometry"] == {
        "intersectionType": "roundabout",
        "intersectionCenter": {"x": 0.0, "y": 0.0},
        "circulatingLanes": 2,
    }
    assert config["controller"]["innerRadius"] == 12
    assert config["scenario"]["strategy"] == "roundabout"


def test_compile_rejects_an_invalid_scenario_with_400() -> None:
    bad = copy.deepcopy(SCENARIO)
    bad["approaches"]["north"]["lanes"] = 3
    response = client.post(
        "/api/v1/scenarios/compile", json={"scenario": bad, "strategy": "fixed_time"}
    )
    assert response.status_code == 400
    assert "same number of lanes" in response.json()["error"]["message"]


def test_a_scenario_runs_through_the_versioned_simulations_endpoint() -> None:
    response = client.post(
        "/api/v1/simulations", json={"scenario": SCENARIO, "strategy": "adaptive"}
    )
    assert response.status_code == 201, response.text
    config = response.json()["config"]
    assert config["controller"]["signalControl"] == "adaptive"
    assert config["simulation"]["randomSeed"] == 11
    client.delete(f"/api/v1/simulations/{response.json()['simulationId']}")


def test_an_unknown_strategy_is_rejected() -> None:
    response = client.post(
        "/api/v1/simulations", json={"scenario": SCENARIO, "strategy": "magic"}
    )
    assert response.status_code == 400


def test_the_live_comparison_runs_both_designs_from_one_scenario() -> None:
    config = _compile_dashboard_config(
        {"intersectionType": "fixed_time_signal", "scenario": SCENARIO}, 1
    )
    orch = DualSimulationOrchestrator(config)
    ring = orch.config_roundabout
    assert ring["geometry"]["circulatingLanes"] == 2
    assert ring["controller"]["innerRadius"] == 12.0
    assert ring["controller"]["outerRadius"] == 22.0
    assert orch.engine_roundabout.network.circulating_lanes == 2
    assert (
        orch.engine_signal.network.lane_count(
            __import__("src.core.enums", fromlist=["Direction"]).Direction.EAST
        )
        == 1
    )
    # The scenario's own seed, not the payload's.
    assert config["simulation"]["randomSeed"] == 11


def test_the_live_config_endpoint_accepts_a_scenario() -> None:
    response = client.post(
        "/api/simulation/config",
        json={"intersectionType": "fixed_time_signal", "scenario": SCENARIO},
    )
    assert response.status_code == 200, response.text
    assert response.json()["randomSeed"] == 11


def test_the_live_config_endpoint_rejects_a_scenario_invalid_for_either_side() -> None:
    bad = copy.deepcopy(SCENARIO)
    bad["roundabout"] = {"circulatingLanes": 3}
    response = client.post(
        "/api/simulation/config",
        json={"intersectionType": "fixed_time_signal", "scenario": bad},
    )
    assert response.status_code == 400
    assert "not supported yet" in response.json()["error"]["message"]


def test_the_comparison_study_runs_a_scenario_with_controlled_inputs() -> None:
    response = client.post(
        "/api/v1/study/control-comparison/run",
        json={
            "scenario": SCENARIO,
            "strategies": ["fixed_time", "roundabout"],
            "numSeeds": 2,
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["study"] == "scenario-comparison"
    assert result["controls"] == ["fixed_time", "roundabout"]
    assert result["seeds"] == [11, 12]
    configs = result["compiledConfigs"]
    assert configs["fixed_time"]["traffic"] == configs["roundabout"]["traffic"]
    assert configs["fixed_time"]["simulation"] == configs["roundabout"]["simulation"]
    row = result["perSeed"][0]
    assert set(row["fixed_time"]["approachBreakdown"]) == {
        "north",
        "south",
        "east",
        "west",
    }
    assert "fixed_time_vs_roundabout" in result["results"][0]["delayComparisons"]


def test_the_study_rejects_built_in_settings_alongside_a_scenario() -> None:
    response = client.post(
        "/api/v1/study/control-comparison/run",
        json={"scenario": SCENARIO, "lanes": 2},
    )
    assert response.status_code == 422
