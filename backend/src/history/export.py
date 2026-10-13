"""CSV export of one stored simulation run (``GET .../runs/{id}/export``).

Pure functions: no database, no HTTP. Missing values stay empty, never 0, and
user-entered text is made spreadsheet-safe (``src/csv_safety.py``).
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any, Dict

from src.csv_safety import spreadsheet_safe


def _flatten(prefix: str, value: Any, out: list[tuple[str, str]]) -> None:
    """Dotted-path rows for nested dicts; lists are kept as JSON."""
    if isinstance(value, dict):
        for k, v in value.items():
            _flatten(f"{prefix}.{k}" if prefix else str(k), v, out)
    else:
        # Keys come from stored configs, which a client may have written.
        out.append((spreadsheet_safe(prefix), _csv_value(value)))


def _csv_value(value: Any) -> str:
    """A cell for one value. Missing values stay empty -- never 0."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, dict)):
        return json.dumps(value)
    if isinstance(value, str):
        return spreadsheet_safe(value)
    return str(value)


def run_export_csv(record: Dict[str, Any]) -> str:
    """One stored run as ``section,key,value`` rows: identity and labels,
    reproducibility, timing, then the flattened config and metrics."""
    rows: list[tuple[str, str, str]] = []
    for key in (
        "runId",
        "name",
        "createdAt",
        "status",
        "intersectionType",
        "runMode",
        "batchId",
    ):
        rows.append(("run", key, _csv_value(record.get(key))))
    rows.append(("run", "tags", _csv_value("; ".join(record.get("tags") or []))))
    rows.append(("run", "notes", _csv_value(record.get("notes"))))
    for key in (
        "seed",
        "provenanceRecorded",
        "configSource",
        "exactConfig",
        "configAvailable",
        "gitCommitHash",
        "pythonVersion",
    ):
        rows.append(("reproducibility", key, _csv_value(record.get(key))))
    for key, value in (record.get("timing") or {}).items():
        rows.append(("timing", key, _csv_value(value)))
    for section, payload in (
        ("config", record.get("config") or {}),
        ("metrics", record.get("summaryMetrics") or {}),
    ):
        flat: list[tuple[str, str]] = []
        _flatten("", payload, flat)
        rows.extend((section, k, v) for k, v in flat)

    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["section", "key", "value"])
    writer.writerows(rows)
    return output.getvalue()
