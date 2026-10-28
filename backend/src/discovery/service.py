"""Discovery searches: submit, follow, cancel, read, package (``/api/v3/discovery``).

Searches run as background jobs on the shared process pool. Each belongs to its creator (404 for anyone
else). At most two run per user at once. The whole planned budget (runs x simulated seconds) is reserved
against the user's daily quota at submission, so a search can never exceed it while running; unused runs
are refunded when it ends. Searches are kept in memory (a server restart drops them; their packages are
the durable record).
"""

from __future__ import annotations

import datetime as _dt
import threading
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.core.provenance import GIT_COMMIT_HASH, PYTHON_VERSION
from src.experiments import limits
from src.experiments.manifest import build_experiment_manifest
from src.experiments.package import PACKAGE_EXTENSION, assemble_package
from src.experiments.service import (
    ConflictError,
    ExperimentService,
    NotFound,
    QuotaExceeded,
)
from src.scenario.documents import ScenarioDocument
from src.study.jobs import JobRegistry, TooManyJobsError
from src.study.runner import Progress

from .evaluator import SimulationEvaluator
from .models import SearchSpec, planned_runs, planned_simulated_seconds
from .search import Evaluator, Search
from .space import regime_scenario

MAX_ACTIVE_SEARCHES_PER_USER = 2
MAX_KEPT_SEARCHES_PER_USER = 20

EvaluatorFactory = Callable[[Progress], Evaluator]


class DiscoveryService:
    def __init__(
        self,
        experiments: ExperimentService,
        evaluator_factory: Optional[EvaluatorFactory] = None,
    ) -> None:
        self.experiments = experiments
        self.evaluator_factory: EvaluatorFactory = evaluator_factory or (
            lambda progress: SimulationEvaluator(progress)
        )
        self.jobs = JobRegistry()
        self._lock = threading.Lock()
        self._records: Dict[str, Dict[str, Any]] = {}

    def submit(self, user_id: str, spec: SearchSpec) -> Dict[str, Any]:
        seconds = planned_simulated_seconds(spec)
        daily = limits.MAX_DAILY_SIMULATED_SECONDS_PER_USER
        if seconds > daily:
            raise QuotaExceeded(
                limits.QUOTA_NAMES["dailySimulatedSecondsPerUser"],
                f"the search's budget is {seconds:,.0f} simulated seconds, more than the {daily:,} "
                "allowed per day; lower the population, generations, seeds or duration",
            )
        with self._lock:
            active = sum(
                1
                for r in self._records.values()
                if r["userId"] == user_id and r["status"] in ("queued", "running")
            )
            if active >= MAX_ACTIVE_SEARCHES_PER_USER:
                raise QuotaExceeded(
                    "maxActiveSearchesPerUser",
                    f"you already have {MAX_ACTIVE_SEARCHES_PER_USER} searches running",
                )
            ok, used = self.experiments.usage.reserve(user_id, seconds, daily)
            if not ok:
                raise QuotaExceeded(
                    limits.QUOTA_NAMES["dailySimulatedSecondsPerUser"],
                    f"{used:,.0f} of your {daily:,} simulated seconds are used today (UTC); "
                    f"this search reserves {seconds:,.0f}",
                )
            record: Dict[str, Any] = {
                "id": uuid.uuid4().hex,
                "userId": user_id,
                "name": spec.name,
                "spec": spec,
                "status": "queued",
                "createdAt": _dt.datetime.now(_dt.timezone.utc).isoformat(),
                "phase": "queued",
                "runsUsed": 0,
                "runsPlanned": planned_runs(spec),
                "result": None,
                "error": None,
                "progress": None,
                "reserved": seconds,
                "usageDay": _dt.datetime.now(_dt.timezone.utc).date().isoformat(),
            }
            self._evict(user_id)
            self._records[record["id"]] = record

        def work(progress: Progress) -> Dict[str, Any]:
            self._run(record, progress)
            return {}

        try:
            self.jobs.submit("discovery", work)
        except TooManyJobsError as err:
            with self._lock:
                self._records.pop(record["id"], None)
            self.experiments.usage.release(user_id, seconds, record["usageDay"])
            raise QuotaExceeded("maxActiveSearches", str(err)) from err
        return self.status_view(record)

    def _evict(self, user_id: str) -> None:
        mine = sorted(
            (
                r
                for r in self._records.values()
                if r["userId"] == user_id and r["status"] not in ("queued", "running")
            ),
            key=lambda r: r["createdAt"],
        )
        for old in mine[: max(0, len(mine) - MAX_KEPT_SEARCHES_PER_USER + 1)]:
            self._records.pop(old["id"], None)

    def _run(self, record: Dict[str, Any], progress: Progress) -> None:
        spec: SearchSpec = record["spec"]
        record["status"] = "running"
        record["progress"] = progress

        def on_progress(phase: str, used: int, planned: int) -> None:
            record["phase"] = phase
            record["runsUsed"] = used

        try:
            if record.get("cancelRequested"):
                progress.cancel()
            search = Search(
                spec,
                self.evaluator_factory(progress),
                should_stop=lambda: progress.cancelled,
                on_progress=on_progress,
            )
            result = search.run()
            result["searchId"] = record["id"]
            result["name"] = spec.name
            result["provenance"] = {
                "gitCommit": GIT_COMMIT_HASH,
                "pythonVersion": PYTHON_VERSION,
                "rngSeed": spec.seed,
                "searchSpecification": spec.model_dump(mode="json"),
            }
            record["result"] = result
            record["runsUsed"] = result["runs"]["used"]
            record["status"] = (
                "cancelled" if result["status"] == "cancelled" else "completed"
            )
        except Exception as exc:  # noqa: BLE001 - reported on the record, logged by the job registry
            record["status"] = "failed"
            record["error"] = (
                f"The search failed ({type(exc).__name__}). The server log has the details."
            )
            raise
        finally:
            record["phase"] = "done"
            record["progress"] = None
            unused = max(0, record["runsPlanned"] - record["runsUsed"]) * float(
                spec.regime.duration
            )
            self.experiments.usage.release(record["userId"], unused, record["usageDay"])

    # ---- read ---------------------------------------------------------------------------------------
    def _get(self, user_id: str, search_id: str) -> Dict[str, Any]:
        with self._lock:
            record = self._records.get(search_id)
        if record is None or record["userId"] != user_id:
            raise NotFound(search_id)
        return record

    @staticmethod
    def status_view(record: Dict[str, Any]) -> Dict[str, Any]:
        progress: Optional[Progress] = record.get("progress")
        return {
            "format": "urbanflow-discovery-status",
            "version": 1,
            "id": record["id"],
            "name": record["name"],
            "status": record["status"],
            "phase": record["phase"],
            "createdAt": record["createdAt"],
            "runs": {"planned": record["runsPlanned"], "used": record["runsUsed"]},
            "progress": progress.snapshot() if progress is not None else None,
            "resultAvailable": record["result"] is not None,
            "error": record["error"],
        }

    def status(self, user_id: str, search_id: str) -> Dict[str, Any]:
        return self.status_view(self._get(user_id, search_id))

    def list_for_user(self, user_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            mine = [r for r in self._records.values() if r["userId"] == user_id]
        return [
            self.status_view(r)
            for r in sorted(mine, key=lambda r: r["createdAt"], reverse=True)
        ]

    def result(self, user_id: str, search_id: str) -> Dict[str, Any]:
        record = self._get(user_id, search_id)
        if record["result"] is None:
            raise ConflictError(f"Search is {record['status']}; there is no result yet")
        result: Dict[str, Any] = record["result"]
        return result

    def cancel(self, user_id: str, search_id: str) -> Dict[str, Any]:
        record = self._get(user_id, search_id)
        if record["status"] not in ("queued", "running"):
            if record["status"] == "cancelled":
                return self.status_view(record)
            raise ConflictError(
                f"Search is {record['status']}; only a running search can be cancelled"
            )
        record["cancelRequested"] = True
        progress: Optional[Progress] = record.get("progress")
        if progress is not None:
            progress.cancel()
        return self.status_view(record)

    # ---- package ------------------------------------------------------------------------------------
    def package(self, user_id: str, search_id: str) -> Tuple[bytes, str]:
        record = self._get(user_id, search_id)
        result = record["result"]
        if (
            record["status"] != "completed"
            or result is None
            or not result.get("complete")
        ):
            raise ConflictError("only a completed search can be exported")
        spec: SearchSpec = record["spec"]
        scenario = ScenarioDocument.model_validate(regime_scenario(spec.regime))
        manifest = build_experiment_manifest(
            scenario=scenario,
            spec_fingerprint=spec.fingerprint(),
            result_fingerprint=result["traceFingerprint"],
            kind="discovery_search",
            extra={"gitCommit": GIT_COMMIT_HASH, "pythonVersion": PYTHON_VERSION},
        )
        data = assemble_package(
            spec.model_dump(mode="json"), result, manifest, record["createdAt"]
        )
        return data, f"urbanflow-discovery-{search_id[:12]}{PACKAGE_EXTENSION}"
