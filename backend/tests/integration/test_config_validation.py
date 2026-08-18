from typing import Any, Dict

from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_api_simulation_new_valid() -> None:
    """Verifies that a valid configuration successfully registers a new simulation."""
    config: Dict[str, Any] = {
        "simulation": {
            "timeStep": 0.1,
            "duration": 300,
            "warmupTime": 30.0,
        },
        "geometry": {
            "intersectionType": "fixed_time_signal",
        },
        "controller": {
            "greenTime": 30,
            "yellowTime": 4,
            "allRedTime": 2,
        },
    }
    response = client.post("/api/simulation/new", json=config)
    assert response.status_code == 200
    data = response.json()
    assert "simulationId" in data
    assert "configId" in data
    assert data["status"] == "initialized"


def test_api_simulation_new_invalid_constraints() -> None:
    """Verifies that configurations violating schema/Pydantic parameter constraints fail with HTTP 422."""
    # Invalid: duration < 1, greenTime < 5, yellowTime > 8
    config_invalid: Dict[str, Any] = {
        "simulation": {
            "timeStep": 0.1,
            "duration": 0,  # invalid: minimum 1
            "warmupTime": 30.0,
        },
        "geometry": {
            "intersectionType": "fixed_time_signal",
        },
        "controller": {
            "greenTime": 2,  # invalid: minimum 5
            "yellowTime": 12,  # invalid: maximum 8
            "allRedTime": 2,
        },
    }
    response = client.post("/api/simulation/new", json=config_invalid)
    assert response.status_code == 422
    errors = response.json()["detail"]
    assert len(errors) > 0
