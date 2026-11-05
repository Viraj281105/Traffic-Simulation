"""``NightlyRegression``: the history of the nightly regression runs, newest first.

Source: ``nightly/history.json`` (format ``urbanflow-nightly-history`` v1), written by the nightly job::

    {"format": "urbanflow-nightly-history", "version": 1, "generatedAt": "2026-11-04T02:40:00Z",
     "runs": [{"id": "2026-11-04", "startedAt": "...", "gitCommit": "...", "status": "pass",
               "durationSeconds": 1520.5, "logUrl": null,
               "checks": [{"id": "delay", "name": "Mean delay", "status": "fail", "metric": "mean_delay",
                           "expected": 12.0, "actual": 14.1, "tolerance": 1.0, "unit": "s",
                           "message": null}]}]}

Nothing is computed: runs and checks are passed through after their fields are checked. A night that does
not have the required fields makes the whole file unavailable rather than being shown half-filled.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from .numbers import finite

HISTORY_FORMAT = "urbanflow-nightly-history"
RUN_STATUSES = ("pass", "fail", "error")
CHECK_STATUSES = ("pass", "fail", "error", "skipped")
MAX_LIMIT = 365


def _text(value: Any) -> Optional[str]:
    return value if isinstance(value, str) else None


def _check(raw: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        return None
    cid, name, status = _text(raw.get("id")), _text(raw.get("name")), raw.get("status")
    if cid is None or name is None or status not in CHECK_STATUSES:
        return None
    return {
        "id": cid,
        "name": name,
        "status": status,
        "metric": _text(raw.get("metric")),
        "expected": finite(raw.get("expected")),
        "actual": finite(raw.get("actual")),
        "tolerance": finite(raw.get("tolerance")),
        "unit": _text(raw.get("unit")),
        "message": _text(raw.get("message")),
    }


def _run(raw: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        return None
    rid, started, commit = (
        _text(raw.get("id")),
        _text(raw.get("startedAt")),
        _text(raw.get("gitCommit")),
    )
    duration = finite(raw.get("durationSeconds"))
    checks_raw = raw.get("checks")
    if (
        rid is None
        or started is None
        or commit is None
        or duration is None
        or raw.get("status") not in RUN_STATUSES
        or not isinstance(checks_raw, list)
    ):
        return None
    checks = [_check(c) for c in checks_raw]
    if any(c is None for c in checks):
        return None
    return {
        "id": rid,
        "startedAt": started,
        "gitCommit": commit,
        "status": raw["status"],
        "durationSeconds": duration,
        "checks": checks,
        "logUrl": _text(raw.get("logUrl")),
    }


def build_nightly(doc: Mapping[str, Any], limit: int) -> Optional[Dict[str, Any]]:
    """The newest ``limit`` runs, or None when the file is not a valid history."""
    generated = _text(doc.get("generatedAt"))
    raw_runs = doc.get("runs")
    if doc.get("format") != HISTORY_FORMAT or generated is None:
        return None
    if not isinstance(raw_runs, list):
        return None
    runs: List[Dict[str, Any]] = []
    for raw in raw_runs:
        run = _run(raw)
        if run is None:
            return None
        runs.append(run)
    # ISO timestamps in one zone sort as text; newest first.
    runs.sort(key=lambda r: r["startedAt"], reverse=True)
    return {"generatedAt": generated, "runs": runs[: max(1, min(limit, MAX_LIMIT))]}
