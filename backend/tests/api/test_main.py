import pytest

try:
    from fastapi.testclient import TestClient

    from src.main import app

    client = TestClient(app)
except ImportError:
    pytest.skip("FastAPI or app module not available yet", allow_module_level=True)


def test_get_single_vehicle() -> None:
    """Test that the single-vehicle endpoint responds correctly and advances state."""
    # Reset and start the simulation first
    client.post("/api/simulation/reset")
    client.post("/api/simulation/start")

    # First request
    response = client.get("/api/simulation/single-vehicle")
    assert response.status_code == 200
    data = response.json()
    assert data["vehicle_id"] == "vehicle_1"
    assert "position" in data
    assert "speed" in data
    assert "acceleration" in data
    assert "x" in data
    assert "y" in data
    assert "heading" in data
    assert "state" in data
    assert "lane_id" in data

    # Second request should advance the vehicle position
    response2 = client.get("/api/simulation/single-vehicle")
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["position"] > data["position"]

    # Reset simulation state
    client.post("/api/simulation/reset")
