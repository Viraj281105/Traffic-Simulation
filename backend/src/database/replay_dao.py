import json
import sqlite3
import uuid
from typing import Any, Dict, List, Optional


class ReplayDAO:
    """DAO for managing deterministic simulation replays (config + final metrics)."""

    @staticmethod
    def save(
        conn: sqlite3.Connection,
        name: str,
        config: Dict[str, Any],
        metrics: Dict[str, Any],
    ) -> str:
        replay_id = str(uuid.uuid4())
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO saved_replays (id, name, config_json, metrics_json)
            VALUES (?, ?, ?, ?);
            """,
            (replay_id, name, json.dumps(config), json.dumps(metrics)),
        )
        conn.commit()
        return replay_id

    @staticmethod
    def get(conn: sqlite3.Connection, replay_id: str) -> Optional[Dict[str, Any]]:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, config_json, metrics_json, created_at FROM saved_replays WHERE id = ?;",
            (replay_id,),
        )
        row = cursor.fetchone()
        if row:
            return {
                "id": row["id"],
                "name": row["name"],
                "config": json.loads(row["config_json"]),
                "metrics": json.loads(row["metrics_json"]),
                "created_at": row["created_at"],
            }
        return None

    @staticmethod
    def list_all(
        conn: sqlite3.Connection, limit: int = 50, offset: int = 0
    ) -> List[Dict[str, Any]]:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, config_json, metrics_json, created_at FROM saved_replays ORDER BY created_at DESC LIMIT ? OFFSET ?;",
            (limit, offset),
        )
        rows = cursor.fetchall()
        return [
            {
                "id": r["id"],
                "name": r["name"],
                "config": json.loads(r["config_json"]),
                "metrics": json.loads(r["metrics_json"]),
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    @staticmethod
    def delete(conn: sqlite3.Connection, replay_id: str) -> bool:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM saved_replays WHERE id = ?;", (replay_id,))
        rows_affected = cursor.rowcount
        conn.commit()
        return rows_affected > 0
