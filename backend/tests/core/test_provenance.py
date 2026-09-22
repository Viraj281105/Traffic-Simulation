"""Tests for src/core/provenance.py -- best-effort git/Python provenance.

Every case here targets the specific requirement that these lookups degrade
safely to "unknown" rather than raising, since the caller (the /reproduce
endpoint) must never fail because provenance couldn't be determined.
"""

from pathlib import Path

from src.core.provenance import (
    UNKNOWN,
    find_git_dir,
    get_git_commit_hash,
    get_python_version,
)


def test_find_git_dir_returns_none_when_no_git_dir_exists(tmp_path: Path) -> None:
    nested = tmp_path / "a" / "b" / "c"
    nested.mkdir(parents=True)
    assert find_git_dir(nested) is None


def test_find_git_dir_finds_it_in_a_parent_directory(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    assert find_git_dir(nested) == tmp_path / ".git"


def test_get_git_commit_hash_is_unknown_when_git_dir_missing(tmp_path: Path) -> None:
    # Simulates the production Docker image, whose .dockerignore excludes
    # .git from the build context entirely.
    nested = tmp_path / "app"
    nested.mkdir()
    assert get_git_commit_hash(nested) == UNKNOWN


def test_get_git_commit_hash_is_unknown_when_head_file_missing(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    assert get_git_commit_hash(tmp_path) == UNKNOWN


def test_get_git_commit_hash_resolves_a_branch_ref(tmp_path: Path) -> None:
    git_dir = tmp_path / ".git"
    (git_dir / "refs" / "heads").mkdir(parents=True)
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (git_dir / "refs" / "heads" / "main").write_text("abc123def456\n", encoding="utf-8")
    assert get_git_commit_hash(tmp_path) == "abc123def456"


def test_get_git_commit_hash_handles_detached_head(tmp_path: Path) -> None:
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "HEAD").write_text("deadbeefcafef00d\n", encoding="utf-8")
    assert get_git_commit_hash(tmp_path) == "deadbeefcafef00d"


def test_get_git_commit_hash_falls_back_to_packed_refs(tmp_path: Path) -> None:
    # A loose ref file can be absent after `git gc` packs it away.
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (git_dir / "packed-refs").write_text(
        "# pack-refs with: peeled fully-peeled sorted\n"
        "1111222233334444555566667777888899990000 refs/heads/main\n",
        encoding="utf-8",
    )
    assert get_git_commit_hash(tmp_path) == "1111222233334444555566667777888899990000"


def test_get_git_commit_hash_is_unknown_when_ref_unresolvable(tmp_path: Path) -> None:
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    # Neither a loose ref file nor a packed-refs entry exists.
    assert get_git_commit_hash(tmp_path) == UNKNOWN


def test_get_git_commit_hash_against_the_real_repo() -> None:
    # This repository's own .git is present in this environment, so the
    # lookup should succeed and look like a real commit hash rather than
    # falling back to "unknown".
    result = get_git_commit_hash()
    assert result != UNKNOWN
    assert len(result) == 40
    assert all(c in "0123456789abcdef" for c in result)


def test_get_python_version_returns_a_dotted_version_string() -> None:
    version = get_python_version()
    assert version != UNKNOWN
    parts = version.split(".")
    assert len(parts) >= 2
    assert all(part.isdigit() for part in parts[:2])
