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
import logging
import threading
import uuid
from typing import Any, Dict, List, Optional, Tuple

from src.core.provenance import GIT_COMMIT_HASH, PYTHON_VERSION
from src.experiments.manifest import build_experiment_manifest
from src.planning.models import fingerprint_of
from src.scenario.documents import (
    STRATEGIES,
    scenario_fingerprint,
)
from src.study.jobs import JobRegistry, TooManyJobsError
from src.study.runner import Progress
from src.uncertainty.apply import FactorApplicationError
from src.uncertainty.runner import (
    EnsembleRefusedError,
    RunAlternative,
    TaskExecutor,
    run_experiment,
)
from src.uncertainty.spec import (
    DistributionKind,
    FactorKind,
    PrimaryIndicator,
    fingerprint,
)

from . import limits
from .models import (
    EXPERIMENT_FORMAT,
    EXPERIMENT_VERSION,
    PARTIAL_RESULT_FORMAT,
    PARTIAL_RESULT_VERSION,
    RESULT_FORMAT,
    RESULT_VERSION,
)

logger = logging.getLogger(__name__)
from .package import PACKAGE_EXTENSION, build_package
from .preparation import Prepared, prepare
from .store import ExperimentStore, UsageStore, utc_day

MAX_ERROR_CHARS = 300


# Exceptions whose message is ours and written for the user. Anything else (an engine or operating-system
# error) may carry file paths or internals, so the user sees its type only and the server log has the rest.
_USER_FACING_ERRORS = (EnsembleRefusedError, FactorApplicationError)


def _public_error(exc: Exception) -> str:
    if isinstance(exc, _USER_FACING_ERRORS):
        return (str(exc) or type(exc).__name__)[:MAX_ERROR_CHARS]
    return (
        f"The experiment failed while running ({type(exc).__name__}). "
        "The server log has the details."
    )


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


class ExperimentService:
    def __init__(
        self,
        store: Optional[ExperimentStore] = None,
        executor: Optional[TaskExecutor] = None,
    ) -> None:
        self.store = store or ExperimentStore()
        self.executor = executor
        self.jobs = JobRegistry()  # our own registry, not the V1 study one
        self.usage = UsageStore(persist=self.store._persist)
        self._progress: Dict[str, Progress] = {}
        self._submit_lock = threading.Lock()
        # Guards every status transition (run start/end, cancel, resume, delete) so duplicate, stale or
        # simultaneous requests see one consistent state.
        self._state_lock = threading.RLock()

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

        cost = self._simulated_seconds(prepared)
        daily = limits.MAX_DAILY_SIMULATED_SECONDS_PER_USER
        if cost > daily:
            # Not a matter of waiting: this experiment can never fit in one day.
            raise ExperimentError(
                [
                    f"quota {limits.QUOTA_NAMES['dailySimulatedSecondsPerUser']}: the experiment "
                    f"needs {cost:,.0f} simulated seconds, more than the {daily:,} a user may use per day"
                ]
            )

        # The quota check and the reservation (the record becomes "queued") happen under one lock, so two
        # simultaneous submissions cannot both pass a limit of one.
        with self._submit_lock:
            self._check_quotas(user_id)
            self._reserve_usage(user_id, cost)
            record = self._new_record(user_id, prepared)
            record["usageDay"] = utc_day()
            record["reservedSeconds"] = cost
            self.store.put(record)

        try:
            self._start(record, prepared, None)
        except QuotaExceeded:
            self.usage.release(user_id, cost, record["usageDay"])
            self.store.delete(record["id"])
            raise
        return self._status_view(record)

    def _start(
        self,
        record: Dict[str, Any],
        prepared: Prepared,
        completed: Optional[Dict[str, Any]],
    ) -> None:
        def work(job_progress: Progress) -> Dict[str, Any]:
            self._run(record, prepared, job_progress, completed)
            return {}

        try:
            self.jobs.submit("experiment", work)
        except TooManyJobsError as err:
            raise QuotaExceeded("maxActiveExperiments", str(err)) from err

    @staticmethod
    def _simulated_seconds(prepared: Prepared, runs: Optional[int] = None) -> float:
        assert prepared.base is not None and prepared.counts is not None
        total = prepared.counts["totalRuns"] if runs is None else runs
        return float(prepared.base.simulation.duration) * total

    def _reserve_usage(self, user_id: str, seconds: float) -> None:
        daily = limits.MAX_DAILY_SIMULATED_SECONDS_PER_USER
        ok, used = self.usage.reserve(user_id, seconds, daily)
        if not ok:
            raise QuotaExceeded(
                limits.QUOTA_NAMES["dailySimulatedSecondsPerUser"],
                f"{used:,.0f} of your {daily:,} simulated seconds are used today (UTC); "
                f"this needs {seconds:,.0f}",
            )

    def _check_quotas(self, user_id: str, new_record: bool = True) -> None:
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
        if (
            new_record
            and self.store.count_stored(user_id)
            >= limits.MAX_STORED_EXPERIMENTS_PER_USER
        ):
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
        self,
        record: Dict[str, Any],
        prepared: Prepared,
        progress: Progress,
        completed: Optional[Dict[str, Any]] = None,
    ) -> None:
        request = prepared.request
        assert request is not None and prepared.baseline is not None
        with self._state_lock:
            self._progress[record["id"]] = progress
            if record.get("cancelRequested"):
                # Cancelled while still queued: nothing was started.
                self._settle_cancelled(
                    record, prepared, {"checkpoint": completed or {}}
                )
                return
            record["status"] = "running"
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
            if completed:
                kwargs["completed"] = completed
            outcome = run_experiment(
                request.uncertainty, alternatives, prepared.baseline, **kwargs
            )
            with self._state_lock:
                if outcome.get("cancelled") or record.get("cancelRequested"):
                    self._settle_cancelled(record, prepared, outcome)
                    return
                outcome.pop("checkpoint", None)
                record["result"] = self._result_document(record, prepared, outcome)
                record["checkpoint"] = None
                record["status"] = "completed"
        except Exception as exc:
            logger.exception("Experiment %s failed", record["id"])
            with self._state_lock:
                record["error"] = _public_error(exc)
                record["status"] = "failed"
                record["cancelRequested"] = False
        finally:
            with self._state_lock:
                self._progress.pop(record["id"], None)
                record["settling"] = False
                self.store.put(record)

    def _settle_cancelled(
        self, record: Dict[str, Any], prepared: Prepared, outcome: Dict[str, Any]
    ) -> None:
        """The runner has stopped: keep what finished, refund what was never run, leave a partial result.

        Called with the state lock held."""
        assert prepared.counts is not None
        checkpoint = dict(outcome.get("checkpoint") or {})
        total = prepared.counts["totalRuns"]
        done = min(len(checkpoint), total)
        reserved = float(record.get("reservedSeconds") or 0.0)
        kept = reserved * done / total if total else 0.0
        if record.get("usageDay"):
            self.usage.release(record["userId"], reserved - kept, record["usageDay"])
        record["reservedSeconds"] = kept
        record["checkpoint"] = checkpoint
        record["result"] = self._partial_result(record, prepared, outcome, done)
        record["status"] = "cancelled"
        record["error"] = None
        self._progress.pop(record["id"], None)
        # Persist the checkpoint before anyone can see the experiment as settled (and resume or restart).
        self.store.put(record)
        record["settling"] = False
        self.store.put(record)

    @staticmethod
    def _partial_result(
        record: Dict[str, Any], prepared: Prepared, outcome: Dict[str, Any], done: int
    ) -> Dict[str, Any]:
        base = prepared.base
        assert base is not None and prepared.counts is not None
        return {
            "format": PARTIAL_RESULT_FORMAT,
            "version": PARTIAL_RESULT_VERSION,
            "experimentId": record["id"],
            "name": record["name"],
            "complete": False,
            "status": "cancelled",
            "scenario": {"name": base.name, "fingerprint": scenario_fingerprint(base)},
            "baseline": prepared.baseline,
            "specFingerprint": record.get("specFingerprint"),
            "runs": {
                "planned": prepared.counts["totalRuns"],
                "completed": done,
                "resumable": True,
            },
            # Computed from the finished conditions only; unfinished ones are excluded as
            # ``incomplete_cancelled``. ``None`` when too little finished to analyse. Not fingerprinted.
            "analysis": outcome.get("analysis"),
            "note": (
                "Cancelled before every run finished. This is not a result: resume the experiment to "
                "complete it. Only a completed result is fingerprinted and exportable."
            ),
        }

    # ---- cancel / resume --------------------------------------------------
    def cancel(self, user_id: str, experiment_id: str) -> Dict[str, Any]:
        """Stop a queued or running experiment (HTTP 202). Repeating the request is harmless.

        Cooperative: runs not yet started are skipped, a simulation already running in a worker finishes
        first, so the experiment stays counted as active until it has fully stopped. A finished or failed
        experiment cannot be cancelled (HTTP 409)."""
        with self._state_lock:
            record = self.store.get(user_id, experiment_id)
            if record is None:
                raise NotFound(experiment_id)
            status = record["status"]
            if status == "cancelled":
                return self._status_view(record)
            if status not in ("queued", "running"):
                raise ConflictError(
                    f"Experiment is {status}; only a queued or running one can be cancelled"
                )
            record["cancelRequested"] = True
            record["settling"] = True
            record["status"] = "cancelled"
            progress = self._progress.get(experiment_id)
            if progress is not None:
                progress.cancel()
            self.store.put(record)
            return self._status_view(record)

    def resume(self, user_id: str, experiment_id: str) -> Dict[str, Any]:
        """Run the rest of a cancelled experiment (HTTP 202).

        The finished runs are kept (each is a deterministic function of the specification) and only the
        missing ones are simulated, so the completed result equals that of an uninterrupted run."""
        with self._state_lock:
            record = self.store.get(user_id, experiment_id)
            if record is None:
                raise NotFound(experiment_id)
            if record["status"] != "cancelled":
                raise ConflictError(
                    f"Experiment is {record['status']}; only a cancelled experiment can be resumed"
                )
            if record.get("settling"):
                raise ConflictError("Experiment is still stopping; retry in a moment")
            prepared = prepare(record["request"])
            if not prepared.valid:
                raise ExperimentError(prepared.errors)
            assert prepared.counts is not None
            checkpoint: Dict[str, Any] = dict(record.get("checkpoint") or {})
            remaining = max(prepared.counts["totalRuns"] - len(checkpoint), 0)
            cost = self._simulated_seconds(prepared, remaining)
            with self._submit_lock:
                self._check_quotas(user_id, new_record=False)
                self._reserve_usage(user_id, cost)
            previous = {
                key: record.get(key)
                for key in (
                    "status",
                    "cancelRequested",
                    "settling",
                    "result",
                    "error",
                    "usageDay",
                    "reservedSeconds",
                )
            }
            record.update(
                status="queued",
                cancelRequested=False,
                settling=False,
                result=None,
                error=None,
                usageDay=utc_day(),
                reservedSeconds=float(record.get("reservedSeconds") or 0.0) + cost,
            )
            try:
                self._start(record, prepared, checkpoint)
            except QuotaExceeded:
                self.usage.release(user_id, cost, record["usageDay"])
                record.update(previous)
                raise
            self.store.put(record)
            return self._status_view(record)

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
        manifest = build_experiment_manifest(
            scenario=base,
            spec_fingerprint=outcome["specFingerprint"],
            result_fingerprint=fingerprint_of(evidence),
            factors=spec.factors,
            extra={
                "gitCommit": GIT_COMMIT_HASH,
                "pythonVersion": PYTHON_VERSION,
            },
        )
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
                "driverAggression": manifest["assumptions"]["driverAggression"],
                "driverAggressionHash": manifest["assumptions"]["driverAggressionHash"],
                "note": "Download the .ufpkg package to verify this result elsewhere: it carries the manifest and checksums (integrity, not authenticity).",
            },
            "manifest": manifest,
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
        """Delete the caller's finished, failed or cancelled experiment. A queued or running one must be
        cancelled first, and a cancelled one that is still stopping must settle."""
        with self._state_lock:
            record = self.store.get(user_id, experiment_id)
            if record is None:
                raise NotFound(experiment_id)
            if record["status"] in ("queued", "running"):
                raise ConflictError(
                    f"Experiment is {record['status']}; cancel it or wait for it to finish, "
                    "then delete it"
                )
            if record.get("settling"):
                raise ConflictError("Experiment is still stopping; retry in a moment")
            self.store.delete(experiment_id)

    # ---- packages ---------------------------------------------------------
    def export_package(self, user_id: str, experiment_id: str) -> Tuple[bytes, str]:
        """The caller's completed experiment as ``.ufpkg`` bytes plus a download file name.

        Raises :class:`NotFound` (not the caller's), :class:`ConflictError` (not completed) or
        :class:`PackageTooLarge` (over the package size limit)."""
        record = self.store.get(user_id, experiment_id)
        if record is None:
            raise NotFound(experiment_id)
        result = record.get("result")
        if record["status"] != "completed" or result is None:
            raise ConflictError(
                f"Experiment is {record['status']}; only a completed experiment can be exported"
            )
        data = build_package(record["request"], result, record["createdAt"])
        return data, f"urbanflow-{experiment_id[:12]}{PACKAGE_EXTENSION}"

    # ---- capabilities ---------------------------------------------------
    @staticmethod
    def capabilities(max_request_body_bytes: int) -> Dict[str, Any]:
        """What this server offers. A client shows a capability only when it is listed here as true.

        ``max_request_body_bytes`` is the delivery layer's body-size cap, reported as is."""
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
                "experimentCancellation": True,
                "experimentPackages": True,
                "personalAccessTokens": True,
                "pythonClient": True,
                # The deterministic experiment assistant (always available). "aiCopilot" stays false
                # until a model provider passes the copilot-eval-v1 evaluation (strategy 15.1.6).
                "experimentCopilot": True,
                "stressLab": True,
                "aiCopilot": False,
                "discoveryLab": True,
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
            "limits": {
                "maxRequestBodyBytes": max_request_body_bytes,
                "maxPackageBytes": limits.MAX_PACKAGE_BYTES,
                "maxPackageUncompressedBytes": limits.MAX_PACKAGE_UNCOMPRESSED_BYTES,
                "maxPackageEntries": limits.MAX_PACKAGE_ENTRIES,
            },
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
