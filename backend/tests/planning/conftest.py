"""Fixtures for the V2.0 planning tests: a canned comparison function that has
the shape of ``run_scenario_comparison`` output, so evidence logic is tested
without simulating."""

from typing import Any, Callable, Dict, List, Optional

import pytest

from src.core.scenario import scenario_fingerprint
from src.planning.service import PlanningService, PlanningStore
from src.study.validation import _calculate_stats

SCENARIO: Dict[str, Any] = {
    "format": "urbanflow-scenario",
    "version": 1,
    "name": "Test junction",
    "junction": {"type": "fixed_time_signal"},
    "approaches": {
        d: {
            "lanes": 1,
            "vehiclesPerHour": 300,
            "turning": {"left": 0.2, "straight": 0.6, "right": 0.2},
        }
        for d in ("north", "south", "east", "west")
    },
    "simulation": {"duration": 30, "warmup": 5, "seed": 3},
}


def study(**over: Any) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "format": "urbanflow-planning-study",
        "version": 1,
        "name": "Test study",
        "subject": {"scenario": SCENARIO},
        "alternatives": [
            {"id": "base", "label": "Fixed", "strategy": "fixed_time"},
            {"id": "adapt", "label": "Adaptive", "strategy": "adaptive"},
            {"id": "rbt", "label": "Roundabout", "strategy": "roundabout"},
        ],
        "repetitions": {"seeds": 5},
    }
    body.update(over)
    return body


# strategy -> (mean delay, per-seed jitter, mean throughput)
DEFAULT_PROFILE = {
    "fixed_time": (30.0, 0.5, 100.0),
    "adaptive": (20.0, 0.5, 100.0),  # clearly lower delay
    "roundabout": (30.2, 3.0, 110.0),  # delay similar/noisy, more vehicles
}


def make_fake(
    profile: Optional[Dict[str, Any]] = None,
    calls: Optional[List[Any]] = None,
    scale_effect: Optional[Callable[[str, float], float]] = None,
) -> Callable[..., Dict[str, Any]]:
    profile = profile or DEFAULT_PROFILE

    def fake(
        document,
        strategies,
        num_seeds=5,
        base_seed=None,
        demand_scales=None,
        confidence_level=0.95,
        progress=None,
    ):
        if calls is not None:
            calls.append((tuple(strategies), document.model_dump().get("signal")))
        scales = list(demand_scales or [1.0])
        first = document.simulation.seed if base_seed is None else base_seed
        seeds = [first + i for i in range(num_seeds)]
        rows, per_seed = [], []
        for scale in scales:
            controls = {}
            for s in strategies:
                mean_d, jit, mean_t = profile[s]
                if scale_effect:
                    mean_d = scale_effect(s, scale)
                delays = [mean_d + jit * ((i % 3) - 1) for i in range(num_seeds)]
                thr = [mean_t + (i % 2) for i in range(num_seeds)]
                queues = [mean_d / 10 + 0.1 * i for i in range(num_seeds)]
                controls[s] = {
                    "averageDelay": _calculate_stats(delays, confidence_level),
                    "throughput": _calculate_stats(thr, confidence_level),
                    "averageQueueLength": _calculate_stats(queues, confidence_level),
                    "maxQueueLength": _calculate_stats(
                        [q * 2 for q in queues], confidence_level
                    ),
                    "averageStopsPerVehicle": _calculate_stats(
                        [1.0] * num_seeds, confidence_level
                    ),
                    "travelTimeReliability": _calculate_stats(
                        [1.2] * num_seeds, confidence_level
                    ),
                }
                if s != "roundabout":
                    controls[s]["greenUtilisation"] = _calculate_stats(
                        [0.6] * num_seeds, confidence_level
                    )
                for i, seed in enumerate(seeds):
                    per_seed.append(
                        {
                            "demandScale": scale,
                            "seed": seed,
                            "_i": i,
                            "_s": s,
                            "vals": (delays[i], thr[i], queues[i]),
                        }
                    )
            rows.append(
                {
                    "demandScale": scale,
                    "demandVph": round(1200 * scale),
                    "vehicleLimitReached": False,
                    "controls": controls,
                    "delayComparisons": {},
                }
            )
        seed_rows = []
        for scale in scales:
            for i, seed in enumerate(seeds):
                row: Dict[str, Any] = {"demandScale": scale, "seed": seed}
                for p in per_seed:
                    if p["demandScale"] == scale and p["seed"] == seed:
                        d, t, q = p["vals"]
                        row[p["_s"]] = {
                            "averageDelay": d,
                            "throughput": t,
                            "averageQueueLength": q,
                            "collisionCount": 0,
                            "approachBreakdown": {
                                "north": {
                                    "exited": 10,
                                    "averageDelay": d,
                                    "averageQueueLength": q,
                                    "maxQueueLength": 2,
                                }
                            },
                            "vehicleTypeBreakdown": {
                                "car": {"exited": 10, "share": 1.0, "averageDelay": d}
                            },
                            "signalTiming": None,
                        }
                seed_rows.append(row)
        return {
            "study": "scenario-comparison",
            "fingerprint": scenario_fingerprint(document),
            "controls": list(strategies),
            "demandScales": scales,
            "seeds": seeds,
            "duration": document.simulation.duration,
            "warmupTime": document.simulation.warmup,
            "confidenceLevel": confidence_level,
            "calibration": {
                "calibrated": False,
                "note": "More than one lane or mixed traffic",
            },
            "tieTolerance": {"absSeconds": 1.0, "relative": 0.05},
            "compiledConfigs": {s: {"strategy": s} for s in strategies},
            "method": {"delayComparison": "paired"},
            "results": rows,
            "perSeed": seed_rows,
        }

    return fake


@pytest.fixture
def fake_service() -> PlanningService:
    return PlanningService(
        store=PlanningStore(persist=False), comparison_fn=make_fake()
    )
