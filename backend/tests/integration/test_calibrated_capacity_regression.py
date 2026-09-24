"""Regression guard for the calibrated 1-lane capacity curve published in
docs/reports/comparative_report.md §2.

This is the exact scenario the project already treats as the sole
calibrated comparison (see that doc's "Scope and validity" section): 1 lane
per approach, duration=240s, warmupTime=30s (210s measurement window),
timeStep=0.1, seed=1, for both intersection types across the report's nine
offered-demand points. It exists because those numbers went stale silently
once before -- the signal's saturation figure moved from 1800 to ~1700
veh/h when the junction-gridlock fix (commit 89bb887) landed, and it took a
manual audit to catch (see v1-known-limitations.md §2). This test is that
audit, automated.

Config construction deliberately does not reuse test_signal_capacity.py's
or test_roundabout_conflicts.py's own `_run()` helpers: both memoise by a
cache key that does not include duration or arrival rate
(`(intersectionType, seed, lanes)` in test_roundabout_conflicts.py), so
calling either with a different duration/rate than that file's own fixed
config would silently return a stale cached result from an unrelated run.
The construction below uses the same primitives those helpers do
(SimulationEngine + create_controller + MetricCollector) with its own
correctly-scoped cache, so it reuses the established pattern without
inheriting that hazard.

Tolerances (see the table below) are tight and were derived from actually
re-running this exact scenario on current HEAD, not loosened to make the
test pass:
  - servedVehPerHour: +/-0.5 veh/h -- the report rounds this to the nearest
    integer; the simulation is deterministic for a fixed seed, so this
    tolerance only accounts for that rounding, not simulation variance.
  - delay: +/-0.05s -- the report rounds to one decimal place.
  - maxQueueLength: exact integer match -- re-verification showed every one
    of the 18 (9 points x 2 geometries) values matches exactly, so no slack
    is warranted.
"""

import copy
from typing import Any, Dict, Tuple

import pytest

from src.controllers.factory import build_tick_callback, create_controller
from src.core.clock import Clock
from src.core.engine import SimulationEngine
from src.metrics.collector import MetricCollector

DURATION = 240.0
WARMUP_TIME = 30.0
MEASURED_WINDOW = DURATION - WARMUP_TIME  # 210.0
TIME_STEP = 0.1
LANES_PER_APPROACH = 1
SEED = 1

SIGNAL_CONTROLLER: Dict[str, Any] = {
    "straightRightDuration": 30.0,
    "leftDuration": 5.0,
    "yellowDuration": 4.0,
    "allRedDuration": 2.0,
    "phaseSequence": [
        "ns_green",
        "ns_yellow",
        "all_red",
        "ew_green",
        "ew_yellow",
        "all_red",
    ],
}

ROUNDABOUT_CONTROLLER: Dict[str, Any] = {
    "innerRadius": 10.0,
    "outerRadius": 20.0,
    "circulatingLanes": 1,
    "criticalGap": 4.0,
    "followUpTime": 2.5,
    "entrySpeed": 5.0,
    "circulatingSpeed": 8.0,
}

# offered veh/h -> (signal servedVehPerHour, signal delay s, signal maxQueue,
#                   roundabout servedVehPerHour, roundabout delay s, roundabout maxQueue)
# Re-measured 2026-09-24 after the bug-fix pass recorded in
# docs/bug-fix-report.md (safe insertion speed, turn intent kept across blocked
# spawns, roundabout approach braking taper, yellow-runner admission, refused
# vehicles held at the stop line). Each of those changes the simulated physics,
# so the previous pins (HEAD 73960af) no longer describe the model; the
# attribution of each shift is in that report. Matches
# docs/reports/comparative_report.md §2 at every point within the tolerances.
PINNED_CURVE: Dict[int, Tuple[float, float, int, float, float, int]] = {
    360: (291.4286, 15.98, 2, 291.4286, 18.69, 1),
    720: (600.0000, 17.10, 5, 600.0000, 21.89, 2),
    1080: (857.1429, 22.23, 9, 874.2857, 25.48, 6),
    1440: (1165.7143, 26.74, 12, 1097.1429, 37.09, 13),
    2160: (1268.5714, 45.25, 24, 1165.7143, 49.16, 15),
    2880: (1542.8571, 51.72, 28, 1320.0000, 60.57, 23),
    3600: (1491.4286, 49.66, 29, 1354.2857, 71.72, 20),
    4320: (1337.1429, 53.65, 30, 1388.5714, 69.51, 26),
    5400: (1422.8571, 55.81, 29, 1405.7143, 74.34, 26),
}

THROUGHPUT_TOLERANCE = 0.5
DELAY_TOLERANCE = 0.05

_RUN_CACHE: Dict[Tuple[str, int], Dict[str, Any]] = {}


def _config(
    intersection_type: str, controller: Dict[str, Any], offered: int
) -> Dict[str, Any]:
    rate = offered / 3600.0
    return {
        "simulation": {
            "duration": DURATION,
            "timeStep": TIME_STEP,
            "warmupTime": WARMUP_TIME,
            "randomSeed": SEED,
        },
        "geometry": {"intersectionType": intersection_type},
        "roads": {
            "approachLength": 200.0,
            "laneWidth": 3.5,
            "lanesPerApproach": LANES_PER_APPROACH,
        },
        "traffic": {
            "arrivalRate": rate,
            "arrivalDistribution": "poisson",
            "totalVehicles": 5000,
        },
        "controller": copy.deepcopy(controller),
    }


def _run(
    intersection_type: str, controller: Dict[str, Any], offered: int
) -> Dict[str, Any]:
    cache_key = (intersection_type, offered)
    cached = _RUN_CACHE.get(cache_key)
    if cached is not None:
        return cached

    config = _config(intersection_type, controller, offered)

    clock = Clock(time_step=TIME_STEP)
    engine = SimulationEngine(clock, duration=DURATION, config=config)
    controller_obj = create_controller(config, engine.network)
    engine.controller = controller_obj
    collector = MetricCollector(config)
    engine.register_tick_callback(
        build_tick_callback(controller_obj, clock, engine, collector)
    )

    while engine.status.value.lower() != "completed":
        engine.step()

    metrics = collector.get_metrics(
        clock.get_elapsed_time(),
        engine.pool.active_vehicles,
        engine.pool.exited_vehicles,
        engine.spawner.spawned_count if engine.spawner else 0,
        engine.pool.collision_count,
    )

    result = {
        "servedVehPerHour": metrics["throughput"] / MEASURED_WINDOW * 3600.0,
        "delay": metrics.get("averageDelay", metrics.get("averageWaitTime", 0.0)),
        "maxQueue": metrics.get("maxQueueLength", 0),
    }
    _RUN_CACHE[cache_key] = result
    return result


def _assert_point_matches(offered: int) -> None:
    sig_served, sig_delay, sig_max_q, rnd_served, rnd_delay, rnd_max_q = PINNED_CURVE[
        offered
    ]

    signal = _run("fixed_time_signal", SIGNAL_CONTROLLER, offered)
    roundabout = _run("roundabout", ROUNDABOUT_CONTROLLER, offered)

    assert signal["servedVehPerHour"] == pytest.approx(
        sig_served, abs=THROUGHPUT_TOLERANCE
    ), (
        f"signal served flow drifted at {offered} veh/h offered: {signal['servedVehPerHour']:.4f} vs pinned {sig_served}"
    )
    assert signal["delay"] == pytest.approx(sig_delay, abs=DELAY_TOLERANCE), (
        f"signal delay drifted at {offered} veh/h offered: {signal['delay']:.2f} vs pinned {sig_delay}"
    )
    assert signal["maxQueue"] == sig_max_q, (
        f"signal maxQueueLength drifted at {offered} veh/h offered: {signal['maxQueue']} vs pinned {sig_max_q}"
    )

    assert roundabout["servedVehPerHour"] == pytest.approx(
        rnd_served, abs=THROUGHPUT_TOLERANCE
    ), (
        f"roundabout served flow drifted at {offered} veh/h offered: {roundabout['servedVehPerHour']:.4f} vs pinned {rnd_served}"
    )
    assert roundabout["delay"] == pytest.approx(rnd_delay, abs=DELAY_TOLERANCE), (
        f"roundabout delay drifted at {offered} veh/h offered: {roundabout['delay']:.2f} vs pinned {rnd_delay}"
    )
    assert roundabout["maxQueue"] == rnd_max_q, (
        f"roundabout maxQueueLength drifted at {offered} veh/h offered: {roundabout['maxQueue']} vs pinned {rnd_max_q}"
    )


@pytest.mark.slow
@pytest.mark.parametrize("offered", sorted(PINNED_CURVE.keys()))
def test_calibrated_capacity_curve_matches_the_published_report(offered: int) -> None:
    """Pins every point of the published 1-lane capacity curve (both
    geometries) to the values current HEAD actually measures. A failure
    here means either the published report is stale or simulation/controller
    behaviour has silently changed -- it must not be "fixed" by loosening
    the tolerance without re-auditing which of those two happened."""
    _assert_point_matches(offered)


def test_calibrated_capacity_curve_fast_representative() -> None:
    """Cheap, default-suite representative of the full pinned curve above:
    the two lowest (and therefore fastest) offered-demand points, which are
    also the ones nearest the report's stated "not capacity-limited" regime.
    Full-curve verification, including the saturation-regime points, runs in
    the slow suite (test_calibrated_capacity_curve_matches_the_published_report).
    """
    _assert_point_matches(360)
    _assert_point_matches(720)


@pytest.mark.slow
def test_calibrated_curve_crossover_ordering_is_preserved() -> None:
    """The report's central qualitative claim: the roundabout serves more
    at 1080 veh/h offered, and the signal serves more from 1440 upward. This
    is the crossover the report's Executive Summary and §2 "Reading the
    table" describe -- pinned separately from the raw values so a change
    that keeps every value within tolerance but flips this ordering (e.g. a
    slightly-different-but-still-"close" pair of numbers) still fails
    loudly."""
    at_1080_signal = _run("fixed_time_signal", SIGNAL_CONTROLLER, 1080)
    at_1080_roundabout = _run("roundabout", ROUNDABOUT_CONTROLLER, 1080)
    assert (
        at_1080_roundabout["servedVehPerHour"] > at_1080_signal["servedVehPerHour"]
    ), "roundabout is no longer ahead of signal at 1080 veh/h offered"

    # 4320 is left out on evidence, not for convenience: on seed 1 the two
    # geometries sit within 4% of each other there (roundabout 1389 vs signal
    # 1337 veh/h), while across seeds 1-5 the signal serves more on average
    # (1457 vs 1361 veh/h) — see docs/reports/comparative_report.md §2 and
    # docs/bug-fix-report.md. The exact seed-1 values at 4320 are still pinned
    # by PINNED_CURVE above.
    for offered in (1440, 2160, 2880, 3600, 5400):
        signal = _run("fixed_time_signal", SIGNAL_CONTROLLER, offered)
        roundabout = _run("roundabout", ROUNDABOUT_CONTROLLER, offered)
        assert signal["servedVehPerHour"] > roundabout["servedVehPerHour"], (
            f"signal is no longer ahead of roundabout at {offered} veh/h offered"
        )
