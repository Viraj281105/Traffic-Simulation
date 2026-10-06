"""Adaptive signal control (V1.3) through the API: dashboard payload,
versioned configs, validation, live/dual snapshots and the three-way study."""

import time
from typing import Any, Dict

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from src.core.config_models import ScenarioConfiguration
from src.main import _compile_dashboard_config, app
from src.snapshot.dual_orchestrator import DualSimulationOrchestrator

client = TestClient(app)

SCENARIO: Dict[str, Any] = {
    "intersectionType": "fixed_time_signal",
    "intersectionSize": 11.0,
    "laneWidth": 3.5,
    "lanesNorth": 1,
    "lanesSouth": 1,
    "lanesEast": 1,
    "lanesWest": 1,
    "arrivalRate": 0.3,
    "duration": 60,
    "randomSeed": 42,
    "greenDuration": 30,
    "yellowDuration": 4,
    "allRedDuration": 2,
    "criticalGap": 4.0,
    "followUpTime": 2.5,
}


# ── Dashboard payload ─────────────────────────────────────────────────────


def test_fixed_time_payload_is_unchanged() -> None:
    plain = _compile_dashboard_config(dict(SCENARIO), 42)
    explicit = _compile_dashboard_config(
        {**SCENARIO, "signalControl": "fixed_time"}, 42
    )
    assert "signalControl" not in plain["controller"]
    assert explicit == plain


def test_adaptive_payload_compiles_to_the_signal_controller() -> None:
    config = _compile_dashboard_config(
        {**SCENARIO, "signalControl": "adaptive", "adaptive": {"maxGreen": 40}}, 42
    )
    ctrl = config["controller"]
    assert ctrl["signalControl"] == "adaptive"
    assert ctrl["adaptive"] == {"maxGreen": 40}
    # Same plan and clearance as the fixed-time signal.
    assert ctrl["phaseSequence"][0] == "ns_green"
    assert ctrl["yellowDuration"] == 4.0
    assert ctrl["allRedDuration"] == 2.0


def test_roundabout_payload_ignores_signal_control() -> None:
    config = _compile_dashboard_config(
        {**SCENARIO, "intersectionType": "roundabout", "signalControl": "adaptive"}, 42
    )
    assert "signalControl" not in config["controller"]


@pytest.mark.parametrize(
    "extra,message",
    [
        ({"signalControl": "smart"}, "signalControl must be"),
        ({"signalControl": "adaptive", "adaptive": [10]}, "adaptive must be an object"),
        (
            {"signalControl": "adaptive", "adaptive": {"minGreen": 40, "maxGreen": 30}},
            "greater than minGreen",
        ),
        ({"signalControl": "adaptive", "adaptive": {"minGreen": 1}}, "minGreen"),
        ({"signalControl": "adaptive", "adaptive": {"gap": 2}}, "'gap'"),
        (
            {
                "signalControl": "adaptive",
                "adaptive": {"detectionDistance": float("nan")},
            },
            "finite",
        ),
    ],
)
def test_dashboard_payload_rejects_invalid_adaptive_settings(
    extra: Dict[str, Any], message: str
) -> None:
    with pytest.raises(HTTPException) as err:
        _compile_dashboard_config({**SCENARIO, **extra}, 42)
    assert err.value.status_code == 400
    assert message in str(err.value.detail)


def test_dual_comparison_runs_the_adaptive_signal() -> None:
    config = _compile_dashboard_config({**SCENARIO, "signalControl": "adaptive"}, 7)
    orch = DualSimulationOrchestrator(config)
    for _ in range(50):
        orch.step()
    snap = orch.get_dual_snapshot()
    assert snap["signal"]["controller"]["signalControl"] == "adaptive"
    assert snap["roundabout"]["controller"]["type"] == "roundabout"


def test_dual_comparison_keeps_adaptive_when_the_view_was_a_roundabout() -> None:
    """A config whose controller holds no green timings still keeps how the
    signal side times its greens."""
    orch = DualSimulationOrchestrator(
        {
            "simulation": {"duration": 30, "randomSeed": 3},
            "geometry": {"intersectionType": "roundabout"},
            "roads": {"lanesPerApproach": 1},
            "controller": {"signalControl": "adaptive", "adaptive": {"minGreen": 8}},
        }
    )
    assert orch.config_signal["controller"]["signalControl"] == "adaptive"
    assert orch.config_signal["controller"]["adaptive"] == {"minGreen": 8}
    assert orch.controller_signal.min_green == 8  # type: ignore[attr-defined]


def test_live_config_endpoint_accepts_adaptive() -> None:
    res = client.post(
        "/api/simulation/config", json={**SCENARIO, "signalControl": "adaptive"}
    )
    assert res.status_code == 200, res.text
    bad = client.post(
        "/api/simulation/config",
        json={**SCENARIO, "signalControl": "adaptive", "adaptive": {"maxGreen": 500}},
    )
    assert bad.status_code == 400


# ── Versioned configs ─────────────────────────────────────────────────────


def _versioned(
    controller: Dict[str, Any], geometry: str = "fixed_time_signal"
) -> Dict[str, Any]:
    return {
        "simulation": {"timeStep": 0.1, "duration": 20, "warmupTime": 0.0},
        "geometry": {"intersectionType": geometry},
        "roads": {"lanesPerApproach": 1},
        "controller": controller,
    }


def test_pydantic_model_keeps_fixed_time_configs_unchanged() -> None:
    dumped = ScenarioConfiguration.model_validate(_versioned({})).model_dump(
        exclude_none=True
    )
    assert "signalControl" not in dumped["controller"]
    assert "adaptive" not in dumped["controller"]
    adaptive = ScenarioConfiguration.model_validate(
        _versioned({"signalControl": "adaptive", "adaptive": {"minGreen": 12}})
    ).model_dump(exclude_none=True)
    assert adaptive["controller"]["adaptive"]["minGreen"] == 12
    assert adaptive["controller"]["adaptive"]["maxGreen"] == 50


def test_validate_endpoint_accepts_adaptive() -> None:
    res = client.post(
        "/api/v1/configs/validate",
        json=_versioned({"signalControl": "adaptive", "adaptive": {"minGreen": 8}}),
    )
    assert res.status_code == 200, res.text
    assert res.json().get("valid", True) is True


@pytest.mark.parametrize(
    "controller,geometry",
    [
        (
            {"signalControl": "adaptive", "adaptive": {"maxGreen": 5}},
            "fixed_time_signal",
        ),
        (
            {"signalControl": "adaptive", "adaptive": {"extensionStep": 0}},
            "fixed_time_signal",
        ),
        (
            {"signalControl": "adaptive", "adaptive": {"demandThreshold": 1.5}},
            "fixed_time_signal",
        ),
        (
            {"signalControl": "adaptive", "adaptive": {"surprise": 1}},
            "fixed_time_signal",
        ),
        ({"signalControl": "adaptive", "offset": 10}, "fixed_time_signal"),
        (
            {
                "signalControl": "adaptive",
                "phaseSequence": ["ns_green", "ew_green", "ns_yellow", "all_red"],
            },
            "fixed_time_signal",
        ),
        ({"signalControl": "adaptive"}, "roundabout"),
        ({"signalControl": "actuated"}, "fixed_time_signal"),
    ],
)
def test_versioned_api_rejects_invalid_adaptive_configs(
    controller: Dict[str, Any], geometry: str
) -> None:
    res = client.post("/api/v1/simulations", json=_versioned(controller, geometry))
    assert res.status_code in (400, 422), res.text


def test_versioned_simulation_reports_the_adaptive_signal() -> None:
    res = client.post(
        "/api/v1/simulations",
        json={
            **_versioned({"signalControl": "adaptive"}),
            "simulation": {
                "timeStep": 0.1,
                "duration": 20,
                "warmupTime": 0.0,
                "randomSeed": 4,
            },
        },
    )
    assert res.status_code == 201, res.text
    sim_id = res.json()["simulationId"]
    client.post(f"/api/v1/simulations/{sim_id}/control", json={"action": "start"})
    time.sleep(0.5)
    client.post(f"/api/v1/simulations/{sim_id}/control", json={"action": "stop"})
    history = client.get(f"/api/v1/simulations/{sim_id}/history").json()
    assert history
    frame = client.get(
        f"/api/v1/simulations/{sim_id}/history/{history[-1]['tick']}"
    ).json()
    assert frame["controller"]["signalControl"] == "adaptive"
    assert "decisions" in frame["controller"]["adaptive"]
    client.delete(f"/api/v1/simulations/{sim_id}")


# ── Three-way study ───────────────────────────────────────────────────────


def _wait(job_id: str, timeout: float = 120.0) -> Dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        body: Dict[str, Any] = client.get(f"/api/v1/study/jobs/{job_id}").json()
        if body["status"] in ("completed", "failed"):
            return body
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} did not finish")


def test_control_comparison_job_runs_all_three_controls() -> None:
    res = client.post(
        "/api/v1/study/control-comparison/jobs",
        json={"levels": ["light"], "numSeeds": 2, "duration": 60, "baseSeed": 11},
    )
    assert res.status_code == 202, res.text
    done = _wait(res.json()["jobId"])
    assert done["status"] == "completed", done["error"]
    assert done["progress"]["total"] == 6  # 1 level x 2 seeds x 3 controls
    result = done["result"]
    assert result["controls"] == ["fixed_time", "adaptive", "roundabout"]
    assert result["seeds"] == [11, 12]
    assert result["calibration"]["calibrated"] is True
    level = result["results"][0]
    assert set(level["controls"]) == {"fixed_time", "adaptive", "roundabout"}
    for pair in (
        "adaptive_vs_fixed_time",
        "adaptive_vs_roundabout",
        "fixed_time_vs_roundabout",
    ):
        assert level["delayComparisons"][pair]["reading"] in (
            "lower",
            "higher",
            "tie",
            "inconclusive",
        )
    seed_row = result["perSeed"][0]
    assert seed_row["fixed_time"]["signalTiming"]["signalControl"] == "fixed_time"
    assert seed_row["adaptive"]["signalTiming"]["signalControl"] == "adaptive"
    assert seed_row["adaptive"]["decisions"]["greens"] >= 1
    assert seed_row["roundabout"]["signalTiming"] is None
    assert result["collisionCount"] == {"fixed_time": 0, "adaptive": 0, "roundabout": 0}


def test_control_comparison_is_reproducible() -> None:
    body = {"levels": ["moderate"], "numSeeds": 2, "duration": 60, "baseSeed": 5}
    a = client.post("/api/v1/study/control-comparison/run", json=body)
    b = client.post("/api/v1/study/control-comparison/run", json=body)
    assert a.status_code == 200, a.text
    assert a.json()["results"] == b.json()["results"]
    assert a.json()["perSeed"] == b.json()["perSeed"]


@pytest.mark.parametrize(
    "body",
    [
        {"numSeeds": 1},
        {"numSeeds": 11},
        {"duration": 30},
        {"levels": ["gridlock"]},
        {"levels": ["light", "light"]},
        {"lanes": 4},
        {"adaptive": {"minGreen": 50, "maxGreen": 40}},
        {"confidenceLevel": 0.5},
    ],
)
def test_control_comparison_request_is_validated(body: Dict[str, Any]) -> None:
    res = client.post("/api/v1/study/control-comparison/jobs", json=body)
    assert res.status_code == 422, res.text
