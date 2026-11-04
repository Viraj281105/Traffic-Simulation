"""Append-to-history helper for the nightly regression DAG.

Writes ``nightly/history.json`` (format ``urbanflow-nightly-history`` v1, read by
``GET /api/v3/regression/nightly``; the fields are those checked by ``backend/src/insights/regression_view.py``).

Plain Python with no Airflow or backend imports, so the DAG module and its tests import it anywhere.

Flow: each DAG task runs through ``checked`` which records one check file under
``nightly/parts/<ds>/``; the last task calls ``record_night`` which collects the parts into one run and
appends it with ``append_run``. A rerun of the same ``ds`` replaces that night's run.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

HISTORY_FORMAT = "urbanflow-nightly-history"
KEEP_RUNS = 365  # the endpoint's own cap


def utc_now_iso() -> str:
    # One fixed format: the endpoint sorts startedAt as text.
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def history_path(results_dir: Path) -> Path:
    return Path(results_dir) / "nightly" / "history.json"


def parts_dir(results_dir: Path, ds: str) -> Path:
    return Path(results_dir) / "nightly" / "parts" / ds


def git_commit(repo: Path) -> str:
    """The checkout's HEAD commit, or ``unknown`` when git is unavailable."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=10,
        )
        text = out.stdout.strip()
        return text if out.returncode == 0 and text else "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _write_json_atomic(path: Path, doc: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, sort_keys=True, allow_nan=False) + "\n"
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def make_check(
    check_id: str,
    name: str,
    status: str,
    *,
    metric: Optional[str] = None,
    expected: Optional[float] = None,
    actual: Optional[float] = None,
    tolerance: Optional[float] = None,
    unit: Optional[str] = None,
    message: Optional[str] = None,
) -> Dict[str, Any]:
    if status not in ("pass", "fail", "error", "skipped"):
        raise ValueError(f"unknown check status {status!r}")
    check: Dict[str, Any] = {"id": check_id, "name": name, "status": status}
    for key, value in (
        ("metric", metric),
        ("expected", expected),
        ("actual", actual),
        ("tolerance", tolerance),
        ("unit", unit),
        ("message", message),
    ):
        if value is not None:
            check[key] = value
    return check


def run_status(checks: Sequence[Dict[str, Any]]) -> str:
    """``error`` if any check errored, else ``fail`` if any failed, else ``pass`` (skipped checks do not fail a night)."""
    statuses = {c["status"] for c in checks}
    if "error" in statuses:
        return "error"
    if "fail" in statuses:
        return "fail"
    return "pass"


def build_run(
    run_id: str,
    started_at: str,
    commit: str,
    checks: List[Dict[str, Any]],
    duration_seconds: float,
    log_url: Optional[str] = None,
) -> Dict[str, Any]:
    run: Dict[str, Any] = {
        "id": run_id,
        "startedAt": started_at,
        "gitCommit": commit,
        "status": run_status(checks),
        "durationSeconds": float(duration_seconds),
        "checks": checks,
    }
    if log_url:
        run["logUrl"] = log_url
    return run


def read_history(path: Path) -> List[Dict[str, Any]]:
    """The runs already stored; an unreadable or foreign file is set aside as ``.bad`` and read as empty."""
    if not path.is_file():
        return []
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        if doc.get("format") == HISTORY_FORMAT and isinstance(doc.get("runs"), list):
            return [r for r in doc["runs"] if isinstance(r, dict)]
    except (OSError, ValueError, AttributeError):
        pass
    os.replace(path, path.with_name(path.name + ".bad"))
    return []


def append_run(path: Path, run: Dict[str, Any], keep: int = KEEP_RUNS) -> Dict[str, Any]:
    """Add ``run`` (replacing any run with the same id), keep the newest ``keep``, write atomically."""
    path = Path(path)
    runs = [r for r in read_history(path) if r.get("id") != run["id"]]
    runs.append(run)
    runs.sort(key=lambda r: str(r.get("startedAt", "")), reverse=True)
    doc = {
        "format": HISTORY_FORMAT,
        "version": 1,
        "generatedAt": utc_now_iso(),
        "runs": runs[: max(1, keep)],
    }
    _write_json_atomic(path, doc)
    return doc


def checked(
    results_dir: Path,
    ds: str,
    check_id: str,
    name: str,
    fn: Callable[[], Optional[Dict[str, Any]]],
) -> None:
    """Run ``fn``; record its outcome as one check part; re-raise any failure so the task still fails.

    ``fn`` may return extra check fields (metric, actual, unit, ...)."""
    started = utc_now_iso()
    t0 = time.monotonic()
    extra: Dict[str, Any] = {}
    status, message = "pass", None
    err: Optional[BaseException] = None
    try:
        extra = fn() or {}
    except RuntimeError as exc:  # common.run raises this for a non-zero exit: a failed check
        status, message, err = "fail", str(exc), exc
    except BaseException as exc:  # anything else is an error in the check itself
        status, message, err = "error", f"{type(exc).__name__}: {exc}", exc
    part = make_check(check_id, name, status, message=message, **extra)
    part["_startedAt"] = started
    part["_durationSeconds"] = round(time.monotonic() - t0, 3)
    _write_json_atomic(parts_dir(results_dir, ds) / f"{check_id}.json", part)
    if err is not None:
        raise err


def collect_checks(
    results_dir: Path, ds: str, expected: Sequence[Tuple[str, str]]
) -> Tuple[List[Dict[str, Any]], str, float]:
    """Checks for ``expected`` (id, name) pairs, a missing part being ``skipped``; plus start time and total seconds."""
    checks: List[Dict[str, Any]] = []
    starts: List[str] = []
    total = 0.0
    for check_id, name in expected:
        file = parts_dir(results_dir, ds) / f"{check_id}.json"
        try:
            part = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            checks.append(
                make_check(check_id, name, "skipped", message="did not run (an earlier task failed)")
            )
            continue
        starts.append(str(part.pop("_startedAt", "")))
        total += float(part.pop("_durationSeconds", 0.0) or 0.0)
        checks.append(part)
    started = min((s for s in starts if s), default=utc_now_iso())
    return checks, started, total


def record_night(
    results_dir: Path,
    ds: str,
    expected: Sequence[Tuple[str, str]],
    repo: Path,
    log_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Collect this night's check parts into one run and append it to the history. Returns the run."""
    checks, started, total = collect_checks(results_dir, ds, expected)
    run = build_run(ds, started, git_commit(repo), checks, total, log_url)
    append_run(history_path(results_dir), run)
    return run
