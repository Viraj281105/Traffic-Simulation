"""Roundabout conflict-handling regression tests.

The roundabout used to produce a steady stream of real geometric vehicle
overlaps — 8 to 22 per 180 s run at a moderate arrival rate, across every seed
and lane count. Four defects combined to cause it:

1. Incoming lanes ended exactly on the circulating ring's outer edge, so a
   vehicle correctly stopped at the give-way line still had half its body
   inside the ring.
2. The ``entrySpeed`` cap was applied over the last 5 m of the approach, a
   distance in which no vehicle can shed its approach speed, so vehicles
   entered the ring at full speed and gap acceptance was meaningless.
3. Entry yielding only considered circulating traffic on the entering
   vehicle's *destination* ring, so a vehicle bound for an inner ring ignored
   the outer ring it had to drive straight across.
4. The radial entry/exit transition was a fixed fraction of each path's
   angular span, which differs hugely by turn intent, so paths leaving one
   entry mouth diverged instead of forming a single channel.

These tests pin the geometric invariants behind fixes 1, 3 and 4 exactly, and
guard the overall collision rate against regression across multiple seeds.
"""

import copy
import math
from typing import Any, Dict, Tuple

import pytest

from src.controllers.factory import build_tick_callback, create_controller
from src.core.clock import Clock
from src.core.engine import SimulationEngine
from src.core.enums import Direction
from src.metrics.collector import MetricCollector
from src.roads.network import ROUNDABOUT_ENTRY_SETBACK, RoadNetwork

ROUNDABOUT_CONFIG: Dict[str, Any] = {
    "simulation": {
        "duration": 120,
        "timeStep": 0.1,
        "warmupTime": 10.0,
        "randomSeed": 1,
    },
    "geometry": {"intersectionType": "roundabout"},
    "roads": {"approachLength": 200.0, "laneWidth": 3.5, "lanesPerApproach": 2},
    "traffic": {"arrivalRate": 0.6, "arrivalDistribution": "poisson"},
    "controller": {
        "innerRadius": 10.0,
        "outerRadius": 20.0,
        "criticalGap": 4.0,
        "followUpTime": 2.5,
        "entrySpeed": 5.0,
        "circulatingSpeed": 8.0,
    },
}

SIGNAL_CONFIG: Dict[str, Any] = {
    **copy.deepcopy(ROUNDABOUT_CONFIG),
    "geometry": {"intersectionType": "fixed_time_signal"},
    "controller": {
        "greenTime": 30.0,
        "yellowTime": 4.0,
        "allRedTime": 2.0,
        "phaseSequence": [
            "ns_green",
            "ns_yellow",
            "all_red",
            "ew_green",
            "ew_yellow",
            "all_red",
        ],
    },
}


def _run(config: Dict[str, Any], seed: int, lanes: int = 2) -> Dict[str, Any]:
    config = copy.deepcopy(config)
    config["simulation"]["randomSeed"] = seed
    config["roads"]["lanesPerApproach"] = lanes

    clock = Clock(time_step=config["simulation"]["timeStep"])
    engine = SimulationEngine(
        clock, duration=config["simulation"]["duration"], config=config
    )
    controller = create_controller(config, engine.network)
    engine.controller = controller
    collector = MetricCollector(config)
    engine.register_tick_callback(
        build_tick_callback(controller, clock, engine, collector)
    )

    while engine.status.value.lower() != "completed":
        engine.step()

    return collector.get_metrics(
        clock.get_elapsed_time(),
        engine.pool.active_vehicles,
        engine.pool.exited_vehicles,
        engine.spawner.spawned_count if engine.spawner else 0,
        engine.pool.collision_count,
    )


# ── Geometry invariants ───────────────────────────────────────────────────


def _roundabout_network(lanes: int = 2) -> RoadNetwork:
    network = RoadNetwork()
    network.setup_default_intersection(
        approach_length=200.0,
        lane_width=3.5,
        lanes_per_approach=lanes,
        is_roundabout=True,
        inner_radius=10.0,
        outer_radius=20.0,
    )
    return network


@pytest.mark.parametrize("lanes", [1, 2, 3])
def test_give_way_line_sits_clear_of_the_circulating_ring(lanes: int) -> None:
    """A vehicle held at the give-way line must not protrude into the ring.

    The incoming lane used to end exactly at ``outer_radius``; the setback is
    what keeps a stationary, correctly-yielding vehicle's body outside the
    outermost circulating lane.
    """
    network = _roundabout_network(lanes)
    for direction in Direction:
        for lane in network.get_incoming_approach(direction).get_lanes():
            end_radius = math.hypot(*lane.end_coords)
            assert end_radius >= 20.0 + ROUNDABOUT_ENTRY_SETBACK - 1e-6


@pytest.mark.parametrize("lanes", [1, 2, 3])
def test_outgoing_lanes_start_clear_of_the_ring(lanes: int) -> None:
    network = _roundabout_network(lanes)
    for direction in Direction:
        for lane in network.get_outgoing_approach(direction).get_lanes():
            start_radius = math.hypot(*lane.start_coords)
            assert start_radius >= 20.0 + ROUNDABOUT_ENTRY_SETBACK - 1e-6


def test_connection_lanes_start_and_end_at_their_approach_lanes() -> None:
    """The straight entry/exit stubs must not break lane connectivity."""
    network = _roundabout_network(2)
    for (origin, lane_index, _turn), conn in network._connection_lane_cache.items():
        incoming = network.get_incoming_approach(origin).get_lanes()[lane_index]
        assert conn.start_coords == pytest.approx(incoming.end_coords, abs=1e-6)


def test_entry_transition_is_a_fixed_arc_length_not_a_fixed_fraction() -> None:
    """Paths from one entry mouth must share a radial profile.

    Sampled a short way in, a right-turn and a left-turn path leaving the same
    incoming lane must be at essentially the same radius. Before the fix the
    transition was a fraction of each path's angular span, so the right-turner
    (90 deg of arc) had already reached its ring while the left-turner
    (270 deg) was still drifting inwards.
    """
    from src.core.enums import TurnIntent

    network = _roundabout_network(2)

    # Probed through the entry taper, which is the stretch where paths from
    # one mouth previously fanned apart. Beyond it the short right-turn path
    # legitimately begins its exit transition while the longer paths are still
    # circulating, so the shared profile is only asserted where it should hold.
    for lane_index in (0, 1):
        for probe_distance in (2.0, 6.0, 10.0):
            radii = []
            for turn in (TurnIntent.LEFT, TurnIntent.STRAIGHT, TurnIntent.RIGHT):
                conn = network._get_or_create_connection_lane(
                    Direction.NORTH, lane_index, turn
                )
                point = conn.get_point_at_distance(probe_distance)
                radii.append(math.hypot(*point))
            assert max(radii) - min(radii) < 2.5, (
                f"paths from lane {lane_index} diverge at {probe_distance} m: {radii}"
            )


def test_entry_stub_keeps_the_vehicle_on_its_approach_heading() -> None:
    """The path must run straight to the ring before it starts curving.

    A path that began curving at the give-way line swung sideways across the
    mouth while still alongside the queue in the neighbouring entry lane.
    """
    from src.core.enums import TurnIntent

    network = _roundabout_network(2)
    incoming = network.get_incoming_approach(Direction.NORTH).get_lanes()[0]
    conn = network._get_or_create_connection_lane(
        Direction.NORTH, 0, TurnIntent.STRAIGHT
    )

    # Just inside the stub, the heading must still match the approach.
    assert conn.get_heading_at_distance(0.5) == pytest.approx(incoming.heading, abs=1.0)


def test_circulating_radii_are_ordered_by_lane_index() -> None:
    """Lane index must map monotonically to ring radius, with no crossings."""
    from src.core.enums import TurnIntent

    network = _roundabout_network(3)
    radii = [
        network._get_or_create_connection_lane(
            Direction.NORTH, idx, TurnIntent.STRAIGHT
        ).circulating_radius
        for idx in range(3)
    ]
    assert radii == sorted(r for r in radii if r is not None)


# ── Entry yielding ────────────────────────────────────────────────────────


def test_entry_yields_to_every_ring_it_crosses() -> None:
    """A vehicle bound for an inner ring must yield to the outer ring too.

    Entry yielding previously required an exact ring-index match, so a vehicle
    heading for ring 0 ignored traffic circulating on ring 1 — the ring it had
    to drive straight across to get there.
    """
    from src.controllers.roundabout import RoundaboutController
    from src.vehicles.vehicle import Vehicle

    config = copy.deepcopy(ROUNDABOUT_CONFIG)
    network = _roundabout_network(2)
    controller = RoundaboutController(config, network)

    # Place a circulating vehicle on the OUTER ring (index 1), just upstream
    # of the NORTH entry, coming from a different approach.
    from src.core.enums import TurnIntent

    outer = network._get_or_create_connection_lane(
        Direction.EAST, 1, TurnIntent.STRAIGHT
    )
    vehicle = Vehicle(
        vehicle_id="circulating",
        length=4.5,
        width=2.0,
        desired_speed=8.0,
        route=[outer],
        start_position=outer.length * 0.25,
        initial_speed=8.0,
        turn_intent=TurnIntent.STRAIGHT,
    )

    controller.update(0.1, [vehicle])

    north_lanes = network.get_incoming_approach(Direction.NORTH).get_lanes()
    blocked = [lane.virtual_obstacle is not None for lane in north_lanes]
    assert any(blocked), (
        "an approach whose entry path crosses an occupied outer ring must be "
        "held at the give-way line"
    )


# ── Behavioural regression guards ─────────────────────────────────────────

_SEEDS: Tuple[int, ...] = (1, 2, 3, 4, 5, 6, 7, 8)

# Collision budget across the whole seed set.
#
# Measured totals for this exact workload (8 seeds x 120 s, arrivalRate 0.6)
# are 10 / 16 / 30 for 1 / 2 / 3 lanes. Normalised to the same seed count and
# duration, the pre-fix code produced roughly 29 / 91 / 78. These ceilings sit
# above the current figures and far below the pre-fix ones, so they catch a
# genuine regression without being brittle about the residual.
#
# The residual is deliberately NOT asserted as zero. The remaining overlaps
# occur where adjacent entry lanes of one approach diverge towards different
# rings, which the simplified concentric-ring geometry cannot fully separate
# without a lane-change/weaving model — see the module docstring.
_ROUNDABOUT_COLLISION_BUDGET = {1: 20, 2: 28, 3: 45}


@pytest.mark.parametrize("lanes", [1, 2, 3])
def test_roundabout_collision_rate_stays_far_below_the_pre_fix_baseline(
    lanes: int,
) -> None:
    total = sum(
        _run(ROUNDABOUT_CONFIG, seed, lanes)["collisionCount"] for seed in _SEEDS
    )
    assert total <= _ROUNDABOUT_COLLISION_BUDGET[lanes], (
        f"roundabout collisions across {len(_SEEDS)} seeds regressed to {total}"
    )


@pytest.mark.parametrize("lanes", [1, 2])
def test_signal_junction_is_effectively_collision_free(lanes: int) -> None:
    """The signalised junction must stay clean across seeds."""
    total = sum(_run(SIGNAL_CONFIG, seed, lanes)["collisionCount"] for seed in _SEEDS)
    assert total <= 2


@pytest.mark.parametrize("lanes", [1, 2, 3])
def test_roundabout_still_moves_traffic(lanes: int) -> None:
    """Conflict avoidance must not be achieved by gridlocking the junction.

    A resolver that simply stops everything would score zero collisions, so
    throughput is asserted alongside them.
    """
    throughputs = [
        _run(ROUNDABOUT_CONFIG, seed, lanes)["throughput"] for seed in _SEEDS
    ]
    # Measured totals are ~250 vehicles cleared per lane count across the seed
    # set. A resolver that simply stopped everything would score zero
    # collisions, so this floor is what keeps the collision budget honest.
    assert sum(throughputs) >= 100, f"roundabout throughput collapsed: {throughputs}"


def test_roundabout_runs_stay_deterministic_for_a_fixed_seed() -> None:
    """Conflict resolution must not depend on iteration order."""
    first = _run(ROUNDABOUT_CONFIG, 3, 2)
    second = _run(ROUNDABOUT_CONFIG, 3, 2)
    assert first == second


def test_different_seeds_still_diverge() -> None:
    assert _run(ROUNDABOUT_CONFIG, 3, 2) != _run(ROUNDABOUT_CONFIG, 4, 2)
