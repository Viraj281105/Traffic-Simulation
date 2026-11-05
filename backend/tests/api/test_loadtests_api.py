"""``GET /api/v3/loadtests/latest`` (``src/insights/loadtest_view.py``): shape matches ``frontend/src/loadtest/types.ts``."""

import copy
import json
from pathlib import Path
from typing import Any, Dict

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from src.api.errors import http_exception_handler
from src.insights.locations import ResultsLocations
from src.insights.router import create_router

URL = "/api/v3/loadtests/latest"


def _summary() -> Dict[str, Any]:
    return {
        "format": "urbanflow-loadtest-summary",
        "version": 1,
        "generatedAt": "2026-11-04T03:10:00Z",
        "tool": "k6",
        "toolVersion": "0.49.0",
        "target": "http://127.0.0.1:8000",
        "scenario": "load.js",
        "durationSeconds": 390.0,
        "vus": {"peak": 10, "max": 10},
        "requests": {
            "total": 4210,
            "ratePerSecond": 10.8,
            "failed": 3,
            "errorRate": 0.0007,
        },
        "latencyMs": {
            "avg": 41.2,
            "min": 3.1,
            "med": 30.0,
            "p90": 80.0,
            "p95": 120.5,
            "p99": None,
            "max": 910.0,
        },
        "checks": {"passes": 8400, "fails": 2},
        "thresholds": [
            {
                "name": "http_req_failed",
                "metric": "http_req_failed",
                "expression": "rate<0.005",
                "passed": True,
            },
            {
                "name": "checks",
                "metric": "checks",
                "expression": "rate>0.99",
                "passed": False,
            },
        ],
        "endpoints": [
            {"name": "health", "requests": 2100, "p95Ms": 20.0, "errorRate": None}
        ],
    }


def _write(root: Path, doc: Any) -> None:
    path = root / "loadtests" / "latest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc), encoding="utf-8")


def _client(root: Path) -> TestClient:
    app = FastAPI()
    app.exception_handler(HTTPException)(http_exception_handler)
    app.include_router(
        create_router(user_dependency=lambda: "alice", locations=ResultsLocations(root))
    )
    return TestClient(app)


def test_latest_matches_the_contract(tmp_path: Path) -> None:
    _write(tmp_path, _summary())
    res = _client(tmp_path).get(URL)
    assert res.status_code == 200
    body = res.json()
    assert body == _summary()
    assert sorted(body) == sorted(_summary())
    assert body["latencyMs"]["p99"] is None
    assert body["thresholds"][1]["passed"] is False


def test_optional_fields_may_be_absent(tmp_path: Path) -> None:
    doc = _summary()
    del doc["toolVersion"], doc["endpoints"]
    _write(tmp_path, doc)
    body = _client(tmp_path).get(URL).json()
    assert "toolVersion" not in body and "endpoints" not in body


def test_404_until_written(tmp_path: Path) -> None:
    res = _client(tmp_path).get(URL)
    assert res.status_code == 404


def test_404_when_not_json(tmp_path: Path) -> None:
    path = tmp_path / "loadtests" / "latest.json"
    path.parent.mkdir(parents=True)
    path.write_text("{not json", encoding="utf-8")
    assert _client(tmp_path).get(URL).status_code == 404


def _break(doc: Dict[str, Any], what: str) -> None:
    if what == "format":
        doc["format"] = "other"
    elif what == "version":
        doc["version"] = 2
    elif what == "no-target":
        del doc["target"]
    elif what == "vus":
        doc["vus"]["peak"] = "ten"
    elif what == "negative-count":
        doc["requests"]["failed"] = -1
    elif what == "fraction":
        doc["requests"]["errorRate"] = 1.5
        doc["requests"]["failed"] = "x"
    elif what == "threshold-passed":
        doc["thresholds"][0]["passed"] = "yes"
    elif what == "thresholds-not-list":
        doc["thresholds"] = {}
    elif what == "endpoint":
        del doc["endpoints"][0]["requests"]
    elif what == "latency":
        doc["latencyMs"] = []
    elif what == "duration":
        doc["durationSeconds"] = None
    else:
        raise AssertionError(what)


@pytest.mark.parametrize(
    "what",
    [
        "format",
        "version",
        "no-target",
        "vus",
        "negative-count",
        "fraction",
        "threshold-passed",
        "thresholds-not-list",
        "endpoint",
        "latency",
        "duration",
    ],
)
def test_malformed_summary_is_404(tmp_path: Path, what: str) -> None:
    doc = copy.deepcopy(_summary())
    _break(doc, what)
    _write(tmp_path, doc)
    assert _client(tmp_path).get(URL).status_code == 404


def test_non_object_file_is_404(tmp_path: Path) -> None:
    _write(tmp_path, [1, 2])
    assert _client(tmp_path).get(URL).status_code == 404


def test_out_of_range_error_rate_is_null_not_zero(tmp_path: Path) -> None:
    doc = _summary()
    doc["requests"]["errorRate"] = 2.0
    _write(tmp_path, doc)
    assert _client(tmp_path).get(URL).json()["requests"]["errorRate"] is None
