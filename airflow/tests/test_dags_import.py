"""DAG modules must import, and build correct commands, without Airflow.

Run from the repo root:  python -m pytest airflow/tests -q -p no:cacheprovider
(use --no-cov / -c /dev/null style isolation if run from backend/, whose
pyproject adds a coverage gate).
"""

import importlib
import sys
from pathlib import Path

import pytest

DAGS = Path(__file__).resolve().parents[1] / "dags"
sys.path.insert(0, str(DAGS))


def load(name):
    return importlib.import_module(name)


def test_modules_import_without_airflow():
    common = load("urbanflow_common")
    for name in ("nightly_regression", "batch_experiments"):
        mod = load(name)
        if not common.AIRFLOW_AVAILABLE:
            assert mod.dag is None


def test_nightly_command_selects_slow_or_not():
    common = load("urbanflow_common")
    assert "not slow" not in common.nightly_pytest_command(slow=True)
    assert common.nightly_pytest_command(slow=False)[-2:] == ["-m", "not slow"]


def test_multiseed_command(tmp_path):
    common = load("urbanflow_common")
    cmd = common.multiseed_command("roundabout", 3, 45.0, tmp_path / "o.json", base_seed=7)
    assert cmd[1].replace("\\", "/").endswith("airflow/scripts/run_multiseed.py")
    assert cmd[cmd.index("--geometry") + 1] == "roundabout"
    assert cmd[cmd.index("--num-seeds") + 1] == "3"
    assert cmd[cmd.index("--base-seed") + 1] == "7"
    with pytest.raises(ValueError):
        common.multiseed_command("bogus", 3, 45.0, tmp_path / "o.json")
    with pytest.raises(ValueError):
        common.multiseed_command("signal", 0, 45.0, tmp_path / "o.json")


def test_full_study_command_targets_existing_script(tmp_path):
    common = load("urbanflow_common")
    cmd = common.full_study_command(tmp_path / "a.csv", tmp_path / "a.json", 4)
    assert Path(cmd[1]).is_file()
    assert cmd[cmd.index("--num-seeds") + 1] == "4"


def test_batch_params_from_conf():
    batch = load("batch_experiments")

    class Run:
        conf = {"num_seeds": 9, "duration": 12, "base_seed": 3}

    assert batch._params(Run.conf) == {"num_seeds": 9, "duration": 12.0, "base_seed": 3}
    assert batch._params(None)["num_seeds"] == 5


def test_run_raises_on_failure():
    common = load("urbanflow_common")
    with pytest.raises(RuntimeError):
        common.run([sys.executable, "-c", "import sys; sys.exit(3)"])
    assert common.run([sys.executable, "-c", "pass"]) == 0
