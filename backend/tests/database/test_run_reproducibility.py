"""V1.1 Phase 1: run identity, reproducibility metadata and backwards
compatibility for saved runs (simulation_runs + saved_replays)."""

import copy
import sqlite3

import pytest
from fastapi.testclient import TestClient

import src.database.db as db_module
from src.core.clock import Clock
from src.core.engine import SimulationEngine
from src.core.provenance import GIT_COMMIT_HASH, PYTHON_VERSION
from src.database.dao import SimulationRunDAO, describe_reproducibility
from src.database.db import get_db_connection, init_db
from src.main import LIVE_SESSION_COOKIE, _live_sessions, app


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test_repro.db")
    monkeypatch.setattr(db_module, "DB_PATH", db_file)
    init_db()
    return db_file


# The dashboard's /api/simulation/config payload for a small, fast scenario.
DASHBOARD_CONFIG = {
    "intersectionType": "fixed_time_signal",
    "intersectionSize": 18.0,
    "laneWidth": 3.5,
    "lanesNorth": 1,
    "lanesSouth": 1,
    "lanesEast": 1,
    "lanesWest": 1,
    "arrivalRate": 0.4,
    "duration": 3,
    "randomSeed": 1234,
    "greenDuration": 20,
    "yellowDuration": 3,
    "allRedDuration": 2,
    "criticalGap": 4.5,
    "followUpTime": 2.8,
}


def _session_for(client: TestClient):
    return _live_sessions[client.cookies[LIVE_SESSION_COOKIE]]


def _configure_and_step_live(client: TestClient, ticks: int, **overrides):
    """Configures the caller's live session and steps its engine
    synchronously (no background thread), like a run paused at ``ticks``."""
    res = client.post("/api/simulation/config", json={**DASHBOARD_CONFIG, **overrides})
    assert res.status_code == 200
    sim = _session_for(client).live_sim_data
    for _ in range(ticks):
        sim["engine"].step()
    return sim


def _final_metrics(sim) -> dict:
    engine = sim["engine"]
    return sim["collector"].get_metrics(
        engine.clock.get_elapsed_time(),
        engine.pool.active_vehicles,
        engine.pool.exited_vehicles,
        engine.spawner.spawned_count,
        engine.pool.collision_count,
    )


def _replay_payload(seed, metrics, elapsed=2.0, **extra):
    return {
        "name": "Signal · test",
        "config": {
            "ui": {"lanes": 1, "randomSeed": seed},
            "simulation": {"duration": 3, "randomSeed": seed, "elapsed": elapsed},
            "geometry": {"intersectionType": "fixed_time_signal", "laneWidth": 3.5},
            "traffic": {"arrivalRate": 0.4},
        },
        "metrics": metrics,
        **extra,
    }


def test_saved_runs_get_unique_run_ids(test_db):
    client = TestClient(app)
    payload = _replay_payload(7, {"averageDelay": 1.0, "throughput": 3})
    ids = {
        client.post("/api/v1/replays", json=payload).json()["runId"] for _ in range(5)
    }
    assert len(ids) == 5
    # The run id is also the replay id, so History rows and runs line up.
    res = client.post("/api/v1/replays", json=payload).json()
    assert res["runId"] == res["replay_id"]


def test_save_captures_exact_engine_config_seed_commit_and_metrics(test_db):
    client = TestClient(app)
    sim = _configure_and_step_live(client, ticks=20)
    engine_config = copy.deepcopy(sim["engine"].config)
    metrics = _final_metrics(sim)

    res = client.post("/api/v1/replays", json=_replay_payload(1234, metrics))
    assert res.status_code == 200
    body = res.json()
    summary = body["reproducibility"]
    assert summary["runId"] == body["runId"]
    assert summary["provenanceRecorded"] is True
    assert summary["configSource"] == "engine"
    assert summary["exactConfig"] is True
    assert summary["seed"] == 1234
    assert summary["gitCommitHash"] == GIT_COMMIT_HASH
    assert "config" not in summary  # compact form for listings

    rep = client.get(
        f"/api/v1/study/history/runs/{body['runId']}/reproducibility"
    ).json()
    assert rep["runId"] == body["runId"]
    assert rep["createdAt"]
    assert rep["intersectionType"] == "fixed_time_signal"
    assert rep["runMode"] == "single"
    assert rep["seed"] == 1234
    assert rep["gitCommitHash"] == GIT_COMMIT_HASH
    assert rep["pythonVersion"] == PYTHON_VERSION
    # Exact restoration: the stored config is the engine's own config.
    assert rep["config"] == engine_config
    assert rep["config"]["simulation"]["randomSeed"] == 1234
    assert rep["timing"] == {
        "timeStep": 0.1,
        "duration": 3.0,
        "warmupTime": engine_config["simulation"]["warmupTime"],
        "elapsed": pytest.approx(2.0),
    }
    assert rep["summaryMetrics"] == metrics

    # The generic run endpoint exposes the same stored data.
    run = client.get(f"/api/v1/study/history/runs/{body['runId']}").json()["run"]
    assert run["git_commit"] == GIT_COMMIT_HASH
    assert run["random_seed"] == 1234
    assert run["config"] == engine_config
    assert run["summary_metrics"] == metrics


def test_restored_config_reproduces_the_same_run(test_db):
    """The stored config + seed rebuild a run with identical arrivals and
    metrics (checked through the existing headless /reproduce)."""
    client = TestClient(app)
    sim = _configure_and_step_live(client, ticks=30)  # runs to its 3 s duration
    metrics = _final_metrics(sim)
    run_id = client.post(
        "/api/v1/replays", json=_replay_payload(1234, metrics, elapsed=3.0)
    ).json()["runId"]

    rep = client.get(f"/api/v1/study/history/runs/{run_id}/reproducibility").json()
    clock = Clock(time_step=rep["timing"]["timeStep"])
    rebuilt = SimulationEngine(
        clock, duration=rep["timing"]["duration"], config=rep["config"]
    )
    assert rebuilt.spawner.random_seed == sim["engine"].spawner.random_seed

    res = client.post(f"/api/v1/study/history/runs/{run_id}/reproduce")
    assert res.status_code == 200
    assert res.json()["isDeterministic"] is True
    assert res.json()["reproducedMetrics"]["throughput"] == metrics["throughput"]


def test_seed_mismatch_falls_back_to_client_config(test_db):
    """A save whose seed isn't the live engine's must not be attributed the
    engine's config."""
    client = TestClient(app)
    _configure_and_step_live(client, ticks=5)
    payload = _replay_payload(999, {"averageDelay": 1.0})
    run_id = client.post("/api/v1/replays", json=payload).json()["runId"]

    rep = client.get(f"/api/v1/study/history/runs/{run_id}/reproducibility").json()
    assert rep["configSource"] == "client"
    assert rep["exactConfig"] is False
    assert rep["seed"] == 999
    assert rep["config"]["ui"] == payload["config"]["ui"]
    assert rep["gitCommitHash"] == GIT_COMMIT_HASH


def test_save_without_session_records_client_config_and_no_invented_seed(test_db):
    client = TestClient(app)
    payload = _replay_payload(5, {"averageDelay": 2.0})
    del payload["config"]["simulation"]["randomSeed"]
    run_id = client.post("/api/v1/replays", json=payload).json()["runId"]

    rep = client.get(f"/api/v1/study/history/runs/{run_id}/reproducibility").json()
    assert rep["configSource"] == "client"
    assert rep["seed"] is None
    assert rep["timing"]["timeStep"] is None
    assert rep["timing"]["elapsed"] == 2.0
    assert rep["summaryMetrics"] == {"averageDelay": 2.0}


def test_dual_comparison_save_records_mode_and_refuses_single_reproduce(test_db):
    client = TestClient(app)
    res = client.post(
        "/api/simulation/config", json={**DASHBOARD_CONFIG, "randomSeed": 77}
    )
    assert res.status_code == 200
    assert client.post("/api/simulation/dual/reset").status_code == 200
    orch = _session_for(client).dual_sim_orchestrator
    for _ in range(10):
        orch.step()
    metrics = {"signal": {"averageDelay": 1.0}, "roundabout": {"averageDelay": 2.0}}

    run_id = client.post(
        "/api/v1/replays", json=_replay_payload(77, metrics, mode="dual")
    ).json()["runId"]
    rep = client.get(f"/api/v1/study/history/runs/{run_id}/reproducibility").json()
    assert rep["runMode"] == "dual"
    assert rep["intersectionType"] == "comparative"
    assert rep["configSource"] == "engine"
    assert rep["seed"] == 77
    assert rep["config"] == orch.config
    assert rep["summaryMetrics"] == metrics

    res = client.post(f"/api/v1/study/history/runs/{run_id}/reproduce")
    assert res.status_code == 400


def test_auto_persisted_api_run_records_provenance(test_db):
    client = TestClient(app)
    config = {
        "simulation": {"timeStep": 0.1, "duration": 1.0, "warmupTime": 0.0},
        "traffic": {"arrivalRate": 0.3},
        "geometry": {
            "intersectionType": "fixed_time_signal",
            "intersectionCenter": {"x": 0.0, "y": 0.0},
            "boundingRadius": 15.0,
        },
    }
    sim_id = client.post("/api/v1/simulations", json=config).json()["simulationId"]
    client.post(f"/api/v1/simulations/{sim_id}/control", json={"action": "start"})
    client.post(f"/api/v1/simulations/{sim_id}/control", json={"action": "stop"})

    rep = client.get(f"/api/v1/study/history/runs/{sim_id}/reproducibility").json()
    assert rep["provenanceRecorded"] is True
    assert rep["gitCommitHash"] == GIT_COMMIT_HASH
    assert rep["configSource"] == "engine"
    # The seed was auto-generated at run time; the restorable config pins it.
    assert isinstance(rep["seed"], int)
    assert rep["config"]["simulation"]["randomSeed"] == rep["seed"]
    assert rep["timing"]["timeStep"] == 0.1
    assert rep["timing"]["duration"] == 1.0
    assert rep["timing"]["warmupTime"] == 0.0


def test_unknown_run_returns_404(test_db):
    client = TestClient(app)
    for path in (
        "/api/v1/study/history/runs/does-not-exist",
        "/api/v1/study/history/runs/does-not-exist/reproducibility",
    ):
        res = client.get(path)
        assert res.status_code == 404


def test_legacy_runs_load_with_unrecorded_fields_as_null(tmp_path, monkeypatch):
    """A database from before V1.1 migrates in place; its runs keep loading
    and report missing provenance as null instead of invented values."""
    legacy_db = str(tmp_path / "legacy.db")
    conn = sqlite3.connect(legacy_db)
    conn.executescript(
        """
        CREATE TABLE simulation_runs (
            id TEXT PRIMARY KEY, status TEXT NOT NULL, elapsed REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO simulation_runs (id, status, elapsed)
            VALUES ('ancient', 'completed', 30.0);
        CREATE TABLE saved_replays (
            id TEXT PRIMARY KEY, name TEXT, config_json TEXT NOT NULL,
            metrics_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO saved_replays (id, name, config_json, metrics_json)
            VALUES ('orphan', 'Old replay',
                    '{"simulation": {"randomSeed": 3}}', '{"averageDelay": 4.0}');
        """
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(db_module, "DB_PATH", legacy_db)
    init_db()

    with get_db_connection() as conn:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(simulation_runs);")}
        assert {"git_commit", "provenance_json"} <= cols
        # A pre-provenance save that did record config and seed.
        SimulationRunDAO.save(
            conn,
            "pre_provenance",
            "completed",
            60.0,
            intersection_type="roundabout",
            random_seed=42,
            config={"simulation": {"randomSeed": 42}},
            summary_metrics={"averageDelay": 5.0},
            batch_id="replay",
        )
        conn.execute(
            "INSERT INTO saved_replays (id, name, config_json, metrics_json) "
            "VALUES ('pre_provenance', 'Saved', '{}', '{}');"
        )
        conn.commit()

    client = TestClient(app)
    ancient = client.get("/api/v1/study/history/runs/ancient/reproducibility").json()
    assert ancient["provenanceRecorded"] is False
    assert ancient["gitCommitHash"] is None
    assert ancient["pythonVersion"] is None
    assert ancient["runMode"] is None
    # No config was ever recorded, so the migrated column default isn't a seed.
    assert ancient["seed"] is None
    assert ancient["configAvailable"] is False
    assert ancient["config"] is None
    assert ancient["timing"] == {
        "timeStep": None,
        "duration": None,
        "warmupTime": None,
        "elapsed": None,
    }

    pre = client.get("/api/v1/study/history/runs/pre_provenance/reproducibility").json()
    assert pre["provenanceRecorded"] is False
    assert pre["seed"] == 42
    assert pre["configAvailable"] is True
    assert pre["summaryMetrics"] == {"averageDelay": 5.0}

    # Older runs still list and load through the existing endpoints.
    assert client.get("/api/v1/study/history/runs").status_code == 200
    replays = {r["id"]: r for r in client.get("/api/v1/replays").json()}
    assert replays["orphan"]["reproducibility"] is None
    assert replays["orphan"]["config"] == {"simulation": {"randomSeed": 3}}
    assert replays["pre_provenance"]["reproducibility"]["provenanceRecorded"] is False
    assert client.get("/api/v1/replays/orphan").json()["reproducibility"] is None


def test_describe_reproducibility_tolerates_malformed_rows():
    rep = describe_reproducibility(
        {"id": "x", "config": None, "summary_metrics": None, "provenance": None}
    )
    assert rep["runId"] == "x"
    assert rep["config"] is None
    assert rep["summaryMetrics"] == {}
    assert rep["seed"] is None
