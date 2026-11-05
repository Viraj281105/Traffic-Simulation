"""Evaluate network policies on held-out seeds and compare them (F18, W44).

Every policy runs the *same* episode seeds on the same environment. The output
follows the ``urbanflow-rl-eval`` v1 shape (``policies[name][metric]`` is one
value per seed) so ``scripts/produce_rl_comparison.py`` can wrap it, with one
extra key, ``paired_comparisons``: RL minus each baseline per metric, with the
interval, p-value and a plain-words verdict from
``src.uncertainty.comparison`` (``compare_paired``, ``verdict``).

Nothing here proves the RL policy wins; with few seeds the intervals are wide
and the document says so (``cautions``).
"""

from __future__ import annotations

import platform
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Sequence

import numpy as np

from src.rl.network_baselines import make_baselines
from src.rl.network_env import NetworkSignalEnv
from src.uncertainty.comparison import compare_paired, verdict

METRICS = (
    "mean_wait_s",
    "total_wait_s",
    "stopped_veh_s",
    "mean_queue",
    "throughput",
    "vehicles",
    "switches",
    "episode_return",
    "mean_delay_s",
    "blocked",
)
LOWER_IS_BETTER = [
    "mean_wait_s",
    "total_wait_s",
    "stopped_veh_s",
    "mean_queue",
    "mean_delay_s",
]
# Compared with intervals (the rest are reported per seed only).
COMPARED_METRICS = ("mean_wait_s", "mean_queue", "throughput")
HELD_OUT_SEED_BASE = 10_000  # training seeds are small integers

Act = Callable[[Any, Dict[str, Any]], Any]


def held_out_seeds(n: int, base: int = HELD_OUT_SEED_BASE) -> List[int]:
    return [base + i for i in range(n)]


def evaluate_network_policy(
    act: Act,
    seeds: Sequence[int],
    env_kwargs: Optional[Dict[str, Any]] = None,
    on_reset: Optional[Callable[[], None]] = None,
) -> Dict[str, List[float]]:
    """One episode per seed; ``{metric: [value per seed]}``."""
    env = NetworkSignalEnv(**(env_kwargs or {}))
    out: Dict[str, List[float]] = {m: [] for m in METRICS}
    for seed in seeds:
        obs, info = env.reset(seed=int(seed))
        if on_reset is not None:
            on_reset()
        done = False
        while not done:
            obs, _r, terminated, truncated, info = env.step(act(obs, info))
            done = terminated or truncated
        metrics = env.episode_metrics()
        for m in METRICS:
            out[m].append(float(metrics[m]))
    env.close()
    return out


def sb3_network_policy(model: Any) -> Act:
    def act(obs: Any, info: Dict[str, Any]) -> Any:
        action, _ = model.predict(obs, deterministic=True)
        return np.asarray(action).reshape(-1)

    return act


def paired_comparisons(
    policies: Dict[str, Dict[str, List[float]]],
    rl_names: Sequence[str],
    baseline_names: Sequence[str],
    metrics: Sequence[str] = COMPARED_METRICS,
    method: str = "paired_t",
    confidence: float = 0.95,
) -> List[Dict[str, Any]]:
    """RL (A) minus baseline (B) per metric, over the shared seeds."""
    rows: List[Dict[str, Any]] = []
    for rl in rl_names:
        for base in baseline_names:
            for metric in metrics:
                a, b = policies[rl].get(metric), policies[base].get(metric)
                if not a or not b or len(a) < 2 or len(a) != len(b):
                    continue
                cmp_ = compare_paired(a, b, method=method, confidence=confidence)
                lower = metric in LOWER_IS_BETTER
                rows.append(
                    {
                        "rl": rl,
                        "baseline": base,
                        "metric": metric,
                        "lower_is_better": lower,
                        "comparison": cmp_.to_dict(),
                        "verdict": verdict(cmp_, lower_is_better=lower)
                        .replace("A beats B", f"{rl} beats {base}")
                        .replace("B beats A", f"{base} beats {rl}"),
                    }
                )
    return rows


def compare_network(
    seeds: Sequence[int],
    env_kwargs: Optional[Dict[str, Any]] = None,
    rl_policies: Optional[Dict[str, Act]] = None,
    fixed_green_s: float = 30.0,
    method: str = "paired_t",
    confidence: float = 0.95,
) -> Dict[str, Any]:
    """Fixed-time, max-pressure and any RL policies over the same seeds."""
    probe = NetworkSignalEnv(**(env_kwargs or {}))
    baselines = make_baselines(probe.signal_nodes, fixed_green_s)
    runners: Dict[str, Any] = {n: (b.act, b.reset) for n, b in baselines.items()}
    for name, act in (rl_policies or {}).items():
        runners[name] = (act, None)
    results: Dict[str, Any] = {}
    for name, (act, reset) in runners.items():
        started = time.time()
        results[name] = evaluate_network_policy(act, seeds, env_kwargs, reset)
        results[name]["wall_seconds"] = round(time.time() - started, 3)
    rl_names = list(rl_policies or {})
    cautions: List[str] = []
    if len(seeds) < 5:
        cautions.append(f"only {len(seeds)} held-out seeds: intervals are wide")
    return {
        "format": "urbanflow-rl-eval",
        "version": 1,
        "kind": "network",
        "seeds": [int(s) for s in seeds],
        "env": probe.params,
        "signal_nodes": probe.signal_nodes,
        "baseline_fixed_green_s": fixed_green_s,
        "metrics": list(METRICS),
        "lower_is_better": list(LOWER_IS_BETTER),
        "policies": results,
        "paired_comparisons": paired_comparisons(
            results, rl_names, list(baselines), method=method, confidence=confidence
        ),
        "comparison_method": method,
        "confidence": confidence,
        "cautions": cautions,
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
        },
    }
