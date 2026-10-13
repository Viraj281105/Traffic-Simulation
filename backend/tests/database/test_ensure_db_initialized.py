"""ensure_db_initialized(): the schema check request handlers run first.

It replaced per-request init_db() calls, so it must still create the schema
on the first use of a database file and after that file is removed, while
skipping the DDL on every other request.
"""

import os
import sqlite3
from typing import Any, List

import pytest

import src.database.db as db_module


def _tables(path: str) -> set[str]:
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        return {row[0] for row in rows}
    finally:
        conn.close()


@pytest.fixture
def counted_init(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> List[str]:
    """Points DB_PATH at a fresh file and records each real init_db() call."""
    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "ensure.db"))
    calls: List[str] = []
    real_init = db_module.init_db

    def counting_init() -> None:
        calls.append(db_module.DB_PATH)
        real_init()

    monkeypatch.setattr(db_module, "init_db", counting_init)
    return calls


def test_first_use_creates_the_schema(counted_init: List[str]) -> None:
    db_module.ensure_db_initialized()
    assert counted_init == [db_module.DB_PATH]
    assert {"simulation_runs", "saved_replays", "scenario_suites"} <= _tables(
        db_module.DB_PATH
    )


def test_later_calls_skip_the_ddl(counted_init: List[str]) -> None:
    for _ in range(5):
        db_module.ensure_db_initialized()
    assert len(counted_init) == 1


def test_a_removed_file_is_recreated(counted_init: List[str]) -> None:
    db_module.ensure_db_initialized()
    for suffix in ("", "-wal", "-shm"):
        if os.path.exists(db_module.DB_PATH + suffix):
            os.remove(db_module.DB_PATH + suffix)

    db_module.ensure_db_initialized()
    assert len(counted_init) == 2
    assert "simulation_runs" in _tables(db_module.DB_PATH)


def test_each_database_file_is_initialised_separately(
    counted_init: List[str], tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_module.ensure_db_initialized()
    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "other.db"))
    db_module.ensure_db_initialized()
    assert len(counted_init) == 2
    assert "simulation_runs" in _tables(db_module.DB_PATH)


def test_concurrent_first_use_of_a_legacy_database_migrates_once(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Threads arriving together at a database that still needs its
    migrations. Unserialised, each read the same columns as missing and
    altered the table at once: "database is locked" / "duplicate column name"
    in nearly every trial."""
    import threading

    path = str(tmp_path / "legacy.db")
    conn = sqlite3.connect(path)
    # The original V1.0 schema of simulation_runs.
    conn.execute(
        "CREATE TABLE simulation_runs (id TEXT PRIMARY KEY, status TEXT NOT NULL, "
        "elapsed REAL NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(db_module, "DB_PATH", path)

    errors: List[BaseException] = []
    start = threading.Barrier(8)

    def request() -> None:
        start.wait()
        try:
            db_module.ensure_db_initialized()
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=request) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    check = sqlite3.connect(path)
    try:
        columns = {
            row[1] for row in check.execute("PRAGMA table_info(simulation_runs)")
        }
    finally:
        check.close()
    assert {"suite_id", "provenance_json", "user_id"} <= columns


def test_a_failed_initialisation_is_retried(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failure partway through leaves the file unmarked, so the next request
    runs the schema again and completes it."""
    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "retry.db"))
    real_schema = db_module._create_schema
    attempts: List[int] = []

    def failing_once(conn: sqlite3.Connection) -> None:
        attempts.append(1)
        if len(attempts) == 1:
            conn.execute("CREATE TABLE configurations (id TEXT PRIMARY KEY)")
            raise sqlite3.OperationalError("disk I/O error")
        real_schema(conn)

    monkeypatch.setattr(db_module, "_create_schema", failing_once)

    with pytest.raises(sqlite3.OperationalError):
        db_module.ensure_db_initialized()
    db_module.ensure_db_initialized()

    assert len(attempts) == 2
    assert "simulation_runs" in _tables(db_module.DB_PATH)


def test_in_memory_databases_are_initialised_every_time(
    counted_init: List[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """ ":memory:" is a new, empty database per connection, so there is no file
    to remember: every call initialises, as init_db() on every request did."""
    monkeypatch.setattr(db_module, "DB_PATH", ":memory:")
    db_module.ensure_db_initialized()
    db_module.ensure_db_initialized()
    assert counted_init == [":memory:", ":memory:"]
