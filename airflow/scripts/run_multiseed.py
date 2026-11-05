#!/usr/bin/env python3
"""Run one multi-seed study and write the result as JSON.

Thin CLI over ``src.study.multiseed.run_multi_seed`` so Airflow (and the
nightly GitHub workflow) can call it as a subprocess without a running API.
Exit status is 0 on success, 1 if any seed hit the vehicle limit and
``--fail-on-limit`` is set, 2 on bad input.

Usage:
    PYTHONPATH=backend python airflow/scripts/run_multiseed.py \
        --geometry signal --num-seeds 5 --duration 60 --output out.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
for p in (REPO_ROOT, BACKEND_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


def parse_args(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--geometry", default="signal", choices=["signal", "roundabout"])
    ap.add_argument("--num-seeds", type=int, default=5)
    ap.add_argument("--duration", type=float, default=60.0)
    ap.add_argument("--base-seed", type=int, default=None)
    ap.add_argument("--output", required=True, help="path of the JSON result")
    ap.add_argument("--fail-on-limit", action="store_true")
    return ap.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.num_seeds < 1 or args.duration <= 0:
        print("num-seeds must be >= 1 and duration > 0", file=sys.stderr)
        return 2
    from src.study.multiseed import run_multi_seed

    result = run_multi_seed(
        geometry=args.geometry,
        num_seeds=args.num_seeds,
        duration=args.duration,
        base_seed=args.base_seed,
    )
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(f"wrote {out} ({args.num_seeds} seeds, {args.geometry})")
    if args.fail_on_limit and result.get("vehicleLimitReachedSeeds"):
        seeds = result["vehicleLimitReachedSeeds"]
        print(f"vehicle limit reached for seeds {seeds}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
