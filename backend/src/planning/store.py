"""Where planning studies are kept: in memory, mirrored to the
``uf_planning_studies`` SQLite table when persistence is on (inline,
additive migration).
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_TABLE = """
CREATE TABLE IF NOT EXISTS uf_planning_studies (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    name TEXT,
    schema_version INTEGER,
    request_json TEXT,
    result_json TEXT,
    fingerprint TEXT,
    created_at TEXT,
    status TEXT,
    error TEXT
)
"""

# Shown for a study that a previous server process was still running: its job
# died with that process (there is no durable job queue), so it is reported as
# failed with this reason rather than vanishing (a 404 would read as "deleted").
INTERRUPTED_ERROR = (
    "Interrupted by a server restart before it finished; run the study again."
)


def _ensure_table(conn: Any) -> None:
    """Create the table, and add the status/error columns to one created
    before they existed (inline migration, as in database/db.py). Rows from
    before the migration were only ever written for completed studies."""
    conn.execute(_TABLE)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(uf_planning_studies)")}
    for column in ("status", "error"):
        if column not in columns:
            conn.execute(f"ALTER TABLE uf_planning_studies ADD COLUMN {column} TEXT")
    conn.commit()


class PlanningStore:
    """In-memory records keyed by id, mirrored to SQLite when available."""

    def __init__(self, persist: bool = True) -> None:
        self._records: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._persist = persist

    def put(self, record: Dict[str, Any]) -> None:
        """Keep the record and persist its current state: queued, running,
        completed and failed studies all survive a restart."""
        with self._lock:
            self._records[record["id"]] = record
        self._save(record)

    def get(self, user_id: str, study_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            rec = self._records.get(study_id)
        if rec is None:
            rec = self._load(study_id)
        if rec is None or rec["userId"] != user_id:
            return None  # another user's study is indistinguishable from none
        return rec

    def delete(self, study_id: str) -> None:
        """Remove a study everywhere. Unlike saving, a failure here is raised:
        a delete that silently left the data on disk would be a false promise
        to the user."""
        with self._lock:
            self._records.pop(study_id, None)
        if not self._persist:
            return
        from src.database.db import get_db_connection

        with get_db_connection() as conn:
            _ensure_table(conn)
            conn.execute("DELETE FROM uf_planning_studies WHERE id = ?", (study_id,))
            conn.commit()

    def mark_interrupted(self) -> int:
        """Mark every study a previous process left queued or running as
        failed (``INTERRUPTED_ERROR``). Call once, before this process starts
        any job. Returns how many were marked."""
        if not self._persist:
            return 0
        from src.database.db import get_db_connection

        with get_db_connection() as conn:
            _ensure_table(conn)
            cursor = conn.execute(
                "UPDATE uf_planning_studies SET status = 'failed', error = ? "
                "WHERE status IN ('queued', 'running')",
                (INTERRUPTED_ERROR,),
            )
            conn.commit()
            return int(cursor.rowcount)

    def _save(self, rec: Dict[str, Any]) -> None:
        if not self._persist:
            return
        try:
            from src.database.db import get_db_connection

            result = rec.get("result")
            with get_db_connection() as conn:
                _ensure_table(conn)
                conn.execute(
                    "INSERT OR REPLACE INTO uf_planning_studies (id, user_id, name, "
                    "schema_version, request_json, result_json, fingerprint, "
                    "created_at, status, error) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (
                        rec["id"],
                        rec["userId"],
                        rec["name"],
                        1,
                        json.dumps(rec["request"]),
                        None if result is None else json.dumps(result),
                        None if result is None else result["scenario"]["fingerprint"],
                        rec["createdAt"],
                        rec["status"],
                        rec.get("error"),
                    ),
                )
                conn.commit()
        except Exception:  # persistence must never fail a study
            logger.warning(
                "Could not persist planning study %s", rec["id"], exc_info=True
            )

    def _load(self, study_id: str) -> Optional[Dict[str, Any]]:
        if not self._persist:
            return None
        try:
            from src.database.db import get_db_connection

            with get_db_connection() as conn:
                _ensure_table(conn)
                row = conn.execute(
                    "SELECT * FROM uf_planning_studies WHERE id = ?", (study_id,)
                ).fetchone()
            if row is None:
                return None
            return {
                "id": row["id"],
                "userId": row["user_id"],
                "name": row["name"],
                "status": row["status"] or "completed",
                "request": json.loads(row["request_json"]),
                "result": None
                if row["result_json"] is None
                else json.loads(row["result_json"]),
                "error": row["error"],
                "createdAt": row["created_at"],
            }
        except Exception:
            return None
