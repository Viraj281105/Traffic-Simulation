import csv
import io
from typing import Any, Dict, Optional

from src.study.validation import run_statistical_validation
from src.study.volume_sweep import run_volume_sweep_experiment


def _summarize_sweep_verdict(sweep: Dict[str, Any]) -> Dict[str, Any]:
    """Derives a measured, data-driven verdict summary from volume-sweep
    results.

    Reuses each run's own ``winner`` classification exactly as computed by
    ``run_volume_sweep_experiment`` (src/study/volume_sweep.py), which already
    applies a tie tolerance (delay difference <= 0.2s or < 2%) before calling
    a point for either geometry -- no new statistical methodology is
    introduced here, only aggregation of that existing, per-point verdict.

    Never asserts either geometry is superior beyond what the supplied
    ``sweep`` data actually shows, and degrades safely when ``sweep`` has no
    runs (e.g. an empty or failed sweep) instead of guessing.
    """
    runs = sweep.get("runs", [])
    total = len(runs)

    if total == 0:
        return {
            "status": "insufficient_data",
            "roundaboutWins": 0,
            "signalWins": 0,
            "ties": 0,
            "totalPoints": 0,
            "crossoverArrivalRate": None,
            "crossoverHourlyVolume": None,
            "text": (
                "No volume-sweep data points were available, so no "
                "comparative recommendation can be made from this run."
            ),
        }

    roundabout_wins = sum(1 for r in runs if r.get("winner") == "roundabout")
    signal_wins = sum(1 for r in runs if r.get("winner") == "signal")
    ties = total - roundabout_wins - signal_wins

    crossover = sweep.get("curves", {}).get("crossoverArrivalRate")
    crossover_h = sweep.get("curves", {}).get("crossoverHourlyVolume")

    if roundabout_wins == 0 and signal_wins == 0:
        text = (
            f"Across all {total} measured volume point(s), the delay "
            "difference between the two geometries stayed within the tie "
            "tolerance (<=0.2s or <2%) -- the measured data does not show "
            "either geometry as consistently better in this sweep."
        )
    elif crossover is not None and roundabout_wins > 0 and signal_wins > 0:
        volume_note = f" (~{crossover_h:,} veh/h total)" if crossover_h else ""
        text = (
            f"Measured delay reversed direction at an arrival rate of "
            f"{crossover:.3f} veh/s/approach{volume_note}. Below that point "
            f"the roundabout had the lower measured delay ({roundabout_wins} "
            f"of {total} points); at or above it the signal did "
            f"({signal_wins} of {total} points"
            + (f", {ties} tie(s)" if ties else "")
            + ")."
        )
    elif roundabout_wins > signal_wins:
        text = (
            f"The roundabout had the lower measured delay at {roundabout_wins} "
            f"of {total} measured volume points (signal: {signal_wins}, "
            f"tie: {ties}); no delay-direction reversal was observed in this "
            "sweep."
        )
    elif signal_wins > roundabout_wins:
        text = (
            f"The fixed-time signal had the lower measured delay at "
            f"{signal_wins} of {total} measured volume points (roundabout: "
            f"{roundabout_wins}, tie: {ties}); no delay-direction reversal "
            "was observed in this sweep."
        )
    else:
        text = (
            f"The measured results are evenly split ({roundabout_wins} "
            f"roundabout / {signal_wins} signal / {ties} tie of {total} "
            "points); this sweep alone does not support a directional "
            "recommendation."
        )

    return {
        "status": "measured",
        "roundaboutWins": roundabout_wins,
        "signalWins": signal_wins,
        "ties": ties,
        "totalPoints": total,
        "crossoverArrivalRate": crossover,
        "crossoverHourlyVolume": crossover_h,
        "text": text,
    }


def generate_study_report_json(
    sweep_results: Optional[Dict[str, Any]] = None,
    validation_results: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Generates a structured comprehensive study report in JSON format."""
    sweep = sweep_results or run_volume_sweep_experiment(duration=30.0)
    validation = validation_results or run_statistical_validation(
        num_seeds=3, duration=20.0
    )

    verdict = _summarize_sweep_verdict(sweep)

    report = {
        "title": "Comprehensive Comparative Traffic Simulation Study: Fixed-Time Signal vs. Modern Roundabout",
        "version": "1.0.0",
        "summary": {
            "totalVolumePointsEvaluated": verdict["totalPoints"],
            "roundaboutOptimalCount": verdict["roundaboutWins"],
            "signalOptimalCount": verdict["signalWins"],
            "tiedCount": verdict["ties"],
            "criticalCrossoverArrivalRate": verdict["crossoverArrivalRate"],
            "criticalCrossoverHourlyVolume": verdict["crossoverHourlyVolume"],
            # Derived directly from this run's measured volume-sweep points
            # (see _summarize_sweep_verdict) -- never a fixed claim about
            # which geometry is better, and never contradicts the supplied
            # sweep data.
            "recommendation": verdict["text"],
        },
        "volumeSweep": sweep,
        "statisticalValidation": validation,
    }
    return report


def generate_study_report_csv(
    sweep_results: Optional[Dict[str, Any]] = None,
    validation_results: Optional[Dict[str, Any]] = None,
) -> str:
    """Generates a comprehensive study report in formatted CSV string format."""
    data = generate_study_report_json(sweep_results, validation_results)
    output = io.StringIO()
    writer = csv.writer(output)

    # 1. Header & Summary
    writer.writerow(["=== COMPREHENSIVE TRAFFIC STUDY REPORT ==="])
    writer.writerow(["Title", data["title"]])
    writer.writerow(["Version", data["version"]])
    writer.writerow(
        [
            "Critical Crossover Flow (veh/s)",
            data["summary"]["criticalCrossoverArrivalRate"] or "N/A",
        ]
    )
    writer.writerow(
        [
            "Critical Crossover Flow (veh/hr)",
            data["summary"]["criticalCrossoverHourlyVolume"] or "N/A",
        ]
    )
    writer.writerow(["Executive Recommendation", data["summary"]["recommendation"]])
    writer.writerow([])

    # 2. Volume Sweep Comparison Table
    writer.writerow(["=== VOLUME SWEEP RESULTS ==="])
    writer.writerow(
        [
            "Arrival Rate (veh/s)",
            "Total Hourly Volume (veh/h)",
            "Signal Delay (s)",
            "Roundabout Delay (s)",
            "Signal Throughput (veh/h)",
            "Roundabout Throughput (veh/h)",
            "Signal Avg Queue",
            "Roundabout Avg Queue",
            "Optimal Strategy",
            "Delay Delta (%)",
        ]
    )

    for run in data.get("volumeSweep", {}).get("runs", []):
        writer.writerow(
            [
                run.get("arrivalRate"),
                run.get("hourlyVolumeVehPerHour"),
                run.get("signal", {}).get("delay"),
                run.get("roundabout", {}).get("delay"),
                run.get("signal", {}).get("throughput"),
                run.get("roundabout", {}).get("throughput"),
                run.get("signal", {}).get("queue"),
                run.get("roundabout", {}).get("queue"),
                run.get("winner"),
                run.get("delayDeltaPercent"),
            ]
        )

    writer.writerow([])

    # 3. Statistical Validation Table
    writer.writerow(["=== STATISTICAL MONTE CARLO VALIDATION ==="])
    writer.writerow(
        [
            "Metric",
            "Signal Mean",
            "Signal StdDev",
            "Signal 95% CI",
            "Roundabout Mean",
            "Roundabout StdDev",
            "Roundabout 95% CI",
        ]
    )

    val = data.get("statisticalValidation", {})
    for metric_name in ["delay", "throughput", "queue"]:
        sig_stat = val.get("signal", {}).get(metric_name, {})
        rnd_stat = val.get("roundabout", {}).get(metric_name, {})
        writer.writerow(
            [
                metric_name.capitalize(),
                sig_stat.get("mean"),
                sig_stat.get("std"),
                sig_stat.get("ci95"),
                rnd_stat.get("mean"),
                rnd_stat.get("std"),
                rnd_stat.get("ci95"),
            ]
        )

    return output.getvalue()
