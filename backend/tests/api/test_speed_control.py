"""Bounds on the live and dual playback-speed endpoints.

The run loops divide the tick period by the multiplier, so a zero used to
raise ZeroDivisionError inside the engine's background thread: the thread
died while the engine still reported RUNNING, and a session holding a
"running" engine is never reclaimed.
"""

import pytest
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)

SPEED_ENDPOINTS = ["/api/simulation/speed", "/api/simulation/dual/speed"]


@pytest.mark.parametrize("endpoint", SPEED_ENDPOINTS)
@pytest.mark.parametrize("multiplier", [0, -1, 10.5])
def test_speed_outside_bounds_is_rejected(endpoint: str, multiplier: float) -> None:
    response = client.post(endpoint, json={"multiplier": multiplier})
    assert response.status_code == 422


def test_live_speed_within_bounds_is_applied() -> None:
    response = client.post("/api/simulation/speed", json={"multiplier": 4})
    assert response.status_code == 200
    # TestClient carries the session cookie the first request minted.
    session_key = client.cookies.get("ts_session")
    assert session_key is not None

    from src.main import _live_sessions

    engine = _live_sessions[session_key].live_sim_data["engine"]
    assert engine.speed_multiplier == 4


def test_dual_speed_within_bounds_is_applied() -> None:
    response = client.post("/api/simulation/dual/speed", json={"multiplier": 2})
    assert response.status_code == 200

    from src.main import _live_sessions

    session_key = client.cookies.get("ts_session")
    assert session_key is not None
    orchestrator = _live_sessions[session_key].dual_sim_orchestrator
    assert orchestrator is not None
    assert orchestrator.speed_multiplier == 2


def test_rejected_speed_leaves_the_previous_multiplier() -> None:
    from src.main import _live_sessions

    assert (
        client.post("/api/simulation/speed", json={"multiplier": 2}).status_code == 200
    )
    assert (
        client.post("/api/simulation/speed", json={"multiplier": 0}).status_code == 422
    )

    session_key = client.cookies.get("ts_session")
    assert session_key is not None
    engine = _live_sessions[session_key].live_sim_data["engine"]
    assert engine.speed_multiplier == 2
