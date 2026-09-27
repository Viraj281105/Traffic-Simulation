"""The CLI study runner must report what it measured, in the right units.

Regression: it printed offered demand as rate x 3600 x 4 (four times the real
whole-junction volume that src/study/volume_sweep.py reports), and whenever a
delay crossover existed it printed fixed conclusions ("up to 50% lower delay",
"better queue fairness") that nothing in the run had measured.
"""

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "run_full_study.py"


def _load_cli() -> Any:
    spec = importlib.util.spec_from_file_location("run_full_study_cli", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cli_reports_whole_junction_volume_and_measured_verdict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import src.database.db as db

    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "study.db"))
    cli = _load_cli()
    # A sweep with a guaranteed crossover message path is not cheap to force,
    # so exercise the verdict helper on a crossover directly as well.
    verdict = cli._summarize_sweep_verdict(
        {
            "runs": [{"winner": "roundabout"}, {"winner": "signal"}],
            "curves": {"crossoverArrivalRate": 0.4, "crossoverHourlyVolume": 1440},
        }
    )["text"]
    assert "50%" not in verdict

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_full_study.py",
            "--sweep-duration",
            "2",
            "--validation-duration",
            "2",
            "--num-seeds",
            "2",
            "--rates",
            "0.25",
            "--output-csv",
            str(tmp_path / "report.csv"),
        ],
    )
    assert cli.main() == 0
    out = capsys.readouterr().out
    assert "[900] veh/h (total intersection)" in out  # 0.25 x 3600
    assert "[3600] veh/h" not in out
    assert "up to 50% lower" not in out
    assert "better queue fairness" not in out
