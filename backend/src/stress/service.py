"""Stress-lab jobs: requests, quota reservation, background execution, ownership."""

from __future__ import annotations

import datetime as _dt
import threading
import uuid
from typing import Any, Callable, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.experiments import limits
from src.experiments.service import (
    ConflictError,
    ExperimentService,
    NotFound,
    QuotaExceeded,
)
from src.scenario.documents import parse_scenario
from src.study.jobs import JobRegistry, TooManyJobsError
from src.study.runner import Progress, run_simulation_tasks_isolated

from .generator import MAX_SCENARIOS
from .lab import Cancelled, Executor, run_breakpoints, run_suite

StrategyName = Literal["fixed_time", "adaptive", "roundabout", "signalised_roundabout"]


def _all_strategies() -> List[StrategyName]:
    return ["fixed_time", "adaptive", "roundabout", "signalised_roundabout"]


def _baseline_strategies() -> List[StrategyName]:
    return ["fixed_time", "adaptive", "roundabout"]


def _demand_levels() -> List[Union[float, str]]:
    return [0.6, 0.8, 1.0, 1.2, 1.4]


MAX_ACTIVE_JOBS_PER_USER = 2
MAX_KEPT_PER_USER = 20


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SuiteRequest(_Strict):
    seed: int = Field(1, ge=0, le=2**31 - 1)
    count: int = Field(8, ge=1, le=MAX_SCENARIOS)
    strategies: List[StrategyName] = Field(
        default_factory=_all_strategies, min_length=1, max_length=4
    )
    seedsPerRun: int = Field(2, ge=1, le=5)
    duration: float = Field(120.0, ge=60, le=600)

    def runs(self) -> int:
        return self.count * len(self.strategies) * self.seedsPerRun


class BreakpointRequest(_Strict):
    # An ``urbanflow-scenario`` document; omitted: a balanced four-arm junction at 500 veh/h per arm.
    scenario: Optional[Dict[str, Any]] = None
    factor: Literal["demand_scale", "aggression"] = "demand_scale"
    levels: List[Union[float, str]] = Field(
        default_factory=_demand_levels, min_length=1, max_length=8
    )
    strategies: List[StrategyName] = Field(
        default_factory=_baseline_strategies,
        min_length=2,
        max_length=4,
    )
    seed: int = Field(1, ge=0, le=2**31 - 1)
    seedsPerLevel: int = Field(3, ge=1, le=6)

    @model_validator(mode="after")
    def _levels(self) -> "BreakpointRequest":
        if self.factor == "demand_scale":
            if not all(
                isinstance(v, (int, float)) and 0.1 <= float(v) <= 3.0
                for v in self.levels
            ):
                raise ValueError(
                    "demand_scale levels must be numbers between 0.1 and 3.0"
                )
        elif not all(v in ("standard", "moderate", "high") for v in self.levels):
            raise ValueError("aggression levels must be standard, moderate or high")
        return self

    def runs(self) -> int:
        return len(self.levels) * len(self.strategies) * self.seedsPerLevel


def default_scenario(duration: float = 120.0) -> Dict[str, Any]:
    return {
        "format": "urbanflow-scenario",
        "version": 1,
        "name": "Breakpoint base junction",
        "junction": {"type": "fixed_time_signal"},
        "approaches": {
            d: {
                "lanes": 1,
                "vehiclesPerHour": 500,
                "turning": {"left": 0.2, "straight": 0.6, "right": 0.2},
            }
            for d in ("north", "south", "east", "west")
        },
        "simulation": {"duration": duration, "warmup": 30, "seed": 1},
    }


class StressService:
    def __init__(
        self, experiments: ExperimentService, executor: Optional[Executor] = None
    ) -> None:
        self.experiments = experiments
        self.executor: Executor = executor or run_simulation_tasks_isolated
        self.jobs = JobRegistry()
        self._lock = threading.Lock()
        self._records: Dict[str, Dict[str, Any]] = {}

    def _submit(
        self,
        user_id: str,
        kind: str,
        runs: int,
        duration: float,
        work: Callable[[Progress], Dict[str, Any]],
    ) -> Dict[str, Any]:
        seconds = runs * duration
        daily = limits.MAX_DAILY_SIMULATED_SECONDS_PER_USER
        with self._lock:
            active = sum(
                1
                for r in self._records.values()
                if r["userId"] == user_id and r["status"] in ("queued", "running")
            )
            if active >= MAX_ACTIVE_JOBS_PER_USER:
                raise QuotaExceeded(
                    "maxActiveStressJobsPerUser",
                    f"you already have {MAX_ACTIVE_JOBS_PER_USER} stress jobs running",
                )
            ok, used = self.experiments.usage.reserve(user_id, seconds, daily)
            if not ok:
                raise QuotaExceeded(
                    limits.QUOTA_NAMES["dailySimulatedSecondsPerUser"],
                    f"{used:,.0f} of your {daily:,} simulated seconds are used today (UTC); this needs {seconds:,.0f}",
                )
            record: Dict[str, Any] = {
                "id": uuid.uuid4().hex,
                "userId": user_id,
                "kind": kind,
                "status": "queued",
                "createdAt": _dt.datetime.now(_dt.timezone.utc).isoformat(),
                "runs": runs,
                "result": None,
                "error": None,
                "progress": None,
                "reserved": seconds,
                "usageDay": _dt.datetime.now(_dt.timezone.utc).date().isoformat(),
            }
            mine = sorted(
                (
                    r
                    for r in self._records.values()
                    if r["userId"] == user_id
                    and r["status"] not in ("queued", "running")
                ),
                key=lambda r: r["createdAt"],
            )
            for old in mine[: max(0, len(mine) - MAX_KEPT_PER_USER + 1)]:
                self._records.pop(old["id"], None)
            self._records[record["id"]] = record

        def job(progress: Progress) -> Dict[str, Any]:
            record["status"] = "running"
            record["progress"] = progress
            try:
                record["result"] = work(progress)
                record["status"] = "completed"
            except Cancelled:
                record["status"] = "cancelled"
                self.experiments.usage.release(user_id, seconds, record["usageDay"])
            except Exception as exc:  # noqa: BLE001
                record["status"] = "failed"
                record["error"] = (
                    f"The job failed ({type(exc).__name__}). The server log has the details."
                )
                raise
            finally:
                record["progress"] = None
            return {}

        try:
            self.jobs.submit(f"stress-{kind}", job)
        except TooManyJobsError as err:
            with self._lock:
                self._records.pop(record["id"], None)
            self.experiments.usage.release(user_id, seconds, record["usageDay"])
            raise QuotaExceeded("maxActiveStressJobs", str(err)) from err
        return self.view(record)

    def submit_suite(self, user_id: str, req: SuiteRequest) -> Dict[str, Any]:
        return self._submit(
            user_id,
            "suite",
            req.runs(),
            req.duration,
            lambda progress: run_suite(
                req.seed,
                req.count,
                req.strategies,
                req.seedsPerRun,
                req.duration,
                self.executor,
                progress,
            ),
        )

    def submit_breakpoints(
        self, user_id: str, req: BreakpointRequest
    ) -> Dict[str, Any]:
        scenario = req.scenario or default_scenario()
        parsed, errors = parse_scenario(scenario)
        if parsed is None:
            raise ConflictError("the scenario is not valid: " + "; ".join(errors[:3]))
        return self._submit(
            user_id,
            "breakpoints",
            req.runs(),
            float(parsed.simulation.duration),
            lambda progress: run_breakpoints(
                scenario,
                req.factor,
                req.levels,
                req.strategies,
                req.seed,
                req.seedsPerLevel,
                self.executor,
                progress,
            ),
        )

    @staticmethod
    def view(record: Dict[str, Any]) -> Dict[str, Any]:
        progress: Optional[Progress] = record.get("progress")
        return {
            "format": "urbanflow-stress-job",
            "version": 1,
            "id": record["id"],
            "kind": record["kind"],
            "status": record["status"],
            "createdAt": record["createdAt"],
            "runs": record["runs"],
            "progress": progress.snapshot() if progress is not None else None,
            "resultAvailable": record["result"] is not None,
            "error": record["error"],
        }

    def _get(self, user_id: str, job_id: str) -> Dict[str, Any]:
        with self._lock:
            record = self._records.get(job_id)
        if record is None or record["userId"] != user_id:
            raise NotFound(job_id)
        return record

    def status(self, user_id: str, job_id: str) -> Dict[str, Any]:
        return self.view(self._get(user_id, job_id))

    def result(self, user_id: str, job_id: str) -> Dict[str, Any]:
        record = self._get(user_id, job_id)
        if record["result"] is None:
            raise ConflictError(f"Job is {record['status']}; there is no result")
        result: Dict[str, Any] = record["result"]
        return result

    def list_for_user(self, user_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            mine = [r for r in self._records.values() if r["userId"] == user_id]
        return [
            self.view(r)
            for r in sorted(mine, key=lambda r: r["createdAt"], reverse=True)
        ]

    def cancel(self, user_id: str, job_id: str) -> Dict[str, Any]:
        record = self._get(user_id, job_id)
        if record["status"] not in ("queued", "running"):
            raise ConflictError(
                f"Job is {record['status']}; only a running job can be cancelled"
            )
        progress: Optional[Progress] = record.get("progress")
        if progress is not None:
            progress.cancel()
        return self.view(record)
