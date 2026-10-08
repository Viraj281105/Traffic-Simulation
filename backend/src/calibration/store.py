"""Storage for calibration results: one table of its own, created on first use.

Does not touch ``database/db.py::init_db`` or any existing table, so V1.6/V1.7
schema changes cannot collide with it.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional

from src.database.db import get_db_connection

_CREATE = """
CREATE TABLE IF NOT EXISTS uf_calibration_runs (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    scenario_fingerprint TEXT NOT NULL,
    observations_fingerprint TEXT NOT NULL,
    status TEXT NOT NULL,
    request_json TEXT NOT NULL,
    result_json TEXT NOT NULL
);
"""


def save(request: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    run_id = uuid.uuid4().hex
    with get_db_connection() as conn:
        conn.execute(_CREATE)
        conn.execute(
            "INSERT INTO uf_calibration_runs (id, scenario_fingerprint, "
            "observations_fingerprint, status, request_json, result_json) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                run_id,
                result["scenario"]["fingerprint"],
                result["meta"]["observationsFingerprint"],
                result["fieldCalibration"]["status"],
                json.dumps(request, sort_keys=True),
                json.dumps(result),
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT created_at FROM uf_calibration_runs WHERE id = ?", (run_id,)
        ).fetchone()
    return {"id": run_id, "createdAt": row["created_at"], "result": result}


def get(run_id: str) -> Optional[Dict[str, Any]]:
    with get_db_connection() as conn:
        conn.execute(_CREATE)
        row = conn.execute(
            "SELECT id, created_at, request_json, result_json "
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
    }


def list_runs(limit: int = 50) -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        conn.execute(_CREATE)
        rows = conn.execute(
            "SELECT id, created_at, scenario_fingerprint, observations_fingerprint, "
            "status FROM uf_calibration_runs ORDER BY created_at DESC, rowid DESC "
            "LIMIT ?",
            (limit,),
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
