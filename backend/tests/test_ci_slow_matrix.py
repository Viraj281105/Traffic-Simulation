"""Every file that holds ``@pytest.mark.slow`` tests runs in CI.

The default CI job deselects slow tests (``-m "not slow"``) and the
``backend-slow-tests`` job runs them file by file from an explicit matrix. A
file missing from that matrix therefore runs nowhere, silently: until the
V2.0 release-gate audit, five files holding 155 of the 190 slow tests were in
that state. This fast test fails the ordinary PR job instead.
"""

import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
WORKFLOW = BACKEND.parent / ".github" / "workflows" / "ci.yml"
# Decorator, module-level ``pytestmark`` and per-case ``marks=`` (pytest.param)
# forms. The last was missed until 2026-10-19, when a file marking only some
# parametrised cases slow would have passed this check with no matrix entry.
SLOW_MARK = re.compile(
    r"^\s*(@pytest\.mark\.slow|pytestmark\s*=.*slow)|marks\s*=[^\n]*pytest\.mark\.slow",
    re.M,
)


def _files_with_slow_tests() -> set[str]:
    return {
        path.relative_to(BACKEND).as_posix()
        for path in (BACKEND / "tests").rglob("test_*.py")
        # This file holds no slow tests, only examples of the marker.
        if path.resolve() != Path(__file__).resolve()
        and SLOW_MARK.search(path.read_text(encoding="utf-8"))
    }


def _slow_matrix_paths() -> set[str]:
    text = WORKFLOW.read_text(encoding="utf-8")
    job = text[text.index("backend-slow-tests:") :]
    job = job[: job.index("\n  frontend-lint-test:")]
    return set(re.findall(r"^\s*path:\s*(\S+)\s*$", job, re.M))


def test_every_slow_test_file_is_in_the_ci_slow_matrix() -> None:
    files = _files_with_slow_tests()
    assert files, "no slow tests found: the marker scan is broken"
    missing = files - _slow_matrix_paths()
    assert not missing, (
        f"{sorted(missing)} hold @pytest.mark.slow tests but are not in the "
        "backend-slow-tests matrix of .github/workflows/ci.yml, so they run "
        "in no CI job"
    )


def test_the_slow_matrix_names_only_real_files() -> None:
    for path in _slow_matrix_paths():
        assert (BACKEND / path).is_file(), path


def test_the_marker_scan_recognises_every_form_of_the_slow_mark() -> None:
    for source in (
        "@pytest.mark.slow\ndef test_x(): ...",
        "pytestmark = [pytest.mark.slow]",
        "pytest.param(1, marks=pytest.mark.slow)",
        'pytest.param(c, marks=() if c["fast"] else (pytest.mark.slow,))',
    ):
        assert SLOW_MARK.search(source), source
    assert not SLOW_MARK.search("pytest.param(1, marks=pytest.mark.unit)")
