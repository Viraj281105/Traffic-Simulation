"""Where experiments are kept: in memory, mirrored to the ``uf_experiments``
SQLite table when persistence is on (inline, additive migration).
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Any, Dict, List, Optional

from .models import (
    EXPERIMENT_VERSION,
)

logger = logging.getLogger(__name__)


_TABLE = """
CREATE TABLE IF NOT EXISTS uf_experiments (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    name TEXT,
    schema_version INTEGER,
    request_json TEXT,
    summary_json TEXT,
    result_json TEXT,
    spec_fingerprint TEXT,
    result_fingerprint TEXT,
    created_at TEXT,
    status TEXT,
    error TEXT
)
"""
_INDEX = (
    "CREATE INDEX IF NOT EXISTS idx_uf_experiments_user "
    "ON uf_experiments (user_id, created_at)"
)

# Below this many measured seconds (duration minus warm-up) a run may finish no trip at all.

INTERRUPTED_ERROR = (
    "Interrupted by a server restart before it finished; submit the experiment again."
)


def ensure_table(conn: Any) -> None:
    """Create the table and its index. Additive and idempotent (inline migration, as in database/db.py):
    it never alters or drops anything that already exists."""
    conn.execute(_TABLE)
    conn.execute(_INDEX)
    conn.commit()


class ExperimentStore:
    """In-memory records keyed by id, mirrored to SQLite when available."""

    def __init__(self, persist: bool = True) -> None:
        self._records: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._persist = persist

    # ---- in-memory ------------------------------------------------------
    def put(self, record: Dict[str, Any]) -> None:
        with self._lock:
            self._records[record["id"]] = record
        self._save(record)

    def get(self, user_id: str, experiment_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            rec = self._records.get(experiment_id)
        if rec is None:
            rec = self._load(experiment_id)
        if rec is None or rec["userId"] != user_id:
            return None  # another user's experiment is indistinguishable from none
        return rec

    def active(self, user_id: Optional[str] = None) -> int:
        with self._lock:
            return sum(
                1
                for r in self._records.values()
                if r["status"] in ("queued", "running")
                and (user_id is None or r["userId"] == user_id)
            )

    def count_stored(self, user_id: str) -> int:
        with self._lock:
            in_memory = {
                r["id"] for r in self._records.values() if r["userId"] == user_id
            }
        if not self._persist:
            return len(in_memory)
        try:
            from src.database.db import get_db_connection

            with get_db_connection() as conn:
                ensure_table(conn)
                ids = {
                    row[0]
                    for row in conn.execute(
                        "SELECT id FROM uf_experiments WHERE user_id = ?", (user_id,)
                    )
                }
            return len(ids | in_memory)
        except Exception:
            return len(in_memory)

    def list_for_user(
        self, user_id: str, limit: int, offset: int
    ) -> List[Dict[str, Any]]:
        """Summaries (no result), newest first. Memory wins over disk for the same id."""
        found: Dict[str, Dict[str, Any]] = {}
        if self._persist:
            try:
                from src.database.db import get_db_connection

                with get_db_connection() as conn:
                    ensure_table(conn)
                    for row in conn.execute(
                        "SELECT id, name, status, error, created_at, summary_json, "
                        "spec_fingerprint, result_fingerprint FROM uf_experiments "
                        "WHERE user_id = ?",
                        (user_id,),
                    ):
                        found[row["id"]] = {
                            "id": row["id"],
                            "userId": user_id,
                            "name": row["name"],
                            "status": row["status"] or "completed",
                            "error": row["error"],
                            "createdAt": row["created_at"],
                            "summary": json.loads(row["summary_json"] or "{}"),
                            "specFingerprint": row["spec_fingerprint"],
                            "resultFingerprint": row["result_fingerprint"],
                        }
            except Exception:
                logger.warning("Could not list stored experiments", exc_info=True)
        with self._lock:
            for rec in self._records.values():
                if rec["userId"] == user_id:
                    found[rec["id"]] = rec
        ordered = sorted(found.values(), key=lambda r: r["createdAt"], reverse=True)
        return ordered[offset : offset + limit]

    def delete(self, experiment_id: str) -> None:
        """Remove an experiment everywhere. A failure is raised: a delete that silently left the data on
        disk would be a false promise."""
        with self._lock:
            self._records.pop(experiment_id, None)
        if not self._persist:
            return
        from src.database.db import get_db_connection

        with get_db_connection() as conn:
            ensure_table(conn)
            conn.execute("DELETE FROM uf_experiments WHERE id = ?", (experiment_id,))
            conn.commit()

    def mark_interrupted(self) -> int:
        """Mark every experiment a previous process left queued or running as failed. Call once, before
        this process starts any job."""
        if not self._persist:
            return 0
        from src.database.db import get_db_connection

        with get_db_connection() as conn:
            ensure_table(conn)
            cursor = conn.execute(
                "UPDATE uf_experiments SET status = 'failed', error = ? "
                "WHERE status IN ('queued', 'running')",
                (INTERRUPTED_ERROR,),
            )
            conn.commit()
            return int(cursor.rowcount)

    # ---- sqlite ---------------------------------------------------------
    def _save(self, rec: Dict[str, Any]) -> None:
        if not self._persist:
            return
        try:
            from src.database.db import get_db_connection

            result = rec.get("result")
            with get_db_connection() as conn:
                ensure_table(conn)
                conn.execute(
                    "INSERT OR REPLACE INTO uf_experiments (id, user_id, name, schema_version, "
                    "request_json, summary_json, result_json, spec_fingerprint, "
                    "result_fingerprint, created_at, status, error) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        rec["id"],
                        rec["userId"],
                        rec["name"],
                        EXPERIMENT_VERSION,
                        json.dumps(rec["request"]),
                        json.dumps(rec["summary"]),
                        None if result is None else json.dumps(result),
                        rec["specFingerprint"],
                        None if result is None else result["resultFingerprint"],
                        rec["createdAt"],
                        rec["status"],
                        rec.get("error"),
                    ),
                )
                conn.commit()
        except Exception:  # persistence must never fail an experiment
            logger.warning("Could not persist experiment %s", rec["id"], exc_info=True)

    def _load(self, experiment_id: str) -> Optional[Dict[str, Any]]:
        if not self._persist:
            return None
        try:
            from src.database.db import get_db_connection

            with get_db_connection() as conn:
                ensure_table(conn)
                row = conn.execute(
                    "SELECT * FROM uf_experiments WHERE id = ?", (experiment_id,)
                ).fetchone()
            if row is None:
                return None
            return {
                "id": row["id"],
                "userId": row["user_id"],
                "name": row["name"],
                "status": row["status"] or "completed",
                "request": json.loads(row["request_json"]),
                "summary": json.loads(row["summary_json"] or "{}"),
                "result": None
                if row["result_json"] is None
                else json.loads(row["result_json"]),
                "specFingerprint": row["spec_fingerprint"],
                "error": row["error"],
                "createdAt": row["created_at"],
            }
        except Exception:
            return None
