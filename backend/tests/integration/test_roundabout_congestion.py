"""End-to-end check of the roundabout spillback cap in a real simulation.

The unit tests in tests/controllers/test_controllers.py drive the controller
with hand-placed vehicles. This one runs the actual engine (IDM, router,
predictive braking, collision detection) and forces the north entry to be
blocked for a window, exactly as a stalled ring would: the controller's own
give-way obstacle is held at the line, so nothing is discharged. The queue then
grows back up the approach on its own, which is what the spillback cap is meant
to respond to.

It asserts the whole life cycle -- cap activates once the queue has propagated
past the trigger distance, stays latched for as long as the ring is blocked,
releases once it clears -- plus that there is no chatter and no collision.
"""

import copy
from typing import Any, Dict, List, Tuple

from src.controllers.factory import build_tick_callback, create_controller
from src.controllers.roundabout import (
    _CONGESTION_MIN_HOLD,
    _QUEUE_TRIGGER_DIST,
    RoundaboutController,
)
from src.controllers.virtual_obstacle import VirtualObstacle
from src.core.clock import Clock
from src.core.engine import SimulationEngine
from src.core.enums import Direction
from src.metrics.collector import MetricCollector

TIME_STEP = 0.1
DURATION = 120.0
BLOCK_START, BLOCK_END = 10.0, 80.0

CONFIG: Dict[str, Any] = {
    "simulation": {
        "duration": DURATION,
        "timeStep": TIME_STEP,
        "warmupTime": 0.0,
        "randomSeed": 1,
    },
    "geometry": {"intersectionType": "roundabout"},
    "roads": {"approachLength": 200.0, "laneWidth": 3.5, "lanesPerApproach": 1},
    # Heavily oversaturated so the blocked north approach fills quickly.
    "traffic": {
        "arrivalRate": 5400 / 3600.0,
        "arrivalDistribution": "poisson",
        "totalVehicles": 5000,
    },
    "controller": {
        "innerRadius": 10.0,
        "outerRadius": 20.0,
        "circulatingLanes": 1,
        "criticalGap": 4.0,
        "followUpTime": 2.5,
        "entrySpeed": 5.0,
        "circulatingSpeed": 8.0,
    },
}


def _run_blocked_ring() -> Dict[str, Any]:
    config = copy.deepcopy(CONFIG)
    clock = Clock(time_step=TIME_STEP)
    engine = SimulationEngine(clock, duration=DURATION, config=config)
    controller = create_controller(config, engine.network)
    assert isinstance(controller, RoundaboutController)
    engine.controller = controller
    collector = MetricCollector(config)
    engine.register_tick_callback(
        build_tick_callback(controller, clock, engine, collector)
    )
    north = engine.network.get_incoming_approach(Direction.NORTH).get_lanes()[0]

    inner_update = controller.update
    limit_violations = 0.0

    def update_with_blocked_ring(dt: float, active_vehicles: List[Any]) -> None:
        nonlocal limit_violations
        inner_update(dt, active_vehicles)
        # Checked immediately after the controller has applied its limits, before
        # the vehicles move, so it is exact.
        if controller._congested.get("north", False):
            for v in north.get_vehicles():
                limit = controller._approach_speed_limit(north, v.position)
                limit_violations = max(limit_violations, v.desired_speed - limit)
        if BLOCK_START <= controller.time_in_current_state < BLOCK_END:
            # The ring is not accepting anyone from the north approach.
            north.virtual_obstacle = VirtualObstacle(position=north.length)

    controller.update = update_with_blocked_ring  # type: ignore[method-assign]

    states: List[Tuple[float, bool]] = []
    while engine.status.value.lower() != "completed":
        engine.step()
        t = controller.time_in_current_state
        congested = controller._congested.get("north", False)
        states.append((t, congested))

    return {
        "states": states,
        "collisions": engine.pool.collision_count,
        "limit_violation": limit_violations,
    }


def _transitions(states: List[Tuple[float, bool]]) -> List[Tuple[float, bool]]:
    out: List[Tuple[float, bool]] = []
    prev = False
    for t, congested in states:
        if congested != prev:
            out.append((t, congested))
            prev = congested
    return out


_RESULT: Dict[str, Any] = {}


def _result() -> Dict[str, Any]:
    if not _RESULT:
        _RESULT.update(_run_blocked_ring())
    return _RESULT


def test_blocked_ring_activates_cap_once_the_queue_has_propagated() -> None:
    transitions = _transitions(_result()["states"])
    on_times = [t for t, c in transitions if c]
    assert on_times, "cap never engaged although the entry was blocked"
    # Not before the block starts, and not instantly: the queue first has to
    # grow past the trigger distance and stall.
    assert BLOCK_START < on_times[0] < BLOCK_END, transitions


def test_cap_stays_latched_while_the_ring_is_blocked() -> None:
    transitions = _transitions(_result()["states"])
    first_on = next(t for t, c in transitions if c)
    flips_while_blocked = [t for t, _ in transitions if first_on < t < BLOCK_END]
    assert not flips_while_blocked, (
        f"congestion state chattered while the ring stayed blocked: {transitions}"
    )


def test_cap_releases_after_the_ring_clears() -> None:
    result = _result()
    transitions = _transitions(result["states"])
    first_on = next(t for t, c in transitions if c)
    offs = [t for t, c in transitions if not c and t > first_on]
    assert offs, "cap never released after the ring cleared"
    assert BLOCK_END <= offs[0] <= BLOCK_END + 10.0, transitions


def test_every_congested_spell_respects_the_minimum_hold() -> None:
    transitions = _transitions(_result()["states"])
    for (t_on, c_on), (t_off, c_off) in zip(transitions, transitions[1:]):
        if c_on and not c_off:
            assert t_off - t_on >= _CONGESTION_MIN_HOLD - TIME_STEP, transitions


def test_cap_enforces_the_kinematic_limit_and_causes_no_collision() -> None:
    result = _result()
    assert result["limit_violation"] < 1e-9
    assert result["collisions"] == 0


def test_trigger_distance_is_beyond_a_normal_give_way_queue() -> None:
    # Sanity on the calibration the scenario relies on: a single-lane queue of
    # three vehicles (~20 m) is ordinary and must not, on its own, trip the cap.
    assert _QUEUE_TRIGGER_DIST >= 3 * 6.0
