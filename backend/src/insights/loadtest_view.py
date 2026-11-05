"""``LoadTestSummary``: the newest k6 load-test result (``frontend/src/loadtest/types.ts``).

Source: ``loadtests/latest.json`` (format ``urbanflow-loadtest-summary`` v1), written by
``scripts/produce_loadtest_summary.py`` from a k6 ``--summary-export`` file::

    {"format": "urbanflow-loadtest-summary", "version": 1, "generatedAt": "2026-11-04T03:10:00Z",
     "tool": "k6", "toolVersion": "0.49.0", "target": "http://127.0.0.1:8000", "scenario": "load.js",
     "durationSeconds": 390.0, "vus": {"peak": 10, "max": 10},
     "requests": {"total": 4210, "ratePerSecond": 10.8, "failed": 3, "errorRate": 0.0007},
     "latencyMs": {"avg": 41.2, "min": 3.1, "med": 30.0, "p90": 80.0, "p95": 120.5, "p99": 300.0, "max": 910.0},
     "checks": {"passes": 8400, "fails": 2},
     "thresholds": [{"name": "http_req_failed", "metric": "http_req_failed",
                     "expression": "rate<0.005", "passed": true}],
     "endpoints": [{"name": "health", "requests": 2100, "p95Ms": 20.0, "errorRate": 0.0}]}

Nothing is computed. Required fields are checked and the document is passed through in the contract's shape;
a number k6 could not report is ``null`` (never 0). A file with a missing or mistyped required field makes
the whole result unavailable rather than being shown half-filled.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from .numbers import finite

LOADTEST_FORMAT = "urbanflow-loadtest-summary"
LATENCY_KEYS = ("avg", "min", "med", "p90", "p95", "p99", "max")


def _text(value: Any) -> Optional[str]:
    return value if isinstance(value, str) else None


def _count(value: Any) -> Optional[int]:
    """A non-negative whole number (not a bool), else None."""
    num = finite(value)
    if num is None or num < 0 or num != int(num):
        return None
    return int(num)


def _rate(value: Any) -> Optional[float]:
    num = finite(value)
    return num if num is not None and 0.0 <= num <= 1.0 else None


def _threshold(raw: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        return None
    name, metric, expression = (
        _text(raw.get("name")),
        _text(raw.get("metric")),
        _text(raw.get("expression")),
    )
    passed = raw.get("passed")
    if name is None or metric is None or expression is None:
        return None
    if not isinstance(passed, bool):
        return None
    return {"name": name, "metric": metric, "expression": expression, "passed": passed}


def _endpoint(raw: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        return None
    name, requests = _text(raw.get("name")), _count(raw.get("requests"))
    if name is None or requests is None:
        return None
    return {
        "name": name,
        "requests": requests,
        "p95Ms": finite(raw.get("p95Ms")),
        "errorRate": _rate(raw.get("errorRate")),
    }


def build_loadtest(doc: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    """The summary in the contract's shape, or None when the file is not a valid v1 summary."""
    if doc.get("format") != LOADTEST_FORMAT or doc.get("version") != 1:
        return None
    generated, tool = _text(doc.get("generatedAt")), _text(doc.get("tool"))
    target, scenario = _text(doc.get("target")), _text(doc.get("scenario"))
    duration = finite(doc.get("durationSeconds"))
    vus, requests = doc.get("vus"), doc.get("requests")
    latency, checks = doc.get("latencyMs"), doc.get("checks")
    raw_thresholds = doc.get("thresholds")
    if (
        generated is None
        or tool is None
        or target is None
        or scenario is None
        or duration is None
        or duration < 0
        or not isinstance(vus, dict)
        or not isinstance(requests, dict)
        or not isinstance(latency, dict)
        or not isinstance(checks, dict)
        or not isinstance(raw_thresholds, list)
    ):
        return None
    peak, vus_max = _count(vus.get("peak")), _count(vus.get("max"))
    total, failed = _count(requests.get("total")), _count(requests.get("failed"))
    passes, fails = _count(checks.get("passes")), _count(checks.get("fails"))
    if (
        peak is None
        or vus_max is None
        or total is None
        or failed is None
        or passes is None
        or fails is None
    ):
        return None
    thresholds: List[Dict[str, Any]] = []
    for raw in raw_thresholds:
        threshold = _threshold(raw)
        if threshold is None:
            return None
        thresholds.append(threshold)
    out: Dict[str, Any] = {
        "format": LOADTEST_FORMAT,
        "version": 1,
        "generatedAt": generated,
        "tool": tool,
        "target": target,
        "scenario": scenario,
        "durationSeconds": duration,
        "vus": {"peak": peak, "max": vus_max},
        "requests": {
            "total": total,
            "ratePerSecond": finite(requests.get("ratePerSecond")),
            "failed": failed,
            "errorRate": _rate(requests.get("errorRate")),
        },
        "latencyMs": {key: finite(latency.get(key)) for key in LATENCY_KEYS},
        "checks": {"passes": passes, "fails": fails},
        "thresholds": thresholds,
    }
    version = _text(doc.get("toolVersion"))
    if version is not None:
        out["toolVersion"] = version
    raw_endpoints = doc.get("endpoints")
    if raw_endpoints is not None:
        if not isinstance(raw_endpoints, list):
            return None
        endpoints = [_endpoint(e) for e in raw_endpoints]
        if any(e is None for e in endpoints):
            return None
        out["endpoints"] = endpoints
    return out
