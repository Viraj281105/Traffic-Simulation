"""Shared pieces of the ``produce_*`` scripts that write files read by ``src/insights``.

Paths come from ``src.insights.locations.ResultsLocations`` (read only, not changed here) so a producer and
the endpoint that reads its file cannot disagree about where the file lives. Writes are atomic (a temporary
file in the same directory, then a rename) so an endpoint never reads a half-written file.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "backend", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from src.insights.locations import ResultsLocations, safe_id  # noqa: E402


def locations(results_dir: "Optional[Path | str]" = None) -> ResultsLocations:
    """The results root: ``results_dir``, else ``URBANFLOW_RESULTS_DIR``, else ``airflow/results``."""
    return ResultsLocations(results_dir)


def require_id(value: str, what: str = "id") -> str:
    ok = safe_id(value)
    if ok is None:
        raise ValueError(
            f"{what} {value!r} must be 1-128 characters: letters, digits, '-' and '_', "
            "starting with a letter or digit"
        )
    return ok


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_json_atomic(path: Path, doc: Mapping[str, Any]) -> Path:
    """Write ``doc`` as UTF-8 JSON with LF line endings, replacing ``path`` atomically."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, sort_keys=True, allow_nan=False, default=str) + "\n"
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
    return path


def parse_pairs(items: List[str], what: str) -> Dict[str, str]:
    """``["a=b", ...]`` as a dict; a missing ``=`` is an error."""
    out: Dict[str, str] = {}
    for item in items:
        key, sep, value = item.partition("=")
        if not sep or not key:
            raise ValueError(f"{what} must look like KEY=VALUE, got {item!r}")
        out[key] = value
    return out
