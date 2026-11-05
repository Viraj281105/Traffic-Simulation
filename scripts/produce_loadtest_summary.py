"""Write ``loadtests/latest.json`` (urbanflow-loadtest-summary v1) from a k6 ``--summary-export`` file.

    k6 run --summary-export k6-summary.json deploy/k6/load.js
    python scripts/produce_loadtest_summary.py --input k6-summary.json \
        --target http://127.0.0.1:8000 --scenario load.js --duration-seconds 390 --vus-limit 10

Mapping from the export's ``metrics`` object (times are already milliseconds in k6):

    vus.peak               vus_max.max          (--vus-limit sets vus.max, default: the peak)
    requests.total         http_reqs.count
    requests.ratePerSecond http_reqs.rate
    requests.failed        http_req_failed.passes   (a k6 Rate counts the true samples = failed requests)
    requests.errorRate     http_req_failed.value    (fraction 0..1)
    latencyMs              http_req_duration: avg, min, med, p(90), p(95), p(99), max
    checks                 checks.passes, checks.fails
    thresholds[]           every ``thresholds`` entry of every metric: name = metric = the metric key
                           (e.g. ``http_req_duration{name:health}``), expression = the rule
    endpoints[]            each ``http_req_duration{name:X}`` with an ``http_reqs{name:X}`` count: p95Ms and
                           (when ``http_req_failed{name:X}`` exists) errorRate

A legacy export stores ``expression: true`` for a threshold that FAILED; the newer ``{"ok": bool}`` form is read
as is. A figure k6 did not report is null, never 0. The target, scenario, run length and k6 version are not in
the export, so they are arguments. The file is replaced atomically.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import produce_common as common  # noqa: E402

LOADTEST_FORMAT = "urbanflow-loadtest-summary"
LATENCY_FIELDS = (
    ("avg", "avg"),
    ("min", "min"),
    ("med", "med"),
    ("p90", "p(90)"),
    ("p95", "p(95)"),
    ("p99", "p(99)"),
    ("max", "max"),
)
_DURATION = "http_req_duration"


def _num(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def _whole(value: Any) -> Optional[int]:
    num = _num(value)
    return int(num) if num is not None and num >= 0 and num == int(num) else None


def _metric(metrics: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    value = metrics.get(name)
    return value if isinstance(value, dict) else {}


def _passed(raw: Any) -> bool:
    if isinstance(raw, dict):
        ok = raw.get("ok")
        if isinstance(ok, bool):
            return ok
    elif isinstance(raw, bool):
        return not raw
    raise ValueError(f"unreadable threshold result {raw!r}")


def _thresholds(metrics: Mapping[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for key in sorted(metrics):
        entry = metrics[key]
        rules = entry.get("thresholds") if isinstance(entry, dict) else None
        if not isinstance(rules, dict):
            continue
        for expression in sorted(rules):
            out.append(
                {
                    "name": key,
                    "metric": key,
                    "expression": expression,
                    "passed": _passed(rules[expression]),
                }
            )
    return out


def _endpoints(metrics: Mapping[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    prefix, tag = _DURATION + "{name:", "}"
    for key in sorted(metrics):
        if not (key.startswith(prefix) and key.endswith(tag)):
            continue
        name = key[len(prefix) : -len(tag)]
        count = _whole(_metric(metrics, f"http_reqs{{name:{name}}}").get("count"))
        if not name or count is None:
            continue
        failed = _metric(metrics, f"http_req_failed{{name:{name}}}")
        out.append(
            {
                "name": name,
                "requests": count,
                "p95Ms": _num(_metric(metrics, key).get("p(95)")),
                "errorRate": _num(failed.get("value")),
            }
        )
    return out


def build_summary(
    export: Mapping[str, Any],
    *,
    target: str,
    scenario: str,
    duration_seconds: float,
    generated_at: str,
    vus_limit: Optional[int] = None,
    tool_version: Optional[str] = None,
) -> Dict[str, Any]:
    """The summary document for a k6 ``--summary-export`` object. Pure; raises ValueError when unusable."""
    metrics = export.get("metrics")
    if not isinstance(metrics, dict):
        raise ValueError("the k6 export has no 'metrics' object")
    if not target or not scenario:
        raise ValueError("target and scenario must not be empty")
    if not math.isfinite(duration_seconds) or duration_seconds < 0:
        raise ValueError("duration must be a number of seconds, 0 or more")
    reqs = _metric(metrics, "http_reqs")
    total = _whole(reqs.get("count"))
    if total is None:
        raise ValueError("the k6 export has no http_reqs count (was an HTTP test run?)")
    duration = _metric(metrics, _DURATION)
    if not duration:
        raise ValueError(f"the k6 export has no {_DURATION} metric")
    failed_metric = _metric(metrics, "http_req_failed")
    failed = _whole(failed_metric.get("passes"))
    if failed is None:
        raise ValueError("the k6 export has no http_req_failed metric")
    rate = _num(failed_metric.get("value"))
    if rate is not None and not 0.0 <= rate <= 1.0:
        raise ValueError("http_req_failed value must be a fraction between 0 and 1")
    peak = _whole(_metric(metrics, "vus_max").get("max"))
    if peak is None:
        peak = _whole(_metric(metrics, "vus").get("max"))
    if peak is None:
        raise ValueError("the k6 export has no vus_max or vus metric")
    if vus_limit is not None and vus_limit < peak:
        raise ValueError("--vus-limit is below the peak the test reached")
    checks = _metric(metrics, "checks")
    doc: Dict[str, Any] = {
        "format": LOADTEST_FORMAT,
        "version": 1,
        "generatedAt": generated_at,
        "tool": "k6",
        "target": target,
        "scenario": scenario,
        "durationSeconds": float(duration_seconds),
        "vus": {"peak": peak, "max": peak if vus_limit is None else vus_limit},
        "requests": {
            "total": total,
            "ratePerSecond": _num(reqs.get("rate")),
            "failed": failed,
            "errorRate": rate,
        },
        "latencyMs": {out: _num(duration.get(src)) for out, src in LATENCY_FIELDS},
        "checks": {
            "passes": _whole(checks.get("passes")) or 0,
            "fails": _whole(checks.get("fails")) or 0,
        },
        "thresholds": _thresholds(metrics),
    }
    if tool_version:
        doc["toolVersion"] = tool_version
    endpoints = _endpoints(metrics)
    if endpoints:
        doc["endpoints"] = endpoints
    return doc


def produce(
    input_path: "Path | str",
    *,
    target: str,
    scenario: str,
    duration_seconds: float,
    vus_limit: Optional[int] = None,
    tool_version: Optional[str] = None,
    results_dir: "Optional[Path | str]" = None,
) -> Path:
    try:
        export = json.loads(Path(input_path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read {input_path}: {exc}") from exc
    except ValueError as exc:
        raise ValueError(f"{input_path} is not valid JSON: {exc}") from exc
    if not isinstance(export, dict):
        raise ValueError(f"{input_path} is not a k6 summary export (not a JSON object)")
    doc = build_summary(
        export,
        target=target,
        scenario=scenario,
        duration_seconds=duration_seconds,
        generated_at=common.utc_now_iso(),
        vus_limit=vus_limit,
        tool_version=tool_version,
    )
    return common.write_json_atomic(common.locations(results_dir).loadtest_file(), doc)


def main(argv: "Optional[List[str]]" = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--input", required=True, help="k6 --summary-export JSON file")
    ap.add_argument("--target", required=True, help="the base URL that was tested")
    ap.add_argument("--scenario", required=True, help="the test script or scenario name")
    ap.add_argument("--duration-seconds", type=float, required=True)
    ap.add_argument("--vus-limit", type=int, default=None)
    ap.add_argument("--tool-version", default=None)
    ap.add_argument("--results-dir", default=None)
    args = ap.parse_args(argv)
    try:
        path = produce(
            args.input,
            target=args.target,
            scenario=args.scenario,
            duration_seconds=args.duration_seconds,
            vus_limit=args.vus_limit,
            tool_version=args.tool_version,
            results_dir=args.results_dir,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
