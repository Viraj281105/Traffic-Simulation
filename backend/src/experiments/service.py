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
from typing import Any, Dict, List, Optional

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
from src.vehicles.driver_aggression import (
    compute_aggression_parameter_hash,
    resolve_aggression_name,
)

from . import limits
from .models import (
    EXPERIMENT_FORMAT,
    EXPERIMENT_VERSION,
    RESULT_FORMAT,
    RESULT_VERSION,
)

logger = logging.getLogger(__name__)
from .preparation import Prepared, prepare
from .store import ExperimentStore

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
            record["error"] = _public_error(exc)
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
        profile = resolve_aggression_name(base.model_dump())
        aggression_hash = compute_aggression_parameter_hash(profile)
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
                "driverAggression": profile,
                "driverAggressionHash": aggression_hash,
                "note": "The full reproducibility manifest and package verification arrive in a later release.",
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
            "limits": {"maxRequestBodyBytes": max_request_body_bytes},
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
