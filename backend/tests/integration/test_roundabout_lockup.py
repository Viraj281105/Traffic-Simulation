"""A multi-lane roundabout must keep discharging traffic at high demand.

The existing roundabout guards only count collisions and sum throughput across
many seeds, so they cannot see a *lock-up*: a run in which the ring seizes and
almost nothing leaves for the rest of the simulation. That is exactly what
happened at high arrival rates on two lanes — for example rate 0.6 veh/s with
seed 2 recorded no collision at all yet cleared 3 vehicles in its last minute,
and rate 1.0 seed 3 recorded two and cleared none.

The cause was in the predictive resolver's give-way arbitration (see
``tests/intersection/test_predictive_conflicts.py``), which let two vehicles in
adjacent entry lanes swap the yielder role every tick. These tests run the
recorded failing configurations end to end and assert on what a lock-up
actually looks like from outside: nothing leaving.

Two measures, both robust to seed-level noise:

* vehicles cleared in the closing window — healthy runs clear 28-39 per minute
  at these demands, locked ones cleared 0-7;
* the longest stretch with no vehicle leaving at all — a healthy junction
  never goes quiet for long while its approaches are saturated.
"""

import copy
import logging
from typing import Any, Dict, List, Optional, Tuple

import pytest

from src.controllers.factory import build_tick_callback, create_controller
from src.core.clock import Clock
from src.core.engine import SimulationEngine
from src.metrics.collector import MetricCollector

TIME_STEP = 0.1

_BASE_CONFIG: Dict[str, Any] = {
    "simulation": {
        "duration": 180,
        "timeStep": TIME_STEP,
        "warmupTime": 10.0,
        "randomSeed": 1,
    },
    "geometry": {"intersectionType": "roundabout"},
    "roads": {"approachLength": 200.0, "laneWidth": 3.5, "lanesPerApproach": 2},
    "traffic": {
        "arrivalRate": 1.0,
        "arrivalDistribution": "poisson",
        "totalVehicles": 100000,
    },
    "controller": {
        "innerRadius": 10.0,
        "outerRadius": 20.0,
        "criticalGap": 4.0,
        "followUpTime": 2.5,
        "entrySpeed": 5.0,
        "circulatingSpeed": 8.0,
    },
}

_RunKey = Tuple[float, int, int, int]
_CACHE: Dict[_RunKey, Dict[str, float]] = {}


def _simulate(rate: float, lanes: int, seed: int, duration: int) -> Dict[str, float]:
    """Run one simulation and summarise how well it discharged traffic."""
    key = (rate, lanes, seed, duration)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached

    config = copy.deepcopy(_BASE_CONFIG)
    config["simulation"]["duration"] = duration
    config["simulation"]["randomSeed"] = seed
    config["roads"]["lanesPerApproach"] = lanes
    config["traffic"]["arrivalRate"] = rate

    clock = Clock(time_step=TIME_STEP)
    engine = SimulationEngine(clock, duration=duration, config=config)
    controller = create_controller(config, engine.network)
    engine.controller = controller
    collector = MetricCollector(config)
    engine.register_tick_callback(
        build_tick_callback(controller, clock, engine, collector)
    )

    # A collision logs a warning per event; a lock-up can log thousands.
    logging.getLogger("src.vehicles.pool").setLevel(logging.ERROR)

    window = int(60 / TIME_STEP)
    exited_by_tick: List[int] = []
    longest_gap = 0.0
    # Gaps are measured from the first exit onwards: the first vehicle needs
    # ~30 s just to cross the 200 m approach, the ring and the 200 m exit, and
    # that is transit time, not a stall.
    last_exit_at: Optional[float] = None
    seen = 0
    while engine.status.value.lower() != "completed":
        engine.step()
        now = clock.get_elapsed_time()
        exited = len(engine.pool.exited_vehicles)
        exited_by_tick.append(exited)
        if exited > seen:
            if last_exit_at is not None:
                longest_gap = max(longest_gap, now - last_exit_at)
            last_exit_at = now
            seen = exited
    if last_exit_at is not None:
        longest_gap = max(longest_gap, clock.get_elapsed_time() - last_exit_at)
    else:
        longest_gap = clock.get_elapsed_time()

    summary = {
        "exited": float(seen),
        "exited_last_minute": float(
            seen - exited_by_tick[max(0, len(exited_by_tick) - 1 - window)]
        ),
        "longest_gap": longest_gap,
        "collisions": float(engine.pool.collision_count),
    }
    _CACHE[key] = summary
    return summary


# The configurations that locked up before the fix, each of which had a
# different first victim: (arrival rate, lanes, seed).
_FORMER_LOCKUPS = [
    (0.6, 2, 2),  # no collision at all; 3 vehicles cleared in the last minute
    (1.0, 2, 2),  # no collision; nothing cleared in the last minute
    (1.0, 2, 3),  # first contact at 59.6 s, then nothing
    (1.5, 2, 1),  # gap in the arbitration re-locked it after a first partial fix
    (2.0, 2, 2),  # heaviest demand; first contact at 103.7 s
]


def test_two_lane_roundabout_keeps_discharging_at_high_demand_smoke() -> None:
    """Fast representative: the recorded 1.0 veh/s, seed 3 lock-up, 90 s.

    Before the fix this run stopped discharging altogether from about 30 s.
    """
    result = _simulate(rate=1.0, lanes=2, seed=3, duration=90)

    assert result["longest_gap"] <= 30.0, (
        f"nothing left the roundabout for {result['longest_gap']:.0f} s: {result}"
    )
    assert result["exited_last_minute"] >= 15, result


@pytest.mark.slow
@pytest.mark.parametrize("rate,lanes,seed", _FORMER_LOCKUPS)
def test_former_lockups_keep_discharging(rate: float, lanes: int, seed: int) -> None:
    result = _simulate(rate, lanes, seed, duration=180)

    assert result["exited_last_minute"] >= 15, (
        f"only {result['exited_last_minute']:.0f} vehicles cleared in the last "
        f"minute: {result}"
    )
    assert result["longest_gap"] <= 30.0, result


@pytest.mark.slow
@pytest.mark.parametrize("rate,lanes,seed", _FORMER_LOCKUPS)
def test_former_lockups_do_not_pay_for_it_in_collisions(
    rate: float, lanes: int, seed: int
) -> None:
    """Discharging is easy if vehicles simply drive through each other."""
    result = _simulate(rate, lanes, seed, duration=180)

    assert result["collisions"] <= 1, result
