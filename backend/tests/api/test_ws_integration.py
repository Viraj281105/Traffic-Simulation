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
    """Verifies that the live WS endpoint broadcasts updates at approximately 10Hz (every 100ms)
    while the simulation runs."""
    assert client.post("/api/simulation/play").status_code == 200
    try:
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
    finally:
        client.post("/api/simulation/pause")


def test_ws_idle_stream_sends_a_heartbeat_not_duplicate_frames() -> None:
    """A paused simulation's snapshot does not change, so it is resent once a
    second as a heartbeat rather than rebuilt ten times a second."""
    client.post("/api/simulation/pause")
    with client.websocket_connect("/ws/simulation/live") as websocket:
        first = websocket.receive_json()
        t_start = time.perf_counter()
        second = websocket.receive_json()
        interval = time.perf_counter() - t_start
    assert 0.8 <= interval <= 1.5
    assert second["tick"] == first["tick"]


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


def test_ws_stream_failure_closes_with_a_generic_reason(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """A snapshot that fails server-side closes the stream with 1011 and a
    generic reason. The handler used to send str(exc) as the reason: internal
    error text on the wire, and close() itself raised once that text passed
    the protocol's 123-byte limit."""
    import pytest
    from starlette.websockets import WebSocketDisconnect

    from src.snapshot.builder import SnapshotBuilder

    created = client.post(
        "/api/v1/simulations",
        json={
            "simulation": {"timeStep": 0.1, "duration": 30, "warmupTime": 0.0},
            "geometry": {"intersectionType": "fixed_time_signal"},
        },
    )
    assert created.status_code == 201
    sim_id = created.json()["simulationId"]

    def failing_build(self: SnapshotBuilder) -> None:
        raise RuntimeError("internal detail " * 20)

    monkeypatch.setattr(SnapshotBuilder, "build", failing_build)

    with client.websocket_connect(f"/ws/v1/stream?simulationId={sim_id}") as ws:
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
    assert closed.value.code == 1011
    assert closed.value.reason == "Internal server error"
