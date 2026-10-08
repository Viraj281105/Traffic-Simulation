"""The shared scenario-configuration JSON schema, for modules outside main.py.

Resolved exactly as main.py resolves it — relative to this package, for both
the repository checkout (repo/shared) and the Docker image (/app/shared) —
and loaded once. A missing schema is an error, never an empty schema: schema
validation is a correctness boundary.
"""

import json
from pathlib import Path
from typing import Any, Dict

_CANDIDATES = [
    Path(__file__).resolve().parents[3] / "shared" / "schemas" / "config.schema.json",
    Path(__file__).resolve().parents[2] / "shared" / "schemas" / "config.schema.json",
]


def _load() -> Dict[str, Any]:
    for path in _CANDIDATES:
        if path.is_file():
            with open(path, "r", encoding="utf-8") as f:
                schema: Dict[str, Any] = json.load(f)
                return schema
    raise RuntimeError(
        f"Failed to load required config schema: none of {[str(p) for p in _CANDIDATES]} exist"
    )


CONFIG_SCHEMA: Dict[str, Any] = _load()
