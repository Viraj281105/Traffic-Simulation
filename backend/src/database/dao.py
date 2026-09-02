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
        cursor.execute(
            "SELECT config_json FROM configurations WHERE id = ?;", (config_id,)
        )
        row = cursor.fetchone()
        if row:
            return cast(Dict[str, Any], json.loads(row["config_json"]))
        return None


class SimulationRunDAO:
    """DAO for tracking simulation runs."""

    @staticmethod
    def save(
        conn: sqlite3.Connection, run_id: str, status: str, elapsed: float
    ) -> None:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO simulation_runs (id, status, elapsed) VALUES (?, ?, ?);",
            (run_id, status, elapsed),
        )

    @staticmethod
    def get(conn: sqlite3.Connection, run_id: str) -> Optional[Dict[str, Any]]:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, status, elapsed, created_at FROM simulation_runs WHERE id = ?;",
            (run_id,),
        )
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

    @staticmethod
    def list_runs(
        conn: sqlite3.Connection, limit: int = 50, offset: int = 0
    ) -> list[Dict[str, Any]]:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, status, elapsed, created_at FROM simulation_runs ORDER BY created_at DESC LIMIT ? OFFSET ?;",
            (limit, offset),
        )
        rows = cursor.fetchall()
        return [dict(r) for r in rows]


class RunMetricsDAO:
    """DAO for storing and retrieving time-series metrics snapshots."""

    @staticmethod
    def save(
        conn: sqlite3.Connection, run_id: str, tick: int, metrics: Dict[str, Any]
    ) -> None:
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
        return [
            {
                "tick": r["tick"],
                "metrics": cast(Dict[str, Any], json.loads(r["metrics_json"])),
            }
            for r in rows
        ]

    @staticmethod
    def get_latest_for_run(
        conn: sqlite3.Connection, run_id: str
    ) -> Optional[Dict[str, Any]]:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT tick, metrics_json FROM run_metrics WHERE run_id = ? ORDER BY tick DESC LIMIT 1;",
            (run_id,),
        )
        row = cursor.fetchone()
        if row:
            return {
                "tick": row["tick"],
                "metrics": cast(Dict[str, Any], json.loads(row["metrics_json"])),
            }
        return None


class SweepSessionDAO:
    """DAO for managing traffic volume sweep sessions and comparative benchmark experiments."""

    @staticmethod
    def save(
        conn: sqlite3.Connection,
        session_id: str,
        name: str,
        config: Dict[str, Any],
        results: Dict[str, Any],
    ) -> None:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO sweep_sessions (id, name, config_json, results_json) VALUES (?, ?, ?, ?);",
            (session_id, name, json.dumps(config), json.dumps(results)),
        )

    @staticmethod
    def get(conn: sqlite3.Connection, session_id: str) -> Optional[Dict[str, Any]]:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, config_json, results_json, created_at FROM sweep_sessions WHERE id = ?;",
            (session_id,),
        )
        row = cursor.fetchone()
        if row:
            return {
                "id": row["id"],
                "name": row["name"],
                "config": json.loads(row["config_json"]),
                "results": json.loads(row["results_json"]),
                "created_at": row["created_at"],
            }
        return None

    @staticmethod
    def list_sessions(
        conn: sqlite3.Connection, limit: int = 50, offset: int = 0
    ) -> list[Dict[str, Any]]:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, config_json, results_json, created_at FROM sweep_sessions ORDER BY created_at DESC LIMIT ? OFFSET ?;",
            (limit, offset),
        )
        rows = cursor.fetchall()
        return [
            {
                "id": r["id"],
                "name": r["name"],
                "config": json.loads(r["config_json"]),
                "results": json.loads(r["results_json"]),
                "created_at": r["created_at"],
            }
            for r in rows
        ]
