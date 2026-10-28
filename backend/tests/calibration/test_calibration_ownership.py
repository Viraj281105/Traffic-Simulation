"""Calibration runs belong to their creator.

A run holds the observations a user typed in, so another user must not list,
read, re-use (as a planning subject) or delete it; admins see every run,
including legacy rows stored before runs had an owner.
"""

import copy
import sqlite3
from functools import lru_cache
from typing import Any, Dict, Iterator

import pytest
from fastapi.testclient import TestClient

from src.api.auth import get_current_user_id, get_current_user_is_admin
from src.calibration import store
from src.calibration.runner import run_calibration
from src.main import app
from tests.calibration.test_calibration import request

client = TestClient(app)


@lru_cache(maxsize=1)
def _result() -> Dict[str, Any]:
    return run_calibration(request())


@pytest.fixture(autouse=True)
def isolated_db(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> str:
    path = str(tmp_path / "cal-owner.db")
    monkeypatch.setattr("src.database.db.DB_PATH", path)
    return path


@pytest.fixture
def act_as() -> Iterator[Any]:
    def sign_in(user: str, admin: bool = False) -> None:
        app.dependency_overrides[get_current_user_id] = lambda: user
        app.dependency_overrides[get_current_user_is_admin] = lambda: admin

    try:
        yield sign_in
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)
        app.dependency_overrides.pop(get_current_user_is_admin, None)


def _saved_by(user: str) -> str:
    return str(store.save(request(), copy.deepcopy(_result()), user)["id"])


def _listed() -> set:
    return {r["id"] for r in client.get("/api/v2/calibration/runs").json()["runs"]}


def test_another_users_run_is_invisible(act_as: Any) -> None:
    alice_run = _saved_by("alice")

    act_as("alice")
    assert client.get(f"/api/v2/calibration/runs/{alice_run}").status_code == 200
    scenario = client.get(f"/api/v2/calibration/runs/{alice_run}/scenario")
    assert scenario.status_code == 200
    assert alice_run in _listed()

    act_as("bob")
    assert client.get(f"/api/v2/calibration/runs/{alice_run}").status_code == 404
    assert (
        client.get(f"/api/v2/calibration/runs/{alice_run}/scenario").status_code == 404
    )
    assert client.delete(f"/api/v2/calibration/runs/{alice_run}").status_code == 404
    assert alice_run not in _listed()

    # Bob's failed delete changed nothing.
    act_as("alice")
    assert client.get(f"/api/v2/calibration/runs/{alice_run}").status_code == 200


def test_owner_can_delete_and_the_run_is_gone(act_as: Any) -> None:
    run_id = _saved_by("alice")
    act_as("alice")
    res = client.delete(f"/api/v2/calibration/runs/{run_id}")
    assert res.status_code == 200 and res.json() == {"id": run_id, "deleted": True}
    assert client.get(f"/api/v2/calibration/runs/{run_id}").status_code == 404
    assert store.get(run_id) is None


def test_runs_are_created_with_the_callers_id(act_as: Any) -> None:
    act_as("carol")
    created = client.post("/api/v2/calibration/runs", json=request())
    assert created.status_code == 201
    run_id = created.json()["id"]
    assert store.get_for_user(run_id, "carol") is not None
    assert store.get_for_user(run_id, "dave") is None


def test_admin_sees_every_run_and_legacy_rows_only_admins_see(
    act_as: Any, isolated_db: str
) -> None:
    alice_run = _saved_by("alice")
    legacy_run = _saved_by("someone")
    with sqlite3.connect(isolated_db) as conn:
        conn.execute(
            "UPDATE uf_calibration_runs SET user_id = NULL WHERE id = ?", (legacy_run,)
        )

    act_as("bob")
    assert legacy_run not in _listed()
    assert client.get(f"/api/v2/calibration/runs/{legacy_run}").status_code == 404

    act_as("root", admin=True)
    assert {alice_run, legacy_run} <= _listed()
    assert client.get(f"/api/v2/calibration/runs/{legacy_run}").status_code == 200


def test_a_table_from_before_ownership_is_migrated(isolated_db: str) -> None:
    with sqlite3.connect(isolated_db) as conn:
        conn.execute(
            """CREATE TABLE uf_calibration_runs (
                id TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                scenario_fingerprint TEXT NOT NULL,
                observations_fingerprint TEXT NOT NULL,
                status TEXT NOT NULL,
                request_json TEXT NOT NULL,
                result_json TEXT NOT NULL)"""
        )
        conn.execute(
            "INSERT INTO uf_calibration_runs VALUES "
            "('old', CURRENT_TIMESTAMP, 'a', 'b', 'uncalibrated', '{}', '{}')"
        )
    assert store.list_runs("anyone") == []
    assert [r["id"] for r in store.list_runs("root", is_admin=True)] == ["old"]
    new_run = _saved_by("alice")
    assert [r["id"] for r in store.list_runs("alice")] == [new_run]


def test_a_planning_study_cannot_attach_another_users_run(act_as: Any) -> None:
    alice_run = _saved_by("alice")
    study = {
        "name": "Borrowed calibration",
        "subject": {},
        "calibration": {"runId": alice_run, "useFittedScenario": True},
        "alternatives": [
            {"id": "base", "strategy": "fixed_time"},
            {"id": "rbt", "strategy": "roundabout"},
        ],
        "repetitions": {"seeds": 2, "baseSeed": 1},
    }

    act_as("bob")
    checked = client.post("/api/v2/planning/validate", json=study).json()
    assert checked["valid"] is False
    assert any("not found" in e for e in checked["errors"])
    # Nothing about Alice's run (its fingerprints) leaks into the answer.
    assert checked.get("scenarioFingerprint") is None
    assert client.post("/api/v2/planning/run", json=study).status_code == 422
    assert client.post("/api/v2/planning/jobs", json=study).status_code == 422

    act_as("alice")
    assert client.post("/api/v2/planning/validate", json=study).json()["valid"]


def test_rejected_study_reasons_arrive_as_a_list(act_as: Any) -> None:
    """The planner shows each reason the server gives; the error envelope
    keeps the planning router's list instead of a flattened repr."""
    act_as("bob")
    res = client.post(
        "/api/v2/planning/run",
        json={"subject": {}, "calibration": {"runId": "missing"}},
    )
    assert res.status_code == 422
    error = res.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["details"]["errors"] and all(
        isinstance(e, str) for e in error["details"]["errors"]
    )
    assert error["message"] == "; ".join(error["details"]["errors"])
