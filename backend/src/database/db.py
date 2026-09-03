import os
import sqlite3
from typing import Generator

DB_PATH = os.environ.get("DB_PATH", "simulation.db")


def init_db() -> None:
    """Initializes the SQLite database tables if they do not exist."""
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Enable Foreign Key support
    cursor.execute("PRAGMA foreign_keys = ON;")

    # 1. Configurations table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS configurations (
            id TEXT PRIMARY KEY,
            config_json TEXT NOT NULL
        );
        """
    )

    # 2. Simulation Runs table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS simulation_runs (
            id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            elapsed REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    # 3. Run Metrics table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS run_metrics (
            run_id TEXT,
            tick INTEGER,
            metrics_json TEXT NOT NULL,
            PRIMARY KEY (run_id, tick),
            FOREIGN KEY (run_id) REFERENCES simulation_runs(id) ON DELETE CASCADE
        );
        """
    )

    # 4. Sweep Sessions table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS sweep_sessions (
            id TEXT PRIMARY KEY,
            name TEXT,
            config_json TEXT NOT NULL,
            results_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    # 5. Saved Replays table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS saved_replays (
            id TEXT PRIMARY KEY,
            name TEXT,
            config_json TEXT NOT NULL,
            metrics_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    conn.commit()
    conn.close()


def get_db_connection() -> Generator[sqlite3.Connection, None, None]:
    """Yields a database connection context manager."""
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
