"""Optional MLflow tracking and the file-based model registry."""

import pytest

from src.rl import tracking
from src.rl.tracking import ModelRegistry, start_run


def _model(tmp_path, name="m.zip", content=b"weights"):
    p = tmp_path / name
    p.write_bytes(content)
    return p


def test_registry_versions_stages_and_resolve(tmp_path):
    reg = ModelRegistry(tmp_path / "reg")
    assert reg.register("sig", _model(tmp_path), "dqn", metrics={"r": -1.0}) == 1
    assert reg.register("sig", _model(tmp_path, "n.zip", b"two"), "dqn") == 2
    assert reg.versions("sig") == [1, 2]
    assert reg.resolve("sig").read_bytes() == b"two"
    assert reg.resolve("sig", 1).read_bytes() == b"weights"
    reg.set_stage("sig", 1, "production")
    assert reg.resolve("sig", "production").read_bytes() == b"weights"
    reg.set_stage("sig", 2, "production")  # one production version only
    assert reg.stage_of("sig", 1) == "archived"
    assert reg.metadata("sig", 1)["metrics"] == {"r": -1.0}
    with pytest.raises(KeyError):
        reg.resolve("sig", "staging")
    with pytest.raises(KeyError):
        reg.resolve("missing")
    with pytest.raises(ValueError):
        reg.set_stage("sig", 1, "bogus")
    assert ModelRegistry(tmp_path / "reg").versions("sig") == [1, 2]  # persisted


def test_disabled_run_is_a_collecting_noop(tmp_path):
    with start_run(tracking_dir=None) as run:
        run.log_params({"a": 1})
        run.log_metrics({"m": 2.0})
    assert not run.active and run.params == {"a": 1} and run.metrics == {"m": [2.0]}
    assert not (tmp_path / "mlruns").exists()


def test_file_based_mlflow_run(tmp_path):
    pytest.importorskip("mlflow")
    assert tracking.mlflow_available()
    with start_run(tracking_dir=tmp_path / "mlruns", run_name="t") as run:
        run.log_params({"algo": "dqn"})
        run.log_metrics({"loss": 0.5}, step=1)
    assert run.active and run.run_id
    assert (tmp_path / "mlruns").is_dir()
