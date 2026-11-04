"""Where result files live, and safe reading of them.

Everything is under one root, ``URBANFLOW_RESULTS_DIR`` (the same variable the Airflow DAGs write to; default
``airflow/results`` in the repository)::

    <root>/runs/<run id>/manifest.json, metrics.parquet     Parquet run store (src/runstore)
    <root>/experiments/<experiment id>/paired.json           per-seed values per alternative
    <root>/experiments/<experiment id>/sensitivity.json      a Sobol result for one metric
    <root>/nightly/history.json                              nightly regression history
    <root>/rl/<comparison id>.json                           RL against fixed-time, per scenario
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

RESULTS_DIR_ENV = "URBANFLOW_RESULTS_DIR"
MAX_RESULT_FILE_BYTES = 20 * 1024 * 1024

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")


def default_results_root() -> Path:
    env = os.environ.get(RESULTS_DIR_ENV)
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[3] / "airflow" / "results"


def safe_id(value: str) -> Optional[str]:
    """The id when it is a plain file-name-safe token, else None (so it can never name a path)."""
    return value if _ID_RE.fullmatch(value) else None


def read_json_object(path: Path) -> Optional[Dict[str, Any]]:
    """A JSON object from ``path``; None when the file is absent, too large, or not a JSON object.

    An unreadable file is logged and treated as not available, never as an empty result."""
    try:
        if not path.is_file():
            return None
        if path.stat().st_size > MAX_RESULT_FILE_BYTES:
            logger.warning("result file too large: %s", path)
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        logger.warning("result file unreadable: %s", path, exc_info=True)
        return None
    if not isinstance(data, dict):
        logger.warning("result file is not a JSON object: %s", path)
        return None
    return data


class ResultsLocations:
    """Paths of the result files under one root."""

    def __init__(self, root: "Optional[Path | str]" = None) -> None:
        self.root = Path(root) if root is not None else default_results_root()

    def experiment_file(self, experiment_id: str, name: str) -> Optional[Path]:
        eid = safe_id(experiment_id)
        return None if eid is None else self.root / "experiments" / eid / name

    def nightly_file(self) -> Path:
        return self.root / "nightly" / "history.json"

    def rl_file(self, comparison_id: str) -> Optional[Path]:
        cid = safe_id(comparison_id)
        return None if cid is None else self.root / "rl" / f"{cid}.json"
