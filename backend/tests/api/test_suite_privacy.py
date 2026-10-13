"""Scenario suites are private to their creator (V2.0 release gate R1.4/R3.4).

Another user's suite answers 404 on every suite route, exactly like a missing
one; admins see every suite, including legacy suites stored before suites had
an owner, which nobody else can see. A suite cannot be created around runs
that belong to another user, so its run list cannot be used to read them.
"""

import sqlite3
from typing import Any, Iterator

import pytest
from fastapi.testclient import TestClient

from src.auth import get_current_user_id, get_current_user_is_admin
from src.database import db
from src.database.dao import SimulationRunDAO
from src.main import app

client = TestClient(app)

BATCH = {
    "baseConfig": {"intersectionType": "fixed_time_signal", "duration": 4},
    "sweepParameters": {"arrivalRate": [0.2]},
    "numSeeds": 1,
}


@pytest.fixture(autouse=True)
def isolated_db(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> str:
    path = str(tmp_path / "suites-private.db")
    monkeypatch.setattr(db, "DB_PATH", path)
    monkeypatch.delenv("API_KEY", raising=False)
    db.init_db()
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


def _create(run_ids: Any = ()) -> Any:
    return client.post(
        "/api/suites",
        json={
            "name": "Private",
            "description": "",
            "run_ids": list(run_ids),
            "config_variations": {},
        },
    )


def _listed() -> set:
    return {s["id"] for s in client.get("/api/suites").json()["suites"]}


def _save_run(run_id: str, user_id: Any) -> None:
    with db.get_db_connection() as conn:
        SimulationRunDAO.save(conn, run_id, "completed", 1.0, user_id=user_id)


def test_suite_routes_require_a_signed_in_user() -> None:
    assert _create().status_code == 401
    assert client.get("/api/suites").status_code == 401
    assert client.get("/api/suites/any").status_code == 401
    assert client.get("/api/suites/any/export/csv").status_code == 401
    assert client.post("/api/suites/any/batch", json=BATCH).status_code == 401


def test_another_users_suite_is_404_everywhere(act_as: Any) -> None:
    act_as("alice")
    suite_id = _create().json()["id"]
    assert client.get(f"/api/suites/{suite_id}").status_code == 200
    assert client.get(f"/api/suites/{suite_id}/export/csv").status_code == 200
    assert suite_id in _listed()

    act_as("bob")
    assert suite_id not in _listed()
    assert client.get(f"/api/suites/{suite_id}").status_code == 404
    assert client.get(f"/api/suites/{suite_id}/export/csv").status_code == 404
    # Refused before any simulation is queued.
    assert client.post(f"/api/suites/{suite_id}/batch", json=BATCH).status_code == 404


def test_admin_sees_all_and_legacy_suites_are_admin_only(
    act_as: Any, isolated_db: str
) -> None:
    act_as("alice")
    alice_suite = _create().json()["id"]
    legacy_suite = _create().json()["id"]
    with sqlite3.connect(isolated_db) as conn:
        conn.execute(
            "UPDATE scenario_suites SET user_id = NULL WHERE id = ?", (legacy_suite,)
        )

    assert legacy_suite not in _listed()
    assert client.get(f"/api/suites/{legacy_suite}").status_code == 404

    act_as("root", admin=True)
    assert {alice_suite, legacy_suite} <= _listed()
    assert client.get(f"/api/suites/{legacy_suite}").status_code == 200
    assert client.get(f"/api/suites/{alice_suite}").status_code == 200


def test_a_suite_cannot_be_built_from_another_users_runs(act_as: Any) -> None:
    _save_run("run_alice", "alice")
    _save_run("run_free", None)

    act_as("bob")
    assert _create(["run_alice"]).status_code == 404
    assert _create(["run_missing"]).status_code == 404
    with db.get_db_connection() as conn:
        assert (
            conn.execute(
                "SELECT suite_id FROM simulation_runs WHERE id = 'run_alice'"
            ).fetchone()[0]
            is None
        )

    act_as("alice")
    created = _create(["run_alice", "run_free"])
    assert created.status_code == 200
    runs = client.get(f"/api/suites/{created.json()['id']}").json()["runs"]
    assert {r["id"] for r in runs} == {"run_alice", "run_free"}
    # A run belongs to one suite at most.
    assert _create(["run_alice"]).status_code == 400


def test_a_suites_table_from_before_ownership_is_migrated(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch, act_as: Any
) -> None:
    old = str(tmp_path / "old.db")
    with sqlite3.connect(old) as conn:
        conn.execute(
            """CREATE TABLE scenario_suites (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT,
                run_ids_json TEXT NOT NULL DEFAULT '[]',
                config_variations_json TEXT NOT NULL DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"""
        )
        conn.execute("INSERT INTO scenario_suites (id, name) VALUES ('old', 'Old')")
    monkeypatch.setattr(db, "DB_PATH", old)
    db.init_db()

    act_as("alice")
    assert "old" not in _listed()
    act_as("root", admin=True)
    assert "old" in _listed()
