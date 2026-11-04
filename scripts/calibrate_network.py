"""Calibrate a road-network graph against link counts (package 1B).

    cd backend
    python ../scripts/calibrate_network.py --graph g.json --flows f.json \
        --counts counts.csv --out report.json [--budget 200] [--seed 1]

    # re-fit on the last 8 intervals, warm-started from an earlier report
    python ../scripts/calibrate_network.py ... --previous report.json --window 8

    # write a synthetic ground-truth example (graph, flows, counts, truth)
    python ../scripts/calibrate_network.py --write-demo ../backend/tests/calibration/fixtures

Files: the graph is an ``urbanflow-graph`` JSON; flows is a JSON list of
{"origin", "destination", "vehiclesPerHour"}; counts is the CSV described in
``src/calibration/network_counts.py``. Exit code: 0 G-CAL passed, 2 report
written but G-CAL not met, 1 unusable input.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from src.calibration.network_counts import load_counts_file  # noqa: E402
from src.calibration.network_fit import (  # noqa: E402
    FitOptions,
    NetworkCalibrationError,
    SimSettings,
    calibrate_network,
    demand_name,
)
from src.calibration.network_metrics import GCalCriteria  # noqa: E402
from src.calibration.network_recalibration import recalibrate  # noqa: E402
from src.calibration.network_synthetic import demo_flows, demo_grid, generate_counts  # noqa: E402
from src.networks.graph import parse_graph, serialize_graph  # noqa: E402
from src.networks.network_sim import Flow  # noqa: E402

DEMO_MULTIPLIERS = [1.4, 0.6, 1.2, 0.8, 1.5, 0.7, 1.0, 1.3]
DEMO_SPEED = 0.8


def write_demo(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    graph, flows = demo_grid(), demo_flows()
    truth = {demand_name(f): m for f, m in zip(flows, DEMO_MULTIPLIERS)}
    truth["speed:all"] = DEMO_SPEED
    csv_text = generate_counts(graph, flows, truth)
    (directory / "demo_graph.json").write_text(
        json.dumps(serialize_graph(graph), indent=2) + "\n", encoding="utf-8", newline="\n")
    (directory / "demo_flows.json").write_text(
        json.dumps([{"origin": f.origin, "destination": f.destination,
                     "vehiclesPerHour": f.vehicles_per_hour} for f in flows], indent=2) + "\n",
        encoding="utf-8", newline="\n")
    (directory / "demo_counts.csv").write_text(csv_text, encoding="utf-8", newline="\n")
    (directory / "demo_truth.json").write_text(
        json.dumps(truth, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"Wrote demo graph, flows, counts and truth to {directory}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--graph")
    ap.add_argument("--flows")
    ap.add_argument("--counts")
    ap.add_argument("--out", help="write the report JSON here (default: stdout summary only)")
    ap.add_argument("--budget", type=int, default=200)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--duration", type=float, default=600.0)
    ap.add_argument("--interval-seconds", type=float, default=None)
    ap.add_argument("--no-speed", action="store_true", help="do not calibrate free-flow speed")
    ap.add_argument("--no-demand", action="store_true", help="do not calibrate demand")
    ap.add_argument("--geh-limit", type=float, default=5.0)
    ap.add_argument("--min-fraction", type=float, default=0.85)
    ap.add_argument("--max-mape", type=float, default=None)
    ap.add_argument("--max-rmse", type=float, default=None)
    ap.add_argument("--previous", help="earlier report JSON: warm start and drift")
    ap.add_argument("--window", type=int, default=None, help="use the last N count intervals")
    ap.add_argument("--write-demo", metavar="DIR")
    args = ap.parse_args()

    if args.write_demo:
        write_demo(Path(args.write_demo))
        return 0
    if not (args.graph and args.flows and args.counts):
        ap.error("--graph, --flows and --counts are required")

    graph, errors = parse_graph(json.loads(Path(args.graph).read_text(encoding="utf-8")))
    if graph is None:
        print("Invalid graph:\n  " + "\n  ".join(errors), file=sys.stderr)
        return 1
    flows = [Flow(f["origin"], f["destination"], float(f["vehiclesPerHour"]))
             for f in json.loads(Path(args.flows).read_text(encoding="utf-8"))]
    counts = load_counts_file(args.counts, interval_seconds=args.interval_seconds,
                              known_links=graph.link_map())
    for w in counts.warnings:
        print(f"warning: {w}", file=sys.stderr)
    options = FitOptions(
        budget=args.budget, seed=args.seed,
        calibrate_speed=not args.no_speed, calibrate_demand=not args.no_demand,
        criteria=GCalCriteria(args.geh_limit, args.min_fraction, args.max_mape, args.max_rmse),
    )
    sim = SimSettings(duration=args.duration)
    try:
        if args.previous:
            previous = json.loads(Path(args.previous).read_text(encoding="utf-8"))["parameters"]["fitted"]
            report = recalibrate(graph, flows, counts, previous,
                                 window_intervals=args.window, options=options, sim=sim)
        else:
            window = counts.window(args.window) if args.window else counts
            report = calibrate_network(graph, flows, window, options, sim)
    except NetworkCalibrationError as err:
        print("Cannot calibrate:\n  " + "\n  ".join(err.errors), file=sys.stderr)
        return 1

    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    b, a = report["before"]["metrics"], report["after"]["metrics"]
    print(f"G-CAL: {report['status']}  ({report['optimiser']['evaluations']} evaluations, "
          f"{report['optimiser']['stopReason']})")
    print(f"  RMSE {b['rmseVph']} -> {a['rmseVph']} veh/h   MAPE {b['mapePercent']} -> {a['mapePercent']} %"
          f"   R2 {b['r2']} -> {a['r2']}   GEH<5 {report['after']['gCal']['gehFraction']}")
    if "recalibration" in report:
        d = report["recalibration"]["drift"]
        print(f"  drift: max {d['maxAbsRelativeChange']}, flagged {d['flagged'] or 'none'}")
    print(f"  manifest {report['manifest']['hash'][:16]}")
    for n in report["notes"]:
        print(f"  note: {n}")
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
