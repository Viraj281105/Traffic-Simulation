"""Shared builders for the job tests."""

from pathlib import Path
from typing import Any, Dict, List

import pytest

from src.core.run_manifest import build_run_manifest
from src.jobs import (
    InMemoryJobQueue,
    JobMessage,
    JobRequest,
    build_job_tags,
    build_message,
)
from src.runstore import LocalFileBackend, RunStore

TAGS = {"project": "urbanflow", "env": "test", "owner": "viraj"}


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def make_message(tenant: str = "acme", **overrides: Any) -> JobMessage:
    request = JobRequest.model_validate(
        {"tenant": tenant, "run": {"numSeeds": 2, "duration": 5}, **overrides}
    )
    tags = build_job_tags(request.run_id or "x", tenant=tenant, tags=TAGS, environ={})
    return build_message(request, tags, now=1.0, job_id="job-1")


def fake_runner(message: JobMessage) -> Dict[str, Any]:
    manifest = build_run_manifest(
        config={"simulation": {"duration": message.run.duration}},
        seed=None,
        run_mode="multi-seed",
        git_commit="abc",
        python_version="3.12.0",
        timing={"timeStep": 0.1, "duration": message.run.duration, "warmupTime": 1.0},
        created_at="2026-11-09T00:00:00+00:00",
    )
    rows: List[Dict[str, Any]] = [
        {"seed": i, "delay": 1.5 * i, "throughput": 10.0, "queue": 2.0}
        for i in range(message.run.num_seeds)
    ]
    return {"manifest": manifest, "seedRuns": rows}


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def queue(clock: Clock) -> InMemoryJobQueue:
    return InMemoryJobQueue(max_receives=3, visibility_timeout=30, clock=clock)


@pytest.fixture
def store(tmp_path: Path) -> RunStore:
    return RunStore(LocalFileBackend(tmp_path))
