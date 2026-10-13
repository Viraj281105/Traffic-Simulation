"""Does a third (merging) approach lane add capacity to a two-lane roundabout?

Evidence for the V2.0 release-gate classification of the two slow failures of
``test_capacity_rises_with_lanes[2|3-roundabout]`` (docs/research/validation.md
§4.4, K1). Runs the test's own harness (5,400 veh/h, 240 s) with 2 and 3
approach lanes for each seed and reports the paired difference.

    python scripts/roundabout_lane_experiment.py [--seeds 20] [--workers 8]

Recorded result (2026-10-12, 20 seeds): mean 98.65 vs 98.95 vehicles served,
paired difference +0.3 (SD 4.3, 95 % CI -1.7 to +2.3), 0 collisions.
Each run takes one to four minutes.
"""

from __future__ import annotations

import argparse
import math
import statistics
import sys
from multiprocessing import Pool
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "tests" / "integration"))

# Two-sided 95 % t quantiles by degrees of freedom (small samples).
_T95 = {4: 2.776, 9: 2.262, 19: 2.093, 29: 2.045}


def _one(args: tuple[int, int, float, float]) -> dict[str, Any]:
    from test_calibration_pass import _run

    lanes, seed, vph, duration = args
    engine, metrics = _run("roundabout", vph, lanes, seed, duration)
    return {
        "lanes": lanes,
        "seed": seed,
        "served": metrics["throughput"],
        "collisions": engine.pool.collision_count,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--first-seed", type=int, default=1)
    parser.add_argument("--vph", type=float, default=5400.0)
    parser.add_argument("--duration", type=float, default=240.0)
    args = parser.parse_args()

    seeds = range(args.first_seed, args.first_seed + args.seeds)
    jobs = [(lanes, s, args.vph, args.duration) for s in seeds for lanes in (2, 3)]
    with Pool(args.workers) as pool:
        rows = pool.map(_one, jobs)

    served = {(r["lanes"], r["seed"]): r["served"] for r in rows}
    diffs = [served[(3, s)] - served[(2, s)] for s in seeds]
    print(
        f"{args.vph:g} veh/h, {args.duration:g} s, seeds {seeds.start}-{seeds.stop - 1}"
    )
    for seed, d in zip(seeds, diffs):
        print(
            f"seed {seed:2d}: 2 lanes {served[(2, seed)]:4d}  3 lanes {served[(3, seed)]:4d}  diff {d:+d}"
        )
    mean = statistics.mean(diffs)
    sd = statistics.stdev(diffs) if len(diffs) > 1 else float("nan")
    t = _T95.get(len(diffs) - 1, 1.96)
    half = t * sd / math.sqrt(len(diffs))
    print(
        f"\nmean served: 2 lanes {statistics.mean(served[(2, s)] for s in seeds):.2f}, "
        f"3 lanes {statistics.mean(served[(3, s)] for s in seeds):.2f}"
    )
    print(
        f"paired difference (3 - 2): {mean:+.2f}, SD {sd:.2f}, 95% CI {mean - half:+.2f} to {mean + half:+.2f}"
    )
    print(f"collisions: {sum(r['collisions'] for r in rows)}")


if __name__ == "__main__":
    main()
