"""Background study jobs: start a sweep or Monte Carlo study, poll its progress.

A study used to run inside its POST request, so the browser sat on one open
request for minutes with nothing to show. A job returns at once with an id;
``GET /api/v1/study/jobs/{id}`` then reports live progress (study/runner.py)
and, when done, the same result the synchronous endpoint returns.

In-process and in-memory by design: a job is tied to the worker pool of this
process, and a finished result is also persisted by the study itself (sweeps
to the database) or returned to the client that polled it. A server restart
drops unfinished jobs, which the client reports as a failed run.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
import weakref
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterator, Optional, Tuple

from src.observability.metrics import JOB_DURATION, JOBS, JOBS_REJECTED
from src.study.runner import Progress

logger = logging.getLogger(__name__)

# Studies running (or waiting) at once. Each already fills the worker pool, so
# more would only queue; the cap stops a client from queueing unbounded work
# now that starting one no longer holds a request open.
MAX_ACTIVE_JOBS = 4

# Finished jobs are kept this long for a client to collect the result.
FINISHED_JOB_TTL_SECONDS = 3600.0
MAX_FINISHED_JOBS = 50


class TooManyJobsError(RuntimeError):
    pass


@dataclass
class StudyJob:
    kind: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    progress: Progress = field(default_factory=Progress)
    status: str = "queued"  # queued | running | completed | failed
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    finished_at: Optional[float] = None
    started_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "jobId": self.id,
            "kind": self.kind,
            "status": self.status,
            "progress": self.progress.snapshot(),
            "result": self.result,
            "error": self.error,
        }


# Every registry in the process (the study one below and each lab's), for
# the active-jobs gauge; weak, so a registry built in a test can go away.
_REGISTRIES: "weakref.WeakSet[JobRegistry]" = weakref.WeakSet()


def active_jobs_by_kind() -> Iterator[Tuple[Tuple[str], float]]:
    """(kind,) -> jobs queued or running, across every registry."""
    counts: Dict[str, int] = {}
    for registry in list(_REGISTRIES):
        for kind in registry.active_kinds():
            counts[kind] = counts.get(kind, 0) + 1
    for kind, n in sorted(counts.items()):
        yield (kind,), float(n)


class JobRegistry:
    def __init__(self) -> None:
        self._jobs: Dict[str, StudyJob] = {}
        self._lock = threading.Lock()
        _REGISTRIES.add(self)
        # Threads only coordinate (submit to the process pool, aggregate,
        # write the database); the simulations run in worker processes.
        self._executor = ThreadPoolExecutor(
            max_workers=MAX_ACTIVE_JOBS, thread_name_prefix="study-job"
        )

    def submit(self, kind: str, work: Callable[[Progress], Dict[str, Any]]) -> StudyJob:
        with self._lock:
            self._evict_finished()
            active = sum(j.finished_at is None for j in self._jobs.values())
            if active >= MAX_ACTIVE_JOBS:
                JOBS_REJECTED.inc(kind)
                logger.warning(
                    "job refused: %d already active",
                    active,
                    extra={"event": "job_rejected", "job_kind": kind},
                )
                raise TooManyJobsError(
                    f"{active} studies are already running; try again when one finishes"
                )
            job = StudyJob(kind=kind)
            self._jobs[job.id] = job
        self._executor.submit(self._run, job, work)
        return job

    def get(self, job_id: str) -> Optional[StudyJob]:
        with self._lock:
            return self._jobs.get(job_id)

    def active_kinds(self) -> list[str]:
        with self._lock:
            return [j.kind for j in self._jobs.values() if j.finished_at is None]

    def _run(self, job: StudyJob, work: Callable[[Progress], Dict[str, Any]]) -> None:
        job.status = "running"
        job.started_at = time.monotonic()
        logger.info(
            "job started",
            extra={"event": "job_started", "job_id": job.id, "job_kind": job.kind},
        )
        try:
            job.result = work(job.progress)
            job.status = "completed"
        except Exception as exc:
            logger.exception(
                "Study job %s (%s) failed",
                job.id,
                job.kind,
                extra={"event": "job_failed", "job_id": job.id, "job_kind": job.kind},
            )
            job.error = str(exc) or type(exc).__name__
            job.status = "failed"
        finally:
            job.progress.set_phase("done")
            job.finished_at = time.monotonic()
            # A lab that honours a cancel request returns normally; its
            # progress records the request, so it is counted as cancelled.
            outcome = (
                "failed"
                if job.status == "failed"
                else "cancelled"
                if job.progress.cancelled
                else "completed"
            )
            seconds = job.finished_at - job.started_at
            JOBS.inc(job.kind, outcome)
            JOB_DURATION.observe(seconds, job.kind)
            if outcome != "failed":
                logger.info(
                    "job %s",
                    outcome,
                    extra={
                        "event": f"job_{outcome}",
                        "job_id": job.id,
                        "job_kind": job.kind,
                        "duration_s": round(seconds, 3),
                    },
                )

    def _evict_finished(self) -> None:
        now = time.monotonic()
        finished = sorted(
            (j for j in self._jobs.values() if j.finished_at is not None),
            key=lambda j: j.finished_at or 0.0,
        )
        excess = len(finished) - MAX_FINISHED_JOBS
        for i, job in enumerate(finished):
            if i < excess or now - (job.finished_at or now) > FINISHED_JOB_TTL_SECONDS:
                del self._jobs[job.id]


jobs = JobRegistry()
