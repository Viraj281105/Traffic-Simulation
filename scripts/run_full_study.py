#!/usr/bin/env python3
"""
Automated Comprehensive Study CLI Runner

Executes an automated end-to-end traffic simulation study without requiring a running API server:
1. Multi-Volume Parameter Sweep: Evaluates Fixed-Time Signal vs. Modern Roundabout
   across varying traffic arrival rates under identical seeds.
2. Monte Carlo Statistical Validation: Runs multi-seed experiments to evaluate
   repeatability, variance, and 95% confidence intervals.
3. Generates and exports the final study_report.csv and optional JSON summary.

Usage:
    python scripts/run_full_study.py [--sweep-duration 60.0] [--validation-duration 30.0] [--num-seeds 5]
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Add project root and backend to python path for direct imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Ensure database path is anchored properly if not specified
if "DB_PATH" not in os.environ:
    os.environ["DB_PATH"] = str(PROJECT_ROOT / "simulation.db")

from src.database.db import init_db
from src.study.report_generator import generate_study_report_csv, generate_study_report_json
from src.study.validation import run_statistical_validation
from src.study.volume_sweep import DEFAULT_ARRIVAL_RATES, run_volume_sweep_experiment


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Automated Traffic Simulation Study CLI Runner (W8 Final Validated Study)"
    )
    parser.add_argument(
        "--sweep-duration",
        type=float,
        default=60.0,
        help="Simulated duration (in seconds) per volume sweep run (default: 60.0)",
    )
    parser.add_argument(
        "--validation-duration",
        type=float,
        default=30.0,
        help="Simulated duration (in seconds) per Monte Carlo validation seed (default: 30.0)",
    )
    parser.add_argument(
        "--num-seeds",
        type=int,
        default=5,
        help="Number of random seeds for Monte Carlo statistical validation (default: 5)",
    )
    parser.add_argument(
        "--time-step",
        type=float,
        default=0.1,
        help="Simulation integration time step dt (default: 0.1)",
    )
    parser.add_argument(
        "--rates",
        type=str,
        default=None,
        help="Comma-separated arrival rates in veh/s/approach (e.g. '0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8')",
    )
    parser.add_argument(
        "--output-csv",
        type=str,
        default="study_report.csv",
        help="Target filepath for output CSV report (default: study_report.csv)",
    )
    parser.add_argument(
        "--output-json",
        type=str,
        default=None,
        help="Optional target filepath for output JSON report",
    )
    return parser.parse_args()


if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def print_banner() -> None:
    print("=" * 78)
    print("   TRAFFIC INTERSECTION CONTROL COMPARISON: AUTOMATED STUDY RUNNER   ")
    print("=" * 78)
    print("Evaluating: Fixed-Time Traffic Signal vs. Modern Roundabout Control")
    print("Physics Engine: Intelligent Driver Model (IDM)")
    print()


def main() -> int:
    args = parse_args()
    print_banner()

    rates = (
        [float(r.strip()) for r in args.rates.split(",") if r.strip()]
        if args.rates
        else DEFAULT_ARRIVAL_RATES
    )

    print(f"[1/3] Initializing simulation database: {os.environ['DB_PATH']}")
    init_db()

    # ── 1. Volume Sweep ────────────────────────────────────────────────────────
    print("\n[2/3] Executing Multi-Volume Parameter Sweep...")
    print(f"  - Arrival Rates: {rates} veh/s")
    print(f"  - Duration per step: {args.sweep_duration}s (dt = {args.time_step}s)")
    start_sweep = time.time()

    sweep_results = run_volume_sweep_experiment(
        arrival_rates=rates,
        duration=args.sweep_duration,
        time_step=args.time_step,
        random_seed=42,
        name="CLI Automated Volume Sweep",
    )
    sweep_elapsed = time.time() - start_sweep
    print(f"  [+] Sweep completed in {sweep_elapsed:.2f}s")

    # Display sweep results table
    print("\n  --- VOLUME SWEEP SUMMARY ---")
    print(
        f"  {'Rate':>6} | {'Vol(veh/h)':>10} | {'Sig Delay':>10} | {'Rnd Delay':>10} | "
        f"{'Sig Tput':>9} | {'Rnd Tput':>9} | {'Sig Q':>6} | {'Rnd Q':>6} | {'Winner':>10}"
    )
    print("  " + "-" * 88)
    for run in sweep_results.get("runs", []):
        r = run.get("arrivalRate", 0.0)
        vol = run.get("hourlyVolumeVehPerHour", 0)
        sig_d = run.get("signal", {}).get("delay", 0.0)
        rnd_d = run.get("roundabout", {}).get("delay", 0.0)
        sig_tp = run.get("signal", {}).get("throughput", 0.0)
        rnd_tp = run.get("roundabout", {}).get("throughput", 0.0)
        sig_q = run.get("signal", {}).get("queue", 0.0)
        rnd_q = run.get("roundabout", {}).get("queue", 0.0)
        winner = run.get("winner", "tie").upper()

        print(
            f"  {r:6.2f} | {vol:10d} | {sig_d:9.2f}s | {rnd_d:9.2f}s | "
            f"{sig_tp:9.1f} | {rnd_tp:9.1f} | {sig_q:6.1f} | {rnd_q:6.1f} | {winner:>10}"
        )

    crossover = sweep_results.get("curves", {}).get("crossoverArrivalRate")
    crossover_h = sweep_results.get("curves", {}).get("crossoverHourlyVolume")
    if crossover:
        print(f"\n  [*] Critical Crossover Saturation Threshold: {crossover:.2f} veh/s (~{crossover_h} veh/h)")
        print("      Below this threshold: Roundabout is significantly more optimal (lower delay).")
        print("      Above this threshold: Signal maintains superior queue stability and throughput.")
    else:
        print("\n  [*] No crossover observed within evaluated rate limits.")

    # ── 2. Monte Carlo Validation ──────────────────────────────────────────────
    print(f"\n[3/3] Executing Monte Carlo Statistical Validation ({args.num_seeds} randomized seeds)...")
    print(f"  - Duration per seed: {args.validation_duration}s")
    start_mc = time.time()

    validation_results = run_statistical_validation(
        num_seeds=args.num_seeds,
        duration=args.validation_duration,
        time_step=args.time_step,
    )
    mc_elapsed = time.time() - start_mc
    print(f"  [+] Monte Carlo validation completed in {mc_elapsed:.2f}s")

    print("\n  --- MONTE CARLO STATISTICAL SUMMARY (95% CI) ---")
    print(f"  {'Metric':<12} | {'Signal Mean +/- 95% CI':<24} | {'Roundabout Mean +/- 95% CI':<26}")
    print("  " + "-" * 66)
    for m in ["delay", "throughput", "queue"]:
        sig_st = validation_results.get("signal", {}).get(m, {})
        rnd_st = validation_results.get("roundabout", {}).get(m, {})
        sig_str = f"{sig_st.get('mean', 0.0):.2f} +/- {sig_st.get('ci95', 0.0):.2f}"
        rnd_str = f"{rnd_st.get('mean', 0.0):.2f} +/- {rnd_st.get('ci95', 0.0):.2f}"
        print(f"  {m.capitalize():<12} | {sig_str:<24} | {rnd_str:<26}")

    # ── 3. Export Reports ──────────────────────────────────────────────────────
    print("\n[Exporting Reports]")
    csv_content = generate_study_report_csv(sweep_results, validation_results)
    output_csv_path = Path(args.output_csv)
    output_csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_csv_path, "w", encoding="utf-8") as f:
        f.write(csv_content)
    print(f"  [+] Successfully saved study CSV report to: {output_csv_path.resolve()}")

    if args.output_json:
        json_data = generate_study_report_json(sweep_results, validation_results)
        output_json_path = Path(args.output_json)
        output_json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_json_path, "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=2)
        print(f"  [+] Successfully saved study JSON report to: {output_json_path.resolve()}")

    total_time = sweep_elapsed + mc_elapsed
    print(f"\n[DONE] Full study successfully executed in {total_time:.2f}s total.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
