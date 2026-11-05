"""Training smoke tests with a tiny budget, registry hand-off and the scripts."""

import json
from pathlib import Path

import pytest

pytest.importorskip("numpy")
pytest.importorskip("gymnasium")
pytest.importorskip("stable_baselines3")

from src.rl.evaluate import evaluate_policy, held_out_seeds, sb3_policy  # noqa: E402
from src.rl.tracking import ModelRegistry  # noqa: E402
from src.rl.train import load_model, train  # noqa: E402

ENV = {"episode_seconds": 30.0, "decision_interval": 5.0, "vehicles_per_hour": 500.0}
SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"


@pytest.mark.parametrize("algo", ["dqn", "ppo"])
def test_tiny_training_run_saves_a_loadable_model(tmp_path, algo):
    meta = train(
        algo,
        total_timesteps=36,
        seed=1,
        env_kwargs=ENV,
        out_dir=tmp_path,
        registry_dir=tmp_path / "reg",
    )
    assert Path(meta["model_path"]).is_file()
    assert meta["registry_version"] == 1
    model = load_model(algo, meta["model_path"])
    res = evaluate_policy(sb3_policy(model), held_out_seeds(1), ENV)
    assert len(res["mean_wait_s"]) == 1
    assert ModelRegistry(tmp_path / "reg").resolve("signal-control").is_file()


def test_unknown_algo_and_budget_rejected(tmp_path):
    with pytest.raises(ValueError):
        train("a2c", out_dir=tmp_path)
    with pytest.raises(ValueError):
        train("dqn", total_timesteps=0, out_dir=tmp_path)


def test_scripts_train_then_evaluate(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    import rl_evaluate
    import rl_train

    common = ["--vph", "500", "--episode-seconds", "30"]
    train_args = [
        "--algo",
        "dqn",
        "--timesteps",
        "36",
        "--out",
        str(tmp_path),
        "--run-name",
        "r",
    ]
    assert rl_train.main(train_args + common) == 0
    out = tmp_path / "eval.json"
    eval_args = [
        "--model",
        str(tmp_path / "r" / "model.zip"),
        "--seeds",
        "2",
        "--out",
        str(out),
    ]
    assert rl_evaluate.main(eval_args + common) == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert len(data["seeds"]) == 2
    assert set(data["policies"]) == {"fixed_time", "max_pressure", "rl_dqn"}
    assert all(len(v["mean_wait_s"]) == 2 for k, v in data["policies"].items())
