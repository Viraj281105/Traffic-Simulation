"""V1.1 Phases 2-5: saved-run records, metadata (name/notes/tags), exports,
deletion and reproduction semantics (mid-run saves, sweep runs, limitations)."""

import csv
import io
import json

import pytest
from fastapi.testclient import TestClient

import src.database.db as db_module
from src.core.provenance import GIT_COMMIT_HASH
from src.database.dao import SimulationRunDAO
from src.database.db import get_db_connection, init_db
from src.main import LIVE_SESSION_COOKIE, _live_sessions, app
from src.study.volume_sweep import run_volume_sweep_experiment


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test_experiments.db")
    monkeypatch.setattr(db_module, "DB_PATH", db_file)
    init_db()
    return db_file


DASHBOARD_CONFIG = {
    "intersectionType": "fixed_time_signal",
    "intersectionSize": 18.0,
    "laneWidth": 3.5,
    "lanesNorth": 1,
    "lanesSouth": 1,
    "lanesEast": 1,
    "lanesWest": 1,
    "arrivalRate": 0.5,
    "duration": 60,
    "randomSeed": 2024,
    "greenDuration": 20,
    "yellowDuration": 3,
    "allRedDuration": 2,
}


def _save_live_run(client: TestClient, ticks: int, name: str = "Signal run") -> str:
    """Configures and steps the caller's live engine, then saves it."""
    assert (
        client.post("/api/simulation/config", json=DASHBOARD_CONFIG).status_code == 200
    )
    engine = _live_sessions[client.cookies[LIVE_SESSION_COOKIE]].live_sim_data["engine"]
    for _ in range(ticks):
        engine.step()
    res = client.post(
        "/api/v1/replays",
        json={
            "name": name,
            "config": {
                "ui": {"randomSeed": DASHBOARD_CONFIG["randomSeed"]},
                "simulation": {"randomSeed": DASHBOARD_CONFIG["randomSeed"]},
                "geometry": {"intersectionType": "fixed_time_signal"},
            },
            "metrics": {},
        },
    )
    assert res.status_code == 200
    return res.json()["runId"]


def _legacy_run(run_id: str = "legacy_run") -> None:
    """A run saved before provenance/names existed, with a History entry."""
    with get_db_connection() as conn:
        SimulationRunDAO.save(
            conn,
            run_id,
            "completed",
            60.0,
            intersection_type="roundabout",
            random_seed=11,
            config={"simulation": {"randomSeed": 11}},
            summary_metrics={"throughput": 9},
            batch_id="replay",
        )
        conn.execute(
            "INSERT INTO saved_replays (id, name, config_json, metrics_json) "
            "VALUES (?, 'Old roundabout', '{}', '{}');",
            (run_id,),
        )
        conn.commit()


# ── Run record ───────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/study/history/runs/{}/reproducibility",
        "/api/v1/study/history/runs/{}/export",
    ],
)
def test_malformed_run_id_is_400_and_unknown_is_404(test_db, path):
    client = TestClient(app)
    assert client.get(path.format("bad id!")).status_code == 400
    assert client.get(path.format("a" * 129)).status_code == 400
    assert client.get(path.format("well-formed_but_missing")).status_code == 404


def test_run_record_carries_name_and_restore_availability(test_db):
    client = TestClient(app)
    run_id = _save_live_run(client, ticks=5, name="  Peak test  ")
    rec = client.get(f"/api/v1/study/history/runs/{run_id}/reproducibility").json()
    assert rec["name"] == "Peak test"
    assert rec["savedReplay"] is True
    assert rec["notes"] is None
    assert rec["tags"] == []
    assert rec["batchId"] == "replay"

    _legacy_run()
    legacy = client.get("/api/v1/study/history/runs/legacy_run/reproducibility").json()
    # Runs saved before names were stored on the run use the History name.
    assert legacy["name"] == "Old roundabout"
    assert legacy["provenanceRecorded"] is False


# ── Metadata ─────────────────────────────────────────────────────────────


def test_rename_notes_and_tags_update_labels_only(test_db):
    client = TestClient(app)
    run_id = _save_live_run(client, ticks=5)
    before = client.get(f"/api/v1/study/history/runs/{run_id}/reproducibility").json()

    res = client.patch(
        f"/api/v1/study/history/runs/{run_id}",
        json={
            "name": "Baseline A",
            "notes": "  first pass  ",
            "tags": ["peak", " Peak ", "", "calibrated  run"],
        },
    )
    assert res.status_code == 200
    rec = res.json()
    assert rec["name"] == "Baseline A"
    assert rec["notes"] == "first pass"
    assert rec["tags"] == ["peak", "calibrated run"]
    for key in ("config", "summaryMetrics", "seed", "gitCommitHash", "timing"):
        assert rec[key] == before[key]

    # History shows the new name too.
    replay = client.get(f"/api/v1/replays/{run_id}").json()
    assert replay["name"] == "Baseline A"
    assert replay["reproducibility"]["tags"] == ["peak", "calibrated run"]

    # Omitted fields are untouched; null/empty clears notes and tags.
    rec = client.patch(
        f"/api/v1/study/history/runs/{run_id}", json={"notes": None, "tags": []}
    ).json()
    assert rec["name"] == "Baseline A"
    assert rec["notes"] is None
    assert rec["tags"] == []


def test_metadata_validation(test_db):
    client = TestClient(app)
    run_id = _save_live_run(client, ticks=2)
    url = f"/api/v1/study/history/runs/{run_id}"
    assert client.patch(url, json={"name": "   "}).status_code == 400
    assert client.patch(url, json={"name": "x" * 121}).status_code == 422
    assert client.patch(url, json={"tags": ["t"] * 21}).status_code == 422
    assert client.patch(url, json={"tags": ["x" * 33]}).status_code == 422
    assert (
        client.patch("/api/v1/study/history/runs/missing", json={}).status_code == 404
    )
    assert client.patch("/api/v1/study/history/runs/bad id", json={}).status_code == 400


def test_legacy_run_can_be_labelled(test_db):
    _legacy_run()
    client = TestClient(app)
    rec = client.patch(
        "/api/v1/study/history/runs/legacy_run", json={"tags": ["legacy"]}
    ).json()
    assert rec["tags"] == ["legacy"]
    assert rec["name"] == "Old roundabout"
    assert rec["gitCommitHash"] is None


# ── Exports ──────────────────────────────────────────────────────────────


def test_json_export_identifies_and_reproduces_the_run(test_db):
    client = TestClient(app)
    run_id = _save_live_run(client, ticks=10)
    client.patch(f"/api/v1/study/history/runs/{run_id}", json={"tags": ["a"]})
    res = client.get(f"/api/v1/study/history/runs/{run_id}/export?format=json")
    assert res.status_code == 200
    assert f'filename="run_{run_id}.json"' in res.headers["content-disposition"]
    body = res.json()
    assert body["exportVersion"] == 1
    assert body["exportedBy"]["gitCommitHash"] == GIT_COMMIT_HASH
    run = body["run"]
    assert run["runId"] == run_id
    assert run["createdAt"]
    assert run["intersectionType"] == "fixed_time_signal"
    assert run["seed"] == 2024
    assert run["gitCommitHash"] == GIT_COMMIT_HASH
    assert run["exactConfig"] is True
    assert run["config"]["simulation"]["randomSeed"] == 2024
    assert run["tags"] == ["a"]
    assert "throughput" in run["summaryMetrics"]


def test_csv_export_rows_and_missing_values_stay_empty(test_db):
    client = TestClient(app)
    run_id = _save_live_run(client, ticks=10)
    res = client.get(f"/api/v1/study/history/runs/{run_id}/export?format=csv")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/csv")
    rows = list(csv.reader(io.StringIO(res.text)))
    assert rows[0] == ["section", "key", "value"]
    cells = {(r[0], r[1]): r[2] for r in rows[1:]}
    assert cells[("run", "runId")] == run_id
    assert cells[("reproducibility", "seed")] == "2024"
    assert cells[("reproducibility", "gitCommitHash")] == GIT_COMMIT_HASH
    assert cells[("config", "simulation.randomSeed")] == "2024"
    assert ("metrics", "throughput") in cells
    # Lists are kept whole, as JSON.
    phases = cells[("config", "controller.phaseSequence")]
    assert json.loads(phases)[0] == "ns_green"

    _legacy_run()
    legacy_rows = list(
        csv.reader(
            io.StringIO(
                client.get(
                    "/api/v1/study/history/runs/legacy_run/export?format=csv"
                ).text
            )
        )
    )
    legacy = {(r[0], r[1]): r[2] for r in legacy_rows[1:]}
    assert legacy[("reproducibility", "gitCommitHash")] == ""
    assert legacy[("timing", "timeStep")] == ""
    assert legacy[("reproducibility", "provenanceRecorded")] == "false"
    assert legacy[("metrics", "throughput")] == "9"


def test_export_rejects_unknown_format(test_db):
    _legacy_run()
    client = TestClient(app)
    res = client.get("/api/v1/study/history/runs/legacy_run/export?format=xml")
    assert res.status_code == 400


# ── Delete ───────────────────────────────────────────────────────────────


def test_deleting_a_saved_run_removes_its_run_record(test_db):
    client = TestClient(app)
    run_id = _save_live_run(client, ticks=3)
    assert client.delete(f"/api/v1/replays/{run_id}").status_code == 200
    assert (
        client.get(f"/api/v1/study/history/runs/{run_id}/reproducibility").status_code
        == 404
    )
    assert client.get(f"/api/v1/study/history/runs/{run_id}").status_code == 404


# ── Reproduction semantics ───────────────────────────────────────────────


def test_mid_run_save_reproduces_to_the_recorded_elapsed_time(test_db):
    client = TestClient(app)
    run_id = _save_live_run(client, ticks=400)  # 40 s of a 60 s run
    stored = client.get(f"/api/v1/study/history/runs/{run_id}/reproducibility").json()
    assert stored["timing"]["elapsed"] == pytest.approx(40.0)

    body = client.post(f"/api/v1/study/history/runs/{run_id}/reproduce").json()
    assert body["reproducedElapsed"] == pytest.approx(40.0)
    assert body["isDeterministic"] is True
    assert body["comparedMetrics"] == ["averageDelay", "throughput"]
    assert body["limitations"] == []
    assert (
        body["reproducedMetrics"]["totalVehiclesSpawned"]
        == stored["summaryMetrics"]["totalVehiclesSpawned"]
    )
    # Reproduction never modifies the stored run.
    after = client.get(f"/api/v1/study/history/runs/{run_id}/reproducibility").json()
    assert after == stored


def test_reproduce_reports_limitations_instead_of_claiming_determinism(test_db):
    client = TestClient(app)
    with get_db_connection() as conn:
        SimulationRunDAO.save(
            conn,
            "nothing_to_compare",
            "completed",
            2.0,
            intersection_type="fixed_time_signal",
            random_seed=5,
            duration=2.0,
            config={"simulation": {"timeStep": 0.1, "duration": 2.0}},
            summary_metrics={},
        )
    body = client.post("/api/v1/study/history/runs/nothing_to_compare/reproduce").json()
    assert body["isDeterministic"] is None
    assert body["comparedMetrics"] == []
    assert any("before provenance" in text for text in body["limitations"])
    assert any("no delay or throughput" in text for text in body["limitations"])


def test_volume_sweep_runs_record_exact_configs_and_reproduce(test_db):
    sweep = run_volume_sweep_experiment(
        arrival_rates=[0.4],
        duration=20.0,
        random_seed=99,
        custom_config={"simulation": {"warmupTime": 5.0}},
        name="tiny sweep",
    )
    client = TestClient(app)
    runs = client.get(
        f"/api/v1/study/history/runs?batch_id={sweep['sessionId']}"
    ).json()
    assert {r["intersection_type"] for r in runs} == {
        "fixed_time_signal",
        "roundabout",
    }
    for run in runs:
        rec = client.get(
            f"/api/v1/study/history/runs/{run['id']}/reproducibility"
        ).json()
        assert rec["exactConfig"] is True
        assert rec["gitCommitHash"] == GIT_COMMIT_HASH
        assert rec["seed"] == 99
        assert rec["timing"]["timeStep"] == 0.1
        # The engine's own config, including the controller settings the
        # comparison orchestrator injects for each geometry.
        assert "controller" in rec["config"]
        assert rec["config"]["geometry"]["intersectionType"] == run["intersection_type"]

        body = client.post(f"/api/v1/study/history/runs/{run['id']}/reproduce").json()
        assert body["isDeterministic"] is True, body["discrepancies"]
        assert (
            body["reproducedMetrics"]["throughput"]
            == run["summary_metrics"]["throughput"]
        )
