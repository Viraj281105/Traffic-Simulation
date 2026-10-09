import json
import sqlite3

import pytest

from src.database.dao import ScenarioSuiteDAO, SimulationRunDAO
from src.database.db import init_db

@pytest.fixture
def test_db():
    # Use in-memory db for testing
    import src.database.db
    src.database.db.DB_PATH = ":memory:"
    init_db()
    conn = sqlite3.connect(":memory:")
    # Wait, we need to run init_db on the exact connection we return, or let init_db create tables in the current memory scope
    # Since :memory: is per-connection, we should just run the init script on our conn
    conn.row_factory = sqlite3.Row
    # Re-create tables manually or patch DB_PATH properly.
    # A better approach for SQLite in-memory:
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    # 1. Runs
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS simulation_runs (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            status TEXT NOT NULL,
            elapsed REAL NOT NULL,
            intersection_type TEXT NOT NULL DEFAULT 'unknown',
            random_seed INTEGER NOT NULL DEFAULT 0,
            arrival_rate REAL DEFAULT 0.5,
            duration REAL DEFAULT 60.0,
            batch_id TEXT,
            config_json TEXT NOT NULL DEFAULT '{}',
            summary_metrics_json TEXT NOT NULL DEFAULT '{}',
            git_commit TEXT,
            provenance_json TEXT,
            name TEXT,
            notes TEXT,
            tags_json TEXT,
            email TEXT,
            suite_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    # 2. Suites
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS scenario_suites (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            run_ids_json TEXT NOT NULL DEFAULT '[]',
            config_variations_json TEXT NOT NULL DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    yield conn
    conn.close()

def test_save_and_get_suite(test_db):
    suite_id = "suite-123"
    run_ids = ["run-1", "run-2"]
    
    # Need to insert runs first because of schema logic, though there's no FK constraint yet
    for r in run_ids:
        test_db.execute("INSERT INTO simulation_runs (id, status, elapsed) VALUES (?, 'COMPLETED', 1.0)", (r,))
    
    ScenarioSuiteDAO.save(
        test_db,
        suite_id=suite_id,
        name="Test Suite",
        description="A test suite",
        run_ids=run_ids,
        config_variations={"run-1": "base", "run-2": "variant"}
    )
    
    suite = ScenarioSuiteDAO.get(test_db, suite_id)
    assert suite is not None
    assert suite["id"] == suite_id
    assert suite["name"] == "Test Suite"
    assert suite["description"] == "A test suite"
    assert suite["run_ids"] == run_ids
    assert suite["config_variations"]["run-1"] == "base"
    
    # Verify the suite_id was updated on the runs
    cursor = test_db.cursor()
    cursor.execute("SELECT id, suite_id FROM simulation_runs;")
    runs = cursor.fetchall()
    assert len(runs) == 2
    for r in runs:
        assert r["suite_id"] == suite_id

def test_list_suites(test_db):
    import time
    ScenarioSuiteDAO.save(test_db, "s1", "Suite 1", "", [], {})
    time.sleep(1.0)
    ScenarioSuiteDAO.save(test_db, "s2", "Suite 2", "", [], {})
    
    suites = ScenarioSuiteDAO.list_suites(test_db)
    assert len(suites) == 2
    # newest first
    assert suites[0]["id"] == "s2"
    assert suites[1]["id"] == "s1"
