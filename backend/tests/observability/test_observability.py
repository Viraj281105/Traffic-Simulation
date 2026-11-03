"""Structured logging, request metrics and /metrics (checkpoint 12)."""

from __future__ import annotations

import io
import json
import logging
import threading
import time
from typing import Any, Dict, Iterator

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.observability import metrics as m
from src.observability.logging_setup import (
    JsonFormatter,
    PlainFormatter,
    RedactingFilter,
    redact,
    request_id_var,
)
from src.observability.router import _authorised
from src.study.jobs import JobRegistry

JWT = "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ1c2VyLTEyMyJ9.c2lnbmF0dXJlLWJ5dGVz"


@pytest.fixture
def capture() -> Iterator[io.StringIO]:
    """Every record logged through the root logger, formatted as JSON."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RedactingFilter())
    root = logging.getLogger()
    old = root.level
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)
    yield stream
    root.removeHandler(handler)
    root.setLevel(old)


def _records(stream: io.StringIO) -> list[Dict[str, Any]]:
    return [json.loads(line) for line in stream.getvalue().splitlines() if line]


# ---- registry -----------------------------------------------------------------------------------


def test_counters_and_histograms_render_in_prometheus_text() -> None:
    reg = m.Registry()
    c = reg.counter("t_requests_total", "Requests.", ("route",))
    h = reg.histogram("t_latency_seconds", "Latency.", ("route",), (0.1, 1.0))
    c.inc("/a/{id}")
    c.inc("/a/{id}", amount=2)
    h.observe(0.05, "/a")
    h.observe(0.5, "/a")
    h.observe(5.0, "/a")
    text = reg.render()
    assert "# TYPE t_requests_total counter" in text
    assert 't_requests_total{route="/a/{id}"} 3' in text
    assert 't_latency_seconds_bucket{route="/a",le="0.1"} 1' in text
    assert 't_latency_seconds_bucket{route="/a",le="1"} 2' in text
    assert 't_latency_seconds_bucket{route="/a",le="+Inf"} 3' in text
    assert 't_latency_seconds_count{route="/a"} 3' in text
    assert text.endswith("\n")


def test_label_values_are_escaped() -> None:
    reg = m.Registry()
    reg.counter("t_total", "x", ("v",)).inc('a"b\\c\nd')
    assert 't_total{v="a\\"b\\\\c\\nd"} 1' in reg.render()


def test_series_beyond_the_cap_are_folded_into_other(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(m, "MAX_SERIES", 5)
    c = m.Counter("t_capped_total", "x", ("id",))
    for i in range(50):
        c.inc(str(i))
    text = "\n".join(c.render())
    assert len(text.splitlines()) == 6
    assert c.value("other") == 45


def test_concurrent_updates_are_not_lost() -> None:
    c = m.Counter("t_conc_total", "x", ("k",))
    h = m.Histogram("t_conc_seconds", "x", ("k",), (1.0,))

    def work() -> None:
        for _ in range(5_000):
            c.inc("a")
            h.observe(0.5, "a")

    threads = [threading.Thread(target=work) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert c.value("a") == 40_000
    assert h.count("a") == 40_000


def test_a_failing_gauge_does_not_break_the_scrape() -> None:
    reg = m.Registry()

    def broken() -> Any:
        raise RuntimeError("boom")

    reg.gauge("t_broken", "x", broken)
    reg.counter("t_ok_total", "x").inc()
    assert "t_ok_total 1" in reg.render()


# ---- middleware and /metrics ------------------------------------------------------------------


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("METRICS_TOKEN", "scrape-secret")
    return TestClient(app)


def _scrape(client: TestClient) -> str:
    res = client.get("/metrics", headers={"Authorization": "Bearer scrape-secret"})
    assert res.status_code == 200, res.text
    assert res.headers["content-type"].startswith("text/plain")
    return res.text


def test_requests_are_counted_by_route_template_not_raw_path(
    client: TestClient,
) -> None:
    run_id = "run_ABCDEF123456"
    client.get(f"/api/v1/study/history/runs/{run_id}")
    client.get("/no/such/path/xyz-987")
    text = _scrape(client)
    assert 'route="/api/v1/study/history/runs/{run_id}"' in text
    assert 'route="unmatched"' in text
    assert run_id not in text
    assert "xyz-987" not in text


def test_request_id_is_returned_and_a_safe_caller_id_is_kept(
    client: TestClient,
) -> None:
    generated = client.get("/health").headers["x-request-id"]
    assert len(generated) == 32
    assert (
        client.get("/health", headers={"X-Request-ID": "trace-42.a"}).headers[
            "x-request-id"
        ]
        == "trace-42.a"
    )
    unsafe = client.get("/health", headers={"X-Request-ID": "x" * 65 + "\n"})
    assert unsafe.headers["x-request-id"] != "x" * 65


def test_request_log_line_carries_the_request_id(
    client: TestClient, capture: io.StringIO
) -> None:
    res = client.get("/api/version", headers={"X-Request-ID": "req-7"})
    lines = [r for r in _records(capture) if r.get("logger") == "urbanflow.request"]
    assert lines, capture.getvalue()
    last = lines[-1]
    assert last["request_id"] == "req-7"
    assert last["route"] == "/api/version" and last["status"] == res.status_code
    assert last["duration_ms"] >= 0


def test_metrics_need_the_token_when_one_is_configured(client: TestClient) -> None:
    assert client.get("/metrics").status_code == 403
    assert (
        client.get("/metrics", headers={"Authorization": "Bearer wrong"}).status_code
        == 403
    )
    assert "urbanflow_http_requests_total" in _scrape(client)


def test_without_a_token_only_loopback_clients_are_answered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("METRICS_TOKEN", raising=False)

    class Req:
        headers: Dict[str, str] = {}

        def __init__(self, host: str) -> None:
            self.client = type("C", (), {"host": host})()

    assert _authorised(Req("127.0.0.1"))  # type: ignore[arg-type]
    assert _authorised(Req("::1"))  # type: ignore[arg-type]
    assert not _authorised(Req("172.18.0.5"))  # type: ignore[arg-type]
    assert TestClient(app).get("/metrics").status_code == 403


def test_limit_refusals_are_counted_by_route(client: TestClient) -> None:
    # The body-size cap answers before routing; the route is still named.
    route = "/api/v2/networks/validate"
    before = m.LIMIT_EVENTS.value("413", route)
    res = client.post(
        route,
        content=b"{" + b" " * (1024 * 1024 + 10) + b"}",
        headers={"Content-Type": "application/json"},
    )
    assert res.status_code == 413
    assert m.LIMIT_EVENTS.value("413", route) == before + 1


# ---- redaction ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "secret, shown",
    [
        ("Authorization: Bearer abc.def-ghi", "Bearer [REDACTED]"),
        ("token uf_pat_9fK2_xYz-77 used", "uf_pat_[REDACTED]"),
        (f"bad token {JWT}", "[REDACTED_JWT]"),
    ],
)
def test_tokens_are_redacted_from_messages(secret: str, shown: str) -> None:
    out = redact(secret)
    assert shown in out
    assert "abc.def-ghi" not in out and "9fK2" not in out and "c2lnbmF0" not in out


def test_redaction_covers_arguments_extras_and_tracebacks(capture: io.StringIO) -> None:
    log = logging.getLogger("t.redact")
    log.warning("presented %s", f"Bearer {JWT}")
    try:
        raise ValueError(f"cannot parse uf_pat_SECRETSECRET {JWT}")
    except ValueError:
        log.exception("failed")
    text = capture.getvalue()
    assert JWT not in text and "SECRETSECRET" not in text
    assert "[REDACTED" in text


def test_plain_and_json_formats(capture: io.StringIO) -> None:
    token = request_id_var.set("rid-1")
    try:
        record = logging.LogRecord(
            "x", logging.INFO, __file__, 1, "hello %s", ("w",), None
        )
        record.job_kind = "stress-suite"
        RedactingFilter().filter(record)
        body = json.loads(JsonFormatter().format(record))
        assert body["message"] == "hello w"
        assert body["request_id"] == "rid-1"
        assert body["job_kind"] == "stress-suite"
        assert body["level"] == "INFO" and body["ts"].endswith("Z")
        assert PlainFormatter().format(record).endswith("[request_id=rid-1]")
    finally:
        request_id_var.reset(token)


# ---- jobs and auth ------------------------------------------------------------------------------


def _wait(job: Any) -> None:
    for _ in range(200):
        if job.finished_at is not None:
            return
        time.sleep(0.01)
    raise AssertionError("job did not finish")


def test_job_outcomes_are_counted_including_cancellation(capture: io.StringIO) -> None:
    registry = JobRegistry()
    before = {
        o: m.JOBS.value("t-kind", o) for o in ("completed", "failed", "cancelled")
    }
    durations = m.JOB_DURATION.count("t-kind")

    def ok(progress: Any) -> Dict[str, Any]:
        return {"ok": True}

    def boom(progress: Any) -> Dict[str, Any]:
        raise RuntimeError("worker exploded")

    def cancelled(progress: Any) -> Dict[str, Any]:
        progress.cancel()
        return {"status": "cancelled"}

    for work in (ok, boom, cancelled):
        _wait(registry.submit("t-kind", work))
    for outcome in ("completed", "failed", "cancelled"):
        assert m.JOBS.value("t-kind", outcome) == before[outcome] + 1
    assert m.JOB_DURATION.count("t-kind") == durations + 3
    events = {r.get("event") for r in _records(capture)}
    assert {"job_started", "job_completed", "job_failed", "job_cancelled"} <= events
    failed = next(r for r in _records(capture) if r.get("event") == "job_failed")
    assert "exception" in failed and "worker exploded" in failed["exception"]


def test_active_jobs_gauge_counts_running_jobs() -> None:
    registry = JobRegistry()
    release = threading.Event()

    def held(progress: Any) -> Dict[str, Any]:
        release.wait(5)
        return {}

    job = registry.submit("t-held", held)
    try:
        for _ in range(100):
            if 'kind="t-held"' in m.REGISTRY.render():
                break
            time.sleep(0.01)
        assert 'urbanflow_jobs_active{kind="t-held"} 1' in m.REGISTRY.render()
    finally:
        release.set()
        _wait(job)


def test_auth_failures_are_counted_and_logged_without_the_token(
    client: TestClient, capture: io.StringIO
) -> None:
    from src.api.auth import reset_auth_failures

    reset_auth_failures()
    before = m.AUTH_FAILURES.value("unknown_token")
    res = client.get(
        "/api/v3/capabilities",
        headers={"Authorization": "Bearer uf_pat_NOTAREALTOKEN123"},
    )
    reset_auth_failures()
    assert res.status_code == 401
    assert m.AUTH_FAILURES.value("unknown_token") == before + 1
    logged = [r for r in _records(capture) if r.get("event") == "auth_failed"]
    assert logged and logged[-1]["reason"] == "unknown_token"
    assert "NOTAREALTOKEN123" not in capture.getvalue()


def test_startup_and_shutdown_are_logged(capture: io.StringIO) -> None:
    with TestClient(app):
        pass
    events = [r.get("event") for r in _records(capture)]
    assert "startup" in events and "shutdown" in events


def test_uvicorn_access_lines_still_format_and_are_redacted() -> None:
    """uvicorn's AccessFormatter unpacks record.args itself; the filter must
    keep their shape (checkpoint 12: collapsing them broke every access line)."""
    from uvicorn.logging import AccessFormatter

    path = f"/ws/simulation/comparison?token={JWT}"
    record = logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        __file__,
        1,
        '%s - "%s %s HTTP/%s" %d',
        ("127.0.0.1:5000", "GET", path, "1.1", 200),
        None,
    )
    assert RedactingFilter().filter(record)
    assert isinstance(record.args, tuple) and len(record.args) == 5
    line = AccessFormatter(
        fmt="%(client_addr)s %(request_line)s %(status_code)s"
    ).format(record)
    assert "GET /ws/simulation/comparison?token=[REDACTED_JWT]" in line
    assert JWT not in line


def test_a_token_split_across_template_and_argument_is_still_redacted() -> None:
    record = logging.LogRecord(
        "x",
        logging.INFO,
        __file__,
        1,
        "header was Bearer %s",
        ("opaque-key-123",),
        None,
    )
    RedactingFilter().filter(record)
    assert "opaque-key-123" not in record.getMessage()
