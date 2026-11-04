"""Tracing helpers, run/API Prometheus metrics, the SLO evaluator (package 1D)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.observability import prom_router, slo, tracing
from src.observability.prom_metrics import PromMetrics

# ---- tracing: no-ops without OpenTelemetry ----------------------------------------------------


def test_spans_are_noops_and_propagate_exceptions() -> None:
    with tracing.request_span("GET", "/health") as sp:
        sp.set_attribute("http.status_code", 200)
    with tracing.run_span("simulation", run_id="r1") as sp:
        sp.set_attribute("x", 1)
    with pytest.raises(ValueError):
        with tracing.span("boom"):
            raise ValueError("x")


def test_traced_decorator_keeps_behaviour() -> None:
    @tracing.traced("add")
    def add(a: int, b: int) -> int:
        """doc"""
        return a + b

    assert add(2, 3) == 5
    assert add.__name__ == "add" and add.__doc__ == "doc"


def test_setup_tracing_without_sdk_returns_bool() -> None:
    # False when the SDK is missing, True when installed; never raises.
    assert isinstance(tracing.setup_tracing("urbanflow-test"), bool)


# ---- run / API metrics ------------------------------------------------------------------------


def _builtin() -> PromMetrics:
    return PromMetrics(use_prometheus_client=False)


def test_run_metrics_render_expected_series() -> None:
    m = _builtin()
    with m.track_run("network"):
        pass
    with pytest.raises(RuntimeError):
        with m.track_run("network"):
            raise RuntimeError("fail")
    m.set_queue_depth(3)
    m.observe_api("GET", "/health", 0.02)
    text = m.render(include_core=False)
    assert 'urbanflow_runs_started_total{kind="network"} 2' in text
    assert (
        'urbanflow_runs_completed_total{kind="network",outcome="completed"} 1' in text
    )
    assert 'urbanflow_runs_completed_total{kind="network",outcome="failed"} 1' in text
    assert 'urbanflow_run_duration_seconds_count{kind="network"} 2' in text
    assert "urbanflow_queue_depth 3" in text
    assert 'urbanflow_api_latency_seconds_count{method="GET",route="/health"} 1' in text


def test_unknown_outcome_is_folded_and_negative_depth_clamped() -> None:
    m = _builtin()
    m.run_finished("x", "weird-outcome", -5.0)
    m.set_queue_depth(-2)
    text = m.render(include_core=False)
    assert 'outcome="failed"' in text and "urbanflow_queue_depth 0" in text


def test_render_includes_core_registry() -> None:
    assert "urbanflow_http_requests_total" in _builtin().render()


def test_prometheus_client_backend_if_installed() -> None:
    pytest.importorskip("prometheus_client")
    m = PromMetrics(use_prometheus_client=True)
    with m.track_run("sim"):
        pass
    assert 'urbanflow_runs_started_total{kind="sim"} 1.0' in m.render(False)


def test_forcing_missing_prometheus_client_raises() -> None:
    try:
        import prometheus_client  # noqa: F401
    except ImportError:
        with pytest.raises(RuntimeError):
            PromMetrics(use_prometheus_client=True)
    else:
        pytest.skip("prometheus_client is installed")


# ---- router -----------------------------------------------------------------------------------


def _client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("METRICS_TOKEN", "tok")
    app = FastAPI()
    app.include_router(prom_router.router)
    return TestClient(app)


def test_prom_route_requires_token(monkeypatch: pytest.MonkeyPatch) -> None:
    c = _client(monkeypatch)
    assert c.get("/metrics/prom").status_code == 403
    ok = c.get("/metrics/prom", headers={"Authorization": "Bearer tok"})
    assert ok.status_code == 200
    assert ok.headers["content-type"].startswith("text/plain")
    assert "urbanflow_queue_depth" in ok.text


# ---- SLO parsing and evaluation ---------------------------------------------------------------

HIST = """\
# TYPE lat histogram
lat_bucket{le="0.1",route="/a"} 50
lat_bucket{le="1.0",route="/a"} 90
lat_bucket{le="+Inf",route="/a"} 100
lat_sum{route="/a"} 30
lat_count{route="/a"} 100
lat_bucket{le="0.1",route="/b"} 0
lat_bucket{le="1.0",route="/b"} 0
lat_bucket{le="+Inf",route="/b"} 10
"""


def test_parse_handles_labels_comments_and_inf() -> None:
    samples = slo.parse_prometheus_text('# c\nm{a="x\\"y",b="2"} 1.5\nplain 3\n')
    assert samples[0].labels == {"a": 'x"y', "b": "2"} and samples[0].value == 1.5
    assert samples[1].name == "plain" and samples[1].labels == {}


def test_histogram_quantile_interpolates() -> None:
    s = slo.parse_prometheus_text(HIST)
    # route /a only: rank 95 of 100 falls in the (1.0, +Inf] bucket -> last finite edge.
    assert slo.histogram_quantile(s, "lat", 0.95, {"route": "/a"}) == 1.0
    # p70: rank 70 within (0.1, 1.0]: 0.1 + 0.9 * (70-50)/(90-50)
    assert slo.histogram_quantile(s, "lat", 0.70, {"route": "/a"}) == pytest.approx(
        0.55
    )
    assert slo.histogram_quantile(s, "missing", 0.5) is None


def _latency_slo(limit: float, **extra: object) -> dict:  # type: ignore[type-arg]
    return {
        "id": "l",
        "kind": "latency_quantile",
        "histogram": "lat",
        "quantile": 0.7,
        "objective_seconds": limit,
        **extra,
    }


def test_latency_slo_ok_violated_no_data() -> None:
    s = slo.parse_prometheus_text(HIST)
    assert (
        slo.evaluate_slo(_latency_slo(1.0, match={"route": "/a"}), s).status == slo.OK
    )
    bad = slo.evaluate_slo(_latency_slo(0.3, match={"route": "/a"}), s)
    assert bad.status == slo.VIOLATED and bad.violated
    assert slo.evaluate_slo(_latency_slo(1.0), []).status == slo.NO_DATA


def _ratio_slo(objective: float) -> dict:  # type: ignore[type-arg]
    return {
        "id": "r",
        "kind": "ratio",
        "good": {"metric": "req", "match": {"status": ["2xx", "4xx"]}},
        "total": {"metric": "req"},
        "objective": objective,
    }


def test_ratio_slo() -> None:
    s = slo.parse_prometheus_text(
        'req{status="2xx"} 90\nreq{status="4xx"} 9\nreq{status="5xx"} 1\n'
    )
    assert slo.evaluate_slo(_ratio_slo(0.99), s).status == slo.OK
    assert slo.evaluate_slo(_ratio_slo(0.999), s).status == slo.VIOLATED
    assert slo.evaluate_slo(_ratio_slo(0.5), []).status == slo.NO_DATA


def test_shipped_slo_file_is_valid_and_idle_service_is_not_violated() -> None:
    slos = slo.load_slos()
    assert {s["id"] for s in slos} >= {"api_latency_p95", "api_availability"}
    results = slo.evaluate_all([], slos)
    assert all(r.status == slo.NO_DATA for r in results)


def test_live_metrics_feed_the_evaluator() -> None:
    m = _builtin()
    for _ in range(20):
        with m.track_run("sim"):
            pass
    with pytest.raises(RuntimeError):
        with m.track_run("sim"):
            raise RuntimeError
    results = {r.id: r for r in slo.evaluate_all(m.snapshot())}
    assert results["run_success_rate"].status == slo.VIOLATED  # 20/21 < 0.99
    assert results["run_duration_p95"].status == slo.OK


def test_load_slos_rejects_bad_files(tmp_path: Path) -> None:
    def write(doc: object) -> Path:
        p = tmp_path / "s.json"
        p.write_text(json.dumps(doc), encoding="utf-8")
        return p

    with pytest.raises(ValueError):
        slo.load_slos(write({"slos": []}))
    with pytest.raises(ValueError):
        slo.load_slos(write({"slos": [{"id": "a", "kind": "nope"}]}))
    with pytest.raises(ValueError):
        slo.load_slos(write({"slos": [{"id": "a", "kind": "ratio"}]}))
    dup: List[dict] = [_ratio_slo(0.9), _ratio_slo(0.9)]  # type: ignore[type-arg]
    with pytest.raises(ValueError):
        slo.load_slos(write({"slos": dup}))


def test_cli_exit_codes(tmp_path: Path) -> None:
    ok = tmp_path / "ok.txt"
    ok.write_text("", encoding="utf-8")
    assert slo.main([str(ok)]) == 0
    bad = tmp_path / "bad.txt"
    bad.write_text('urbanflow_runs_completed_total{kind="s",outcome="failed"} 5\n')
    assert slo.main([str(bad)]) == 1
    assert slo.main([]) == 2
