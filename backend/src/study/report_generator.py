import csv
import io
from typing import Any, Dict, Optional

from src.study.validation import run_statistical_validation
from src.study.volume_sweep import run_volume_sweep_experiment


def generate_study_report_json(
    sweep_results: Optional[Dict[str, Any]] = None,
    validation_results: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Generates a structured comprehensive study report in JSON format."""
    sweep = sweep_results or run_volume_sweep_experiment(duration=30.0)
    validation = validation_results or run_statistical_validation(
        num_seeds=3, duration=20.0
    )

    # Calculate executive takeaways
    crossover = sweep.get("curves", {}).get("crossoverArrivalRate")
    runs = sweep.get("runs", [])

    roundabout_wins = sum(1 for r in runs if r.get("winner") == "roundabout")
    signal_wins = sum(1 for r in runs if r.get("winner") == "signal")

    report = {
        "title": "Comprehensive Comparative Traffic Simulation Study: Fixed-Time Signal vs. Modern Roundabout",
        "version": "1.0.0",
        "summary": {
            "totalVolumePointsEvaluated": len(runs),
            "roundaboutOptimalCount": roundabout_wins,
            "signalOptimalCount": signal_wins,
            "criticalCrossoverArrivalRate": crossover,
            "criticalCrossoverHourlyVolume": sweep.get("curves", {}).get(
                "crossoverHourlyVolume"
            ),
            "recommendation": (
                f"Modern roundabouts exhibit significantly superior performance at lower to medium demand (< {crossover or 0.6:.2f} veh/s/appr). "
                f"Above this critical saturation threshold, Fixed-Time Signals maintain better queue stability and throughput."
            ),
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
