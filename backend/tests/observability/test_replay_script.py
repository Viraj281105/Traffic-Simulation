"""The Redpanda replay script: parsing and dry run (package 1D). No broker needed."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import List, Tuple

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "replay_to_redpanda.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("replay_script", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


replay = _load()

CSV = "Link_ID,interval_start,count,sensor_id\nL1,0,12,s1\nL2,0,x,s2\nL1,30,7,s1\n,30,1,s3\n"


def _file(tmp_path: Path, text: str = CSV) -> Path:
    p = tmp_path / "obs.csv"
    p.write_text(text, encoding="utf-8")
    return p


def test_read_rows_skips_bad_rows_and_keeps_extra_columns(tmp_path: Path) -> None:
    rows = list(replay.read_rows(_file(tmp_path)))
    assert [r["link_id"] for r in rows] == ["L1", "L1"]
    assert rows[0] == {
        "link_id": "L1",
        "interval_start": "0",
        "count": 12.0,
        "sensor_id": "s1",
    }


def test_missing_required_column_exits(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        list(replay.read_rows(_file(tmp_path, "link_id,count\nL1,1\n")))


def test_replay_sends_keyed_json_with_sequence_and_loops(tmp_path: Path) -> None:
    rows = list(replay.read_rows(_file(tmp_path)))
    sent: List[Tuple[str, bytes]] = []
    n = replay.replay(rows, lambda k, v: sent.append((k, v)), loop=2)
    assert n == 4 and [k for k, _ in sent] == ["L1"] * 4
    assert json.loads(sent[3][1])["seq"] == 3


def test_rate_throttles_via_injected_sleep(tmp_path: Path) -> None:
    rows = list(replay.read_rows(_file(tmp_path)))
    naps: List[float] = []
    replay.replay(rows, lambda k, v: None, rate=4.0, sleep=naps.append)
    assert naps == [0.25, 0.25]


def test_dry_run_prints_and_needs_no_client(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert replay.main([str(_file(tmp_path)), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert out.count("[dry-run] urbanflow.observations key=L1") == 2
    assert "would publish 2 message(s)" in out
