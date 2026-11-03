"""Multi-seed runs of one scenario on one geometry.

``run_statistical_validation`` (study/validation.py) repeats a scenario on both
junction types and tests one against the other. This is the general primitive
underneath: repeat *one* scenario on *one* geometry over N seeds derived from a
base seed (study/seeds.py) and report each seed's metrics with a descriptive
summary. It reports no interval or p-value; those need a stated method and come
with the statistics module.

``default_study_config`` and ``seeded_run_config`` are shared with the
validation study so both prepare a repetition identically.
"""

import json
import math
import random
from typing import Any, Dict, List, Optional, Sequence

from src.core.limits import demand_vehicle_limit
from src.core.run_manifest import build_study_manifest
from src.study.calibration import demand_vph, study_warmup
from src.study.runner import GEOMETRY_TITLES, Progress, SimTask, run_simulation_tasks
from src.study.seeds import MAX_SEED, SEED_SCHEME, derive_run_seeds

# (result key, engine metric names tried in order)
SUMMARY_METRICS = (
    ("delay", ("averageDelay", "averageWaitTime")),
    ("throughput", ("throughput",)),
    ("queue", ("averageQueueLength",)),
)


def default_study_config(duration: float, time_step: float = 0.1) -> Dict[str, Any]:
    """The calibrated study scenario: one lane per approach, "busy" demand."""
    return {
        "simulation": {
            "timeStep": time_step,
            "duration": duration,
            "warmupTime": study_warmup(duration),
        },
        "roads": {
            "approachLength": 200.0,
            "laneWidth": 3.5,
            # One lane per approach: the calibrated comparison
            # (study/calibration.py).
            "lanesPerApproach": {"north": 1, "south": 1, "east": 1, "west": 1},
        },
        # "Busy": 75% of the measured 1-lane reference capacity.
        "traffic": {
            "arrivalRate": demand_vph("busy", 1) / 3600.0,
            "arrivalDistribution": "poisson",
        },
        "vehicleGeneration": {
            "stopSpeedThreshold": 0.1,
            "waitSpeedThreshold": 0.5,
            # Engine defaults: the calibrated study's vehicles (see live/dashboard_config.py).
        },
    }


def seeded_run_config(
    base_config: Dict[str, Any], seed: int, duration: float
) -> Dict[str, Any]:
    """A private copy of ``base_config`` for one repetition."""
    run_cfg: Dict[str, Any] = json.loads(json.dumps(base_config))
    run_cfg.setdefault("simulation", {})
    run_cfg["simulation"]["randomSeed"] = seed
    # As in the volume sweep: the validated request duration is the one
    # the engines run, and ticks are counted on their own clock.
    run_cfg["simulation"]["duration"] = duration
    # Size the vehicle limit to the scenario (unless set) so the default
    # cap cannot silently truncate the demand being repeated.
    run_traffic = run_cfg.setdefault("traffic", {})
    run_traffic.setdefault(
        "totalVehicles",
        demand_vehicle_limit(float(run_traffic.get("arrivalRate", 0.5)), duration),
    )
    return run_cfg


def _metric(metrics: Dict[str, Any], names: Sequence[str]) -> float:
    for name in names:
        value = metrics.get(name)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return 0.0


def describe(values: Sequence[float]) -> Dict[str, Any]:
    """n, mean, sample standard deviation (None below two values), min, max."""
    n = len(values)
    if n == 0:
        return {"n": 0, "mean": None, "sd": None, "min": None, "max": None}
    mean = math.fsum(values) / n
    sd: Optional[float] = None
    if n >= 2:
        sd = math.sqrt(math.fsum((v - mean) ** 2 for v in values) / (n - 1))
    return {"n": n, "mean": mean, "sd": sd, "min": min(values), "max": max(values)}


def run_multi_seed(
    config: Optional[Dict[str, Any]] = None,
    geometry: str = "signal",
    num_seeds: int = 5,
    duration: float = 30.0,
    base_seed: Optional[int] = None,
    progress: Optional[Progress] = None,
) -> Dict[str, Any]:
    """Run ``config`` on ``geometry`` over ``num_seeds`` seeds derived from ``base_seed``.

    Seeds are run in parallel and reported in seed order, so the result is the
    same however the workers finish. An omitted ``base_seed`` is drawn once and
    reported as ``baseSeed``.
    """
    if geometry not in GEOMETRY_TITLES:
        raise ValueError(f"geometry must be one of {sorted(GEOMETRY_TITLES)}")
    if num_seeds < 1:
        raise ValueError("num_seeds must be at least 1")
    base_config = config or default_study_config(duration)
    if base_seed is None:
        base_seed = random.randint(0, MAX_SEED)
    seeds = derive_run_seeds(base_seed, num_seeds)

    results = run_simulation_tasks(
        [
            SimTask(
                config=seeded_run_config(base_config, seed, duration),
                geometry=geometry,
                duration=duration,
                label=f"Seed {i + 1}/{num_seeds} · {GEOMETRY_TITLES[geometry]}",
                cost=1.5 if geometry == "roundabout" else 1.0,
            )
            for i, seed in enumerate(seeds)
        ],
        progress,
    )

    series: Dict[str, List[float]] = {key: [] for key, _ in SUMMARY_METRICS}
    seed_runs: List[Dict[str, Any]] = []
    limit_seeds: List[int] = []
    for seed, result in zip(seeds, results):
        metrics = result["metrics"]
        row: Dict[str, Any] = {"seed": seed}
        for key, names in SUMMARY_METRICS:
            value = _metric(metrics, names)
            series[key].append(value)
            row[key] = value
        if metrics.get("vehicleLimitReached"):
            limit_seeds.append(seed)
        seed_runs.append(row)

    return {
        "geometry": geometry,
        "numSeeds": num_seeds,
        "baseSeed": base_seed,
        "seedScheme": SEED_SCHEME,
        "manifest": build_study_manifest(
            config=base_config,
            run_mode="multi-seed",
            base_seed=base_seed,
            seed_scheme=SEED_SCHEME,
            duration=duration,
        ),
        "seeds": seeds,
        "duration": duration,
        "summary": {key: describe(values) for key, values in series.items()},
        "seedRuns": seed_runs,
        # Seeds whose run hit the vehicle-generation cap: their demand was
        # truncated, so they are not full-demand samples.
        "vehicleLimitReachedSeeds": limit_seeds,
        "method": {
            "summary": "n, mean, sample standard deviation (n - 1), min, max",
            "note": (
                "Descriptive only: no confidence interval or significance test "
                "is computed here."
            ),
        },
    }
