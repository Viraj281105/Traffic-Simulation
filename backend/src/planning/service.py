"""Planning service: submit, run, retrieve, export, reproduce.

Framework-free so tests and the router share it. Studies are owned by the
user who submitted them, and a study may attach only a calibration run its
user can see (``calibration_store.get_for_user``). Results are kept in memory and, best effort, in a
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


class NotFound(LookupError):  # noqa: N818
    pass


class StudyProgress(Progress):
    """Progress of a whole study. ``run_study`` runs one comparison per
    distinct alternative and each calls ``begin`` again, which on a plain
    ``Progress`` restarts the count; this keeps the simulations already
    finished and reports against the study's total."""

    def __init__(self, total: int) -> None:
        super().__init__()
        self._study_total = total
        self._finished_before = 0

    def begin(self, labels: List[str]) -> None:
        with self._lock:
            self._finished_before += len(self._labels)
        super().begin(labels)

    def snapshot(self) -> Dict[str, Any]:
        out = super().snapshot()
        with self._lock:
            done = self._finished_before + sum(self._fractions)
            completed = self._finished_before + sum(self._done)
        total = max(self._study_total, completed)
        out["total"] = total
        out["completed"] = completed
        out["fraction"] = round(done / total, 4) if total else 0.0
        out["etaSeconds"] = None  # only meaningful per batch; not shown
        return out


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

    # ---- access ---------------------------------------------------------
    @staticmethod
    def _calibration_access_errors(
        user_id: str, study: PlanningStudy, is_admin: bool
    ) -> List[str]:
        """Refuse a calibration run the caller cannot see, with the same
        message as a missing run, before anything reads it."""
        if study.calibration is None:
            return []
        from src.calibration import store as calibration_store

        run_id = study.calibration.runId
        try:
            visible = calibration_store.get_for_user(run_id, user_id, is_admin)
        except Exception as exc:  # the table or database is unusable
            return [f"calibration: could not read stored runs ({exc})"]
        if visible is None:
            return [
                f"calibration: run {run_id!r} not found "
                "(create one with POST /api/v2/calibration/runs)"
            ]
        return []

    # ---- validate / run -------------------------------------------------
    def validate(
        self, user_id: str, payload: Any, is_admin: bool = False
    ) -> Dict[str, Any]:
        study, errors = parse_study(payload)
        if study is not None:
            errors = self._calibration_access_errors(user_id, study, is_admin)
            if errors:
                study = None
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

    def _require_study(
        self, payload: Any, user_id: str, is_admin: bool = False
    ) -> PlanningStudy:
        study, errors = parse_study(payload)
        if study is None:
            raise PlanningError(errors)
        errors = self._calibration_access_errors(user_id, study, is_admin)
        if errors:
            raise PlanningError(errors)
        return study

    def run(self, user_id: str, payload: Any, is_admin: bool = False) -> Dict[str, Any]:
        """Synchronous run; returns the stored record."""
        study = self._require_study(payload, user_id, is_admin)
        record = self._new_record(user_id, study)
        self._execute(record, study, None)
        return record

    # ---- jobs -----------------------------------------------------------
    def submit(
        self, user_id: str, payload: Any, is_admin: bool = False
    ) -> Dict[str, Any]:
        study = self._require_study(payload, user_id, is_admin)
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
        distinct = {(r.spec.strategy, r.fingerprint) for r in check["alternatives"]}
        study_progress = StudyProgress(
            len(distinct) * len(study.demand.scales) * study.repetitions.seeds
        )
        self._progress[record["id"]] = study_progress

        def work(_job_progress: Progress) -> Dict[str, Any]:
            record["status"] = "running"
            try:
                self._execute(record, study, study_progress)
            finally:
                self._progress.pop(record["id"], None)
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
        # Simulations finished so far, while the study is queued or running.
        progress = self._progress.get(record["id"])
        out["progress"] = (
            progress.snapshot()
            if progress is not None and record["status"] in ("queued", "running")
            else None
        )
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
        study = self._require_study(rec["request"], user_id)
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

    def delete(self, user_id: str, study_id: str) -> None:
        """Delete the caller's finished or failed study, in memory and on
        disk. A queued or running study cannot be deleted (there is no job
        cancellation); that is a ``PlanningError``."""
        rec = self.store.get(user_id, study_id)
        if rec is None:
            raise NotFound(study_id)
        if rec["status"] in ("queued", "running"):
            raise PlanningError(
                [f"Study is {rec['status']}; wait for it to finish, then delete it"]
            )
        self.store.delete(study_id)


def _fingerprint(doc: Any) -> str:
    from src.core.scenario import scenario_fingerprint

    return scenario_fingerprint(doc)


_default: Optional[PlanningService] = None


def get_service() -> PlanningService:
    """The process-wide service. Created once per process, so this is where
    studies an earlier process was running are marked interrupted: before it
    exists, no job of this process can be queued or running."""
    global _default
    if _default is None:
        service = PlanningService()
        try:
            marked = service.store.mark_interrupted()
        except Exception:  # an unusable database must not stop the API
            logger.warning("Could not check for interrupted studies", exc_info=True)
        else:
            if marked:
                logger.warning("%d planning study(ies) interrupted by restart", marked)
        _default = service
    return _default
