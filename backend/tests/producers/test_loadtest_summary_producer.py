import copy
import json
from pathlib import Path
from typing import Any, Dict

import produce_loadtest_summary as pl  # noqa: E402
import pytest

from tests.producers import _helpers as h


def _export() -> Dict[str, Any]:
    return {
        "metrics": {
            "http_reqs": {"count": 4210, "rate": 10.8},
            "http_req_failed": {
                "value": 0.0007,
                "passes": 3,
                "fails": 4207,
                "thresholds": {"rate<0.005": False},
            },
            "http_req_duration": {
                "avg": 41.2,
                "min": 3.1,
                "med": 30.0,
                "max": 910.0,
                "p(90)": 80.0,
                "p(95)": 120.5,
                "p(99)": 300.0,
            },
            "http_req_duration{name:health}": {
                "p(95)": 20.0,
                "thresholds": {"p(95)<2500": False},
            },
            "http_reqs{name:health}": {"count": 2100, "rate": 5.4},
            "http_req_failed{name:health}": {"value": 0.0, "passes": 0, "fails": 2100},
            "http_req_duration{name:orphan}": {"p(95)": 1.0},
            "vus_max": {"value": 10, "min": 10, "max": 10},
            "checks": {
                "passes": 8400,
                "fails": 2,
                "value": 0.99,
                "thresholds": {"rate>0.99": True},
            },
        }
    }


def _build(export: Any = None, **kw: Any) -> Dict[str, Any]:
    args: Dict[str, Any] = dict(
        target="http://x",
        scenario="load.js",
        duration_seconds=390.0,
        generated_at="2026-11-04T03:10:00Z",
    )
    args.update(kw)
    return pl.build_summary(_export() if export is None else export, **args)


def test_mapping() -> None:
    doc = _build(tool_version="0.49.0", vus_limit=20)
    assert doc["format"] == "urbanflow-loadtest-summary" and doc["version"] == 1
    assert doc["tool"] == "k6" and doc["toolVersion"] == "0.49.0"
    assert doc["vus"] == {"peak": 10, "max": 20}
    assert doc["requests"] == {
        "total": 4210,
        "ratePerSecond": 10.8,
        "failed": 3,
        "errorRate": 0.0007,
    }
    assert doc["latencyMs"] == {
        "avg": 41.2,
        "min": 3.1,
        "med": 30.0,
        "p90": 80.0,
        "p95": 120.5,
        "p99": 300.0,
        "max": 910.0,
    }
    assert doc["checks"] == {"passes": 8400, "fails": 2}
    # Legacy export: true means the threshold failed.
    assert {(t["metric"], t["expression"]): t["passed"] for t in doc["thresholds"]} == {
        ("checks", "rate>0.99"): False,
        ("http_req_duration{name:health}", "p(95)<2500"): True,
        ("http_req_failed", "rate<0.005"): True,
    }
    assert doc["endpoints"] == [
        {"name": "health", "requests": 2100, "p95Ms": 20.0, "errorRate": 0.0}
    ]


def test_ok_form_thresholds_and_missing_figures_are_null() -> None:
    export = _export()
    export["metrics"]["http_req_failed"]["thresholds"] = {"rate<0.005": {"ok": False}}
    del export["metrics"]["http_req_duration"]["p(99)"]
    del export["metrics"]["http_reqs"]["rate"]
    doc = _build(export)
    assert doc["latencyMs"]["p99"] is None and doc["requests"]["ratePerSecond"] is None
    assert doc["vus"]["max"] == 10 and "toolVersion" not in doc
    failed = [t for t in doc["thresholds"] if t["metric"] == "http_req_failed"]
    assert failed[0]["passed"] is False


@pytest.mark.parametrize(
    "mutate",
    [
        lambda e: e.pop("metrics"),
        lambda e: e["metrics"].pop("http_reqs"),
        lambda e: e["metrics"].pop("http_req_duration"),
        lambda e: e["metrics"].pop("http_req_failed"),
        lambda e: e["metrics"].pop("vus_max"),
        lambda e: e["metrics"]["http_req_failed"].update(value=3.0),
        lambda e: e["metrics"]["http_req_failed"].update(thresholds={"x": "bad"}),
    ],
)
def test_unusable_exports_are_rejected(mutate: Any) -> None:
    export = copy.deepcopy(_export())
    mutate(export)
    with pytest.raises(ValueError):
        _build(export)


def test_bad_arguments() -> None:
    for kw in ({"target": ""}, {"duration_seconds": -1.0}, {"vus_limit": 5}):
        with pytest.raises(ValueError):
            _build(**kw)


def test_produce_writes_the_file_the_endpoint_serves(tmp_path: Path) -> None:
    src = tmp_path / "k6.json"
    src.write_text(json.dumps(_export()), encoding="utf-8")
    root = tmp_path / "results"
    path = pl.produce(
        src,
        target="http://x",
        scenario="load.js",
        duration_seconds=60,
        results_dir=root,
    )
    assert path == root / "loadtests" / "latest.json"
    assert b"\r" not in path.read_bytes()
    assert [p.name for p in path.parent.iterdir()] == ["latest.json"]
    res = h.client(root).get("/api/v3/loadtests/latest")
    assert res.status_code == 200
    body = res.json()
    assert body["requests"]["total"] == 4210 and body["scenario"] == "load.js"


def test_main_exit_codes_and_no_partial_write(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "results"
    bad = tmp_path / "bad.json"
    bad.write_text("{nope", encoding="utf-8")
    common_args = [
        "--target",
        "http://x",
        "--scenario",
        "s",
        "--duration-seconds",
        "5",
        "--results-dir",
        str(root),
    ]
    assert pl.main(["--input", str(bad)] + common_args) == 2
    assert pl.main(["--input", str(tmp_path / "missing.json")] + common_args) == 2
    assert not root.exists()
    good = tmp_path / "good.json"
    good.write_text(json.dumps(_export()), encoding="utf-8")
    assert pl.main(["--input", str(good)] + common_args) == 0
    assert "latest.json" in capsys.readouterr().out
