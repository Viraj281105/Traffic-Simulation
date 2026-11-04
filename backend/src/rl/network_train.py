"""PPO training and a small hyper-parameter sweep for the network env (F18, W44).

``train_network`` is one run (budget = ``total_timesteps``). ``tune_ppo`` draws
``trials`` configurations from a small grid with its own seeded generator,
trains each for ``timesteps`` on each of ``train_seeds`` and scores it on
validation seeds that are neither the training seeds nor the held-out
evaluation seeds. Score = mean ``mean_wait_s`` (lower is better). Everything
about the budget is an argument, so a smoke test is seconds and a real sweep
just passes bigger numbers.

Long-budget command (hours; not run in tests)::

    cd backend && .venv/Scripts/python -m src.rl.network_train tune \\
        --trials 12 --timesteps 50000 --train-seeds 0 1 2 --val-seeds 5 \\
        --out ../rl_runs/network-tune --rows 3 --cols 3

    cd backend && .venv/Scripts/python -m src.rl.network_train train \\
        --timesteps 300000 --seed 0 --out ../rl_runs/network \\
        --registry-dir ../rl_registry --rows 3 --cols 3

Needs ``stable-baselines3`` (``backend/requirements-rl.txt``).
"""

from __future__ import annotations

import argparse
import itertools
import json
import random
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

from src.rl.network_env import NetworkSignalEnv, demo_network
from src.rl.tracking import ModelRegistry, start_run
from src.rl.train import default_hyperparams, load_model, make_model

NETWORK_MODEL_NAME = "network-signal-control"
VALIDATION_SEED_BASE = 5_000  # between training seeds (small) and held-out (10000+)

SEARCH_SPACE: Dict[str, Sequence[Any]] = {
    "learning_rate": (1e-4, 3e-4, 1e-3),
    "ent_coef": (0.0, 0.01, 0.03),
    "n_steps": (32, 64, 128),
    "gamma": (0.95, 0.99),
    "hidden": (32, 64),
}


def _write_json(path: Path, data: Any) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, sort_keys=True, default=str)
        f.write("\n")


def _hyperparams(
    total_timesteps: int, overrides: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    over = dict(overrides or {})
    hidden = int(over.pop("hidden", 64))
    hp = default_hyperparams("ppo", total_timesteps, hidden=hidden)
    hp.update(over)
    hp["batch_size"] = min(int(hp["batch_size"]), int(hp["n_steps"]))
    return hp


def train_network(
    total_timesteps: int = 2000,
    seed: int = 0,
    env_kwargs: Optional[Dict[str, Any]] = None,
    hyperparams: Optional[Dict[str, Any]] = None,
    out_dir: Union[str, Path] = "rl_runs",
    run_name: Optional[str] = None,
    tracking_dir: Union[str, Path, None] = None,
    registry_dir: Union[str, Path, None] = None,
    model_name: str = NETWORK_MODEL_NAME,
) -> Dict[str, Any]:
    """Train one PPO agent; save ``<out_dir>/<run_name>/model.zip`` + ``meta.json``."""
    if total_timesteps <= 0:
        raise ValueError("total_timesteps must be positive")
    hp = _hyperparams(total_timesteps, hyperparams)
    run_name = run_name or f"ppo-net-s{seed}-t{total_timesteps}"
    run_dir = Path(out_dir) / run_name
    run_dir.mkdir(parents=True, exist_ok=True)
    env = NetworkSignalEnv(**(env_kwargs or {}))
    env.reset(seed=seed)
    started = time.time()
    with start_run(
        experiment="rl-network-signal-control",
        run_name=run_name,
        tracking_dir=tracking_dir,
        enabled=tracking_dir is not None,
    ) as run:
        run.log_params(
            {"algo": "ppo", "seed": seed, "total_timesteps": total_timesteps}
            | {f"env.{k}": v for k, v in env.params.items() if k != "flows"}
            | {f"hp.{k}": v for k, v in hp.items()}
        )
        model = make_model("ppo", env, seed, hp)  # type: ignore[arg-type]
        model.learn(total_timesteps=total_timesteps)
        model_path = run_dir / "model.zip"
        model.save(str(model_path))
        buf = list(getattr(model, "ep_info_buffer", []) or [])
        train_return = float(sum(e["r"] for e in buf) / len(buf)) if buf else None
        meta: Dict[str, Any] = {
            "algo": "ppo",
            "kind": "network",
            "seed": seed,
            "total_timesteps": total_timesteps,
            "env_kwargs": env.params,
            "hyperparams": hp,
            "model_path": str(model_path),
            "train_seconds": round(time.time() - started, 3),
            "mean_train_return": train_return,
            "mlflow_run_id": run.run_id,
        }
        run.log_metrics({"train_seconds": meta["train_seconds"]})
        if train_return is not None:
            run.log_metrics({"mean_train_return": train_return})
        _write_json(run_dir / "meta.json", meta)
        run.log_artifact(model_path)
        if registry_dir is not None:
            meta["registry_version"] = ModelRegistry(registry_dir).register(
                model_name,
                model_path,
                "ppo",
                metrics={"mean_train_return": train_return}
                if train_return is not None
                else {},
                tags={
                    "seed": str(seed),
                    "timesteps": str(total_timesteps),
                    "kind": "network",
                },
                run_id=run.run_id,
            )
    env.close()
    return meta


def sample_configs(trials: int, seed: int = 0) -> List[Dict[str, Any]]:
    """``trials`` distinct configurations from :data:`SEARCH_SPACE`, seeded."""
    keys = sorted(SEARCH_SPACE)
    grid = [
        dict(zip(keys, vals))
        for vals in itertools.product(*(SEARCH_SPACE[k] for k in keys))
    ]
    rng = random.Random(seed)
    rng.shuffle(grid)
    return grid[: max(0, min(trials, len(grid)))]


def validation_score(
    model: Any, env_kwargs: Optional[Dict[str, Any]], n_seeds: int
) -> float:
    from src.rl.network_eval import evaluate_network_policy, sb3_network_policy

    seeds = [VALIDATION_SEED_BASE + i for i in range(n_seeds)]
    res = evaluate_network_policy(sb3_network_policy(model), seeds, env_kwargs)
    return float(sum(res["mean_wait_s"]) / len(res["mean_wait_s"]))


def tune_ppo(
    trials: int = 4,
    timesteps: int = 2000,
    train_seeds: Sequence[int] = (0, 1),
    val_seeds: int = 3,
    env_kwargs: Optional[Dict[str, Any]] = None,
    out_dir: Union[str, Path] = "rl_runs/tune",
    tune_seed: int = 0,
) -> Dict[str, Any]:
    """Small seeded sweep. Returns ``{"trials": [...], "best": {...}}``.

    The score of a trial is its mean validation ``mean_wait_s`` over the
    training seeds (lower is better); ties go to the earlier trial.
    """
    if trials <= 0 or timesteps <= 0 or not train_seeds or val_seeds <= 0:
        raise ValueError(
            "trials, timesteps, train_seeds and val_seeds must be positive"
        )
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rows: List[Dict[str, Any]] = []
    for i, cfg in enumerate(sample_configs(trials, tune_seed)):
        scores: List[float] = []
        for s in train_seeds:
            meta = train_network(
                timesteps,
                seed=int(s),
                env_kwargs=env_kwargs,
                hyperparams=cfg,
                out_dir=out,
                run_name=f"trial{i}-s{s}",
            )
            model = load_model("ppo", meta["model_path"])
            scores.append(validation_score(model, env_kwargs, val_seeds))
        rows.append(
            {
                "trial": i,
                "config": cfg,
                "seeds": [int(s) for s in train_seeds],
                "scores": scores,
                "mean_score": sum(scores) / len(scores),
            }
        )
    best = min(rows, key=lambda r: (r["mean_score"], r["trial"]))
    result = {
        "metric": "mean_wait_s (validation, lower is better)",
        "timesteps": timesteps,
        "val_seeds": val_seeds,
        "trials": rows,
        "best": best,
    }
    _write_json(out / "tuning.json", result)
    return result


def _env_kwargs_from(args: argparse.Namespace) -> Dict[str, Any]:
    graph, flows = demo_network(args.rows, args.cols, vehicles_per_hour=args.vph)
    return {
        "graph": graph,
        "flows": flows,
        "episode_seconds": args.episode_seconds,
        "decision_interval": args.decision_interval,
    }


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="PPO training / tuning on the network env")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("train", "tune"):
        p = sub.add_parser(name)
        p.add_argument("--rows", type=int, default=2)
        p.add_argument("--cols", type=int, default=2)
        p.add_argument("--vph", type=float, default=450.0)
        p.add_argument("--episode-seconds", type=float, default=300.0)
        p.add_argument("--decision-interval", type=float, default=5.0)
        p.add_argument("--out", default="rl_runs/network")
        p.add_argument("--timesteps", type=int, default=2000)
    t = sub.choices["train"]
    t.add_argument("--seed", type=int, default=0)
    t.add_argument("--registry-dir", default=None)
    t.add_argument("--model-name", default=NETWORK_MODEL_NAME)
    t.add_argument("--tracking-dir", default=None)
    u = sub.choices["tune"]
    u.add_argument("--trials", type=int, default=4)
    u.add_argument("--train-seeds", type=int, nargs="+", default=[0, 1])
    u.add_argument("--val-seeds", type=int, default=3)
    u.add_argument("--tune-seed", type=int, default=0)
    args = ap.parse_args(argv)
    env_kwargs = _env_kwargs_from(args)
    if args.cmd == "train":
        meta = train_network(
            args.timesteps,
            seed=args.seed,
            env_kwargs=env_kwargs,
            out_dir=args.out,
            tracking_dir=args.tracking_dir,
            registry_dir=args.registry_dir,
            model_name=args.model_name,
        )
        print(f"wrote {meta['model_path']}")
    else:
        res = tune_ppo(
            args.trials,
            args.timesteps,
            args.train_seeds,
            args.val_seeds,
            env_kwargs,
            args.out,
            args.tune_seed,
        )
        print(f"best trial {res['best']['trial']}: {res['best']['config']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
