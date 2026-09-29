"""A sweep is saved in one transaction, and the sweep listing is summaries."""

import sqlite3
from typing import Any

import pytest

from src.database import db
from src.database.dao import RunMetricsDAO, SimulationRunDAO, SweepSessionDAO
from src.study.volume_sweep import run_volume_sweep_experiment


@pytest.fixture
def conn(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "batch.db"))
    db.init_db()
    with db.get_db_connection() as connection:
        yield connection


def _count(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f"SELECT COUNT(*) FROM {table};").fetchone()[0])


def test_uncommitted_writes_belong_to_the_callers_transaction(conn: Any) -> None:
    SimulationRunDAO.save(conn, "r1", "completed", 1.0, commit=False)
    RunMetricsDAO.save(conn, "r1", 10, {"throughput": 3}, commit=False)
    SweepSessionDAO.save(conn, "s1", "sweep", {}, {"runs": []}, commit=False)
    conn.rollback()
    assert _count(conn, "simulation_runs") == 0
    assert _count(conn, "run_metrics") == 0
    assert _count(conn, "sweep_sessions") == 0

    SimulationRunDAO.save(conn, "r2", "completed", 1.0)  # default: commits
    conn.rollback()
    assert _count(conn, "simulation_runs") == 1


def test_sweep_persists_every_run_and_lists_as_a_summary(conn: Any) -> None:
    result = run_volume_sweep_experiment(arrival_rates=[0.2, 0.4], duration=5.0)
    assert _count(conn, "simulation_runs") == 4
    assert _count(conn, "run_metrics") == 4

    listed = SweepSessionDAO.list_sessions(conn)
    assert listed == [
        {
            "id": result["sessionId"],
            "name": "Comparative Volume Sweep",
            "created_at": listed[0]["created_at"],
        }
    ]
    stored = SweepSessionDAO.get(conn, result["sessionId"])
    assert stored is not None
    assert stored["results"]["runs"] == result["runs"]
