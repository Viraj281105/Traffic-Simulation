import time

from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_ws_live_connection_lifecycle() -> None:
    """Verifies that we can connect to /ws/simulation/live and receive simulation snapshot state frames."""
    with client.websocket_connect("/ws/simulation/live") as websocket:
        # Receive first snapshot frame
        data = websocket.receive_json()
        assert data["schemaVersion"] == "1.0.0"
        assert "simulationId" in data
        assert "simulationStatus" in data
        assert "vehicles" in data
        assert "metrics" in data


def test_ws_frequency_consistency() -> None:
    """Verifies that the live WS endpoint broadcasts updates at approximately 10Hz (every 100ms)."""
    with client.websocket_connect("/ws/simulation/live") as websocket:
        timestamps = []
        for _ in range(5):
            t_start = time.perf_counter()
            websocket.receive_json()
            t_end = time.perf_counter()
            timestamps.append(t_end - t_start)

        # Average interval should be approximately 0.1s (100ms) with minor network test client tolerance
        avg_interval = sum(timestamps[1:]) / len(timestamps[1:])
        assert 0.05 <= avg_interval <= 0.15


def test_simulation_command_apis() -> None:
    """Verifies control play, pause commands change the live simulation engine status."""
    # Play
    res_play = client.post("/api/simulation/play")
    assert res_play.status_code == 200
    assert res_play.json()["status"] == "running"

    # Pause
    res_pause = client.post("/api/simulation/pause")
    assert res_pause.status_code == 200
    assert res_pause.json()["status"] == "paused"
