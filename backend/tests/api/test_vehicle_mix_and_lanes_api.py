"""V1.1 / V1.2 through the API: dashboard payload, versioned configs, snapshots."""

from typing import Any, Dict

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from src.main import _compile_dashboard_config, app

client = TestClient(app)

SCENARIO: Dict[str, Any] = {
    "intersectionType": "fixed_time_signal",
    "intersectionSize": 11.0,
    "laneWidth": 3.5,
    "lanesNorth": 2,
    "lanesSouth": 2,
    "lanesEast": 2,
    "lanesWest": 2,
    "arrivalRate": 0.4,
    "duration": 60,
    "randomSeed": 42,
    "greenDuration": 20,
    "yellowDuration": 3,
    "allRedDuration": 2,
    "criticalGap": 4.5,
    "followUpTime": 2.8,
}
MIX = {"car": 0.6, "suv": 0.2, "bus": 0.05, "truck": 0.05, "motorcycle": 0.1}


def test_dashboard_payload_without_mix_is_the_calibrated_population() -> None:
    config = _compile_dashboard_config(dict(SCENARIO), 42)
    assert "vehicleMix" not in config["vehicleGeneration"]
    assert "laneChange" not in config["roads"]


def test_dashboard_payload_carries_mix_and_lane_changing() -> None:
    config = _compile_dashboard_config(
        {**SCENARIO, "vehicleMix": MIX, "laneChanging": False}, 42
    )
    assert config["vehicleGeneration"]["vehicleMix"] == MIX
    assert config["roads"]["laneChange"] == {"enabled": False}


@pytest.mark.parametrize(
    "extra,message",
    [
        ({"vehicleMix": {"car": 0.5}}, "sum to 1.0"),
        ({"vehicleMix": {"car": 0.5, "bike": 0.5}}, "bike"),
        ({"vehicleMix": [0.5, 0.5]}, "vehicleMix must be an object"),
        ({"laneChanging": "yes"}, "laneChanging must be true or false"),
        ({"lanesNorth": 1}, "north and south"),
    ],
)
def test_dashboard_payload_rejects_invalid_values(
    extra: Dict[str, Any], message: str
) -> None:
    with pytest.raises(HTTPException) as err:
        _compile_dashboard_config({**SCENARIO, **extra}, 42)
    assert err.value.status_code == 400
    assert message in str(err.value.detail)


def test_live_config_endpoint_accepts_a_mix() -> None:
    res = client.post("/api/simulation/config", json={**SCENARIO, "vehicleMix": MIX})
    assert res.status_code == 200, res.text
    bad = client.post(
        "/api/simulation/config", json={**SCENARIO, "vehicleMix": {"car": 2}}
    )
    assert bad.status_code == 400


def _versioned(**extra: Any) -> Dict[str, Any]:
    config: Dict[str, Any] = {
        "simulation": {"timeStep": 0.1, "duration": 20, "warmupTime": 0.0},
        "geometry": {"intersectionType": "fixed_time_signal"},
        "roads": {"lanesPerApproach": 2},
    }
    for section, value in extra.items():
        config.setdefault(section, {}).update(value)
    return config


def test_validate_endpoint_accepts_v11_v12_sections() -> None:
    config = _versioned(
        roads={
            "approaches": [
                {"direction": "east", "lanes": 1},
                {"direction": "west", "lanes": 1},
            ],
            "laneChange": {"enabled": True, "politeness": 0.2},
        },
        vehicleGeneration={
            "vehicleMix": MIX,
            "vehicleTypes": {"bus": {"maxAcceleration": 0.9}},
        },
    )
    res = client.post("/api/v1/configs/validate", json=config)
    assert res.status_code == 200, res.text
    assert res.json().get("valid", True) is True


@pytest.mark.parametrize(
    "extra",
    [
        {"vehicleGeneration": {"vehicleMix": {"tram": 1.0}}},
        {"vehicleGeneration": {"vehicleMix": {"car": 0.3}}},
        {"vehicleGeneration": {"vehicleTypes": {"bus": {"politeness": 3}}}},
        {"roads": {"laneChange": {"safeDeceleration": 0}}},
        {"roads": {"approaches": [{"direction": "north", "lanes": 1}]}},
    ],
)
def test_versioned_api_rejects_invalid_v11_v12_configs(extra: Dict[str, Any]) -> None:
    res = client.post("/api/v1/simulations", json=_versioned(**extra))
    assert res.status_code in (400, 422), res.text


def test_versioned_simulation_snapshot_reports_vehicle_classes() -> None:
    import time

    res = client.post(
        "/api/v1/simulations",
        json=_versioned(
            simulation={"randomSeed": 5},
            vehicleGeneration={"vehicleMix": {"bus": 0.5, "car": 0.5}},
        ),
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
    approaches = frame["intersection"]["approaches"]
    # No controller section: the signal runs its protected-left plan, whose
    # lane-0 head shows only a left arrow, so lane 0 is a left-turn pocket.
    assert approaches[0]["lanePermittedTurns"] == [["left"], ["straight", "right"]]
    # Buses (up to 12 m) in the mix: design-vehicle stop lines.
    assert frame["intersection"]["stopLineSetback"] == pytest.approx(3.5 + 7.0)
    assert "laneModel" in frame
    for vehicle in frame["vehicles"]:
        assert vehicle["vehicleType"] in ("bus", "car")
    client.delete(f"/api/v1/simulations/{sim_id}")
