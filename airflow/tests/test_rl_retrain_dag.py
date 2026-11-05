"""The RL retraining DAG module imports without Airflow and builds the right commands."""

import importlib
import sys
from pathlib import Path

import pytest

DAGS = Path(__file__).resolve().parents[1] / "dags"
sys.path.insert(0, str(DAGS))


def load():
    return importlib.import_module("rl_retrain")


def test_imports_without_airflow():
    common = importlib.import_module("urbanflow_common")
    mod = load()
    if not common.AIRFLOW_AVAILABLE:
        assert mod.dag is None


def test_params_defaults_and_conf():
    mod = load()
    assert mod._params(None)["timesteps"] == 20000
    p = mod._params({"timesteps": "500", "seed": 3, "eval_seeds": 4, "rows": 3, "cols": 3})
    assert (p["timesteps"], p["seed"], p["eval_seeds"], p["rows"], p["cols"]) == (500, 3, 4, 3, 3)


def test_retrain_command_per_stage():
    mod = load()
    for stage in mod.STAGES:
        cmd = mod.retrain_command(stage, "run1", {"timesteps": 7, "seed": 2})
        assert cmd[1:4] == ["-m", "src.rl.retrain", stage]
        assert cmd[cmd.index("--timesteps") + 1] == "7"
        assert cmd[cmd.index("--seed") + 1] == "2"
        assert cmd[cmd.index("--work-dir") + 1].replace("\\", "/").endswith("rl/retrain/run1")
        assert "registry" in cmd[cmd.index("--registry-dir") + 1]
    with pytest.raises(ValueError):
        mod.retrain_command("bogus")


def test_run_id_is_made_filesystem_safe():
    mod = load()
    d = mod.work_dir("scheduled__2026-11-01T03:00:00+00:00")
    assert ":" not in d.name and "+" not in d.name


def test_run_stage_invokes_the_command(monkeypatch, tmp_path):
    mod = load()
    seen = []
    monkeypatch.setattr(mod.common, "run", lambda cmd, cwd=None: seen.append(cmd) or 0)
    monkeypatch.setattr(mod.common, "RESULTS_DIR", tmp_path)

    class Run:
        conf = {"timesteps": 11}

    mod.run_train("r1", Run)
    assert seen[0][seen[0].index("--timesteps") + 1] == "11"
