"""Run and API metrics for the Prometheus/Grafana/SLO stack (package 1D, F15).

Metrics (names are what ``deploy/observability`` queries):

* ``urbanflow_runs_started_total{kind}``
* ``urbanflow_runs_completed_total{kind,outcome}``  (outcome: completed, failed, cancelled)
* ``urbanflow_run_duration_seconds{kind}``           (histogram)
* ``urbanflow_queue_depth``                           (gauge, jobs waiting/active)
* ``urbanflow_api_latency_seconds{method,route}``     (histogram, route *template*)

With ``prometheus_client`` installed they live in a private
``CollectorRegistry`` and are rendered by ``generate_latest``. Without it the
same names are recorded by the stdlib registry in ``observability.metrics``
(its own instance, so nothing collides with the always-on ``REGISTRY``).
:func:`render` also appends the always-on ``REGISTRY`` text
(``urbanflow_http_*``, ``urbanflow_jobs_*``, ...), so one scrape carries both.

Labels are low-cardinality only (kind, outcome, method, route template).
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any, Iterator, List, Optional

from .metrics import JOB_BUCKETS, LATENCY_BUCKETS, REGISTRY, Registry
from .slo import Sample, parse_prometheus_text

CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"

_RUN_OUTCOMES = frozenset({"completed", "failed", "cancelled"})


class PromMetrics:
    """One set of run/API metrics. Tests build their own; the app uses ``METRICS``."""

    def __init__(self, use_prometheus_client: Optional[bool] = None) -> None:
        self._queue = 0.0
        self._pc: Any = None
        if use_prometheus_client is not False:
            try:
                import prometheus_client as pc  # type: ignore[import-not-found,unused-ignore]
            except Exception:  # noqa: BLE001 - optional dependency
                pc = None
            if pc is None and use_prometheus_client:
                raise RuntimeError("prometheus_client is not installed")
            self._pc = pc
        self.backend = "prometheus_client" if self._pc is not None else "builtin"
        if self._pc is not None:
            self._build_pc()
        else:
            self._build_builtin()

    # -- construction ---------------------------------------------------------------
    def _build_pc(self) -> None:
        pc = self._pc
        self._registry = pc.CollectorRegistry()
        self._started = pc.Counter(
            "urbanflow_runs_started",
            "Simulation runs started, by kind.",
            ["kind"],
            registry=self._registry,
        )
        self._completed = pc.Counter(
            "urbanflow_runs_completed",
            "Simulation runs finished, by kind and outcome.",
            ["kind", "outcome"],
            registry=self._registry,
        )
        self._duration = pc.Histogram(
            "urbanflow_run_duration_seconds",
            "Simulation run wall time, by kind.",
            ["kind"],
            buckets=JOB_BUCKETS,
            registry=self._registry,
        )
        self._latency = pc.Histogram(
            "urbanflow_api_latency_seconds",
            "API request latency, by method and route template.",
            ["method", "route"],
            buckets=LATENCY_BUCKETS,
            registry=self._registry,
        )
        self._gauge = pc.Gauge(
            "urbanflow_queue_depth",
            "Jobs queued or running.",
            registry=self._registry,
        )

    def _build_builtin(self) -> None:
        reg = Registry()
        self._registry = reg
        self._started = reg.counter(
            "urbanflow_runs_started_total",
            "Simulation runs started, by kind.",
            ("kind",),
        )
        self._completed = reg.counter(
            "urbanflow_runs_completed_total",
            "Simulation runs finished, by kind and outcome.",
            ("kind", "outcome"),
        )
        self._duration = reg.histogram(
            "urbanflow_run_duration_seconds",
            "Simulation run wall time, by kind.",
            ("kind",),
            JOB_BUCKETS,
        )
        self._latency = reg.histogram(
            "urbanflow_api_latency_seconds",
            "API request latency, by method and route template.",
            ("method", "route"),
            LATENCY_BUCKETS,
        )
        reg.gauge(
            "urbanflow_queue_depth",
            "Jobs queued or running.",
            lambda: [((), self._queue)],
        )

    # -- recording ------------------------------------------------------------------
    def run_started(self, kind: str) -> None:
        if self._pc is not None:
            self._started.labels(kind).inc()
        else:
            self._started.inc(kind)

    def run_finished(self, kind: str, outcome: str, seconds: float) -> None:
        if outcome not in _RUN_OUTCOMES:
            outcome = "failed"
        seconds = max(0.0, float(seconds))
        if self._pc is not None:
            self._completed.labels(kind, outcome).inc()
            self._duration.labels(kind).observe(seconds)
        else:
            self._completed.inc(kind, outcome)
            self._duration.observe(seconds, kind)

    def set_queue_depth(self, depth: int) -> None:
        self._queue = float(max(0, depth))
        if self._pc is not None:
            self._gauge.set(self._queue)

    def observe_api(self, method: str, route: str, seconds: float) -> None:
        seconds = max(0.0, float(seconds))
        if self._pc is not None:
            self._latency.labels(method, route).observe(seconds)
        else:
            self._latency.observe(seconds, method, route)

    @contextmanager
    def track_run(self, kind: str) -> Iterator[None]:
        """Count a run as started, then completed/failed with its duration."""
        self.run_started(kind)
        began = time.perf_counter()
        outcome = "completed"
        try:
            yield
        except BaseException:
            outcome = "failed"
            raise
        finally:
            self.run_finished(kind, outcome, time.perf_counter() - began)

    @contextmanager
    def track_request(self, method: str, route: str) -> Iterator[None]:
        began = time.perf_counter()
        try:
            yield
        finally:
            self.observe_api(method, route, time.perf_counter() - began)

    # -- output ---------------------------------------------------------------------
    def render(self, include_core: bool = True) -> str:
        """Prometheus text for these metrics (+ the always-on registry)."""
        if self._pc is not None:
            text = str(self._pc.generate_latest(self._registry).decode("utf-8"))
        else:
            text = str(self._registry.render())
        if include_core:
            text = text.rstrip("\n") + "\n" + REGISTRY.render()
        return text

    def snapshot(self) -> List[Sample]:
        """Parsed samples, for the SLO evaluator."""
        return parse_prometheus_text(self.render())


METRICS = PromMetrics()


def render() -> str:
    """Prometheus text of the shared :data:`METRICS` plus the core registry."""
    return METRICS.render()
