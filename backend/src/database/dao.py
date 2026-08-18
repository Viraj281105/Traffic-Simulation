import json
import sqlite3
from typing import Any, Dict, Optional, cast


class ConfigurationDAO:
    """DAO for managing simulation configuration items."""

    @staticmethod
    def save(conn: sqlite3.Connection, config_id: str, config: Dict[str, Any]) -> None:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO configurations (id, config_json) VALUES (?, ?);",
            (config_id, json.dumps(config)),
        )

    @staticmethod
    def get(conn: sqlite3.Connection, config_id: str) -> Optional[Dict[str, Any]]:
        cursor = conn.cursor()
        cursor.execute("SELECT config_json FROM configurations WHERE id = ?;", (config_id,))
        row = cursor.fetchone()
        if row:
            return cast(Dict[str, Any], json.loads(row["config_json"]))
        return None


class SimulationRunDAO:
    """DAO for tracking simulation runs."""

    @staticmethod
    def save(conn: sqlite3.Connection, run_id: str, status: str, elapsed: float) -> None:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO simulation_runs (id, status, elapsed) VALUES (?, ?, ?);",
            (run_id, status, elapsed),
        )

    @staticmethod
    def get(conn: sqlite3.Connection, run_id: str) -> Optional[Dict[str, Any]]:
        cursor = conn.cursor()
        cursor.execute("SELECT id, status, elapsed, created_at FROM simulation_runs WHERE id = ?;", (run_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None


class RunMetricsDAO:
    """DAO for storing and retrieving time-series metrics snapshots."""

    @staticmethod
    def save(conn: sqlite3.Connection, run_id: str, tick: int, metrics: Dict[str, Any]) -> None:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO run_metrics (run_id, tick, metrics_json) VALUES (?, ?, ?);",
            (run_id, tick, json.dumps(metrics)),
        )

    @staticmethod
    def get_all_for_run(conn: sqlite3.Connection, run_id: str) -> list[Dict[str, Any]]:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT tick, metrics_json FROM run_metrics WHERE run_id = ? ORDER BY tick ASC;",
            (run_id,),
        )
        rows = cursor.fetchall()
        return [{"tick": r["tick"], "metrics": cast(Dict[str, Any], json.loads(r["metrics_json"]))} for r in rows]
