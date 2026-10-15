"""Experiment service: validate, submit, run in the background, retrieve, delete (``/api/v3/experiments``).

Framework-free so the router and the tests share it. Every experiment belongs to the user who submitted it
and is invisible to everyone else: another user's id gives the same answer as an unknown one
(:class:`NotFound`, HTTP 404), and there is no administrator override in v3 (ADR-013 decision 5).

Records live in memory and, best effort, in ``uf_experiments`` (created lazily, additive) so finished
experiments survive a restart. A database failure never fails an experiment. There is no durable job
queue: an experiment a previous process was still running is reported as failed after a restart, not lost.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from src.core.provenance import GIT_COMMIT_HASH, PYTHON_VERSION
from src.core.scenario import (
    STRATEGIES,
    ScenarioDocument,
    parse_scenario,
    scenario_fingerprint,
)
from src.planning.alternatives import (
    DefaultStrategyAlternatives,
    InlineAlternatives,
    ResolvedAlternative,
    resolve_all,
)
from src.planning.models import fingerprint_of
from src.study.jobs import JobRegistry, TooManyJobsError
from src.study.runner import Progress
from src.uncertainty.apply import preflight
from src.uncertainty.runner import (
    RunAlternative,
    TaskExecutor,
    run_experiment,
)
from src.uncertainty.spec import (
    DistributionKind,
    FactorKind,
    PrimaryIndicator,
    fingerprint,
    run_counts,
)

from . import limits
from .models import (
    EXPERIMENT_FORMAT,
    EXPERIMENT_VERSION,
    RESULT_FORMAT,
    RESULT_VERSION,
    ExperimentRequest,
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

INTERRUPTED_ERROR = (
    "Interrupted by a server restart before it finished; submit the experiment again."
)
MAX_ERROR_CHARS = 300


def ensure_table(conn: Any) -> None:
    """Create the table and its index. Additive and idempotent (inline migration, as in database/db.py):
    it never alters or drops anything that already exists."""
    conn.execute(_TABLE)
    conn.execute(_INDEX)
    conn.commit()


class NotFound(LookupError):  # noqa: N818
    pass


class ExperimentError(ValueError):
    """The request cannot be accepted as it is (HTTP 422). ``errors`` name every problem found."""

    def __init__(self, errors: List[str]) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors


class QuotaExceeded(RuntimeError):  # noqa: N818
    """A per-user or server-wide limit on running or stored work (HTTP 429). Names the quota."""

    def __init__(self, quota: str, message: str) -> None:
        super().__init__(f"quota {quota}: {message}")
        self.quota = quota


class ConflictError(RuntimeError):
    """The request is valid but not possible in the experiment's current state (HTTP 409)."""


@dataclass
class Prepared:
    request: Optional[ExperimentRequest] = None
    base: Optional[ScenarioDocument] = None
    alternatives: List[ResolvedAlternative] = field(default_factory=list)
    baseline: Optional[str] = None
    counts: Optional[Dict[str, int]] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.errors


def _pydantic_errors(err: ValidationError) -> List[str]:
    return [
        f"{'.'.join(str(p) for p in e.get('loc', ()))}: {e.get('msg', 'invalid')}"
        for e in err.errors()
    ]


def _quota_error(quota: str, message: str) -> str:
    return f"quota {limits.QUOTA_NAMES[quota]}: {message}"


def prepare(payload: Any) -> Prepared:
    """Validate a request without simulating anything."""
    out = Prepared()
    if not isinstance(payload, dict):
        out.errors.append("An experiment must be a JSON object")
        return out
    try:
        request = ExperimentRequest.model_validate(payload)
    except ValidationError as err:
        out.errors.extend(_pydantic_errors(err))
        return out
    out.request = request

    base, scenario_errors = parse_scenario(request.scenario)
    if base is None:
        out.errors.extend(f"scenario: {e}" for e in scenario_errors)
        return out
    out.base = base

    source = (
        InlineAlternatives(request.alternatives)
        if request.alternatives
        else DefaultStrategyAlternatives()
    )
    resolved = resolve_all(base, source)
    out.alternatives = resolved
    ids = [r.id for r in resolved]
    if len(set(ids)) != len(ids):
        out.errors.append("alternative ids must be unique")
    if len(resolved) < 2:
        out.errors.append("an experiment needs at least two alternatives")
    if len(resolved) > limits.MAX_ALTERNATIVES:
        out.errors.append(
            _quota_error(
                "alternatives",
                f"{len(resolved)} alternatives given, at most {limits.MAX_ALTERNATIVES} allowed",
            )
        )
    for r in resolved:
        out.errors.extend(r.errors)
        out.warnings.extend(r.warnings)
        if r.document is not None:
            out.errors.extend(
                f"{r.id}: {e}"
                for e in preflight(r.document, request.uncertainty.factors)
            )

    out.baseline = request.baseline or (resolved[0].id if resolved else None)
    if out.baseline is not None and out.baseline not in ids:
        out.errors.append(f"baseline {out.baseline!r} is not one of the alternatives")

    if len(resolved) >= 2:
        out.counts = run_counts(request.uncertainty, len(resolved))
        if out.counts["totalRuns"] > limits.MAX_RUNS_PER_EXPERIMENT:
            out.errors.append(
                _quota_error(
                    "runsPerExperiment",
                    f"{out.counts['conditions']} conditions x {out.counts['alternatives']} "
                    f"alternatives x {out.counts['replications']} replications = "
                    f"{out.counts['totalRuns']} runs, at most {limits.MAX_RUNS_PER_EXPERIMENT} allowed",
                )
            )
        seconds = out.counts["totalRuns"] * base.simulation.duration
        if seconds > limits.MAX_SIMULATED_SECONDS_PER_EXPERIMENT:
            out.errors.append(
                _quota_error(
                    "simulatedSecondsPerExperiment",
                    f"{out.counts['totalRuns']} runs of {base.simulation.duration:g} s = "
                    f"{seconds:g} simulated seconds, at most "
                    f"{limits.MAX_SIMULATED_SECONDS_PER_EXPERIMENT:g} allowed",
                )
            )
    return out


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


class ExperimentService:
    def __init__(
        self,
        store: Optional[ExperimentStore] = None,
        executor: Optional[TaskExecutor] = None,
    ) -> None:
        self.store = store or ExperimentStore()
        self.executor = executor
        self.jobs = JobRegistry()  # our own registry, not the V1 study one
        self._progress: Dict[str, Progress] = {}
        self._submit_lock = threading.Lock()

    # ---- validate / submit ----------------------------------------------
    def validate(self, payload: Any) -> Dict[str, Any]:
        prepared = prepare(payload)
        return {
            "valid": prepared.valid,
            "errors": prepared.errors,
            "warnings": prepared.warnings,
            "counts": prepared.counts,
            "baseline": prepared.baseline,
            "specFingerprint": (
                None
                if prepared.request is None
                else fingerprint(prepared.request.uncertainty)
            ),
            "scenarioFingerprint": (
                None if prepared.base is None else scenario_fingerprint(prepared.base)
            ),
            "alternatives": [
                {
                    "id": r.id,
                    "label": r.label,
                    "strategy": r.spec.strategy,
                    "fingerprint": r.fingerprint,
                    "changesFromBase": r.changes,
                }
                for r in prepared.alternatives
            ],
        }

    def submit(self, user_id: str, payload: Any) -> Dict[str, Any]:
        prepared = prepare(payload)
        if not prepared.valid:
            raise ExperimentError(prepared.errors)
        assert prepared.request is not None and prepared.counts is not None
        assert prepared.baseline is not None and prepared.base is not None

        # The quota check and the reservation (the record becomes "queued") happen under one lock, so two
        # simultaneous submissions cannot both pass a limit of one.
        with self._submit_lock:
            self._check_quotas(user_id)
            record = self._new_record(user_id, prepared)

        def work(job_progress: Progress) -> Dict[str, Any]:
            self._run(record, prepared, job_progress)
            return {}

        try:
            self.jobs.submit("experiment", work)
        except TooManyJobsError as err:
            self.store.delete(record["id"])
            raise QuotaExceeded("maxActiveExperiments", str(err)) from err
        return self._status_view(record)

    def _check_quotas(self, user_id: str) -> None:
        if self.store.active(user_id) >= limits.MAX_ACTIVE_EXPERIMENTS_PER_USER:
            raise QuotaExceeded(
                limits.QUOTA_NAMES["activeExperimentsPerUser"],
                f"you already have {limits.MAX_ACTIVE_EXPERIMENTS_PER_USER} experiment running; "
                "wait for it to finish",
            )
        if self.store.active() >= limits.MAX_ACTIVE_EXPERIMENTS:
            raise QuotaExceeded(
                limits.QUOTA_NAMES["activeExperiments"],
                f"the server is already running {limits.MAX_ACTIVE_EXPERIMENTS} experiments; "
                "try again shortly",
            )
        if self.store.count_stored(user_id) >= limits.MAX_STORED_EXPERIMENTS_PER_USER:
            raise QuotaExceeded(
                limits.QUOTA_NAMES["storedExperimentsPerUser"],
                f"you already keep {limits.MAX_STORED_EXPERIMENTS_PER_USER} experiments; "
                "delete one first",
            )

    def _new_record(self, user_id: str, prepared: Prepared) -> Dict[str, Any]:
        request = prepared.request
        assert request is not None and prepared.counts is not None
        record = {
            "id": uuid.uuid4().hex,
            "userId": user_id,
            "name": request.name,
            "status": "queued",
            "request": request.model_dump(mode="json"),
            "summary": dict(prepared.counts),
            "result": None,
            "specFingerprint": fingerprint(request.uncertainty),
            "error": None,
            "createdAt": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        }
        self.store.put(record)
        return record

    # ---- execution --------------------------------------------------------
    def _run(
        self, record: Dict[str, Any], prepared: Prepared, progress: Progress
    ) -> None:
        request = prepared.request
        assert request is not None and prepared.baseline is not None
        record["status"] = "running"
        self._progress[record["id"]] = progress
        self.store.put(record)
        try:
            progress.set_phase("preparing")
            alternatives = [
                RunAlternative(r.id, r.spec.strategy, r.document)
                for r in prepared.alternatives
                if r.document is not None
            ]
            kwargs: Dict[str, Any] = {"progress": progress}
            if self.executor is not None:
                kwargs["executor"] = self.executor
            outcome = run_experiment(
                request.uncertainty, alternatives, prepared.baseline, **kwargs
            )
            record["result"] = self._result_document(record, prepared, outcome)
            record["status"] = "completed"
        except Exception as exc:
            logger.exception("Experiment %s failed", record["id"])
            record["error"] = (str(exc) or type(exc).__name__)[:MAX_ERROR_CHARS]
            record["status"] = "failed"
        finally:
            self._progress.pop(record["id"], None)
            self.store.put(record)

    @staticmethod
    def _result_document(
        record: Dict[str, Any], prepared: Prepared, outcome: Dict[str, Any]
    ) -> Dict[str, Any]:
        request = prepared.request
        base = prepared.base
        assert request is not None and base is not None
        spec = request.uncertainty
        alternatives = [
            {
                "id": r.id,
                "label": r.label,
                "strategy": r.spec.strategy,
                "isBaseline": r.id == prepared.baseline,
                "fingerprint": r.fingerprint,
                "changesFromBase": r.changes,
            }
            for r in prepared.alternatives
        ]
        evidence = {
            "scenarioFingerprint": scenario_fingerprint(base),
            "alternatives": [
                [a["id"], a["strategy"], a["fingerprint"]] for a in alternatives
            ],
            "baseline": prepared.baseline,
            "specFingerprint": outcome["specFingerprint"],
            "analysis": outcome["analysis"],
        }
        return {
            "format": RESULT_FORMAT,
            "version": RESULT_VERSION,
            "experimentId": record["id"],
            "name": record["name"],
            "scenario": {"name": base.name, "fingerprint": scenario_fingerprint(base)},
            "alternatives": alternatives,
            "baseline": prepared.baseline,
            "specification": spec.model_dump(mode="json"),
            "specFingerprint": outcome["specFingerprint"],
            # The assumptions behind every number, with who vouches for them (strategy section 5.1, 5.8).
            "assumptions": [
                {
                    "id": f.id,
                    "kind": f.kind,
                    "distribution": f.distribution.model_dump(
                        mode="json", exclude_none=True
                    ),
                    "bounds": f.bounds,
                    "basis": f.basis,
                    "rationale": f.rationale,
                }
                for f in spec.factors
            ],
            "analysis": outcome["analysis"],
            "analysisFingerprint": outcome["resultFingerprint"],
            # Identical inputs and seed give an identical value; it covers what was run, not how long it took.
            "resultFingerprint": fingerprint_of(evidence),
            "provenance": {
                "gitCommit": GIT_COMMIT_HASH,
                "pythonVersion": PYTHON_VERSION,
                "sampling": "seeded Latin hypercube, stratified per factor",
                "commonRandomNumbers": True,
                "seedRule": "sha256('urbanflow-uncertainty-v1:<seed>:<condition>:<replication>')[:4] & 0x7fffffff",
                "note": "The full reproducibility manifest and package verification arrive in a later release.",
            },
            "execution": outcome["execution"],
        }

    # ---- retrieve -------------------------------------------------------
    def _status_view(self, record: Dict[str, Any]) -> Dict[str, Any]:
        progress = self._progress.get(record["id"])
        active = record["status"] in ("queued", "running")
        return {
            "format": "urbanflow-experiment-status",
            "version": 1,
            "id": record["id"],
            "name": record["name"],
            "status": record["status"],
            "error": record.get("error"),
            "createdAt": record["createdAt"],
            "counts": record.get("summary") or None,
            "specFingerprint": record.get("specFingerprint"),
            "resultAvailable": record.get("result") is not None
            or record.get("resultFingerprint") is not None,
            "progress": progress.snapshot()
            if progress is not None and active
            else None,
        }

    def status(self, user_id: str, experiment_id: str) -> Dict[str, Any]:
        record = self.store.get(user_id, experiment_id)
        if record is None:
            raise NotFound(experiment_id)
        return self._status_view(record)

    def result(self, user_id: str, experiment_id: str) -> Dict[str, Any]:
        record = self.store.get(user_id, experiment_id)
        if record is None:
            raise NotFound(experiment_id)
        if record["result"] is None:
            detail = f"Experiment is {record['status']}; there is no result"
            if record["status"] == "failed" and record.get("error"):
                detail += f" ({record['error']})"
            raise ConflictError(detail)
        result: Dict[str, Any] = record["result"]
        return result

    def list_experiments(self, user_id: str, limit: int, offset: int) -> Dict[str, Any]:
        records = self.store.list_for_user(user_id, limit, offset)
        return {
            "format": "urbanflow-experiment-list",
            "version": 1,
            "limit": limit,
            "offset": offset,
            "experiments": [self._status_view(r) for r in records],
        }

    def delete(self, user_id: str, experiment_id: str) -> None:
        """Delete the caller's finished or failed experiment. A queued or running one cannot be deleted:
        there is no cancellation in this release."""
        record = self.store.get(user_id, experiment_id)
        if record is None:
            raise NotFound(experiment_id)
        if record["status"] in ("queued", "running"):
            raise ConflictError(
                f"Experiment is {record['status']}; cancellation is not supported yet, "
                "wait for it to finish, then delete it"
            )
        self.store.delete(experiment_id)

    # ---- capabilities ---------------------------------------------------
    @staticmethod
    def capabilities() -> Dict[str, Any]:
        """What this server offers. A client shows a capability only when it is listed here as true."""
        from src.request_limits import MAX_V2_BODY_BYTES
        from src.uncertainty import spec as uspec

        def literal_values(alias: Any) -> List[str]:
            return list(alias.__args__)

        return {
            "format": "urbanflow-capabilities",
            "version": 1,
            "apiVersion": 3,
            "gitCommit": GIT_COMMIT_HASH,
            "features": {
                "robustnessExperiments": True,
                "experimentCancellation": False,
                "experimentPackages": False,
                "personalAccessTokens": False,
                "pythonClient": False,
                "aiCopilot": False,
                "discoveryLab": False,
            },
            "documents": {
                "request": f"{EXPERIMENT_FORMAT}@{EXPERIMENT_VERSION}",
                "specification": f"{uspec.SPEC_FORMAT}@{uspec.SPEC_VERSION}",
                "result": f"{RESULT_FORMAT}@{RESULT_VERSION}",
            },
            "experiments": {
                "strategies": list(STRATEGIES),
                "factorKinds": literal_values(FactorKind),
                "distributions": literal_values(DistributionKind),
                "primaryIndicators": literal_values(PrimaryIndicator),
                "maxFactors": uspec.MAX_FACTORS,
                "maxConditions": uspec.MAX_CONDITIONS,
                "maxReplications": uspec.MAX_REPLICATIONS,
            },
            "quotas": limits.quotas(),
            "limits": {"maxRequestBodyBytes": MAX_V2_BODY_BYTES},
        }


_default: Optional[ExperimentService] = None


def get_service() -> ExperimentService:
    """The process-wide service. Created once, so this is where experiments an earlier process was
    running are marked interrupted: before it exists, no job of this process can be queued or running."""
    global _default
    if _default is None:
        service = ExperimentService()
        try:
            marked = service.store.mark_interrupted()
        except Exception:  # an unusable database must not stop the API
            logger.warning("Could not check for interrupted experiments", exc_info=True)
        else:
            if marked:
                logger.warning("Marked %d interrupted experiment(s) as failed", marked)
        _default = service
    return _default
