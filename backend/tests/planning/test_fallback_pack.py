"""scripts/build_fallback_pack.py: the committed preview fallback pack verifies whatever line
endings the checkout uses, and a changed file is still caught."""

import importlib.util
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "build_fallback_pack.py"
PACK = ROOT / "fallback-pack"


@pytest.fixture(scope="module")
def builder():
    spec = importlib.util.spec_from_file_location("build_fallback_pack", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _copy(tmp_path: Path) -> Path:
    pack = tmp_path / "pack"
    shutil.copytree(PACK, pack)
    return pack


def test_the_committed_pack_verifies(builder):
    assert builder.verify(PACK) == 0


@pytest.mark.parametrize("ending", [b"\n", b"\r\n"])
def test_the_pack_verifies_with_either_line_ending(builder, tmp_path, ending):
    pack = _copy(tmp_path)
    for path in pack.rglob("*"):
        if path.is_file():
            text = path.read_bytes().replace(b"\r\n", b"\n")
            path.write_bytes(text.replace(b"\n", ending))
    assert builder.verify(pack) == 0


def test_a_changed_file_is_caught(builder, tmp_path):
    pack = _copy(tmp_path)
    report = pack / "small-live" / "report.csv"
    report.write_bytes(report.read_bytes().replace(b",", b";", 1))
    assert builder.verify(pack) == 1
