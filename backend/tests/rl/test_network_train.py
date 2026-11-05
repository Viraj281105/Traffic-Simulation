"""Tiny-budget network training, tuning, registry promotion, retrain stages and the CLI."""

import json
from pathlib import Path

import pytest

pytest.importorskip("numpy")
pytest.importorskip("gymnasium")
pytest.importorskip("stable_baselines3")

from src.rl.network_train import sample_configs, train_network, tune_ppo  # noqa: E402
from src.rl.retrain import stage_evaluate, stage_promote, stage_train  # noqa: E402
from src.rl.tracking import ModelRegistry  # noqa: E402

ENV = {"episode_seconds": 20.0, "decision_interval": 5.0}
SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"


def test_train_network_saves_and_registers(tmp_path):
    meta = train_network(
        32, seed=1, env_kwargs=ENV, out_dir=tmp_path, registry_dir=tmp_path / "reg"
    )
    assert Path(meta["model_path"]).is_file() and meta["registry_version"] == 1
    reg = ModelRegistry(tmp_path / "reg")
    assert reg.load_model("network-signal-control") is not None
    with pytest.raises(ValueError):
        train_network(0, out_dir=tmp_path)


def test_sample_configs_seeded_and_distinct():
    a, b = sample_configs(5, seed=1), sample_configs(5, seed=1)
    assert a == b and len({json.dumps(c, sort_keys=True) for c in a}) == 5
    assert sample_configs(5, seed=2) != a


def test_tune_ppo_picks_lowest_score(tmp_path):
    res = tune_ppo(
        trials=2,
        timesteps=32,
        train_seeds=(0,),
        val_seeds=1,
        env_kwargs=ENV,
        out_dir=tmp_path,
    )
    assert len(res["trials"]) == 2
    assert res["best"]["mean_score"] == min(t["mean_score"] for t in res["trials"])
    assert (tmp_path / "tuning.json").is_file()


def test_registry_promote_and_history(tmp_path):
    src = tmp_path / "m.zip"
    src.write_bytes(b"x")
    reg = ModelRegistry(tmp_path / "reg")
    v1 = reg.register("m", src, "ppo", metrics={"w": 10.0})
    v2 = reg.register("m", src, "ppo", metrics={"w": 12.0})
    v3 = reg.register("m", src, "ppo", metrics={"w": 8.0})
    assert reg.promote_if_better("m", v1, "w")["promoted"]  # no incumbent
    assert not reg.promote_if_better("m", v2, "w")["promoted"]
    assert reg.promote_if_better("m", v3, "w")["promoted"]
    assert reg.stage_version("m") == v3 and reg.stage_of("m", v1) == "archived"
    assert reg.resolve("m", "production").parent.name == "v3"
    assert [h["version"] for h in reg.history("m")] == [v1, v3]
    assert not reg.promote_if_better("m", v3, "missing")["promoted"]


def test_retrain_stages_train_evaluate_promote(tmp_path):
    work, reg = tmp_path / "w", tmp_path / "reg"
    stage_train(work, reg, 32, 0, ENV)
    doc = stage_evaluate(work, reg, 2, ENV)
    assert "rl_candidate" in doc["policies"] and "rl_production" not in doc["policies"]
    assert stage_promote(work, reg)["promoted"]  # first model becomes production
    stage_train(work, reg, 32, 1, ENV)
    doc2 = stage_evaluate(work, reg, 2, ENV)
    assert {"rl_candidate", "rl_production"} <= set(doc2["policies"])
    decision = stage_promote(work, reg)
    assert decision["promoted"] == (decision["candidate"] < decision["incumbent"])
    with pytest.raises(RuntimeError):
        stage_train(work, reg, 32, 2, ENV)
        stage_promote(work, reg)


def test_cli_script_and_produce_comparison_wrap(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    import produce_rl_comparison
    import rl_network_evaluate

    from src.rl.network_train import main as train_main

    common = ["--episode-seconds", "20"]
    assert (
        train_main(
            [
                "train",
                "--timesteps",
                "32",
                "--out",
                str(tmp_path / "r"),
                "--registry-dir",
                str(tmp_path / "reg"),
            ]
            + common
        )
        == 0
    )
    out = tmp_path / "eval.json"
    assert (
        rl_network_evaluate.main(
            ["--registry-dir", str(tmp_path / "reg"), "--seeds", "3", "--out", str(out)]
            + common
        )
        == 0
    )
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert set(doc["policies"]) == {"fixed_time", "max_pressure", "rl_ppo"}
    wrapped = produce_rl_comparison.build_rl_doc(
        junction="2x2 demo grid",
        metric="mean_wait_s",
        rl_policy="rl_ppo",
        rl_label="PPO",
        policy_id="network-signal-control/1",
        algorithm="PPO",
        training_steps=32,
        scenarios=[("base", "Base demand", doc)],
    )
    from src.insights.rl_view import build_rl_comparison

    view = build_rl_comparison("t", wrapped)
    assert view is not None
