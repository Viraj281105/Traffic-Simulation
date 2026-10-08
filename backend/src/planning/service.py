"""Planning service: submit, run, retrieve, export, reproduce.

Framework-free so tests and the router share it. Studies are owned by the
user who submitted them. Results are kept in memory and, best effort, in a
table of our own (``uf_planning_studies``, created lazily) so they survive a
restart; a database failure never fails a study.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import threading
import uuid
from typing import Any, Dict, List, Optional, Tuple

from pydantic import ValidationError

from src.planning.models import PlanningStudy
from src.planning.report import export
from src.planning.runner import (
    ComparisonFn,
    PlanningError,
    prepare,
    result_fingerprint,
    run_study,
)
from src.study.jobs import JobRegistry, TooManyJobsError
from src.study.runner import Progress

logger = logging.getLogger(__name__)

MAX_ACTIVE_PLANNING_JOBS = 2

_TABLE = """
CREATE TABLE IF NOT EXISTS uf_planning_studies (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    name TEXT,
    schema_version INTEGER,
    request_json TEXT,
    result_json TEXT,
    fingerprint TEXT,
    created_at TEXT
)
"""


class NotFound(LookupError):  # noqa: N818
    pass


def parse_study(payload: Any) -> Tuple[Optional[PlanningStudy], List[str]]:
    if not isinstance(payload, dict):
        return None, ["A planning study must be a JSON object"]
    try:
        return PlanningStudy.model_validate(payload), []
    except ValidationError as err:
        return None, [
            f"{'.'.join(str(p) for p in e.get('loc', ()))}: {e.get('msg', 'invalid')}"
            for e in err.errors()
        ]


class PlanningStore:
    """In-memory records keyed by id, mirrored to SQLite when available."""

    def __init__(self, persist: bool = True) -> None:
        self._records: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._persist = persist

    def put(self, record: Dict[str, Any]) -> None:
        with self._lock:
            self._records[record["id"]] = record
        if record.get("result") is not None:
            self._save(record)

    def get(self, user_id: str, study_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            rec = self._records.get(study_id)
        if rec is None:
            rec = self._load(study_id)
        if rec is None or rec["userId"] != user_id:
            return None  # another user's study is indistinguishable from none
        return rec

    def _save(self, rec: Dict[str, Any]) -> None:
        if not self._persist:
            return
        try:
            from src.database.db import get_db_connection

            with get_db_connection() as conn:
                conn.execute(_TABLE)
                conn.execute(
                    "INSERT OR REPLACE INTO uf_planning_studies VALUES (?,?,?,?,?,?,?,?)",
                    (
                        rec["id"],
                        rec["userId"],
                        rec["name"],
                        1,
                        json.dumps(rec["request"]),
                        json.dumps(rec["result"]),
                        rec["result"]["scenario"]["fingerprint"],
                        rec["createdAt"],
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
                conn.execute(_TABLE)
                row = conn.execute(
                    "SELECT * FROM uf_planning_studies WHERE id = ?", (study_id,)
                ).fetchone()
            if row is None:
                return None
            return {
                "id": row["id"],
                "userId": row["user_id"],
                "name": row["name"],
                "status": "completed",
                "request": json.loads(row["request_json"]),
                "result": json.loads(row["result_json"]),
                "error": None,
                "createdAt": row["created_at"],
            }
        except Exception:
            return None


class PlanningService:
    def __init__(
        self,
        store: Optional[PlanningStore] = None,
        comparison_fn: Optional[ComparisonFn] = None,
    ) -> None:
        self.store = store or PlanningStore()
        self.comparison_fn = comparison_fn
        self.jobs = JobRegistry()  # our own registry, not the V1 study one
        self._progress: Dict[str, Progress] = {}

    # ---- validate / run -------------------------------------------------
    def validate(self, payload: Any) -> Dict[str, Any]:
        study, errors = parse_study(payload)
        if study is None:
            return {
                "valid": False,
                "errors": errors,
                "warnings": [],
                "alternatives": [],
            }
        prepared = prepare(study)
        return {
            "valid": prepared["valid"],
            "errors": prepared["errors"],
            "warnings": prepared["warnings"],
            "simulations": prepared.get("runs"),
            "scenarioFingerprint": (
                None if prepared["base"] is None else _fingerprint(prepared["base"])
            ),
            "alternatives": [
                {
                    "id": r.id,
                    "label": r.label,
                    "strategy": r.spec.strategy,
                    "fingerprint": r.fingerprint,
                    "changesFromBase": r.changes,
                }
                for r in prepared["alternatives"]
            ],
        }

    def _require_study(self, payload: Any) -> PlanningStudy:
        study, errors = parse_study(payload)
        if study is None:
            raise PlanningError(errors)
        return study

    def run(self, user_id: str, payload: Any) -> Dict[str, Any]:
        """Synchronous run; returns the stored record."""
        study = self._require_study(payload)
        record = self._new_record(user_id, study)
        self._execute(record, study, None)
        return record

    # ---- jobs -----------------------------------------------------------
    def submit(self, user_id: str, payload: Any) -> Dict[str, Any]:
        study = self._require_study(payload)
        check = prepare(study)
        if not check["valid"]:
            raise PlanningError(check["errors"])
        active = sum(
            1
            for r in self.store._records.values()
            if r["status"] in ("queued", "running")
        )
        if active >= MAX_ACTIVE_PLANNING_JOBS:
            raise TooManyJobsError(f"{active} planning studies are already running")
        record = self._new_record(user_id, study)

        def work(progress: Progress) -> Dict[str, Any]:
            record["status"] = "running"
            self._execute(record, study, progress)
            return {}

        self.jobs.submit("planning", work)
        return self._public(record)

    def _new_record(self, user_id: str, study: PlanningStudy) -> Dict[str, Any]:
        record = {
            "id": uuid.uuid4().hex,
            "userId": user_id,
            "name": study.name,
            "status": "queued",
            "request": study.model_dump(mode="json"),
            "result": None,
            "error": None,
            "createdAt": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        }
        self.store.put(record)
        return record

    def _execute(
        self, record: Dict[str, Any], study: PlanningStudy, progress: Optional[Progress]
    ) -> None:
        record["status"] = "running"
        try:
            record["result"] = run_study(
                study, comparison_fn=self.comparison_fn, progress=progress
            )
            record["status"] = "completed"
        except Exception as exc:
            logger.exception("Planning study %s failed", record["id"])
            record["error"] = str(exc) or type(exc).__name__
            record["status"] = "failed"
        self.store.put(record)

    # ---- retrieve / export / reproduce ----------------------------------
    def _public(
        self, record: Dict[str, Any], with_result: bool = False
    ) -> Dict[str, Any]:
        out = {k: record[k] for k in ("id", "name", "status", "error", "createdAt")}
        out["result"] = record["result"] if with_result else None
        return out

    def get(self, user_id: str, study_id: str) -> Dict[str, Any]:
        rec = self.store.get(user_id, study_id)
        if rec is None:
            raise NotFound(study_id)
        return self._public(rec, with_result=True)

    def export(self, user_id: str, study_id: str, fmt: str) -> Dict[str, str]:
        rec = self.store.get(user_id, study_id)
        if rec is None:
            raise NotFound(study_id)
        if rec["result"] is None:
            raise PlanningError([f"Study is {rec['status']}; no result to export yet"])
        return export(rec["result"], fmt)

    def reproduce(self, user_id: str, study_id: str) -> Dict[str, Any]:
        """Re-execute the stored request and compare the evidence hashes."""
        rec = self.store.get(user_id, study_id)
        if rec is None:
            raise NotFound(study_id)
        if rec["result"] is None:
            raise PlanningError([f"Study is {rec['status']}; nothing to reproduce yet"])
        study = self._require_study(rec["request"])
        rerun = run_study(study, comparison_fn=self.comparison_fn)
        original = rec["result"]["meta"]["resultFingerprint"]
        again = result_fingerprint(rerun)
        return {
            "id": study_id,
            "reproduced": original == again,
            "originalResultFingerprint": original,
            "rerunResultFingerprint": again,
            "gitCommitOriginal": rec["result"]["meta"]["gitCommit"],
            "gitCommitRerun": rerun["meta"]["gitCommit"],
        }


def _fingerprint(doc: Any) -> str:
    from src.core.scenario import scenario_fingerprint

    return scenario_fingerprint(doc)


_default: Optional[PlanningService] = None


def get_service() -> PlanningService:
    global _default
    if _default is None:
        _default = PlanningService()
    return _default
