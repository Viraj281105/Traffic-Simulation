"""Evaluate policies on held-out seeds and emit per-seed results.

Every policy is run on *the same* episode seeds (paired by seed), against an
environment built from the same parameters; baselines are not tuned here.
Output is raw per-seed arrays only; intervals and tests are computed elsewhere
(F6 statistics).

``evaluate_policy`` needs only the environment (gymnasium/numpy); an RL policy
is any callable ``(obs, info) -> action`` -- :func:`sb3_policy` adapts a saved
stable-baselines3 model.
"""

from __future__ import annotations

import platform
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Sequence

from src.rl.baselines import FixedTimePolicy, MaxPressurePolicy
from src.rl.env import SignalControlEnv

METRICS = (
    "mean_wait_s",
    "total_wait_s",
    "stopped_veh_s",
    "mean_queue",
    "throughput",
    "vehicles",
    "switches",
    "episode_return",
)
# Seeds used for training are small integers; held-out evaluation starts here.
HELD_OUT_SEED_BASE = 10_000


def held_out_seeds(n: int, base: int = HELD_OUT_SEED_BASE) -> List[int]:
    return [base + i for i in range(n)]


def evaluate_policy(
    act: Callable[[Any, Dict[str, Any]], int],
    seeds: Sequence[int],
    env_kwargs: Optional[Dict[str, Any]] = None,
    on_reset: Optional[Callable[[], None]] = None,
) -> Dict[str, List[float]]:
    """Run one episode per seed; return ``{metric: [value per seed]}``."""
    env = SignalControlEnv(**(env_kwargs or {}))
    out: Dict[str, List[float]] = {m: [] for m in METRICS}
    for seed in seeds:
        obs, info = env.reset(seed=int(seed))
        if on_reset is not None:
            on_reset()
        total = 0.0
        done = False
        while not done:
            obs, reward, terminated, truncated, info = env.step(act(obs, info))
            total += reward
            done = terminated or truncated
        metrics = env.episode_metrics()
        metrics["episode_return"] = total
        for m in METRICS:
            out[m].append(float(metrics[m]))
    env.close()
    return out


def sb3_policy(model: Any) -> Callable[[Any, Dict[str, Any]], int]:
    def act(obs: Any, info: Dict[str, Any]) -> int:
        action, _ = model.predict(obs, deterministic=True)
        return int(action)

    return act


def compare(
    seeds: Sequence[int],
    env_kwargs: Optional[Dict[str, Any]] = None,
    rl_policies: Optional[Dict[str, Callable[[Any, Dict[str, Any]], int]]] = None,
    fixed_green_s: float = 30.0,
) -> Dict[str, Any]:
    """Fixed-time, max-pressure and any RL policies over the same seeds."""
    policies: Dict[str, Any] = {}
    fixed = FixedTimePolicy(fixed_green_s)
    policies[fixed.name] = (fixed.act, fixed.reset)
    mp = MaxPressurePolicy()
    policies[mp.name] = (mp.act, mp.reset)
    for name, act in (rl_policies or {}).items():
        policies[name] = (act, None)

    results: Dict[str, Any] = {}
    for name, (act, reset) in policies.items():
        started = time.time()
        results[name] = evaluate_policy(act, seeds, env_kwargs, reset)
        results[name]["wall_seconds"] = round(time.time() - started, 3)
    probe = SignalControlEnv(**(env_kwargs or {}))
    return {
        "format": "urbanflow-rl-eval",
        "version": 1,
        "seeds": [int(s) for s in seeds],
        "env": probe.params,
        "baseline_fixed_green_s": fixed_green_s,
        "metrics": list(METRICS),
        "lower_is_better": [
            "mean_wait_s",
            "total_wait_s",
            "stopped_veh_s",
            "mean_queue",
        ],
        "policies": results,
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
        },
    }
