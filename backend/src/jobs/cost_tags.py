"""Cost-allocation tags for a job, and a simple per-job compute-time recorder (F17, package 2E).

Every job carries the tags AWS Cost Explorer groups by. ``project``, ``env`` and ``owner`` are
mandatory (the Terraform tagging module applies the same three to every resource); ``tenant`` and
``run-id`` are added per job. ``src/costing`` (a later package) turns recorded compute time into
money; this module only records seconds and never prices them.
"""

from __future__ import annotations

import os
import re
import threading
import time
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Callable, Deque, Dict, Iterator, List, Mapping, Optional

MANDATORY_TAGS = ("project", "env", "owner")
OPTIONAL_TAGS = ("tenant", "run-id")

DEFAULT_PROJECT = "urbanflow"
MAX_TAGS = 50
MAX_KEY_LENGTH = 128
MAX_VALUE_LENGTH = 256

# The character set AWS allows in tag keys and values.
_TAG_TEXT = re.compile(r"^[A-Za-z0-9 _.:/=+@-]*$")


class CostTagError(ValueError):
    """The tags are missing a mandatory key or hold a value AWS would reject."""


def default_tags(environ: Optional[Mapping[str, str]] = None) -> Dict[str, str]:
    """Tags the server can fill in itself: project, env and owner from the environment."""
    env = os.environ if environ is None else environ
    found = {
        "project": env.get("URBANFLOW_PROJECT", DEFAULT_PROJECT),
        "env": env.get("URBANFLOW_ENV", ""),
        "owner": env.get("URBANFLOW_OWNER", ""),
    }
    return {k: v for k, v in found.items() if v}


def validate_tags(tags: Mapping[str, str]) -> Dict[str, str]:
    """Return a clean copy of ``tags`` or raise ``CostTagError`` naming every problem."""
    problems: List[str] = []
    missing = [k for k in MANDATORY_TAGS if not str(tags.get(k, "")).strip()]
    if missing:
        problems.append("missing mandatory tag(s): " + ", ".join(missing))
    if len(tags) > MAX_TAGS:
        problems.append(f"at most {MAX_TAGS} tags are allowed")
    clean: Dict[str, str] = {}
    for key, value in tags.items():
        if not isinstance(key, str) or not isinstance(value, str):
            problems.append("tag keys and values must be strings")
            continue
        if not key or len(key) > MAX_KEY_LENGTH or not _TAG_TEXT.match(key):
            problems.append(f"invalid tag key {key!r}")
        elif key.lower().startswith("aws:"):
            problems.append(f"tag key {key!r} uses the reserved aws: prefix")
        if len(value) > MAX_VALUE_LENGTH or not _TAG_TEXT.match(value):
            problems.append(f"invalid value for tag {key!r}")
        clean[key] = value.strip()
    if problems:
        raise CostTagError("; ".join(problems))
    return clean


def build_job_tags(
    run_id: str,
    *,
    tenant: Optional[str] = None,
    tags: Optional[Mapping[str, str]] = None,
    environ: Optional[Mapping[str, str]] = None,
) -> Dict[str, str]:
    """The validated tag set for one job: server defaults, then caller tags, then tenant/run-id.

    Tenant and run id come from the job itself and cannot be overridden by ``tags``.
    """
    merged: Dict[str, str] = dict(default_tags(environ))
    merged.update({k: v for k, v in (tags or {}).items()})
    merged["run-id"] = run_id
    if tenant:
        merged["tenant"] = tenant
    return validate_tags(merged)


@dataclass
class Measurement:
    """Filled in by ``ComputeTimeRecorder.measure``: set ``ok`` inside the block; read
    ``wall_seconds`` after it."""

    ok: bool = False
    wall_seconds: float = 0.0


@dataclass(frozen=True)
class JobUsage:
    """What one attempt at a job consumed: wall-clock seconds on one worker."""

    job_id: str
    run_id: str
    tenant: str
    worker_id: str
    started_at: float
    wall_seconds: float
    succeeded: bool
    tags: Dict[str, str] = field(default_factory=dict)


class ComputeTimeRecorder:
    """Keeps the most recent ``capacity`` usage records and totals per tenant.

    Wall-clock seconds are what an EKS node bills for; vCPU weighting belongs to the costing
    package. Thread-safe, because a worker may report from a helper thread.
    """

    def __init__(
        self, capacity: int = 1000, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._records: Deque[JobUsage] = deque(maxlen=capacity)
        self._clock = clock
        self._lock = threading.Lock()

    @contextmanager
    def measure(
        self,
        *,
        job_id: str,
        run_id: str,
        tenant: str,
        worker_id: str,
        tags: Optional[Mapping[str, str]] = None,
    ) -> Iterator[Measurement]:
        """Time a block. Set ``m.ok = True`` inside it to mark success; an exception leaves it
        False (and propagates)."""
        outcome = Measurement()
        start = self._clock()
        try:
            yield outcome
        finally:
            outcome.wall_seconds = max(0.0, self._clock() - start)
            self.record(
                JobUsage(
                    job_id=job_id,
                    run_id=run_id,
                    tenant=tenant,
                    worker_id=worker_id,
                    started_at=start,
                    wall_seconds=outcome.wall_seconds,
                    succeeded=outcome.ok,
                    tags=dict(tags or {}),
                )
            )

    def record(self, usage: JobUsage) -> None:
        with self._lock:
            self._records.append(usage)

    def records(self) -> List[JobUsage]:
        with self._lock:
            return list(self._records)

    def seconds_by_tenant(self) -> Dict[str, float]:
        totals: Dict[str, float] = {}
        for rec in self.records():
            totals[rec.tenant] = totals.get(rec.tenant, 0.0) + rec.wall_seconds
        return totals

    def total_seconds(self) -> float:
        return sum(rec.wall_seconds for rec in self.records())
