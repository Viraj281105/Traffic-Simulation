"""Train a DQN or PPO signal controller on one junction (F18).

    python scripts/rl_train.py --algo dqn --timesteps 20000 --seed 0 \
        --out rl_runs --tracking-dir mlruns --registry-dir rl_registry

Needs ``backend/requirements-rl.txt``. MLflow tracking is used only when a
``--tracking-dir`` is given *and* mlflow is installed (file-based store, no
server). ``--registry-dir`` registers the trained model as a new version.
Environment options mirror ``SignalControlEnv``.
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
    ap.add_argument("--algo", choices=("dqn", "ppo"), default="dqn")
    ap.add_argument("--timesteps", type=int, default=20_000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="rl_runs")
    ap.add_argument("--run-name", default=None)
    ap.add_argument("--tracking-dir", default=None)
    ap.add_argument("--registry-dir", default=None)
    ap.add_argument("--model-name", default="signal-control")
    ap.add_argument("--vph", type=float, default=400.0, help="veh/h per approach")
    ap.add_argument("--lanes", type=int, default=1)
    ap.add_argument("--ns-share", type=float, default=1.0)
    ap.add_argument("--episode-seconds", type=float, default=300.0)
    ap.add_argument("--decision-interval", type=float, default=5.0)
    ap.add_argument("--reward-mode", choices=("delay", "queue"), default="delay")
    args = ap.parse_args(argv)

    try:
        from src.rl.train import train
    except ImportError as exc:
        print(f"RL dependencies missing ({exc}); pip install -r backend/requirements-rl.txt")
        return 2

    meta = train(
        args.algo,
        args.timesteps,
        args.seed,
        env_kwargs={
            "vehicles_per_hour": args.vph,
            "lanes": args.lanes,
            "ns_share": args.ns_share,
            "episode_seconds": args.episode_seconds,
            "decision_interval": args.decision_interval,
            "reward_mode": args.reward_mode,
        },
        out_dir=args.out,
        run_name=args.run_name,
        tracking_dir=args.tracking_dir,
        registry_dir=args.registry_dir,
        model_name=args.model_name,
    )
    print(json.dumps(meta, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
