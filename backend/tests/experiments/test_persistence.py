"""Persistence and the additive migration of ``uf_experiments``."""

import sqlite3

from src.database import db
from src.experiments.service import ExperimentService
from src.experiments.store import INTERRUPTED_ERROR, ExperimentStore, ensure_table

from .conftest import as_user, build_client, submit, wait_for


def _schema(path: str) -> dict:
    with sqlite3.connect(path) as conn:
        return dict(conn.execute("SELECT name, sql FROM sqlite_master").fetchall())


def test_finished_experiments_survive_a_new_process(make_service):
    first = build_client(make_service(persist=True))
    done = wait_for(first, submit(first)["id"])
    before = first.get(
        f"/api/v3/experiments/{done['id']}/result", headers=as_user("alice")
    ).json()

    reopened = build_client(
        make_service(persist=True)
    )  # a new store: nothing in memory
    status = reopened.get(
        f"/api/v3/experiments/{done['id']}", headers=as_user("alice")
    ).json()
    assert status["status"] == "completed" and status["resultAvailable"] is True
    assert status["counts"]["totalRuns"] == 40
    after = reopened.get(
        f"/api/v3/experiments/{done['id']}/result", headers=as_user("alice")
    ).json()
    assert after == before
    listing = reopened.get("/api/v3/experiments", headers=as_user("alice")).json()
    assert [e["id"] for e in listing["experiments"]] == [done["id"]]
    assert listing["experiments"][0]["resultAvailable"] is True
    # still private after reload
    other = reopened.get(f"/api/v3/experiments/{done['id']}", headers=as_user("bob"))
    assert other.status_code == 404
    bobs = reopened.get("/api/v3/experiments", headers=as_user("bob")).json()
    assert bobs["experiments"] == []


def test_delete_removes_the_row_from_disk(make_service):
    client = build_client(make_service(persist=True))
    done = wait_for(client, submit(client)["id"])
    response = client.delete(
        f"/api/v3/experiments/{done['id']}", headers=as_user("alice")
    )
    assert response.status_code == 200
    with sqlite3.connect(db.DB_PATH) as conn:
        assert conn.execute("SELECT COUNT(*) FROM uf_experiments").fetchone()[0] == 0
    reopened = build_client(make_service(persist=True))
    gone = reopened.get(f"/api/v3/experiments/{done['id']}", headers=as_user("alice"))
    assert gone.status_code == 404


def test_an_experiment_a_dead_process_was_running_is_reported_failed(make_service):
    service = make_service(persist=True)
    service.store.put(
        {
            "id": "a" * 32,
            "userId": "alice",
            "name": "interrupted",
            "status": "running",
            "request": {},
            "summary": {
                "conditions": 1,
                "alternatives": 2,
                "replications": 1,
                "totalRuns": 2,
            },
            "result": None,
            "specFingerprint": "0" * 16,
            "error": None,
            "createdAt": "2026-10-15T00:00:00+00:00",
        }
    )
    restarted = make_service(persist=True)
    assert restarted.store.mark_interrupted() == 1
    client = build_client(restarted)
    status = client.get(
        f"/api/v3/experiments/{'a' * 32}", headers=as_user("alice")
    ).json()
    assert status["status"] == "failed" and status["error"] == INTERRUPTED_ERROR
    # it no longer counts as running, so the owner can submit again
    wait_for(client, submit(client)["id"])


def test_migration_is_additive_and_idempotent(tmp_path, monkeypatch):
    path = str(tmp_path / "existing.db")
    monkeypatch.setattr(db, "DB_PATH", path)
    db.init_db()  # the application's own tables, as an existing deployment has them
    before = _schema(path)
    assert "uf_experiments" not in before

    with sqlite3.connect(path) as conn:
        ensure_table(conn)
        ensure_table(conn)  # running it again changes nothing
    after = _schema(path)

    assert {
        k: v for k, v in after.items() if k in before
    } == before  # nothing existing was touched
    added = {
        name for name in set(after) - set(before) if not name.startswith("sqlite_")
    }
    assert added == {"uf_experiments", "idx_uf_experiments_user"}


def test_migration_keeps_rows_already_written(tmp_path):
    with sqlite3.connect(str(tmp_path / "rows.db")) as conn:
        ensure_table(conn)
        conn.execute(
            "INSERT INTO uf_experiments (id, user_id, name, status) "
            "VALUES ('x', 'u', 'kept', 'completed')"
        )
        conn.commit()
        ensure_table(conn)
        row = conn.execute("SELECT name FROM uf_experiments WHERE id='x'").fetchone()
        assert row[0] == "kept"


def test_a_broken_database_never_fails_an_experiment(make_service, monkeypatch):
    service = make_service(persist=True)
    monkeypatch.setattr(
        "src.database.db.DB_PATH", str(db.os.path.join("Z:\\no-such-drive", "x.db"))
    )
    client = build_client(service)
    done = wait_for(client, submit(client)["id"])
    assert (
        done["status"] == "completed"
    )  # kept in memory even though it could not be saved


def test_default_service_uses_the_real_executor():
    service = ExperimentService(store=ExperimentStore(persist=False))
    assert (
        service.executor is None
    )  # run_experiment's own default: the isolated process pool


def test_a_failing_audit_write_never_fails_an_experiment(
    make_service, monkeypatch, caplog
):
    service = make_service(persist=False)

    def broken(*args, **kwargs):
        raise RuntimeError("audit store down")

    monkeypatch.setattr("src.api.token_store.AuditStore.record_event", broken)
    client = build_client(service)
    with caplog.at_level("WARNING"):
        done = wait_for(client, submit(client)["id"])
    assert done["status"] == "completed"
    assert any("audit event not recorded" in r.getMessage() for r in caplog.records)
