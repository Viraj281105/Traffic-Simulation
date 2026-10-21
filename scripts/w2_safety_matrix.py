"""V3.0 W2 G-SR evidence: the signalised-roundabout safety matrix, with its numbers.

Runs the same paired matrix as the slow pytest shard
(``backend/tests/integration/test_signalised_roundabout.py``): seeds 1-8 x demand
{low, medium, saturated} x four layouts, each cell once metered and once conventional
(192 simulations, 90 s each), plus an optional "protections" row with the spillback
guard and queue cap switched on.  The runs are the test module's own ``_simulate``, so
this script and the gate cannot drift apart; here they are spread over processes and
every per-cell number is written down instead of being reduced to pass/fail.

    python scripts/w2_safety_matrix.py [--workers 8] [--out DIR] [--no-protections]

Writes ``safety_matrix.json`` into DIR (default
``docs/research/examples/signalised-roundabout-baseline``) and prints the aggregates:
collisions, discharge, longest stall, longest signal denial vs its bound, H2 uncommitted
non-green entries, and ring-blocking onsets (D-W2-9b) summed over the paired matrix.
Simulation evidence only; not a proof of safety.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from tests.integration import test_signalised_roundabout as m  # noqa: E402

Cell = Tuple[str, str, int, bool, bool]  # layout, demand, seed, metered, protections


def run_cell(cell: Cell) -> Dict[str, Any]:
    layout, demand, seed, metered, protections = cell
    res = dict(m._simulate(layout, demand, seed, metered, protections=protections))
    res["protections"] = protections
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--no-protections", action="store_true")
    ap.add_argument(
        "--out",
        default=str(
            ROOT / "docs" / "research" / "examples" / "signalised-roundabout-baseline"
        ),
    )
    args = ap.parse_args()

    cells: List[Cell] = []
    for layout in m._LAYOUTS:
        for demand in m._DEMANDS:
            for seed in m._SEEDS:
                cells.append((layout, demand, seed, False, False))
                cells.append((layout, demand, seed, True, False))
                if not args.no_protections:
                    cells.append((layout, demand, seed, True, True))
    print(f"{len(cells)} simulations on {args.workers} workers")
    t0 = time.perf_counter()
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        rows = list(pool.map(run_cell, cells, chunksize=1))
    print(f"done in {(time.perf_counter() - t0) / 60:.1f} min")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "safety_matrix.json").write_text(json.dumps(rows, indent=1) + "\n")

    def agg(sel: List[Dict[str, Any]], key: str) -> float:
        return sum(float(r[key]) for r in sel)

    conv = [r for r in rows if not r["metered"]]
    met = [r for r in rows if r["metered"] and not r["protections"]]
    prot = [r for r in rows if r["metered"] and r["protections"]]
    print(
        f"\n{'':<14}{'runs':>5}{'collis':>8}{'ringblk':>9}{'maxstall':>10}{'maxdeny':>9}{'uncomm':>8}"
    )
    for name, sel in (("conventional", conv), ("metered", met), ("metered+prot", prot)):
        if not sel:
            continue
        print(
            f"{name:<14}{len(sel):>5}{agg(sel, 'collisions'):>8.0f}"
            f"{agg(sel, 'ring_blocking_onsets'):>9.0f}"
            f"{max(r['longest_stall'] for r in sel):>10.1f}"
            f"{max(r['max_denied_time'] for r in sel):>9.1f}"
            f"{agg(sel, 'uncommitted_nongreen_entries'):>8.0f}"
        )
    if met:
        print(
            f"\nstarvation bound {met[0]['starvation_bound']} s, stall bound "
            f"{met[0]['stall_bound']} s; min exits in closing minute (metered) "
            f"{min(r['exited_last_minute'] for r in met):.0f}"
        )
        print("\nRing-blocking onsets by layout (conventional -> metered):")
        for layout in m._LAYOUTS:
            c = sum(r["ring_blocking_onsets"] for r in conv if r["layout"] == layout)
            t = sum(r["ring_blocking_onsets"] for r in met if r["layout"] == layout)
            print(f"  {layout:<14}{c:>4} -> {t:<4}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
