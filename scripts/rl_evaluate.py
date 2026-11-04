"""Compare RL policies with fixed-time and max-pressure over several seeds (F18).

    python scripts/rl_evaluate.py --model rl_runs/dqn-s0-t20000/model.zip --algo dqn \
        --seeds 20 --out rl_eval.json

``--registry-dir/--model-name`` (with optional ``--stage``) loads a registered
model instead of ``--model``. Without any model only the two baselines run.
Seeds are held out from training (default base 10000). The JSON holds one
value per seed for every metric and policy and nothing else: confidence
intervals and tests are computed by the F6 statistics, not here.
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
    ap.add_argument("--algo", choices=("dqn", "ppo"), default="dqn")
    ap.add_argument("--registry-dir", default=None)
    ap.add_argument("--model-name", default="signal-control")
    ap.add_argument("--stage", default=None, help="stage or version (default latest)")
    ap.add_argument("--seeds", type=int, default=10, help="number of held-out seeds")
    ap.add_argument("--seed-base", type=int, default=10_000)
    ap.add_argument("--out", default="rl_eval.json")
    ap.add_argument("--fixed-green", type=float, default=30.0)
    ap.add_argument("--vph", type=float, default=400.0)
    ap.add_argument("--lanes", type=int, default=1)
    ap.add_argument("--ns-share", type=float, default=1.0)
    ap.add_argument("--episode-seconds", type=float, default=300.0)
    ap.add_argument("--decision-interval", type=float, default=5.0)
    args = ap.parse_args(argv)

    from src.rl.evaluate import compare, held_out_seeds, sb3_policy

    env_kwargs = {
        "vehicles_per_hour": args.vph,
        "lanes": args.lanes,
        "ns_share": args.ns_share,
        "episode_seconds": args.episode_seconds,
        "decision_interval": args.decision_interval,
    }
    policies = {}
    paths = list(args.model)
    if args.registry_dir:
        from src.rl.tracking import ModelRegistry

        paths.append(
            str(ModelRegistry(args.registry_dir).resolve(args.model_name, args.stage))
        )
    if paths:
        try:
            from src.rl.train import load_model
        except ImportError as exc:
            print(f"RL dependencies missing ({exc}); pip install -r backend/requirements-rl.txt")
            return 2
        for i, path in enumerate(paths):
            name = f"rl_{args.algo}" if len(paths) == 1 else f"rl_{args.algo}_{i}"
            policies[name] = sb3_policy(load_model(args.algo, path))

    result = compare(
        held_out_seeds(args.seeds, args.seed_base),
        env_kwargs,
        policies,
        fixed_green_s=args.fixed_green,
    )
    result["models"] = paths
    Path(args.out).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {args.out}: {len(result['seeds'])} seeds, policies {list(result['policies'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
