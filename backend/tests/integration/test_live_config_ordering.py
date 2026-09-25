"""A config update must not leave the previous scenario ready to play.

The dual stream (websocket_dual_stream) recreates a missing orchestrator from
the session's config on every frame. update_simulation_config used to clear
the orchestrator first and assign the new config afterwards, so a frame
arriving in between rebuilt the *previous* scenario — and the next Play ran
it instead of the one just configured (seen as a 2-minute comparison still
running past 2:00). These tests stand in for that frame by building the
orchestrator while the new config is being compiled.
"""

from typing import Any, Dict

from fastapi.testclient import TestClient

import src.main as main
from src.main import app

SCENARIO: Dict[str, Any] = {
    "intersectionType": "fixed_time_signal",
    "intersectionSize": 11.0,
    "laneWidth": 3.5,
    "lanesNorth": 1,
    "lanesSouth": 1,
    "lanesEast": 1,
    "lanesWest": 1,
    "arrivalRate": 0.3,
    "randomSeed": 42,
    "greenDuration": 25,
    "yellowDuration": 3,
    "allRedDuration": 2,
    "criticalGap": 4.5,
    "followUpTime": 2.8,
}


def test_a_stream_frame_mid_update_cannot_resurrect_the_old_scenario(
    monkeypatch,
) -> None:
    client = TestClient(app)
    assert (
        client.post(
            "/api/simulation/config", json={**SCENARIO, "duration": 300}
        ).json()["status"]
        == "ok"
    )

    real_compile = main._compile_dashboard_config
    captured: Dict[str, Any] = {}

    def compile_while_streaming(payload, seed_val):
        # A dual-stream frame lands while the update is in progress.
        captured["session"] = main._current_session()
        main.get_or_create_dual_orchestrator()
        return real_compile(payload, seed_val)

    monkeypatch.setattr(main, "_compile_dashboard_config", compile_while_streaming)
    assert (
        client.post(
            "/api/simulation/config", json={**SCENARIO, "duration": 120}
        ).json()["status"]
        == "ok"
    )

    session = captured["session"]
    # Whatever the next frame or Play runs comes from the new scenario: any
    # orchestrator left behind was built from it, and a missing one will be.
    assert session.current_live_config["simulation"]["duration"] == 120
    orch = session.dual_sim_orchestrator
    if orch is not None:
        assert orch.engine_signal.duration == 120
        assert orch.engine_roundabout.duration == 120


def test_a_rejected_config_leaves_the_running_scenario_alone() -> None:
    client = TestClient(app)
    client.post("/api/simulation/config", json={**SCENARIO, "duration": 300})
    assert client.post("/api/simulation/dual/play").status_code == 200

    res = client.post(
        "/api/simulation/config", json={**SCENARIO, "duration": 120, "lanesNorth": 0}
    )

    assert res.status_code == 400
    status = client.get("/api/simulation/dual/status").json()
    assert status["status"] == "running"
    client.post("/api/simulation/dual/reset")
