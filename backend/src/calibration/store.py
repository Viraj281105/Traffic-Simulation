"""Storage for calibration results: one table of its own, created on first use.

Does not touch ``database/db.py::init_db`` or any existing table, so V1.6/V1.7
schema changes cannot collide with it.

Each run belongs to the user who created it (``user_id``). The public read and
delete functions take the caller and return nothing for another user's run;
admins see every run, including legacy rows stored before the owner column
existed (``user_id`` NULL), which nobody else can see. ``get`` is the unscoped
lookup for internal callers that have already checked access.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional

from src.access import Caller, can_see, owner_filter
from src.database.db import get_db_connection

_CREATE = """
CREATE TABLE IF NOT EXISTS uf_calibration_runs (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    scenario_fingerprint TEXT NOT NULL,
    observations_fingerprint TEXT NOT NULL,
    status TEXT NOT NULL,
    request_json TEXT NOT NULL,
    result_json TEXT NOT NULL,
    user_id TEXT
);
"""


def _ensure_table(conn: Any) -> None:
    """Create the table, and add ``user_id`` to one created before it existed
    (the inline migration pattern of ``database/db.py``)."""
    conn.execute(_CREATE)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(uf_calibration_runs)")}
    if "user_id" not in columns:
        conn.execute("ALTER TABLE uf_calibration_runs ADD COLUMN user_id TEXT")
        conn.commit()


def _visible(owner: Optional[str], user_id: str, is_admin: bool) -> bool:
    # Calibration runs are private: unowned (legacy) rows are admin-only.
    return can_see(owner, Caller(user_id, is_admin), unowned_public=False)


def save(
    request: Dict[str, Any], result: Dict[str, Any], user_id: str
) -> Dict[str, Any]:
    run_id = uuid.uuid4().hex
    with get_db_connection() as conn:
        _ensure_table(conn)
        conn.execute(
            "INSERT INTO uf_calibration_runs (id, scenario_fingerprint, "
            "observations_fingerprint, status, request_json, result_json, user_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                result["scenario"]["fingerprint"],
                result["meta"]["observationsFingerprint"],
                result["fieldCalibration"]["status"],
                json.dumps(request, sort_keys=True),
                json.dumps(result),
                user_id,
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT created_at FROM uf_calibration_runs WHERE id = ?", (run_id,)
        ).fetchone()
    return {"id": run_id, "createdAt": row["created_at"], "result": result}


def _load(run_id: str) -> Optional[Dict[str, Any]]:
    with get_db_connection() as conn:
        _ensure_table(conn)
        row = conn.execute(
            "SELECT id, created_at, request_json, result_json, user_id "
            "FROM uf_calibration_runs WHERE id = ?",
            (run_id,),
        ).fetchone()
    if row is None:
        return None
    return {
        "id": row["id"],
        "createdAt": row["created_at"],
        "request": json.loads(row["request_json"]),
        "result": json.loads(row["result_json"]),
        "userId": row["user_id"],
    }


def get(run_id: str) -> Optional[Dict[str, Any]]:
    """Unscoped lookup for callers that have already checked access."""
    found = _load(run_id)
    if found is not None:
        found.pop("userId")
    return found


def get_for_user(
    run_id: str, user_id: str, is_admin: bool = False
) -> Optional[Dict[str, Any]]:
    """The run, or None when it does not exist **or** is not the caller's:
    another user's run is indistinguishable from a missing one."""
    found = _load(run_id)
    if found is None or not _visible(found.pop("userId"), user_id, is_admin):
        return None
    return found


def list_runs(
    user_id: str, is_admin: bool = False, limit: int = 50
) -> List[Dict[str, Any]]:
    """The caller's runs, newest first; every run for an admin."""
    where, params = owner_filter(Caller(user_id, is_admin), unowned_public=False)
    with get_db_connection() as conn:
        _ensure_table(conn)
        rows = conn.execute(
            "SELECT id, created_at, scenario_fingerprint, observations_fingerprint, "
            f"status FROM uf_calibration_runs WHERE {where} "
            "ORDER BY created_at DESC, rowid DESC LIMIT ?",
            (*params, limit),
        ).fetchall()
    return [
        {
            "id": r["id"],
            "createdAt": r["created_at"],
            "scenarioFingerprint": r["scenario_fingerprint"],
            "observationsFingerprint": r["observations_fingerprint"],
            "status": r["status"],
        }
        for r in rows
    ]


def delete(run_id: str, user_id: str, is_admin: bool = False) -> bool:
    """Delete the caller's run (any run for an admin). False when there is no
    such run visible to the caller."""
    with get_db_connection() as conn:
        _ensure_table(conn)
        row = conn.execute(
            "SELECT user_id FROM uf_calibration_runs WHERE id = ?", (run_id,)
        ).fetchone()
        if row is None or not _visible(row["user_id"], user_id, is_admin):
            return False
        conn.execute("DELETE FROM uf_calibration_runs WHERE id = ?", (run_id,))
        conn.commit()
    return True
