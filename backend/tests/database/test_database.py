import sqlite3

from src.database.dao import ConfigurationDAO, RunMetricsDAO, SimulationRunDAO
from src.database.db import DB_PATH, init_db


def test_database_crud_operations() -> None:
    """Verifies that we can insert, select, and delete configurations, runs, and metrics from SQLite."""
    init_db()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        # 1. Config DAO Save & Get
        config_id = "test_cfg_1"
        config_data = {"test_key": "test_value"}
        ConfigurationDAO.save(conn, config_id, config_data)
        retrieved_config = ConfigurationDAO.get(conn, config_id)
        assert retrieved_config == config_data

        # 2. Run DAO Save & Get
        run_id = "test_run_1"
        SimulationRunDAO.save(conn, run_id, "completed", 12.5)
        retrieved_run = SimulationRunDAO.get(conn, run_id)
        assert retrieved_run is not None
        assert retrieved_run["status"] == "completed"
        assert retrieved_run["elapsed"] == 12.5

        # 3. Metrics DAO Save & Get
        metrics_data = {"throughput": 15, "wait_time": 4.2}
        RunMetricsDAO.save(conn, run_id, 10, metrics_data)
        retrieved_metrics = RunMetricsDAO.get_all_for_run(conn, run_id)
        assert len(retrieved_metrics) == 1
        assert retrieved_metrics[0]["tick"] == 10
        assert retrieved_metrics[0]["metrics"] == metrics_data

    finally:
        conn.close()


def test_database_transaction_rollback() -> None:
    """Verifies that failures during a transaction successfully trigger a rollback of all written changes."""
    init_db()
    conn = sqlite3.connect(DB_PATH)

    # First ensure rollback_run_1 doesn't exist
    conn.execute("DELETE FROM simulation_runs WHERE id = 'rollback_run_1';")
    conn.commit()

    try:
        # Start transaction
        conn.execute("BEGIN TRANSACTION;")

        # Write valid simulation run
        SimulationRunDAO.save(conn, "rollback_run_1", "running", 0.0)

        # Trigger unique constraint violation by inserting the duplicate primary key manually
        # (This will fail because 'rollback_run_1' was just inserted in the same transaction)
        conn.execute("INSERT INTO simulation_runs (id, status, elapsed) VALUES ('rollback_run_1', 'failed', 0.0);")

        conn.commit()
    except sqlite3.IntegrityError:
        # Successfully caught exception, rollback!
        conn.rollback()

    finally:
        conn.close()

    # Verify that the run 'rollback_run_1' was NOT committed to the database
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        run = SimulationRunDAO.get(conn, "rollback_run_1")
        assert run is None
    finally:
        conn.close()
