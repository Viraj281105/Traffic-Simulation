"""Cross-field contract rules (scenario contract §5) and their API wiring.

Regression: every rule below was documented but enforced nowhere — an inverted
roundabout ring or a directional split summing to 4 was accepted with a 201,
``arrivalDistribution: "burst"`` crashed creation with a 500, and the live
dashboard endpoint accepted zero/negative lane counts and NaN arrival rates.
"""

from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

from src.core.config_validation import semantic_config_errors
from src.main import app

client = TestClient(app)


def _base(**sections: Dict[str, Any]) -> Dict[str, Any]:
    config: Dict[str, Any] = {
        "simulation": {"duration": 60, "randomSeed": 1},
        "geometry": {"intersectionType": "roundabout"},
    }
    config.update(sections)
    return config


@pytest.mark.parametrize(
    "config, fragment",
    [
        (_base(controller={"innerRadius": 30, "outerRadius": 10}), "outerRadius"),
        # One explicit radius can invert the ring against the other's default.
        (_base(controller={"innerRadius": 25}), "outerRadius"),
        (
            _base(
                traffic={
                    "directionalSplit": {
                        "north": 1,
                        "south": 1,
                        "east": 1,
                        "west": 1,
                    }
                }
            ),
            "directionalSplit",
        ),
        (
            _base(
                traffic={
                    "turnProbabilities": {"left": 0.5, "straight": 0.5, "right": 0.5}
                }
            ),
            "turnProbabilities",
        ),
        (_base(traffic={"arrivalDistribution": "burst"}), "burst"),
        (
            {
                "simulation": {"duration": 20, "warmupTime": 20},
                "geometry": {"intersectionType": "fixed_time_signal"},
            },
            "warmupTime",
        ),
        (
            _base(vehicleGeneration={"desiredSpeed": {"min": 20, "max": 10}}),
            "desiredSpeed",
        ),
        (_base(traffic={"arrivalRate": float("nan")}), "finite"),
    ],
)
def test_violations_are_reported(config: Dict[str, Any], fragment: str) -> None:
    errors = semantic_config_errors(config)
    assert any(fragment in e for e in errors), errors


def test_valid_config_has_no_errors() -> None:
    config = _base(
        traffic={
            "directionalSplit": {"north": 0.4, "south": 0.2, "east": 0.2, "west": 0.2},
            "turnProbabilities": {"left": 0.2, "straight": 0.6, "right": 0.2},
            "arrivalDistribution": "poisson",
        },
        controller={"innerRadius": 12, "outerRadius": 22},
    )
    assert semantic_config_errors(config) == []


def test_implicit_warmup_default_does_not_reject_short_runs() -> None:
    # 10 s run relying on the 30 s warm-up default: long-standing usage.
    assert semantic_config_errors({"simulation": {"duration": 10}}) == []


def test_create_rejects_inverted_ring_with_400() -> None:
    response = client.post(
        "/api/v1/simulations",
        json=_base(controller={"innerRadius": 30, "outerRadius": 10}),
    )
    assert response.status_code == 400
    assert "outerRadius" in response.json()["error"]["message"]


def test_create_rejects_burst_with_400_not_500() -> None:
    for route in ("/api/v1/simulations", "/api/simulation/new"):
        response = client.post(
            route, json=_base(traffic={"arrivalDistribution": "burst"})
        )
        assert response.status_code == 400, (route, response.text)


def test_typed_route_keeps_accepting_short_run_with_default_warmup() -> None:
    response = client.post(
        "/api/simulation/new",
        json={
            "simulation": {"duration": 10, "randomSeed": 1},
            "geometry": {"intersectionType": "fixed_time_signal"},
        },
    )
    assert response.status_code in (200, 201), response.text


def test_validate_endpoint_reports_cross_field_errors() -> None:
    response = client.post(
        "/api/v1/configs/validate",
        json=_base(controller={"innerRadius": 30, "outerRadius": 10}),
    )
    body = response.json()
    assert body["valid"] is False
    assert any("outerRadius" in e for e in body["errors"])


@pytest.mark.parametrize(
    "payload",
    [
        {"lanesNorth": 0},
        {"lanesEast": 9},
        {"arrivalRate": -1},
        {"arrivalRate": "nan"},
        {"yellowDuration": -5},
        {"greenDuration": 0},
        {"intersectionType": "roundabout", "followUpTime": -2},
    ],
)
def test_live_config_rejects_out_of_range_values(payload: Dict[str, Any]) -> None:
    before = client.post("/api/simulation/config", json={"arrivalRate": 0.4})
    assert before.status_code == 200
    response = client.post("/api/simulation/config", json=payload)
    assert response.status_code == 400, response.text


def test_live_config_accepts_short_duration_despite_fixed_warmup() -> None:
    response = client.post("/api/simulation/config", json={"duration": 5})
    assert response.status_code == 200, response.text
