"""Fixed-time signal vs adaptive signal vs roundabout (V1.3).

A reproducible three-way study: at each demand level, every seed is run once
with each control on the same junction -- the same geometry, lane count,
vehicle population, arrival sequence (the seed fixes it, see
vehicles/spawner.py), duration and warm-up. The fixed-time and adaptive
signals also share one phase plan, yellow and all-red; only how a green ends
differs. Nothing is tuned per control.

Results are evidence, not a verdict. Per level it reports each control's mean
and Student-t interval, and for every pair a *paired* comparison of mean delay
(the same seeds run under both controls, so per-seed differences are tested):
the mean difference, its interval and a reading:

* ``lower`` / ``higher`` -- the interval excludes zero *and* the means differ
  by more than the shared tie tolerance (study/tolerances.py);
* ``tie`` -- the means are within the tie tolerance;
* ``inconclusive`` -- they differ by more than the tolerance, but the interval
  includes zero: these seeds cannot separate the two.
"""

from __future__ import annotations

import json
import math
from typing import Any, Dict, List, Optional, Sequence

from src.core.limits import demand_vehicle_limit
from src.study.calibration import (
    DEMAND_LEVEL_RATIOS,
    calibration_status,
    demand_vph,
    study_warmup,
)
from src.study.runner import Progress, SimTask, run_simulation_tasks
from src.study.tolerances import delays_are_tied, tie_tolerance
from src.study.validation import (
    DEFAULT_CONFIDENCE_LEVEL,
    _calculate_stats,
    _t_critical,
)

CONTROLS = ("fixed_time", "adaptive", "roundabout")
CONTROL_TITLES = {
    "fixed_time": "Fixed-time signal",
    "adaptive": "Adaptive signal",
    "roundabout": "Roundabout",
}
DEFAULT_LEVELS = ["light", "moderate", "busy", "near", "capacity", "over"]
DEFAULT_SEEDS = 5
DEFAULT_DURATION = 300.0

# Measures summarised per control (keys of MetricCollector.get_metrics()).
_MEASURES = (
    "averageDelay",
    "averageWaitTime",
    "throughput",
    "averageQueueLength",
    "maxQueueLength",
    "averageStopsPerVehicle",
    "travelTimeReliability",
)
# Signal-only green-time measures (metrics.signalTiming).
_SIGNAL_MEASURES = (
    "phaseChanges",
    "averageGreenDuration",
    "unusedGreenSeconds",
    "greenUtilisation",
)
_PAIRS = (
    ("adaptive", "fixed_time"),
    ("adaptive", "roundabout"),
    ("fixed_time", "roundabout"),
)


def _paired_delay(
    a: Sequence[float], b: Sequence[float], confidence: float
) -> Dict[str, Any]:
    """Paired comparison of per-seed mean delays (a - b)."""
    n = len(a)
    diffs = [x - y for x, y in zip(a, b)]
    mean_a = sum(a) / n
    mean_b = sum(b) / n
    mean_d = sum(diffs) / n
    if n > 1:
        sd = math.sqrt(sum((d - mean_d) ** 2 for d in diffs) / (n - 1))
        half = _t_critical(n - 1, confidence) * sd / math.sqrt(n)
    else:
        half = float("inf")
    low, high = mean_d - half, mean_d + half
    if delays_are_tied(mean_a, mean_b):
        reading = "tie"
    elif n > 1 and (high < 0 or low > 0):
        reading = "lower" if mean_d < 0 else "higher"
    else:
        reading = "inconclusive"
    return {
        "meanDifference": round(mean_d, 2),
        "ciLow": round(low, 2) if math.isfinite(low) else None,
        "ciHigh": round(high, 2) if math.isfinite(high) else None,
        "reading": reading,
    }


def _control_config(base: Dict[str, Any], control: str) -> Dict[str, Any]:
    cfg: Dict[str, Any] = json.loads(json.dumps(base))
    if control == "roundabout":
        return cfg
    ctrl = cfg.setdefault("controller", {})
    if control == "adaptive":
        ctrl["signalControl"] = "adaptive"
    else:
        ctrl.pop("signalControl", None)
        ctrl.pop("adaptive", None)
    return cfg


def run_scenario_comparison(
    document: Any,
    strategies: Sequence[str],
    num_seeds: int = DEFAULT_SEEDS,
    base_seed: Optional[int] = None,
    demand_scales: Optional[Sequence[float]] = None,
    confidence_level: float = DEFAULT_CONFIDENCE_LEVEL,
    progress: Optional[Progress] = None,
) -> Dict[str, Any]:
    """A user's own scenario (V1.4), run under each strategy over seeds.

    Every strategy is compiled from the same scenario document
    (core/scenario.py), so geometry, lanes, lane use, traffic, vehicle mix,
    duration, warm-up and seed are identical by construction; only the
    control section differs. ``demand_scales`` optionally repeats the study
    with every approach's demand scaled (1.0 = as configured). Seeds run
    ``base_seed`` (default: the scenario's own seed) onwards.
    """
    from src.core.scenario import (
        STRATEGY_TITLES,
        compile_scenario,
        scenario_fingerprint,
        total_vehicles_per_hour,
    )

    strategies = [s for s in strategies]
    scales = [float(s) for s in (demand_scales or [1.0])]
    first_seed = document.simulation.seed if base_seed is None else base_seed
    seeds = [first_seed + i for i in range(num_seeds)]
    duration = document.simulation.duration

    tasks: List[SimTask] = []
    keys: List[tuple[float, int, str]] = []
    compiled: Dict[str, Dict[str, Any]] = {}
    for scale in scales:
        scaled = document.model_copy(deep=True)
        # Every arm that exists (V1.5: a three-arm junction has three).
        for arm in scaled.approaches.present().values():
            arm.vehiclesPerHour = arm.vehiclesPerHour * scale
        for seed in seeds:
            scaled.simulation.seed = seed
            for strategy in strategies:
                cfg = compile_scenario(scaled, strategy)
                if scale == scales[0] and seed == seeds[0]:
                    compiled[strategy] = cfg
                tasks.append(
                    SimTask(
                        config=cfg,
                        geometry="roundabout" if strategy == "roundabout" else "signal",
                        duration=duration,
                        label=f"x{scale:g} · seed {seed} · {STRATEGY_TITLES[strategy]}",
                        cost=(1.5 if strategy == "roundabout" else 1.0) * (1.0 + scale),
                    )
                )
                keys.append((scale, seed, strategy))
    results = run_simulation_tasks(tasks, progress)
    by_key = {key: res for key, res in zip(keys, results)}

    pairs = [(a, b) for i, a in enumerate(strategies) for b in strategies[i + 1 :]]
    collisions = {s: 0 for s in strategies}
    per_seed: List[Dict[str, Any]] = []
    rows: List[Dict[str, Any]] = []
    base_vph = total_vehicles_per_hour(document)
    for scale in scales:
        values: Dict[str, Dict[str, List[float]]] = {
            s: {m: [] for m in _MEASURES + _SIGNAL_MEASURES} for s in strategies
        }
        limit_hit = False
        for seed in seeds:
            row: Dict[str, Any] = {"demandScale": scale, "seed": seed}
            for strategy in strategies:
                res = by_key[(scale, seed, strategy)]
                m = res["metrics"]
                collisions[strategy] += int(m.get("collisionCount") or 0)
                limit_hit = limit_hit or bool(m.get("vehicleLimitReached"))
                for key in _MEASURES:
                    v = m.get(key)
                    if isinstance(v, (int, float)):
                        values[strategy][key].append(float(v))
                timing = m.get("signalTiming") or {}
                for key in _SIGNAL_MEASURES:
                    v = timing.get(key)
                    if isinstance(v, (int, float)):
                        values[strategy][key].append(float(v))
                row[strategy] = {
                    "averageDelay": m.get("averageDelay"),
                    "throughput": m.get("throughput"),
                    "averageQueueLength": m.get("averageQueueLength"),
                    "collisionCount": m.get("collisionCount"),
                    "activeVehicleCount": m.get("activeVehicleCount"),
                    "vehicleTypeBreakdown": m.get("vehicleTypeBreakdown"),
                    "approachBreakdown": m.get("approachBreakdown"),
                    "signalTiming": m.get("signalTiming"),
                }
            per_seed.append(row)
        stats = {
            s: {
                key: _calculate_stats(vals, confidence_level)
                for key, vals in values[s].items()
                if vals
            }
            for s in strategies
        }
        delays = {s: values[s]["averageDelay"] for s in strategies}
        comparisons = {}
        if all(len(delays[s]) == len(seeds) for s in strategies):
            comparisons = {
                f"{a}_vs_{b}": _paired_delay(delays[a], delays[b], confidence_level)
                for a, b in pairs
            }
        rows.append(
            {
                "demandScale": scale,
                "demandVph": round(base_vph * scale),
                "vehicleLimitReached": limit_hit,
                "controls": stats,
                "delayComparisons": comparisons,
            }
        )

    any_config = next(iter(compiled.values()))
    return {
        "study": "scenario-comparison",
        "scenario": document.model_dump(),
        "fingerprint": scenario_fingerprint(document),
        "controls": list(strategies),
        "demandScales": scales,
        "seeds": seeds,
        "duration": duration,
        "warmupTime": document.simulation.warmup,
        "confidenceLevel": confidence_level,
        "calibration": calibration_status(any_config),
        "tieTolerance": tie_tolerance(),
        "collisionCount": collisions,
        # The exact engine configuration each strategy ran (first seed, first
        # demand scale), so a reader can see that only the control differs.
        "compiledConfigs": compiled,
        "method": {
            "design": (
                "Every seed is run once under each strategy, each compiled from "
                "the same scenario document: same approaches, lanes, lane use, "
                "demand, turning, vehicles, arrival sequence, duration and "
                "warm-up. Only the control section differs."
            ),
            "interval": "mean +/- t(n-1) * s / sqrt(n), two-sided Student-t",
            "delayComparison": (
                "Paired per-seed differences in mean delay (first strategy minus "
                "second), Student-t interval on the mean difference. 'lower'/"
                "'higher' needs the interval to exclude zero and the means to "
                "differ by more than the tie tolerance; 'tie' means within the "
                "tolerance; otherwise 'inconclusive'. No multiple-comparison "
                "correction."
            ),
        },
        "results": rows,
        "perSeed": per_seed,
    }


def run_control_comparison(
    lanes: int = 1,
    levels: Optional[List[str]] = None,
    num_seeds: int = DEFAULT_SEEDS,
    base_seed: int = 1,
    duration: float = DEFAULT_DURATION,
    adaptive: Optional[Dict[str, Any]] = None,
    vehicle_mix: Optional[Dict[str, float]] = None,
    confidence_level: float = DEFAULT_CONFIDENCE_LEVEL,
    progress: Optional[Progress] = None,
) -> Dict[str, Any]:
    levels = list(levels or DEFAULT_LEVELS)
    unknown = [lv for lv in levels if lv not in DEMAND_LEVEL_RATIOS]
    if unknown:
        raise ValueError(f"Unknown demand levels: {', '.join(unknown)}")
    seeds = [base_seed + i for i in range(num_seeds)]

    base: Dict[str, Any] = {
        "simulation": {
            "timeStep": 0.1,
            "duration": duration,
            "warmupTime": study_warmup(duration),
        },
        "roads": {
            "approachLength": 200.0,
            "laneWidth": 3.5,
            "lanesPerApproach": {d: lanes for d in ("north", "south", "east", "west")},
        },
        "traffic": {"arrivalDistribution": "poisson"},
        "vehicleGeneration": {"stopSpeedThreshold": 0.1, "waitSpeedThreshold": 0.5},
        # The canonical paired NS/EW plan for both signals (the orchestrator
        # fills it in); adaptive settings are carried for the adaptive side.
        "controller": {"adaptive": dict(adaptive)} if adaptive else {},
    }
    if vehicle_mix:
        base["vehicleGeneration"]["vehicleMix"] = dict(vehicle_mix)

    tasks: List[SimTask] = []
    keys: List[tuple[str, int, str]] = []
    for level in levels:
        rate = demand_vph(level, lanes) / 3600.0
        for seed in seeds:
            run_base = json.loads(json.dumps(base))
            run_base["simulation"]["randomSeed"] = seed
            run_base["traffic"]["arrivalRate"] = rate
            run_base["traffic"]["totalVehicles"] = demand_vehicle_limit(rate, duration)
            for control in CONTROLS:
                tasks.append(
                    SimTask(
                        config=_control_config(run_base, control),
                        geometry="roundabout" if control == "roundabout" else "signal",
                        duration=duration,
                        label=f"{level} · seed {seed} · {CONTROL_TITLES[control]}",
                        cost=(1.5 if control == "roundabout" else 1.0)
                        * (1.0 + DEMAND_LEVEL_RATIOS[level]),
                    )
                )
                keys.append((level, seed, control))
    results = run_simulation_tasks(tasks, progress)

    by_key = {key: res for key, res in zip(keys, results)}
    level_rows: List[Dict[str, Any]] = []
    per_seed: List[Dict[str, Any]] = []
    collisions = {c: 0 for c in CONTROLS}
    for level in levels:
        values: Dict[str, Dict[str, List[float]]] = {
            c: {m: [] for m in _MEASURES + _SIGNAL_MEASURES} for c in CONTROLS
        }
        limit_hit = False
        for seed in seeds:
            row: Dict[str, Any] = {"level": level, "seed": seed}
            for control in CONTROLS:
                res = by_key[(level, seed, control)]
                m = res["metrics"]
                collisions[control] += int(m.get("collisionCount") or 0)
                limit_hit = limit_hit or bool(m.get("vehicleLimitReached"))
                for key in _MEASURES:
                    v = m.get(key)
                    if isinstance(v, (int, float)):
                        values[control][key].append(float(v))
                timing = m.get("signalTiming") or {}
                for key in _SIGNAL_MEASURES:
                    v = timing.get(key)
                    if isinstance(v, (int, float)):
                        values[control][key].append(float(v))
                row[control] = {
                    "averageDelay": m.get("averageDelay"),
                    "throughput": m.get("throughput"),
                    "averageQueueLength": m.get("averageQueueLength"),
                    "collisionCount": m.get("collisionCount"),
                    "activeVehicleCount": m.get("activeVehicleCount"),
                    "signalTiming": m.get("signalTiming"),
                }
                if control == "adaptive":
                    state = (res.get("controllerState") or {}).get("adaptive")
                    if state:
                        row[control]["decisions"] = state.get("decisions")
            per_seed.append(row)

        stats = {
            c: {
                key: _calculate_stats(vals, confidence_level)
                for key, vals in values[c].items()
                if vals
            }
            for c in CONTROLS
        }
        delays = {c: values[c]["averageDelay"] for c in CONTROLS}
        comparisons = {}
        if all(len(delays[c]) == len(seeds) for c in CONTROLS):
            comparisons = {
                f"{a}_vs_{b}": _paired_delay(delays[a], delays[b], confidence_level)
                for a, b in _PAIRS
            }
        level_rows.append(
            {
                "level": level,
                "arrivalRate": round(demand_vph(level, lanes) / 3600.0, 4),
                "demandVph": demand_vph(level, lanes),
                "degreeOfSaturation": DEMAND_LEVEL_RATIOS[level],
                "vehicleLimitReached": limit_hit,
                "controls": stats,
                "delayComparisons": comparisons,
            }
        )

    adaptive_settings = _control_config(base, "adaptive")["controller"]
    return {
        "study": "control-comparison",
        "controls": list(CONTROLS),
        "lanesPerApproach": lanes,
        "levels": levels,
        "seeds": seeds,
        "duration": duration,
        "warmupTime": base["simulation"]["warmupTime"],
        "confidenceLevel": confidence_level,
        "adaptiveSettings": adaptive_settings.get("adaptive") or {},
        "vehicleMix": vehicle_mix,
        "calibration": calibration_status(base),
        "tieTolerance": tie_tolerance(),
        "collisionCount": collisions,
        "method": {
            "design": (
                "Every seed is run once under each control: same geometry, "
                "lanes, vehicles, arrival sequence, duration and warm-up. Both "
                "signals use the same paired north-south / east-west plan, "
                "yellow and all-red."
            ),
            "interval": "mean +/- t(n-1) * s / sqrt(n), two-sided Student-t",
            "delayComparison": (
                "Paired per-seed differences in mean delay (first control minus "
                "second), Student-t interval on the mean difference. 'lower'/"
                "'higher' needs the interval to exclude zero and the means to "
                "differ by more than the tie tolerance; 'tie' means within the "
                "tolerance; otherwise 'inconclusive'. Several levels and pairs "
                "are read without multiple-comparison correction."
            ),
        },
        "results": level_rows,
        "perSeed": per_seed,
    }
