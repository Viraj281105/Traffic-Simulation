"""A minimal in-process metrics registry, rendered as Prometheus text.

Counters, histograms and callback gauges with **fixed label names** whose
values come from small, closed sets (an HTTP method, a route *template*, a
status class, a job kind, an outcome). Nothing records a raw URL, an id, a
user or an exception message, so the number of series stays bounded however
long the process runs (``MAX_SERIES`` per metric is a backstop: a series
beyond it is folded into ``other``).

Thread-safe (one lock per metric; the worker threads of the job registry and
the request handlers update concurrently). Recording is a dictionary update;
rendering walks the series once. Values reset when the process restarts, as
Prometheus counters are expected to.
"""

from __future__ import annotations

import math
import threading
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

LabelValues = Tuple[str, ...]

# A label set beyond this many series per metric is recorded as "other".
MAX_SERIES = 500

# Request latency (s): fast API reads to slow synchronous compute routes.
LATENCY_BUCKETS = (
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
    30.0,
    60.0,
)
# Background job duration (s): seconds-long studies to hour-long searches.
JOB_BUCKETS = (1.0, 5.0, 15.0, 30.0, 60.0, 120.0, 300.0, 600.0, 1800.0, 3600.0)


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _labels(names: Sequence[str], values: LabelValues, extra: str = "") -> str:
    parts = [f'{n}="{_escape(v)}"' for n, v in zip(names, values)]
    if extra:
        parts.append(extra)
    return "{" + ",".join(parts) + "}" if parts else ""


def _number(value: float) -> str:
    if math.isinf(value):
        return "+Inf" if value > 0 else "-Inf"
    return repr(float(value)) if not float(value).is_integer() else str(int(value))


class _Metric:
    kind = ""

    def __init__(self, name: str, help_text: str, labels: Sequence[str]) -> None:
        self.name = name
        self.help = help_text
        self.label_names = tuple(labels)
        self._lock = threading.Lock()

    def _key(
        self, values: Sequence[str], existing: Dict[LabelValues, object]
    ) -> LabelValues:
        if len(values) != len(self.label_names):
            raise ValueError(f"{self.name} takes labels {self.label_names}")
        key = tuple(str(v) for v in values)
        if key not in existing and len(existing) >= MAX_SERIES:
            key = tuple("other" for _ in key)
        return key

    def render(self) -> List[str]:
        raise NotImplementedError


class Counter(_Metric):
    kind = "counter"

    def __init__(self, name: str, help_text: str, labels: Sequence[str] = ()) -> None:
        super().__init__(name, help_text, labels)
        self._values: Dict[LabelValues, float] = {}

    def inc(self, *labels: str, amount: float = 1.0) -> None:
        with self._lock:
            key = self._key(labels, self._values)  # type: ignore[arg-type]
            self._values[key] = self._values.get(key, 0.0) + amount

    def value(self, *labels: str) -> float:
        with self._lock:
            return self._values.get(tuple(labels), 0.0)

    def render(self) -> List[str]:
        with self._lock:
            items = sorted(self._values.items())
        return [
            f"{self.name}{_labels(self.label_names, k)} {_number(v)}" for k, v in items
        ]


class Histogram(_Metric):
    kind = "histogram"

    def __init__(
        self,
        name: str,
        help_text: str,
        labels: Sequence[str] = (),
        buckets: Sequence[float] = LATENCY_BUCKETS,
    ) -> None:
        super().__init__(name, help_text, labels)
        self.buckets = tuple(sorted(buckets))
        # key -> (per-bucket counts, sum, count)
        self._values: Dict[LabelValues, Tuple[List[int], float, int]] = {}

    def observe(self, value: float, *labels: str) -> None:
        with self._lock:
            key = self._key(labels, self._values)  # type: ignore[arg-type]
            counts, total, n = self._values.get(key, ([0] * len(self.buckets), 0.0, 0))
            for i, bound in enumerate(self.buckets):
                if value <= bound:
                    counts[i] += 1
            self._values[key] = (counts, total + value, n + 1)

    def count(self, *labels: str) -> int:
        with self._lock:
            entry = self._values.get(tuple(labels))
            return entry[2] if entry else 0

    def render(self) -> List[str]:
        with self._lock:
            items = sorted(
                (k, (list(c), s, n)) for k, (c, s, n) in self._values.items()
            )
        lines: List[str] = []
        for key, (counts, total, n) in items:
            for bound, c in zip(self.buckets, counts):
                le = f'le="{_number(bound)}"'
                lines.append(
                    f"{self.name}_bucket{_labels(self.label_names, key, le)} {c}"
                )
            inf = 'le="+Inf"'
            lines.append(f"{self.name}_bucket{_labels(self.label_names, key, inf)} {n}")
            lines.append(
                f"{self.name}_sum{_labels(self.label_names, key)} {_number(total)}"
            )
            lines.append(f"{self.name}_count{_labels(self.label_names, key)} {n}")
        return lines


class Gauge(_Metric):
    """A value read at scrape time from a cheap callback."""

    kind = "gauge"

    def __init__(
        self,
        name: str,
        help_text: str,
        read: Callable[[], Iterable[Tuple[LabelValues, float]]],
        labels: Sequence[str] = (),
    ) -> None:
        super().__init__(name, help_text, labels)
        self._read = read

    def render(self) -> List[str]:
        try:
            values = list(self._read())
        except Exception:  # noqa: BLE001 - one failing reader must not break the scrape
            return []
        return [
            f"{self.name}{_labels(self.label_names, k)} {_number(v)}" for k, v in values
        ]


class Registry:
    def __init__(self) -> None:
        self._metrics: Dict[str, _Metric] = {}
        self._lock = threading.Lock()

    def register(self, metric: _Metric) -> _Metric:
        with self._lock:
            existing = self._metrics.get(metric.name)
            if existing is not None:
                return existing
            self._metrics[metric.name] = metric
            return metric

    def counter(self, name: str, help_text: str, labels: Sequence[str] = ()) -> Counter:
        return self.register(Counter(name, help_text, labels))  # type: ignore[return-value]

    def histogram(
        self,
        name: str,
        help_text: str,
        labels: Sequence[str] = (),
        buckets: Sequence[float] = LATENCY_BUCKETS,
    ) -> Histogram:
        return self.register(Histogram(name, help_text, labels, buckets))  # type: ignore[return-value]

    def gauge(
        self,
        name: str,
        help_text: str,
        read: Callable[[], Iterable[Tuple[LabelValues, float]]],
        labels: Sequence[str] = (),
    ) -> Gauge:
        return self.register(Gauge(name, help_text, read, labels))  # type: ignore[return-value]

    def get(self, name: str) -> Optional[_Metric]:
        with self._lock:
            return self._metrics.get(name)

    def render(self) -> str:
        with self._lock:
            metrics = sorted(self._metrics.values(), key=lambda m: m.name)
        out: List[str] = []
        for m in metrics:
            out.append(f"# HELP {m.name} {m.help}")
            out.append(f"# TYPE {m.name} {m.kind}")
            out.extend(m.render())
        return "\n".join(out) + "\n"


REGISTRY = Registry()

# ---- the metrics the application records ------------------------------------------------

HTTP_REQUESTS = REGISTRY.counter(
    "urbanflow_http_requests_total",
    "HTTP requests handled, by method, route template and status class.",
    ("method", "route", "status"),
)
HTTP_LATENCY = REGISTRY.histogram(
    "urbanflow_http_request_duration_seconds",
    "HTTP request latency, by method and route template.",
    ("method", "route"),
)
HTTP_UNHANDLED = REGISTRY.counter(
    "urbanflow_http_unhandled_exceptions_total",
    "Requests that raised an unhandled exception, by route template.",
    ("route",),
)
JOBS = REGISTRY.counter(
    "urbanflow_jobs_total",
    "Background jobs finished, by kind and outcome (completed, cancelled, failed).",
    ("kind", "outcome"),
)
JOB_DURATION = REGISTRY.histogram(
    "urbanflow_job_duration_seconds",
    "Background job wall time from start to finish, by kind.",
    ("kind",),
    JOB_BUCKETS,
)
JOBS_REJECTED = REGISTRY.counter(
    "urbanflow_jobs_rejected_total",
    "Jobs refused because too many were already active, by kind.",
    ("kind",),
)
AUTH_FAILURES = REGISTRY.counter(
    "urbanflow_auth_failures_total",
    "Failed authentications, by reason (a fixed vocabulary, see api/auth.py).",
    ("reason",),
)
LIMIT_EVENTS = REGISTRY.counter(
    "urbanflow_limit_events_total",
    "Requests refused by a size, rate or quota limit (HTTP 413 or 429), by status and route template.",
    ("status", "route"),
)
SIMULATIONS_FINISHED = REGISTRY.counter(
    "urbanflow_simulations_finished_total",
    "Registered (/api/v1/simulations) runs that finished, by outcome (completed, error).",
    ("outcome",),
)
