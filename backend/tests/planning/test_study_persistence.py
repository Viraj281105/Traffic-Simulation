"""A planning study's state survives a server restart (V2.0 release gate).

Before: only completed studies were written to ``uf_planning_studies``. A
study that was queued or running when the process stopped, or one that had
failed, answered 404 afterwards -- indistinguishable from "deleted" or
"another user's". Now every state is stored, and the process-wide service
marks studies an earlier process left unfinished as failed, with a reason.
"""

import sqlite3
from typing import Any

import pytest

import src.planning.service as service_module
from src.planning.service import PlanningService, get_service
from src.planning.store import INTERRUPTED_ERROR, PlanningStore

from .conftest import make_fake, study


@pytest.fixture(autouse=True)
def isolated_db(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> str:
    path = str(tmp_path / "planning-persist.db")
    monkeypatch.setattr("src.database.db.DB_PATH", path)
    monkeypatch.setattr(service_module, "_default", None)
    return path


def _queued(svc: PlanningService, user: str = "alice") -> str:
    """A study recorded as queued, as submit() leaves it before its job runs."""
    parsed = svc._require_study(study(), user)
    return str(svc._new_record(user, parsed)["id"])


def test_a_study_left_queued_is_reported_interrupted_after_restart() -> None:
    sid = _queued(PlanningService(store=PlanningStore(persist=True)))

    restarted = get_service()  # a new process's service
    record = restarted.get("alice", sid)
    assert record["status"] == "failed"
    assert record["error"] == INTERRUPTED_ERROR
    assert record["result"] is None
    # Still private, and deletable now that it is no longer running.
    with pytest.raises(service_module.NotFound):
        restarted.get("bob", sid)
    restarted.delete("alice", sid)
    with pytest.raises(service_module.NotFound):
        restarted.get("alice", sid)


def test_a_failed_study_survives_a_restart() -> None:
    def broken(*_: Any, **__: Any) -> Any:
        raise RuntimeError("engine exploded")

    svc = PlanningService(store=PlanningStore(persist=True), comparison_fn=broken)
    record = svc.run("alice", study())
    assert record["status"] == "failed"

    fresh = PlanningStore(persist=True).get("alice", record["id"])
    assert fresh is not None
    assert fresh["status"] == "failed"
    assert "engine exploded" in fresh["error"]


def test_completed_studies_are_untouched_by_recovery() -> None:
    svc = PlanningService(store=PlanningStore(persist=True), comparison_fn=make_fake())
    done = svc.run("alice", study())["id"]
    assert PlanningStore(persist=True).mark_interrupted() == 0
    record = PlanningStore(persist=True).get("alice", done)
    assert record is not None and record["status"] == "completed"
    assert record["result"] is not None


def test_a_table_from_before_the_status_columns_is_migrated(isolated_db: str) -> None:
    """Rows written before this change were only ever completed studies."""
    with sqlite3.connect(isolated_db) as conn:
        conn.execute(
            "CREATE TABLE uf_planning_studies (id TEXT PRIMARY KEY, user_id TEXT "
            "NOT NULL, name TEXT, schema_version INTEGER, request_json TEXT, "
            "result_json TEXT, fingerprint TEXT, created_at TEXT)"
        )
        conn.execute(
            "INSERT INTO uf_planning_studies VALUES (?,?,?,?,?,?,?,?)",
            ("old", "alice", "Old", 1, "{}", '{"x": 1}', "fp", "2026-10-01"),
        )
    record = PlanningStore(persist=True).get("alice", "old")
    assert record is not None
    assert record["status"] == "completed" and record["result"] == {"x": 1}
    assert PlanningStore(persist=True).mark_interrupted() == 0
