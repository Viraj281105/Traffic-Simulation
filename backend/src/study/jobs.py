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
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "jobId": self.id,
            "kind": self.kind,
            "status": self.status,
            "progress": self.progress.snapshot(),
            "result": self.result,
            "error": self.error,
        }


class JobRegistry:
    def __init__(self) -> None:
        self._jobs: Dict[str, StudyJob] = {}
        self._lock = threading.Lock()
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

    def _run(self, job: StudyJob, work: Callable[[Progress], Dict[str, Any]]) -> None:
        job.status = "running"
        try:
            job.result = work(job.progress)
            job.status = "completed"
        except Exception as exc:
            logger.exception("Study job %s (%s) failed", job.id, job.kind)
            job.error = str(exc) or type(exc).__name__
            job.status = "failed"
        finally:
            job.progress.set_phase("done")
            job.finished_at = time.monotonic()

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
