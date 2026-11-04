"""Shared, Airflow-free helpers for the UrbanFlow DAGs.

Everything here is plain Python so the DAG modules can be imported (and the
command construction unit-tested) on a machine without Airflow installed.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Sequence

# Where the repository is checked out on the Airflow worker.
REPO_ROOT = Path(os.environ.get("URBANFLOW_REPO", Path(__file__).resolve().parents[2]))
PYTHON = os.environ.get("URBANFLOW_PYTHON", sys.executable or "python")
RESULTS_DIR = Path(os.environ.get("URBANFLOW_RESULTS_DIR", REPO_ROOT / "airflow" / "results"))

try:  # Airflow is optional at import time.
    # Import a real name: when run from the repo root, this repository's own
    # ``airflow/`` directory is importable as an empty namespace package, so a
    # bare ``import airflow`` would wrongly succeed.
    from airflow import DAG  # noqa: F401

    AIRFLOW_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only without Airflow
    AIRFLOW_AVAILABLE = False


def command_env() -> dict:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(REPO_ROOT / "backend"), str(REPO_ROOT)])
    return env


def nightly_pytest_command(slow: bool = True) -> List[str]:
    """Backend regression: the whole suite, or only the fast subset."""
    cmd = [PYTHON, "-m", "pytest", "-q", "--no-cov", "-p", "no:cacheprovider"]
    if not slow:
        cmd += ["-m", "not slow"]
    return cmd


def multiseed_command(
    geometry: str, num_seeds: int, duration: float, output: Path, base_seed: Optional[int] = None
) -> List[str]:
    if geometry not in ("signal", "roundabout"):
        raise ValueError(f"unknown geometry {geometry!r}")
    if num_seeds < 1:
        raise ValueError("num_seeds must be >= 1")
    cmd = [
        PYTHON,
        str(REPO_ROOT / "airflow" / "scripts" / "run_multiseed.py"),
        "--geometry", geometry,
        "--num-seeds", str(num_seeds),
        "--duration", str(duration),
        "--output", str(output),
        "--fail-on-limit",
    ]
    if base_seed is not None:
        cmd += ["--base-seed", str(base_seed)]
    return cmd


def full_study_command(output_csv: Path, output_json: Path, num_seeds: int = 5) -> List[str]:
    """The existing scripts/run_full_study.py CLI, unchanged."""
    return [
        PYTHON,
        str(REPO_ROOT / "scripts" / "run_full_study.py"),
        "--num-seeds", str(num_seeds),
        "--output-csv", str(output_csv),
        "--output-json", str(output_json),
    ]


def run(cmd: Sequence[str], cwd: Optional[Path] = None) -> int:
    """Run ``cmd``; raise RuntimeError on non-zero exit so the task fails."""
    print("$", " ".join(shlex.quote(c) for c in cmd), flush=True)
    proc = subprocess.run(list(cmd), cwd=str(cwd or REPO_ROOT / "backend"), env=command_env())
    if proc.returncode != 0:
        raise RuntimeError(f"command failed with exit status {proc.returncode}: {cmd[0]} ...")
    return proc.returncode
