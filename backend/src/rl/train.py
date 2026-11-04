"""DQN and PPO training for :class:`SignalControlEnv` (stable-baselines3).

``train`` is short and fully configurable: the step budget, network size and
the main hyper-parameters are arguments, so a smoke test trains in seconds and a
real run just passes a larger ``total_timesteps``. Training is reproducible for a
fixed ``seed`` on one machine (CPU torch); the environment seeds every episode
from it.

Needs ``stable-baselines3`` (``backend/requirements-rl.txt``).
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional, Union

from src.rl.env import SignalControlEnv
from src.rl.tracking import ModelRegistry, start_run

ALGOS = ("dqn", "ppo")


def default_hyperparams(algo: str, total_timesteps: int, hidden: int = 64) -> Dict[str, Any]:
    """Hyper-parameters scaled to the budget (small budgets get small buffers)."""
    net = {"net_arch": [hidden, hidden]}
    if algo == "dqn":
        return {
            "learning_rate": 1e-3,
            "buffer_size": max(1000, min(50_000, total_timesteps * 2)),
            "learning_starts": max(10, min(500, total_timesteps // 4)),
            "batch_size": 32,
            "gamma": 0.99,
            "train_freq": 4,
            "target_update_interval": max(50, min(500, total_timesteps // 4)),
            "exploration_fraction": 0.4,
            "exploration_final_eps": 0.05,
            "policy_kwargs": net,
        }
    if algo == "ppo":
        n_steps = max(16, min(256, total_timesteps // 2))
        return {
            "learning_rate": 3e-4,
            "n_steps": n_steps,
            "batch_size": min(64, n_steps),
            "n_epochs": 5,
            "gamma": 0.99,
            "gae_lambda": 0.95,
            "ent_coef": 0.01,
            "policy_kwargs": net,
        }
    raise ValueError(f"algo must be one of {ALGOS}")


def make_model(algo: str, env: SignalControlEnv, seed: int, hyperparams: Dict[str, Any]) -> Any:
    from stable_baselines3 import DQN, PPO

    cls = {"dqn": DQN, "ppo": PPO}[algo]
    return cls("MlpPolicy", env, seed=seed, device="cpu", verbose=0, **hyperparams)


def load_model(algo: str, path: Union[str, Path]) -> Any:
    from stable_baselines3 import DQN, PPO

    cls = {"dqn": DQN, "ppo": PPO}[algo]
    return cls.load(str(path), device="cpu")


def train(
    algo: str,
    total_timesteps: int = 2000,
    seed: int = 0,
    env_kwargs: Optional[Dict[str, Any]] = None,
    hyperparams: Optional[Dict[str, Any]] = None,
    out_dir: Union[str, Path] = "rl_runs",
    run_name: Optional[str] = None,
    tracking_dir: Union[str, Path, None] = None,
    registry_dir: Union[str, Path, None] = None,
    model_name: str = "signal-control",
) -> Dict[str, Any]:
    """Train one agent; save ``<out_dir>/<run_name>/model.zip`` and metadata.

    ``tracking_dir`` (file-based MLflow store) turns tracking on when MLflow is
    installed; ``registry_dir`` registers the result as a new version of
    ``model_name``. Returns the metadata dict that is also written as JSON.
    """
    algo = algo.lower()
    if algo not in ALGOS:
        raise ValueError(f"algo must be one of {ALGOS}")
    if total_timesteps <= 0:
        raise ValueError("total_timesteps must be positive")
    env_kwargs = dict(env_kwargs or {})
    hp = default_hyperparams(algo, total_timesteps)
    hp.update(hyperparams or {})
    run_name = run_name or f"{algo}-s{seed}-t{total_timesteps}"
    run_dir = Path(out_dir) / run_name
    run_dir.mkdir(parents=True, exist_ok=True)

    env = SignalControlEnv(**env_kwargs)
    env.reset(seed=seed)
    started = time.time()
    with start_run(
        run_name=run_name, tracking_dir=tracking_dir, enabled=tracking_dir is not None
    ) as run:
        run.log_params(
            {"algo": algo, "seed": seed, "total_timesteps": total_timesteps}
            | {f"env.{k}": v for k, v in env.params.items()}
            | {f"hp.{k}": v for k, v in hp.items()}
        )
        model = make_model(algo, env, seed, hp)
        model.learn(total_timesteps=total_timesteps)
        model_path = run_dir / "model.zip"
        model.save(str(model_path))

        # Training-curve summary from the algorithm's own episode buffer.
        buf = list(getattr(model, "ep_info_buffer", []) or [])
        train_return = float(sum(e["r"] for e in buf) / len(buf)) if buf else None
        meta: Dict[str, Any] = {
            "algo": algo,
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
        with open(run_dir / "meta.json", "w", encoding="utf-8", newline="\n") as f:
            json.dump(meta, f, indent=2, sort_keys=True, default=str)
            f.write("\n")
        run.log_artifact(model_path)
        if registry_dir is not None:
            meta["registry_version"] = ModelRegistry(registry_dir).register(
                model_name,
                model_path,
                algo,
                metrics={"mean_train_return": train_return}
                if train_return is not None
                else {},
                tags={"seed": str(seed), "timesteps": str(total_timesteps)},
                run_id=run.run_id,
            )
    env.close()
    return meta
