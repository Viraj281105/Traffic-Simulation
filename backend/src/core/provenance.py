"""Best-effort reproducibility provenance (git commit, Python runtime).

Used to stamp headless reproduction runs (see main.py's
``/reproduce`` endpoint) with the code version and interpreter that produced
them, so a divergent result can be told apart from an environment
difference rather than a real non-determinism bug.

Every lookup here degrades to ``"unknown"`` rather than raising --
reproduction must never fail because provenance couldn't be determined.
Git state is read directly from the ``.git`` directory (no subprocess /
``git`` binary dependency), so this also degrades safely wherever ``.git``
isn't present at all -- e.g. the production Docker image, whose
``.dockerignore`` deliberately excludes ``.git`` from the build context
(see ``backend/Dockerfile``). Such builds can instead pass the commit in as
the ``GIT_COMMIT`` build argument / environment variable, which is used
only when ``.git`` cannot be read.
"""

import os
import platform
import re
from pathlib import Path
from typing import Any, Dict, Optional

UNKNOWN = "unknown"


def find_git_dir(start: Optional[Path] = None, max_levels: int = 6) -> Optional[Path]:
    """Walks upward from `start` (default: this file's directory) looking
    for a `.git` entry, same as how `git` itself locates a repository."""
    current = (start or Path(__file__).resolve().parent).resolve()
    for _ in range(max_levels):
        candidate = current / ".git"
        if candidate.exists():
            return candidate
        if current.parent == current:
            break
        current = current.parent
    return None


def get_git_commit_hash(start: Optional[Path] = None) -> str:
    """Current commit hash of HEAD, or "unknown" if it can't be determined."""
    try:
        git_dir = find_git_dir(start)
        if git_dir is None:
            return UNKNOWN

        head_file = git_dir / "HEAD"
        if not head_file.is_file():
            return UNKNOWN

        head_content = head_file.read_text(encoding="utf-8").strip()
        if not head_content.startswith("ref:"):
            # Detached HEAD: the file itself holds the hash.
            return head_content or UNKNOWN

        ref_path = head_content.split(" ", 1)[1].strip()
        ref_file = git_dir / ref_path
        if ref_file.is_file():
            resolved = ref_file.read_text(encoding="utf-8").strip()
            return resolved or UNKNOWN

        # Loose ref file may be absent after `git gc` packs it away.
        packed_refs = git_dir / "packed-refs"
        if packed_refs.is_file():
            suffix = " " + ref_path
            for line in packed_refs.read_text(encoding="utf-8").splitlines():
                if line.endswith(suffix):
                    return line.split(" ", 1)[0]

        return UNKNOWN
    except OSError:
        return UNKNOWN


def get_python_version() -> str:
    """Interpreter version string, e.g. "3.11.16". Effectively never fails."""
    try:
        return platform.python_version()
    except Exception:
        return UNKNOWN


_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{7,40}$")


def resolve_git_commit_hash(start: Optional[Path] = None) -> str:
    """The running code's commit: HEAD of the enclosing repository when one
    is readable, else the ``GIT_COMMIT`` environment variable (set at image
    build time, see backend/Dockerfile) when it holds a plausible hex hash,
    else "unknown". A malformed value is ignored rather than recorded."""
    from_git = get_git_commit_hash(start)
    if from_git != UNKNOWN:
        return from_git
    env = os.environ.get("GIT_COMMIT", "").strip().lower()
    return env if _COMMIT_PATTERN.fullmatch(env) else UNKNOWN


# Computed once per process: git HEAD doesn't move during a run, and this
# avoids repeated filesystem reads on every /reproduce call.
GIT_COMMIT_HASH: str = resolve_git_commit_hash()
PYTHON_VERSION: str = get_python_version()


# Version of the per-run provenance record below; bump if its shape changes.
RUN_PROVENANCE_SCHEMA_VERSION = 1


def build_run_provenance(
    *,
    config_source: str,
    run_mode: str,
    time_step: Optional[float],
    duration: Optional[float],
    warmup_time: Optional[float],
) -> Dict[str, Any]:
    """The reproducibility record stored with each saved run (V1.1).

    ``config_source`` says where the stored configuration came from:
    ``"engine"`` -- the exact config dict the simulation engine ran with --
    or ``"client"`` -- the client-supplied summary, used only when no engine
    was available to read it from. ``run_mode`` is ``"single"`` or ``"dual"``
    (the lockstep signal-vs-roundabout comparison). The timing fields are
    the values the engine actually used, not config defaults re-derived
    later; None when they could not be read.
    """
    return {
        "schemaVersion": RUN_PROVENANCE_SCHEMA_VERSION,
        "gitCommitHash": GIT_COMMIT_HASH,
        "pythonVersion": PYTHON_VERSION,
        "configSource": config_source,
        "runMode": run_mode,
        "timing": {
            "timeStep": time_step,
            "duration": duration,
            "warmupTime": warmup_time,
        },
    }
