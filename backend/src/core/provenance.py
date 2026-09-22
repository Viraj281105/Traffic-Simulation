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
(see ``backend/Dockerfile``).
"""

import platform
from pathlib import Path
from typing import Optional

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


# Computed once per process: git HEAD doesn't move during a run, and this
# avoids repeated filesystem reads on every /reproduce call.
GIT_COMMIT_HASH: str = get_git_commit_hash()
PYTHON_VERSION: str = get_python_version()
