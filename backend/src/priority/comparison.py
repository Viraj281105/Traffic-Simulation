"""With-versus-without comparisons over seeds (F12), using the repository's
paired statistics (``uncertainty.comparison``).

Every seed is run twice on identical background traffic: arm A with priority,
arm B without. Seeds are the unit of analysis; per-seed means are paired and
compared with a paired interval and test. Results are in-model only.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from src.priority.audit import audit_phase_log
from src.priority.models import (
    EmergencySpec,
    PreemptionConfig,
    ScenarioSpec,
    TransitLineSpec,
    TransitPriorityConfig,
    YieldConfig,
    check_seed_budget,
)
from src.priority.runs import PriorityRun, build_run, execute
from src.uncertainty.comparison import compare_paired, verdict

IN_MODEL_LABEL = (
    "In-model only: results describe this simulation model and its assumed "
    "parameters, not observed emergency-response or transit performance."
)

Metric = Tuple[str, str]  # (key, plain label)


def _compare(
    key: str,
    label: str,
    a: Sequence[float],
    b: Sequence[float],
    method: str,
    confidence: float,
    seed: int,
    lower_is_better: bool = True,
) -> Dict[str, Any]:
    result = compare_paired(a, b, method=method, confidence=confidence, seed=seed)
    out = result.to_dict()
    out["metric"] = key
    out["label"] = label
    out["verdict"] = verdict(result, lower_is_better=lower_is_better)
    out["lowerIsBetter"] = lower_is_better
    out["meanBaseline"] = result.mean_b
    out["meanWithPriority"] = result.mean_a
    out["changePercent"] = (
        round(100.0 * result.difference / result.mean_b, 2) if result.mean_b else None
    )
    return out


def _signal_audit(run: PriorityRun, min_green_s: float) -> Dict[str, Any]:
    spec = run.spec
    return audit_phase_log(
        run.controller.phase_log,
        yellow_s=spec.yellow_s,
        all_red_s=spec.all_red_s,
        min_green_s=min_green_s,
        time_step_s=spec.time_step_s,
    )


def _arm_summary(
    seeds: Sequence[int],
    runs: Sequence[Dict[str, Any]],
    audits: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "collisions": [m["collisions"] for m in runs],
        "vehiclesConserved": all(m["vehicles"]["conserved"] for m in runs),
        "signalAuditOk": all(a["ok"] for a in audits),
        "signalViolations": [v for a in audits for v in a["violations"]],
        "preemptions": [m["signal"]["preemptions"] for m in runs],
    }


def _emergency_means(metrics: Dict[str, Any]) -> Optional[Dict[str, float]]:
    records = metrics["emergency"]
    if (
        not records
        or metrics["emergencyNotPlaced"]
        or not all(r["completed"] for r in records)
    ):
        return None
    n = len(records)
    return {
        "travelTime": sum(r["travelTime"] for r in records) / n,
        "delay": sum(r["delay"] for r in records) / n,
        "waitTime": sum(r["waitTime"] for r in records) / n,
        "collateral": float(metrics["nonEmergency"]["meanTimeLost"]),
    }


def run_emergency_comparison(
    spec: ScenarioSpec,
    emergencies: Sequence[EmergencySpec],
    preemption: PreemptionConfig,
    yielding: YieldConfig,
    seeds: Sequence[int],
    method: str = "paired_t",
    confidence: float = 0.95,
    progress: Optional[Callable[[int, int], None]] = None,
) -> Dict[str, Any]:
    """Pre-emption on (A) versus off (B), same seeds, same emergency schedule,
    same yielding behaviour in both arms. ``preemption.enabled`` is ignored:
    arm A always has it on, arm B never."""
    if not emergencies:
        raise ValueError("give at least one emergency vehicle")
    check_seed_budget(len(seeds), spec.duration_s)
    on = replace(preemption, enabled=True)
    per_seed: Dict[str, List[Dict[str, Any]]] = {"withPreemption": [], "baseline": []}
    audits: Dict[str, List[Dict[str, Any]]] = {"withPreemption": [], "baseline": []}
    kept: List[int] = []
    dropped: List[Dict[str, Any]] = []
    series: Dict[str, Dict[str, List[float]]] = {
        "withPreemption": {
            k: [] for k in ("travelTime", "delay", "waitTime", "collateral")
        },
        "baseline": {k: [] for k in ("travelTime", "delay", "waitTime", "collateral")},
    }
    for i, seed in enumerate(seeds):
        runs = {}
        for arm, cfg in (("withPreemption", on), ("baseline", None)):
            run = build_run(
                spec,
                seed,
                emergencies=emergencies,
                preemption=cfg,
                yielding=yielding,
            )
            runs[arm] = (run, execute(run))
        means = {arm: _emergency_means(m) for arm, (_, m) in runs.items()}
        for arm, (run, metrics) in runs.items():
            per_seed[arm].append(metrics)
            audits[arm].append(_signal_audit(run, on.min_green_s))
        if all(v is not None for v in means.values()):
            kept.append(seed)
            for arm, values in means.items():
                assert values is not None
                for key, number in values.items():
                    series[arm][key].append(number)
        else:
            dropped.append(
                {
                    "seed": seed,
                    "reason": "an emergency vehicle did not enter or did not finish in one arm",
                }
            )
        if progress is not None:
            progress(i + 1, len(seeds))
    if len(kept) < 2:
        raise ValueError(
            "fewer than two seeds finished every emergency vehicle in both arms; "
            "lengthen the run or move the vehicle earlier"
        )
    a, b = series["withPreemption"], series["baseline"]
    comparisons = {
        "emergencyTravelTime": _compare(
            "emergencyTravelTime",
            "Emergency vehicle travel time (s)",
            a["travelTime"],
            b["travelTime"],
            method,
            confidence,
            1,
        ),
        "emergencyDelay": _compare(
            "emergencyDelay",
            "Emergency vehicle delay versus free flow (s)",
            a["delay"],
            b["delay"],
            method,
            confidence,
            2,
        ),
        "emergencyWaitTime": _compare(
            "emergencyWaitTime",
            "Emergency vehicle time stopped (s)",
            a["waitTime"],
            b["waitTime"],
            method,
            confidence,
            3,
        ),
        "collateralDelay": _compare(
            "collateralDelay",
            "Mean time lost by other vehicles (s per vehicle)",
            a["collateral"],
            b["collateral"],
            method,
            confidence,
            4,
        ),
    }
    return {
        "kind": "emergency-comparison",
        "inModelOnly": True,
        "label": IN_MODEL_LABEL,
        "method": method,
        "confidence": confidence,
        "seeds": kept,
        "droppedSeeds": dropped,
        "perSeed": {
            arm: {
                "travelTime": series[arm]["travelTime"],
                "delay": series[arm]["delay"],
                "waitTime": series[arm]["waitTime"],
                "collateralDelay": series[arm]["collateral"],
            }
            for arm in series
        },
        "comparison": comparisons,
        "safety": {
            arm: _arm_summary(seeds, per_seed[arm], audits[arm]) for arm in per_seed
        },
        "runs": {arm: [_run_view(m) for m in per_seed[arm]] for arm in per_seed},
    }


def _run_view(metrics: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "seed": metrics["seed"],
        "emergency": metrics["emergency"],
        "vehicles": metrics["vehicles"],
        "collisions": metrics["collisions"],
        "nonEmergency": metrics["nonEmergency"],
        "signal": {k: v for k, v in metrics["signal"].items() if k != "events"},
    }


def run_transit_comparison(
    spec: ScenarioSpec,
    lines: Sequence[TransitLineSpec],
    priority: TransitPriorityConfig,
    seeds: Sequence[int],
    method: str = "paired_t",
    confidence: float = 0.95,
) -> Dict[str, Any]:
    """Conditional transit priority on (A) versus off (B), same seeds and
    timetable. ``priority.enabled`` is ignored: arm A has it, arm B does not."""
    if not lines:
        raise ValueError("give at least one transit line")
    check_seed_budget(len(seeds), spec.duration_s)
    on = replace(priority, enabled=True)
    keys = (
        "lateness",
        "busTimeLost",
        "personDelay",
        "vehicleDelay",
        "otherDelay",
    )
    series: Dict[str, Dict[str, List[float]]] = {
        "withPriority": {k: [] for k in keys},
        "baseline": {k: [] for k in keys},
    }
    per_seed: Dict[str, List[Dict[str, Any]]] = {"withPriority": [], "baseline": []}
    audits: Dict[str, List[Dict[str, Any]]] = {"withPriority": [], "baseline": []}
    kept: List[int] = []
    dropped: List[Dict[str, Any]] = []
    for seed in seeds:
        runs = {}
        for arm, cfg in (("withPriority", on), ("baseline", None)):
            run = build_run(
                spec,
                seed,
                transit_lines=lines,
                transit=cfg,
                schedule_padding_s=priority.schedule_padding_s,
            )
            runs[arm] = (run, execute(run))
        usable = all(m["transit"]["busesCrossed"] > 0 for _, m in runs.values())
        for arm, (run, metrics) in runs.items():
            per_seed[arm].append(metrics)
            audits[arm].append(_signal_audit(run, on.min_green_s))
        if not usable:
            dropped.append(
                {"seed": seed, "reason": "no bus reached the stop line in one arm"}
            )
            continue
        kept.append(seed)
        for arm, (_, metrics) in runs.items():
            t = metrics["transit"]
            series[arm]["lateness"].append(t["meanScheduleLateness"])
            series[arm]["busTimeLost"].append(t["meanBusTimeLost"])
            series[arm]["personDelay"].append(t["personDelayPerPerson"])
            series[arm]["vehicleDelay"].append(t["vehicleDelayMean"])
            series[arm]["otherDelay"].append(t["otherVehicleDelayMean"])
    if len(kept) < 2:
        raise ValueError(
            "fewer than two seeds had a bus reach the stop line in both arms; "
            "lengthen the run or start the buses earlier"
        )
    a, b = series["withPriority"], series["baseline"]
    labels = {
        "lateness": ("busScheduleLateness", "Bus lateness at the stop line (s)"),
        "busTimeLost": ("busTimeLost", "Bus time lost excluding dwell (s)"),
        "personDelay": ("personDelayPerPerson", "Person delay (s per person)"),
        "vehicleDelay": ("vehicleDelay", "Vehicle delay (s per vehicle)"),
        "otherDelay": (
            "otherVehicleDelay",
            "Delay of non-line vehicles (s per vehicle)",
        ),
    }
    comparisons = {
        name: _compare(name, label, a[k], b[k], method, confidence, i)
        for i, (k, (name, label)) in enumerate(labels.items())
    }
    return {
        "kind": "transit-comparison",
        "inModelOnly": True,
        "label": IN_MODEL_LABEL,
        "method": method,
        "confidence": confidence,
        "seeds": kept,
        "droppedSeeds": dropped,
        "perSeed": {
            arm: {labels[k][0]: series[arm][k] for k in keys} for arm in series
        },
        "comparison": comparisons,
        "safety": {
            arm: _arm_summary(seeds, per_seed[arm], audits[arm]) for arm in per_seed
        },
        "runs": {
            arm: [
                {
                    "seed": m["seed"],
                    "transit": m["transit"],
                    "vehicles": m["vehicles"],
                    "collisions": m["collisions"],
                    "signal": {k: v for k, v in m["signal"].items() if k != "events"},
                }
                for m in per_seed[arm]
            ]
            for arm in per_seed
        },
    }
