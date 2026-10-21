"""Runtime and memory of the metered (signalised) roundabout vs the conventional one.

V3.0 W2, SR-24 / H11: wall time and ``tracemalloc`` peak per simulated second, same
scenario and seeds, N repetitions each.  The sprint plan's target is <= 1.3x and is an
unverified estimate; this script only *measures* it and prints the ratio, it does not
pass or fail the gate.

    python scripts/benchmark_signalised_roundabout.py [--repeats 3] [--duration 90]
        [--seeds 1,2] [--json out.json]

Timing and memory are measured in separate passes (``tracemalloc`` slows the
interpreter several-fold, which would swamp the ratio being measured).  Run on an
otherwise idle machine; the result is only comparable within one run of this script.

Standard library plus the backend sources.  Every number printed is measured here.
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
import time
import tracemalloc
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from src.controllers.factory import create_controller  # noqa: E402
from src.core.clock import Clock  # noqa: E402
from src.engine.simulation_engine import SimulationEngine  # noqa: E402
from src.engine.tick_callback import build_tick_callback  # noqa: E402
from src.metrics.collector import MetricCollector  # noqa: E402
from src.scenario.documents import compile_scenario, parse_scenario  # noqa: E402

TIME_STEP = 0.1

# (label, circulating lanes, lanes per approach, veh/h per approach)
LAYOUTS: Tuple[Tuple[str, int, int, int], ...] = (
    ("1ring_4arm_medium", 1, 1, 350),
    ("2ring_4arm_medium", 2, 2, 500),
    ("2ring_4arm_saturated", 2, 2, 1000),
)


def scenario(
    rings: int,
    lanes: int,
    vph: int,
    seed: int,
    duration: float,
    metered: bool,
    always_green: bool = False,
) -> Dict[str, Any]:
    doc: Dict[str, Any] = {
        "format": "urbanflow-scenario",
        "version": 1,
        "name": "bench",
        "junction": {"type": "roundabout"},
        "approaches": {
            d: {
                "lanes": lanes,
                "length": 150.0,
                "vehiclesPerHour": vph,
                "turning": {"left": 0.25, "straight": 0.5, "right": 0.25},
            }
            for d in ("north", "south", "east", "west")
        },
        "roundabout": {"circulatingLanes": rings},
        "simulation": {"duration": duration, "warmup": 10.0, "seed": seed},
    }
    if metered:
        doc["roundabout"]["entryControl"] = "metered_entry"
        # always_green: one 120 s phase for every arm, so the gate never closes and the
        # traffic is the conventional run's; what is left is the controller's own cost.
        phases = (
            [{"entries": ["north", "south", "east", "west"], "green": 120.0}]
            if always_green
            else [
                {"entries": ["north", "south"], "green": 20.0},
                {"entries": ["east", "west"], "green": 20.0},
            ]
        )
        doc["roundabout"]["entryMetering"] = {
            "phases": phases,
            "yellow": 3.0,
            "allRed": 2.0,
            # Both optional protections on, so the per-tick sector scans (H11) are in
            # the measured path rather than switched off.
            "spillbackGuard": {"enabled": True, "stoppedThreshold": 2, "maxHold": 10.0},
            "queueCap": {"enabled": True, "vehicles": 8},
        }
    return doc


def run_once(
    rings: int,
    lanes: int,
    vph: int,
    seed: int,
    duration: float,
    metered: bool,
    always_green: bool = False,
) -> int:
    parsed, errors = parse_scenario(
        scenario(rings, lanes, vph, seed, duration, metered, always_green)
    )
    assert not errors, errors
    config = compile_scenario(parsed, "roundabout")
    clock = Clock(time_step=TIME_STEP)
    engine = SimulationEngine(clock, duration=duration, config=config)
    controller = create_controller(config, engine.network)
    engine.controller = controller
    collector = MetricCollector(config)
    engine.register_tick_callback(
        build_tick_callback(controller, clock, engine, collector)
    )
    for _ in range(int(round(duration / TIME_STEP))):
        engine.step()
    return len(engine.pool.exited_vehicles)


Variant = Tuple[str, bool, bool]  # name, metered, always_green
VARIANTS: List[Variant] = [
    ("conventional", False, False),
    ("metered", True, False),
    ("alwaysgreen", True, True),
]


def measure_all(
    rings: int,
    lanes: int,
    vph: int,
    seeds: List[int],
    repeats: int,
    duration: float,
) -> Dict[str, Dict[str, Any]]:
    """Wall time with the variants interleaved (so drift in machine load hits all of them
    alike) and reported as the minimum over repeats, the usual estimate of a cost that
    noise can only add to; the median is kept for the spread.  Memory in a separate pass."""
    walls: Dict[str, List[float]] = {name: [] for name, _, _ in VARIANTS}
    for _ in range(repeats):
        for name, metered, always_green in VARIANTS:
            t0 = time.perf_counter()
            for s in seeds:
                run_once(rings, lanes, vph, s, duration, metered, always_green)
            walls[name].append(time.perf_counter() - t0)
    sim_seconds = duration * len(seeds)
    out: Dict[str, Dict[str, Any]] = {}
    for name, metered, always_green in VARIANTS:
        per_sim_s = [w / sim_seconds for w in walls[name]]
        peaks: List[float] = []
        for s in seeds:
            tracemalloc.start()
            run_once(rings, lanes, vph, s, duration, metered, always_green)
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            peaks.append(peak / duration)
        out[name] = {
            "wall_s_per_sim_s": per_sim_s,
            "wall_min": min(per_sim_s),
            "wall_median": statistics.median(per_sim_s),
            "peak_bytes_per_sim_s": peaks,
            "peak_median": statistics.median(peaks),
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--duration", type=float, default=90.0)
    ap.add_argument("--seeds", default="1,2")
    ap.add_argument("--json", default="")
    args = ap.parse_args()
    seeds = [int(s) for s in args.seeds.split(",")]

    print(
        f"python {platform.python_version()} {platform.platform()} | "
        f"duration {args.duration}s dt {TIME_STEP}s seeds {seeds} repeats {args.repeats}"
    )
    results: Dict[str, Any] = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "duration": args.duration,
        "seeds": seeds,
        "repeats": args.repeats,
        "layouts": {},
    }
    header = (
        f"{'layout / variant':<34}{'conv ms/s':>11}{'meter ms/s':>12}{'time x':>8}"
        f"{'conv KiB/s':>12}{'meter KiB/s':>13}{'mem x':>8}"
    )
    print(header)
    print("-" * len(header))
    # "metered" changes the traffic (red holds vehicles back, so fewer are in the network
    # and the run gets cheaper or dearer for that reason alone); "alwaysgreen" keeps the
    # conventional run's traffic exactly (hazard H13) and so isolates the controller's cost.
    for label, rings, lanes, vph in LAYOUTS:
        m = measure_all(rings, lanes, vph, seeds, args.repeats, args.duration)
        conv = m["conventional"]
        for variant in ("metered", "alwaysgreen"):
            met = m[variant]
            t_ratio = met["wall_min"] / conv["wall_min"]
            m_ratio = met["peak_median"] / conv["peak_median"]
            results["layouts"][f"{label}_{variant}"] = {
                "conventional": conv,
                "metered": met,
                "time_ratio": t_ratio,
                "memory_ratio": m_ratio,
                "same_traffic": variant == "alwaysgreen",
            }
            print(
                f"{label + '_' + variant:<34}{conv['wall_min'] * 1000:>11.2f}"
                f"{met['wall_min'] * 1000:>12.2f}{t_ratio:>8.3f}"
                f"{conv['peak_median'] / 1024:>12.1f}{met['peak_median'] / 1024:>13.1f}"
                f"{m_ratio:>8.3f}"
            )
    same = [v["time_ratio"] for v in results["layouts"].values() if v["same_traffic"]]
    worst = max(v["time_ratio"] for v in results["layouts"].values())
    results["worst_time_ratio"] = worst
    results["worst_same_traffic_time_ratio"] = max(same)
    print(
        f"\nworst time ratio {worst:.3f}; worst same-traffic (alwaysgreen) ratio "
        f"{max(same):.3f} (sprint target <= 1.3, unverified estimate)"
    )
    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
