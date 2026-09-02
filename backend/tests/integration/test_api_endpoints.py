from typing import Any, Dict

from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_api_config_validation() -> None:
    # Valid config
    config: Dict[str, Any] = {
        "simulation": {
            "timeStep": 0.1,
            "duration": 300,
            "warmupTime": 30.0,
        },
        "geometry": {
            "intersectionType": "fixed_time_signal",
            "intersectionCenter": {"x": 0.0, "y": 0.0},
            "boundingRadius": 15.0,
        },
        "controller": {
            "greenDuration": 30,
            "yellowDuration": 5,
            "allRedDuration": 2,
        },
        "vehicleGeneration": {
            "stopSpeedThreshold": 0.1,
            "waitSpeedThreshold": 0.5,
        },
    }
    # Validate configuration
    response = client.post("/api/v1/configs/validate", json=config)
    assert response.status_code == 200
    assert response.json()["valid"] is True


def test_api_lifecycle_and_ws_stream() -> None:
    config: Dict[str, Any] = {
        "simulation": {
            "timeStep": 0.1,
            "duration": 300,
            "warmupTime": 0.0,
        },
        "geometry": {
            "intersectionType": "fixed_time_signal",
            "intersectionCenter": {"x": 0.0, "y": 0.0},
            "boundingRadius": 15.0,
        },
        "controller": {
            "greenDuration": 30,
            "yellowDuration": 5,
            "allRedDuration": 2,
        },
        "vehicleGeneration": {
            "stopSpeedThreshold": 0.1,
            "waitSpeedThreshold": 0.5,
        },
    }
    # 1. Create Simulation
    res_create = client.post("/api/v1/simulations", json=config)
    assert res_create.status_code == 200
    sim_id = res_create.json()["simulationId"]

    # 2. Start control request
    res_start = client.post(
        f"/api/v1/simulations/{sim_id}/control", json={"action": "start"}
    )
    assert res_start.status_code == 200
    assert res_start.json()["status"] == "running"

    # 3. WebSocket stream checks
    with client.websocket_connect(f"/ws/v1/stream?simulationId={sim_id}") as websocket:
        data = websocket.receive_json()
        assert "simulationStatus" in data
        assert "tick" in data

    # 4. Pause control request
    res_pause = client.post(
        f"/api/v1/simulations/{sim_id}/control", json={"action": "pause"}
    )
    assert res_pause.status_code == 200
    assert res_pause.json()["status"] == "paused"

    # 5. Stop control request
    res_stop = client.post(
        f"/api/v1/simulations/{sim_id}/control", json={"action": "stop"}
    )
    assert res_stop.status_code == 200
    assert res_stop.json()["status"] == "completed"
