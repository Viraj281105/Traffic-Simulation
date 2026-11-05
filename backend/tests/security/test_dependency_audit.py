"""scripts/dependency_audit.py (package 2F): the script's own logic, and the repo's pins."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "dependency_audit.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("dependency_audit", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["dependency_audit"] = module
    spec.loader.exec_module(module)
    return module


audit = _load()


def _run(text: str) -> list:  # type: ignore[type-arg]
    return audit.check_requirements(audit.parse_requirements(text, "r.txt"))


def test_clean_file_has_no_findings() -> None:
    assert _run("fastapi==0.141.1  # web\n\n# comment\nPyJWT==2.15.1\n") == []


def test_unpinned_lines_are_errors() -> None:
    levels = [f.level for f in _run("a>=1.0\nb\nc~=2.0\nd==1.0\n")]
    assert levels == ["error", "error", "error"]


def test_duplicates_are_detected_after_normalisation() -> None:
    found = _run("typing_extensions==4.0\nTyping-Extensions==4.1\n")
    assert any("listed twice" in f.message for f in found)


def test_curated_risks_use_version_order_not_string_order() -> None:
    assert any("below" in f.message for f in _run("requests==2.9.0\n"))
    assert not _run("requests==2.33.1\n")
    assert not _run("urllib3==2.10.0\n")
    assert any(f.level == "error" for f in _run("python-jose==3.3.0\n"))


def test_installed_comparison() -> None:
    reqs = audit.parse_requirements("alpha==1.0\nbeta==2.0\ngamma==3.0\n", "r.txt")
    found = audit.compare_installed(reqs, {"alpha": "1.0", "beta": "2.1"})
    assert [(f.level, f.message.split()[0]) for f in found] == [
        ("error", "beta"),
        ("warning", "gamma"),
    ]


def test_every_risk_entry_has_a_date_and_note() -> None:
    for risk in audit.RISKY:
        assert risk.added.startswith("20") and len(risk.note) > 10
        assert risk.severity in ("error", "warning")


@pytest.mark.parametrize("name", ["requirements.txt", "requirements-dev.txt"])
def test_repository_requirements_are_pinned_without_duplicates(name: str) -> None:
    path = REPO / "backend" / name
    reqs = audit.parse_requirements(path.read_text(encoding="utf-8"), name)
    assert len(reqs) > 5
    errors = [f for f in audit.check_requirements(reqs) if f.level == "error"]
    assert not errors, "\n".join(str(f) for f in errors)


def test_script_runs_offline_and_exits_zero_on_the_runtime_file() -> None:
    assert audit.main([str(REPO / "backend" / "requirements.txt")]) == 0
