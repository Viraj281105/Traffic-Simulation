import csv
import io
from typing import Any, Dict, List, Optional, Tuple

from src.study.tolerances import tie_tolerance
from src.study.validation import run_statistical_validation
from src.study.volume_sweep import run_volume_sweep_experiment

_SIDE_NAME = {"signal": "fixed-time signal", "roundabout": "roundabout"}

_ONE_SEED_NOTE = (
    "Each point is one random traffic pattern, so a difference here may be "
    "chance; only the repeated-seed validation tests that."
)


def _decided_sequence(runs: List[Dict[str, Any]]) -> List[str]:
    """Winners of the decided tiers (ties and inconclusive tiers dropped), in
    arrival-rate order (run order when a run carries no rate)."""
    indexed: List[Tuple[float, str]] = [
        (r.get("arrivalRate", float(i)), str(r["winner"]))
        for i, r in enumerate(runs)
        if r.get("winner") in ("signal", "roundabout")
    ]
    return [w for _, w in sorted(indexed, key=lambda item: item[0])]


def _summarize_sweep_verdict(sweep: Dict[str, Any]) -> Dict[str, Any]:
    """Describes, from the measured data only, which control had the lower
    mean delay at each demand point of a volume sweep.

    Every statement is derived from the per-point ``winner`` classification
    that ``run_volume_sweep_experiment`` already produced (shared tie rule in
    study/tolerances.py; a point is ``inconclusive`` when too few vehicles got
    through or the vehicle limit cut demand off). Nothing here assumes which
    control does better at low or high demand: the direction is read from the
    data, ties and inconclusive points are counted as such, and a sweep has
    exactly one random traffic pattern per point, so the text always says it
    is descriptive. It never asserts a difference is real; that is the job of
    the repeated-seed validation.
    """
    runs = sweep.get("runs", [])
    total = len(runs)
    calibration = sweep.get("calibration")
    tolerance = sweep.get("tieTolerance") or tie_tolerance()

    if total == 0:
        return {
            "status": "insufficient_data",
            "evidenceLevel": "none",
            "directional": "none",
            "roundaboutWins": 0,
            "signalWins": 0,
            "ties": 0,
            "inconclusive": 0,
            "totalPoints": 0,
            "crossoverArrivalRate": None,
            "crossoverHourlyVolume": None,
            "text": (
                "No volume-sweep data points were available, so no "
                "comparative statement can be made from this run."
            ),
        }

    roundabout_wins = sum(1 for r in runs if r.get("winner") == "roundabout")
    signal_wins = sum(1 for r in runs if r.get("winner") == "signal")
    inconclusive = sum(1 for r in runs if r.get("winner") == "inconclusive")
    ties = total - roundabout_wins - signal_wins - inconclusive

    curves = sweep.get("curves", {})
    crossover = curves.get("crossoverArrivalRate")
    crossover_h = curves.get("crossoverHourlyVolume")

    sequence = _decided_sequence(runs)
    changes = sum(1 for x, y in zip(sequence, sequence[1:]) if x != y)

    tol = f"<={tolerance['absSeconds']:g}s or <={tolerance['relative'] * 100:g}%"
    extras = ""
    if ties:
        extras += f", {ties} tie(s)"
    if inconclusive:
        extras += f", {inconclusive} inconclusive"

    if roundabout_wins == 0 and signal_wins == 0:
        directional = "none"
        if inconclusive == total:
            text = (
                f"None of the {total} measured volume point(s) could be "
                "decided: too few vehicles got through, or the vehicle "
                "limit cut demand off, so no direction is reported."
            )
        else:
            text = (
                f"Across the {total} measured volume point(s), no delay "
                f"difference exceeded the tie tolerance ({tol})"
                + (f", and {inconclusive} were inconclusive" if inconclusive else "")
                + " -- the measured data does not show either geometry as "
                "consistently better in this sweep."
            )
    elif changes == 1 and crossover is not None:
        directional = "reversal"
        first = sequence[0]
        other = "signal" if first == "roundabout" else "roundabout"
        n_first = sum(1 for r in runs if r.get("winner") == first)
        n_other = sum(1 for r in runs if r.get("winner") == other)
        volume_note = f" (~{crossover_h:,} veh/h total)" if crossover_h else ""
        text = (
            f"Measured delay reversed direction at an arrival rate of "
            f"{crossover:.3f} veh/s (whole junction){volume_note}. Below that "
            f"point the {_SIDE_NAME[first]} had the lower measured delay "
            f"({n_first} of {total} points); at or above it the "
            f"{_SIDE_NAME[other]} did ({n_other} of {total} points{extras})."
        )
    elif changes > 1:
        directional = "multiple_changes"
        text = (
            f"The control with the lower measured delay changed {changes} "
            f"times across the sweep (signal at {signal_wins}, roundabout at "
            f"{roundabout_wins} of {total} points{extras}); there is no "
            "single crossover and no consistent direction."
        )
    elif roundabout_wins > 0 and signal_wins > 0:
        directional = "mixed"
        leader = "signal" if signal_wins >= roundabout_wins else "roundabout"
        n_lead, n_other = (
            (signal_wins, roundabout_wins)
            if leader == "signal"
            else (roundabout_wins, signal_wins)
        )
        other = "roundabout" if leader == "signal" else "signal"
        text = (
            f"The {_SIDE_NAME[leader]} had the lower measured delay at "
            f"{n_lead} of {total} measured volume points ({other}: {n_other}"
            f"{extras}); each control had the lower delay at some points, so "
            "no single direction is supported."
        )
    elif roundabout_wins > 0:
        directional = "roundabout"
        text = (
            f"The roundabout had the lower measured delay at {roundabout_wins} "
            f"of {total} measured volume points (signal: 0{extras}); no "
            "delay-direction reversal was observed in this sweep."
        )
    else:
        directional = "signal"
        text = (
            f"The fixed-time signal had the lower measured delay at "
            f"{signal_wins} of {total} measured volume points (roundabout: 0"
            f"{extras}); no delay-direction reversal was observed in this "
            "sweep."
        )

    text += " " + _ONE_SEED_NOTE
    if calibration is not None and not calibration.get("calibrated", True):
        text += " " + str(calibration.get("note", ""))

    return {
        "status": "measured",
        "evidenceLevel": "single_seed_descriptive",
        "directional": directional,
        "roundaboutWins": roundabout_wins,
        "signalWins": signal_wins,
        "ties": ties,
        "inconclusive": inconclusive,
        "totalPoints": total,
        "crossoverArrivalRate": crossover,
        "crossoverHourlyVolume": crossover_h,
        "text": text,
    }


_VALIDATION_METRICS = (
    ("delay", "Delay", "s", "lower"),
    ("throughput", "Vehicles served", "veh", "higher"),
    ("queue", "Average queue", "veh", "lower"),
)


def _summarize_validation_evidence(validation: Dict[str, Any]) -> Dict[str, Any]:
    """States, per metric, what the repeated-seed study does and does not
    support. Direction is read from the two means; support is exactly the
    Welch test's ``significant`` flag at the study's own alpha. Nothing is
    inferred beyond that, and a non-significant result is never described as
    "no difference"."""
    comparison = validation.get("comparison") or {}
    n = validation.get("numSeeds")
    alpha = validation.get("alpha", 0.05)
    rows: List[Dict[str, Any]] = []
    sentences: List[str] = []

    for key, label, unit, _direction_word in _VALIDATION_METRICS:
        cmp = comparison.get(key)
        sig = (validation.get("signal") or {}).get(key)
        rnd = (validation.get("roundabout") or {}).get(key)
        if not cmp or not sig or not rnd:
            continue
        p = cmp.get("pValue")
        d = cmp.get("cohensD")
        supported = bool(cmp.get("significant"))
        s_mean, r_mean = sig.get("mean"), rnd.get("mean")
        lower = "signal" if (s_mean or 0) <= (r_mean or 0) else "roundabout"
        rows.append(
            {
                "metric": key,
                "signalMean": s_mean,
                "roundaboutMean": r_mean,
                "pValue": p,
                "cohensD": d,
                "supported": supported,
                "lowerMeanControl": lower,
            }
        )
        head = (
            f"{label}: signal mean {s_mean} {unit}, roundabout mean {r_mean} "
            f"{unit} over {n} random traffic patterns"
        )
        if p is None:
            sentences.append(head + "; no test was possible (fewer than 2 patterns).")
        elif supported:
            sentences.append(
                head
                + f"; the difference is statistically supported at alpha = {alpha} "
                f"(p = {p}, Cohen's d = {d}), with the lower mean at the "
                f"{_SIDE_NAME[lower]}."
            )
        else:
            sentences.append(
                head + f"; not statistically supported at alpha = {alpha} (p = {p}, "
                f"Cohen's d = {d}): this study cannot distinguish the controls "
                "on this metric, which is not the same as showing they are equal."
            )

    if not rows:
        return {
            "status": "unavailable",
            "metrics": [],
            "text": (
                "No repeated-seed validation was supplied, so no statistical "
                "statement is made."
            ),
        }
    return {"status": "available", "metrics": rows, "text": " ".join(sentences)}


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
    evidence = _summarize_validation_evidence(validation)
    evidence_summary = f"{verdict['text']} {evidence['text']}"

    report = {
        "title": "Comprehensive Comparative Traffic Simulation Study: Fixed-Time Signal vs. Modern Roundabout",
        "version": "1.1.0",
        "summary": {
            "totalVolumePointsEvaluated": verdict["totalPoints"],
            # Counts of demand points by which control had the LOWER mean
            # delay in this one-seed-per-point sweep. Descriptive, not a
            # ranking; kept under the original key names for compatibility.
            "roundaboutOptimalCount": verdict["roundaboutWins"],
            "signalOptimalCount": verdict["signalWins"],
            "tiedCount": verdict["ties"],
            "inconclusiveCount": verdict["inconclusive"],
            "criticalCrossoverArrivalRate": verdict["crossoverArrivalRate"],
            "criticalCrossoverHourlyVolume": verdict["crossoverHourlyVolume"],
            "directional": verdict["directional"],
            "calibration": sweep.get("calibration") or validation.get("calibration"),
            "sweepEvidence": verdict["text"],
            "validationEvidence": evidence,
            # Everything the study does and does not support, derived only
            # from this run's measurements and tests. "recommendation" is the
            # legacy name for the same text; it recommends nothing.
            "evidenceSummary": evidence_summary,
            "recommendation": evidence_summary,
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
            "Delay-ordering change, upper decided tier (veh/s)",
            data["summary"]["criticalCrossoverArrivalRate"] or "N/A",
        ]
    )
    writer.writerow(
        [
            "Delay-ordering change, upper decided tier (veh/h)",
            data["summary"]["criticalCrossoverHourlyVolume"] or "N/A",
        ]
    )
    sweep_meta = data.get("volumeSweep", {})
    val_meta = data.get("statisticalValidation", {})
    writer.writerow(["Sweep duration per point (s)", sweep_meta.get("duration")])
    writer.writerow(["Random patterns per sweep point", sweep_meta.get("seedsPerTier")])
    writer.writerow(["Sweep random seed", sweep_meta.get("randomSeed")])
    writer.writerow(["Validation random patterns", val_meta.get("numSeeds")])
    writer.writerow(["Validation duration per pattern (s)", val_meta.get("duration")])
    calibration = data["summary"].get("calibration") or {}
    if calibration:
        writer.writerow(
            [
                "Calibration",
                "calibrated" if calibration.get("calibrated") else "exploratory",
                calibration.get("note", ""),
            ]
        )
    # Derived only from this run's measurements and tests; it recommends nothing.
    writer.writerow(["Evidence summary", data["summary"]["evidenceSummary"]])
    writer.writerow([])

    # 2. Volume Sweep Comparison Table
    writer.writerow(["=== VOLUME SWEEP RESULTS ==="])
    writer.writerow(
        [
            "Arrival Rate (veh/s)",
            "Total Hourly Volume (veh/h)",
            "Signal Delay (s)",
            "Roundabout Delay (s)",
            # The sweep's "throughput" is a vehicle count (post-warm-up exits),
            # not a flow rate; it used to be labelled veh/h.
            "Signal Throughput (vehicles served)",
            "Roundabout Throughput (vehicles served)",
            "Signal Avg Queue",
            "Roundabout Avg Queue",
            "Lower mean delay (tie / inconclusive shown as such)",
            "Delay Delta (%) (roundabout vs signal; + = signal lower)",
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
    val = data.get("statisticalValidation", {})
    level = val.get("confidenceLevel", 0.95)
    writer.writerow(["=== STATISTICAL MONTE CARLO VALIDATION ==="])
    writer.writerow(
        [
            "Metric",
            "Signal Mean",
            "Signal StdDev",
            f"Signal {round(level * 100):g}% CI half-width (Student t)",
            "Roundabout Mean",
            "Roundabout StdDev",
            f"Roundabout {round(level * 100):g}% CI half-width (Student t)",
            "Welch p-value",
            "Cohen's d (+ = signal higher)",
            f"Significant at alpha = {val.get('alpha', 0.05)}",
        ]
    )

    for metric_name in ["delay", "throughput", "queue"]:
        sig_stat = val.get("signal", {}).get(metric_name, {})
        rnd_stat = val.get("roundabout", {}).get(metric_name, {})
        cmp = val.get("comparison", {}).get(metric_name, {})
        writer.writerow(
            [
                metric_name.capitalize(),
                sig_stat.get("mean"),
                sig_stat.get("std"),
                sig_stat.get("ci", sig_stat.get("ci95")),
                rnd_stat.get("mean"),
                rnd_stat.get("std"),
                rnd_stat.get("ci", rnd_stat.get("ci95")),
                cmp.get("pValue"),
                cmp.get("cohensD"),
                cmp.get("significant"),
            ]
        )

    return output.getvalue()
