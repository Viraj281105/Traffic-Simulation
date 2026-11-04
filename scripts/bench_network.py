"""Benchmark ``simulate_network`` on corridor, grid and larger lattices (F5).

    python scripts/bench_network.py [--repeats 5] [--duration 900] [--json out.json]
        [--legacy-from-git REV] [--profile]

For each scenario it reports the best wall time of N repetitions (best-of is
the right statistic for a CPU-bound deterministic function: the minimum is the
run least disturbed by the machine), simulated seconds per wall second, and
microseconds per link-step. With ``--legacy-from-git REV`` it also times the
engine as it was at git revision REV (for example ``HEAD``) on the same
scenarios and checks the results are identical apart from added keys.
``--profile`` prints the cProfile top of the heaviest scenario.

Run on an otherwise idle machine; numbers are only comparable within one run.
Standard library plus the backend sources.
"""

from __future__ import annotations

import argparse
import cProfile
import importlib.util
import io
import json
import platform
import pstats
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from src.netmetrics import network_metrics  # noqa: E402
from src.networks.corridor import build_two_junction_corridor, corridor_flows  # noqa: E402
from src.networks.grid import build_grid, build_three_by_three, build_twelve_junction_network, grid_flows  # noqa: E402
from src.networks.network_sim import simulate_network  # noqa: E402

IGNORED_KEYS = {"totalTravelSeconds", "totalDelaySeconds"}  # added after the legacy engine


def scenarios() -> List[Tuple[str, Any, Any, int]]:
    """(name, graph, flows, junction count)."""
    return [
        ("corridor (2 junctions)", build_two_junction_corridor(), corridor_flows(), 2),
        ("3x3 grid (9)", build_three_by_three(), grid_flows(3, 3, 500), 9),
        ("3x4 network (12)", build_twelve_junction_network(), grid_flows(3, 4, 500), 12),
        ("3x4 network (12), heavy", build_twelve_junction_network(), grid_flows(3, 4, 1200), 12),
        ("6x6 grid (36)", build_grid(6, 6, 300.0, arterial_rows=(2,), arterial_cols=(2,)), grid_flows(6, 6, 500), 36),
        ("10x10 grid (100)", build_grid(10, 10, 300.0), grid_flows(10, 10, 400), 100),
    ]


def best_of(fn: Callable[[], Any], repeats: int) -> Tuple[float, Any]:
    best, out = float("inf"), None
    for _ in range(repeats):
        t0 = time.perf_counter()
        out = fn()
        best = min(best, time.perf_counter() - t0)
    return best, out


def load_legacy(rev: str) -> Optional[Callable[..., Dict[str, Any]]]:
    """``simulate_network`` as of git revision ``rev``, loaded as a throwaway module."""
    try:
        src = subprocess.run(
            ["git", "show", f"{rev}:backend/src/networks/network_sim.py"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError) as err:
        print(f"cannot read legacy engine from git {rev}: {err}", file=sys.stderr)
        return None
    spec = importlib.util.spec_from_loader("legacy_network_sim", loader=None)
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules["legacy_network_sim"] = module  # dataclasses looks the module up
    exec(compile(src, f"<git {rev} network_sim.py>", "exec"), module.__dict__)
    return module.simulate_network


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--duration", type=float, default=900.0)
    ap.add_argument("--seed", type=int, default=5)
    ap.add_argument("--json", type=Path, default=None)
    ap.add_argument("--legacy-from-git", default=None, metavar="REV")
    ap.add_argument("--profile", action="store_true")
    args = ap.parse_args()

    legacy = load_legacy(args.legacy_from_git) if args.legacy_from_git else None
    rows: List[Dict[str, Any]] = []
    header = f"{'scenario':28} {'links':>5} {'veh':>6} {'wall s':>8} {'sim s/s':>9} {'us/link-step':>12}"
    if legacy:
        header += f" {'legacy s':>9} {'speed-up':>9} {'same':>5}"
    header += f" {'+metrics s':>10}"
    print(header)
    for name, graph, flows, junctions in scenarios():
        wall, res = best_of(
            lambda: simulate_network(graph, flows, duration=args.duration, seed=args.seed), args.repeats
        )
        steps = int(round(args.duration))
        row: Dict[str, Any] = {
            "scenario": name,
            "junctions": junctions,
            "links": len(graph.links),
            "entered": res["entered"],
            "completed": res["completed"],
            "wallSeconds": round(wall, 5),
            "simSecondsPerWallSecond": round(args.duration / wall, 1),
            "microsecondsPerLinkStep": round(wall / (steps * len(graph.links)) * 1e6, 3),
        }
        line = (
            f"{name:28} {len(graph.links):5d} {res['entered']:6d} {wall:8.4f} "
            f"{row['simSecondsPerWallSecond']:9.1f} {row['microsecondsPerLinkStep']:12.3f}"
        )
        if legacy:
            lw, lres = best_of(
                lambda: legacy(graph, flows, duration=args.duration, seed=args.seed), args.repeats
            )
            same = {k: v for k, v in res.items() if k not in IGNORED_KEYS} == lres
            row.update({"legacySeconds": round(lw, 5), "speedUp": round(lw / wall, 2), "identical": same})
            line += f" {lw:9.4f} {lw / wall:8.2f}x {'yes' if same else 'NO':>5}"
        try:
            mw, _ = best_of(
                lambda: network_metrics(graph, flows, duration=args.duration, seed=args.seed),
                max(1, args.repeats // 2),
            )
            row["withMetricsSeconds"] = round(mw, 5)
            line += f" {mw:10.4f}"
        except ValueError:
            line += f" {'(too big)':>10}"
        print(line)
        rows.append(row)

    if args.profile:
        _, graph, flows, _ = scenarios()[3]
        prof = cProfile.Profile()
        prof.runcall(simulate_network, graph, flows, duration=args.duration, seed=args.seed)
        buf = io.StringIO()
        pstats.Stats(prof, stream=buf).sort_stats("tottime").print_stats(8)
        print("\nProfile of the heavy 12-junction scenario:\n" + buf.getvalue())

    meta = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "durationSeconds": args.duration,
        "repeats": args.repeats,
        "seed": args.seed,
    }
    if args.json:
        args.json.write_text(json.dumps({"meta": meta, "rows": rows}, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
