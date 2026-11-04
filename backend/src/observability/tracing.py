"""OpenTelemetry tracing helpers (package 1D, F15).

``opentelemetry`` is an optional dependency, imported lazily. Without it (or
before :func:`setup_tracing` runs) every helper here is a cheap no-op, so the
application and its tests behave identically with or without tracing.

Usage (no middleware needed)::

    from src.observability.tracing import request_span, run_span, setup_tracing

    setup_tracing("urbanflow-backend")          # once, at startup (optional)

    with run_span("simulation", run_id="abc"):  # around a simulation run
        engine.run()

    with request_span("POST", "/api/v2/network-metrics/simulate") as span:
        ...                                      # inside a handler / middleware
        span.set_attribute("http.status_code", 200)

Environment:

* ``OTEL_EXPORTER_OTLP_ENDPOINT`` - OTLP/HTTP collector, e.g.
  ``http://localhost:4318``. Unset: spans are created but not exported
  (console exporter only when ``OTEL_TRACES_CONSOLE=1``).
* ``OTEL_SERVICE_NAME`` - overrides the service name.

Span attributes use only low-cardinality values (method, route template,
run kind); never put request bodies, ids of users or tokens in a span.
"""

from __future__ import annotations

import os
import time
from contextlib import contextmanager
from typing import Any, Callable, Dict, Iterator, Optional, TypeVar

F = TypeVar("F", bound=Callable[..., Any])

_TRACER_NAME = "urbanflow"
_state: Dict[str, Any] = {"configured": False}


class _NoopSpan:
    """Stands in for a span when OpenTelemetry is unavailable."""

    def set_attribute(self, key: str, value: Any) -> None:
        return None

    def record_exception(self, exc: BaseException) -> None:
        return None

    def set_status(self, *args: Any, **kwargs: Any) -> None:
        return None


_NOOP = _NoopSpan()


def _import_trace() -> Optional[Any]:
    try:
        from opentelemetry import trace  # type: ignore[import-not-found,unused-ignore]
    except Exception:  # noqa: BLE001 - optional dependency; any import failure disables
        return None
    return trace


def otel_available() -> bool:
    """True when the ``opentelemetry`` API package can be imported."""
    return _import_trace() is not None


def tracing_enabled() -> bool:
    """True once :func:`setup_tracing` installed a real tracer provider."""
    return bool(_state["configured"])


def setup_tracing(
    service_name: str = "urbanflow-backend", endpoint: Optional[str] = None
) -> bool:
    """Install a tracer provider. Returns False (and does nothing) if the
    OpenTelemetry SDK is not installed. Safe to call more than once."""
    if _state["configured"]:
        return True
    try:
        from opentelemetry import trace  # type: ignore[import-not-found,unused-ignore]
        from opentelemetry.sdk.resources import (  # type: ignore[import-not-found,unused-ignore]
            Resource,
        )
        from opentelemetry.sdk.trace import (  # type: ignore[import-not-found,unused-ignore]
            TracerProvider,
        )
        from opentelemetry.sdk.trace.export import (  # type: ignore[import-not-found,unused-ignore]
            BatchSpanProcessor,
            ConsoleSpanExporter,
        )
    except Exception:  # noqa: BLE001
        return False

    name = os.getenv("OTEL_SERVICE_NAME", service_name)
    provider = TracerProvider(resource=Resource.create({"service.name": name}))
    target = endpoint or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    if target:
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (  # type: ignore[import-not-found,unused-ignore]
                OTLPSpanExporter,
            )

            url = target.rstrip("/")
            if not url.endswith("/v1/traces"):
                url += "/v1/traces"
            provider.add_span_processor(
                BatchSpanProcessor(OTLPSpanExporter(endpoint=url))
            )
        except Exception:  # noqa: BLE001 - exporter package missing: keep running
            pass
    if os.getenv("OTEL_TRACES_CONSOLE") == "1":
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)
    _state["configured"] = True
    return True


@contextmanager
def span(name: str, **attributes: Any) -> Iterator[Any]:
    """A span named ``name`` with the given attributes; a no-op without OTel.

    Exceptions raised in the block are recorded on the span and re-raised."""
    trace = _import_trace()
    if trace is None:
        yield _NOOP
        return
    tracer = trace.get_tracer(_TRACER_NAME)
    with tracer.start_as_current_span(name) as sp:
        for key, value in attributes.items():
            if value is not None:
                sp.set_attribute(key, value)
        try:
            yield sp
        except BaseException as exc:
            sp.record_exception(exc)
            raise


@contextmanager
def request_span(method: str, route: str) -> Iterator[Any]:
    """Span for one API request. ``route`` is the route *template*."""
    with span(
        f"{method} {route}", **{"http.request.method": method, "http.route": route}
    ) as sp:
        yield sp


@contextmanager
def run_span(kind: str, **attributes: Any) -> Iterator[Any]:
    """Span around one simulation run (``kind``: e.g. ``simulation``, ``network``)."""
    with span(f"run {kind}", **{"urbanflow.run.kind": kind, **attributes}) as sp:
        started = time.perf_counter()
        try:
            yield sp
        finally:
            sp.set_attribute("urbanflow.run.seconds", time.perf_counter() - started)


def traced(name: Optional[str] = None) -> Callable[[F], F]:
    """Decorator form of :func:`span` for a synchronous function."""

    def wrap(fn: F) -> F:
        label = name or f"{fn.__module__}.{fn.__qualname__}"

        def inner(*args: Any, **kwargs: Any) -> Any:
            with span(label):
                return fn(*args, **kwargs)

        inner.__name__ = fn.__name__
        inner.__doc__ = fn.__doc__
        return inner  # type: ignore[return-value]

    return wrap
