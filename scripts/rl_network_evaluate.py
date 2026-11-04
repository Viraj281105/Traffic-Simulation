"""Compare a network RL policy with fixed-time and max-pressure over held-out seeds (F18).

    python scripts/rl_network_evaluate.py --model rl_runs/network/ppo-net-s0-t300000/model.zip \
        --rows 3 --cols 3 --seeds 20 --out rl_network_eval.json

``--registry-dir/--model-name`` (optional ``--stage``) loads a registered model
instead of ``--model``. Without any model only the two baselines run. The JSON
is in the ``urbanflow-rl-eval`` shape (one value per seed per metric and
policy), so ``scripts/produce_rl_comparison.py`` can wrap it, plus
``paired_comparisons``: RL minus each baseline with a confidence interval,
p-value and verdict from ``src/uncertainty/comparison.py``. Seeds are held out
from training (default base 10000). Small seed counts give wide intervals.

Wrap for the /rl/comparisons endpoint:

    python scripts/produce_rl_comparison.py --id ppo-network --junction "3x3 grid" \
        --scenario base="Base demand"=rl_network_eval.json --rl-policy rl_ppo \
        --rl-label PPO --policy-id network-signal-control/1 --algorithm PPO \
        --training-steps 300000 --fixed-label "Fixed time, 30 s green"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def main(argv: "list[str] | None" = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--model", action="append", default=[], help="model.zip (repeatable)")
    ap.add_argument("--registry-dir", default=None)
    ap.add_argument("--model-name", default="network-signal-control")
    ap.add_argument("--stage", default=None, help="stage or version (default latest)")
    ap.add_argument("--seeds", type=int, default=10, help="number of held-out seeds")
    ap.add_argument("--seed-base", type=int, default=10_000)
    ap.add_argument("--method", choices=("paired_t", "paired_bootstrap"), default="paired_t")
    ap.add_argument("--confidence", type=float, default=0.95)
    ap.add_argument("--out", default="rl_network_eval.json")
    ap.add_argument("--fixed-green", type=float, default=30.0)
    ap.add_argument("--rows", type=int, default=2)
    ap.add_argument("--cols", type=int, default=2)
    ap.add_argument("--vph", type=float, default=450.0)
    ap.add_argument("--episode-seconds", type=float, default=300.0)
    ap.add_argument("--decision-interval", type=float, default=5.0)
    args = ap.parse_args(argv)

    from src.rl.network_env import demo_network
    from src.rl.network_eval import compare_network, held_out_seeds, sb3_network_policy

    graph, flows = demo_network(args.rows, args.cols, vehicles_per_hour=args.vph)
    env_kwargs = {
        "graph": graph,
        "flows": flows,
        "episode_seconds": args.episode_seconds,
        "decision_interval": args.decision_interval,
    }
    paths = list(args.model)
    if args.registry_dir:
        from src.rl.tracking import ModelRegistry

        paths.append(str(ModelRegistry(args.registry_dir).resolve(args.model_name, args.stage)))
    policies = {}
    if paths:
        try:
            from src.rl.train import load_model
        except ImportError as exc:
            print(f"RL dependencies missing ({exc}); pip install -r backend/requirements-rl.txt")
            return 2
        for i, path in enumerate(paths):
            name = "rl_ppo" if len(paths) == 1 else f"rl_ppo_{i}"
            policies[name] = sb3_network_policy(load_model("ppo", path))

    result = compare_network(
        held_out_seeds(args.seeds, args.seed_base),
        env_kwargs,
        policies,
        fixed_green_s=args.fixed_green,
        method=args.method,
        confidence=args.confidence,
    )
    result["models"] = paths
    Path(args.out).write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"wrote {args.out}: {len(result['seeds'])} seeds, policies {list(result['policies'])}")
    for row in result["paired_comparisons"]:
        if row["metric"] == "mean_wait_s":
            print(f"  {row['verdict']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
