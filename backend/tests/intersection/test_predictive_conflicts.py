"""Regression tests for the predictive conflict resolver's give-way stability.

At high demand a multi-lane roundabout used to lock up. Two vehicles leaving
adjacent entry lanes of one approach ended up side by side in the mouth, and
the resolver swapped which of them had to give way *every tick*: one was braked
to a halt while the other crept forward, then the reverse, at ~0.2 m/s,
indefinitely. The ring behind them seized, and — since the vehicles were creeping
with turning bounding boxes — they eventually touched.

Three defects combined, and each has a test here:

1. A stopped vehicle outranked every structural rule, so a vehicle the
   controller was holding at the give-way line beat one already inside the
   mouth beside it.
2. "Stopped" was ``speed <= 0.1``, a quantity the resolver's own braking
   toggles, so the rule set in force changed on every tick.
3. A stationary vehicle was compared with its neighbour by circumscribed
   circle (~5.4 m) against a 3.5 m lane spacing, so anything passing a queue in
   the next lane counted as a conflict.
"""

from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

from src.core.enums import Direction, TurnIntent
from src.intersection.predictive_conflicts import (
    _DECISION_MEMORY_TICKS,
    PredictiveConflictResolver,
)
from src.roads.network import RoadNetwork
from src.vehicles.pool import VehiclePool
from src.vehicles.vehicle import Vehicle

DT = 0.1


def _network(lanes: int = 2) -> RoadNetwork:
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


def _vehicle(
    network: RoadNetwork,
    vehicle_id: str,
    origin: Direction,
    lane_index: int,
    turn: TurnIntent,
    *,
    on_approach: bool,
    position: float,
    speed: float,
) -> Vehicle:
    """A vehicle on its approach lane (``on_approach``) or on its connection lane."""
    route = network.generate_route(origin, lane_index, turn)
    if not on_approach:
        route = route[1:]
    return Vehicle(
        vehicle_id=vehicle_id,
        length=4.5,
        width=2.0,
        desired_speed=8.0,
        route=route,
        start_position=position,
        initial_speed=speed,
        turn_intent=turn,
    )


def _held_at_line(network: RoadNetwork, vehicle_id: str, lane_index: int) -> Vehicle:
    """A vehicle stopped at the give-way line of a south approach lane."""
    lane = network.get_incoming_approach(Direction.SOUTH).get_lanes()[lane_index]
    return _vehicle(
        network,
        vehicle_id,
        Direction.SOUTH,
        lane_index,
        TurnIntent.LEFT if lane_index == 0 else TurnIntent.RIGHT,
        on_approach=True,
        position=lane.length,
        speed=0.0,
    )


# ── 1. Structural priority beats "stopped" ────────────────────────────────


def test_inside_vehicle_is_not_braked_for_one_held_at_the_line() -> None:
    """A vehicle already in the mouth must not stop for its held neighbour.

    This is the exact opening move of the lock-up: lane 1 was released while
    lane 0's head was held, and the vehicle that had legitimately entered was
    emergency-braked for the one that had not.
    """
    network = _network()
    held = _held_at_line(network, "held", 0)
    inside = _vehicle(
        network,
        "inside",
        Direction.SOUTH,
        1,
        TurnIntent.RIGHT,
        on_approach=False,
        position=0.4,
        speed=4.3,
    )

    limits = PredictiveConflictResolver().compute_braking_distances([held, inside])

    assert "inside" not in limits


def test_inside_outranks_a_stopped_vehicle_outside() -> None:
    """The structural rule is decided before any speed-dependent one."""
    network = _network()
    resolver = PredictiveConflictResolver()
    held = _held_at_line(network, "held", 0)
    inside = _vehicle(
        network,
        "inside",
        Direction.SOUTH,
        1,
        TurnIntent.RIGHT,
        on_approach=False,
        position=0.4,
        speed=4.3,
    )
    resolver._stopped = {"held"}

    yielder, _ = resolver._select_yielder(held, inside, 0.0, 2.0)
    assert yielder is held
    # Order of the arguments must not matter.
    yielder, _ = resolver._select_yielder(inside, held, 2.0, 0.0)
    assert yielder is held


# ── 2. Stopped-ness has hysteresis ────────────────────────────────────────


def test_a_released_vehicle_stays_stopped_until_it_is_really_moving() -> None:
    network = _network()
    v = _held_at_line(network, "v", 0)
    resolver = PredictiveConflictResolver()

    resolver.compute_braking_distances([v])
    assert "v" in resolver._stopped

    # Released and accelerating, but still only crawling: the tick after a
    # brake to a stop must not already count as moving.
    v.speed = 0.2
    resolver.compute_braking_distances([v])
    assert "v" in resolver._stopped

    v.speed = 0.6
    resolver.compute_braking_distances([v])
    assert "v" not in resolver._stopped


# ── 3. Stationary vehicles are compared by real clearance ────────────────


def test_a_stopped_vehicle_only_conflicts_with_a_path_through_its_box() -> None:
    """Passing a queue in the next lane is not a conflict; driving into it is."""
    network = _network()
    resolver = PredictiveConflictResolver()
    held = _held_at_line(network, "held", 0)

    # One lane over (3.5 m), moving past: no overlap, hence no constraint.
    passing = _vehicle(
        network,
        "passing",
        Direction.SOUTH,
        1,
        TurnIntent.STRAIGHT,
        on_approach=False,
        position=0.5,
        speed=3.0,
    )
    assert resolver.compute_braking_distances([held, passing]) == {}

    # A stopped vehicle sitting where a mover's path goes: the mover must stop.
    # Inner-lane left-turn and outer-lane right-turn converge to ~2.6 m centre
    # distance a few metres in, i.e. their boxes touch when side by side.
    obstacle = _vehicle(
        network,
        "obstacle",
        Direction.SOUTH,
        1,
        TurnIntent.RIGHT,
        on_approach=False,
        position=6.0,
        speed=0.0,
    )
    mover = _vehicle(
        network,
        "mover",
        Direction.SOUTH,
        0,
        TurnIntent.LEFT,
        on_approach=False,
        position=1.0,
        speed=3.0,
    )
    limits = PredictiveConflictResolver().compute_braking_distances([obstacle, mover])
    assert "mover" in limits
    assert "obstacle" not in limits


# ── 4. Decisions are stable ───────────────────────────────────────────────


def _mouth_pair(network: RoadNetwork) -> "tuple[Vehicle, Vehicle]":
    """Two vehicles side by side in the west mouth, as in the recorded lock-up."""
    inner = _vehicle(
        network, "veh_11", Direction.WEST, 0, TurnIntent.LEFT,
        on_approach=False, position=2.3, speed=1.0,
    )  # fmt: skip
    outer = _vehicle(
        network, "veh_9", Direction.WEST, 1, TurnIntent.STRAIGHT,
        on_approach=False, position=4.0, speed=1.0,
    )  # fmt: skip
    return inner, outer


def test_a_decision_survives_whatever_would_have_flipped_it() -> None:
    """The regression at the heart of the lock-up: the choice is made once."""
    network = _network()
    resolver = PredictiveConflictResolver()
    inner, outer = _mouth_pair(network)

    first, _ = resolver._select_yielder(inner, outer, 4.0, 2.0)
    # Distances, positions and argument order all change from tick to tick as
    # the vehicles creep; none of it may change who gives way.
    for dist_inner, dist_outer in ((2.0, 4.0), (3.0, 3.0), (0.0, 9.0), (5.0, 1.0)):
        inner.position, outer.position = outer.position, inner.position
        again, _ = resolver._select_yielder(inner, outer, dist_inner, dist_outer)
        assert again is first
        again, _ = resolver._select_yielder(outer, inner, dist_outer, dist_inner)
        assert again is first


def test_the_vehicle_ahead_in_the_same_mouth_goes_first() -> None:
    """Vehicles from adjacent lanes of one approach: the physical leader wins.

    Entry order is deliberately made to say the opposite (the trailing vehicle
    "entered first"): giving way to the vehicle behind is what left both wedged
    in the mouth.
    """
    network = _network()
    resolver = PredictiveConflictResolver()
    inner, outer = _mouth_pair(network)  # outer is 1.7 m further along
    resolver._entry_order = {"veh_11": 1, "veh_9": 2}

    # Distances to the conflict are irrelevant to the choice (they move as the
    # yielder brakes and could invert it); only who is ahead counts.
    for dist_inner, dist_outer in ((0.0, 0.0), (6.0, 2.0), (2.0, 6.0)):
        resolver.reset()
        resolver._entry_order = {"veh_11": 1, "veh_9": 2}
        yielder, _ = resolver._select_yielder(inner, outer, dist_inner, dist_outer)
        assert yielder is inner


def test_first_in_goes_first_between_vehicles_from_different_approaches() -> None:
    network = _network()
    resolver = PredictiveConflictResolver()
    early = _vehicle(
        network, "veh_9", Direction.WEST, 1, TurnIntent.STRAIGHT,
        on_approach=False, position=1.0, speed=3.0,
    )  # fmt: skip
    late = _vehicle(
        network, "veh_11", Direction.NORTH, 0, TurnIntent.LEFT,
        on_approach=False, position=30.0, speed=3.0,
    )  # fmt: skip
    resolver._entry_order = {"veh_9": 5, "veh_11": 9}

    # ``position`` says veh_11 is "further along" (30 m vs 1 m), but that is a
    # different lane's arc length; entry order is what counts.
    yielder, _ = resolver._select_yielder(early, late, 4.0, 4.0)
    assert yielder is late
    yielder, _ = resolver._select_yielder(late, early, 4.0, 4.0)
    assert yielder is late


def test_a_stopped_vehicle_in_the_way_never_yields_to_the_mover() -> None:
    """Unlike the tie-breaks, this one is re-derived every tick.

    A remembered "A gives way to B" turns lethal once A has stopped in B's
    path: B is then unconstrained and drives into it. This is the state the
    first version of the fix got wrong.
    """
    network = _network()
    resolver = PredictiveConflictResolver()
    inner, outer = _mouth_pair(network)

    # Decide the pair while both are moving: the vehicle behind (the inner one)
    # yields to the one ahead.
    yielder, _ = resolver._select_yielder(inner, outer, 2.0, 6.0)
    assert yielder is inner

    # The vehicle that was told to yield stops, and the other, which had priority,
    # is now the one that would drive into it: the roles must reverse.
    resolver._stopped = {"veh_11"}
    yielder, _ = resolver._select_yielder(inner, outer, 0.0, 3.0)
    assert yielder is outer
    yielder, _ = resolver._select_yielder(outer, inner, 3.0, 0.0)
    assert yielder is outer


def test_reset_forgets_everything() -> None:
    network = _network()
    resolver = PredictiveConflictResolver()
    a = _vehicle(
        network, "a", Direction.WEST, 0, TurnIntent.LEFT,
        on_approach=False, position=2.0, speed=0.0,
    )  # fmt: skip
    b = _vehicle(
        network, "b", Direction.WEST, 1, TurnIntent.STRAIGHT,
        on_approach=False, position=2.0, speed=3.0,
    )  # fmt: skip
    resolver.compute_braking_distances([a, b])
    assert resolver._entry_order and resolver._stopped

    resolver.reset()
    assert not resolver._entry_order
    assert not resolver._stopped
    assert not resolver._priority
    assert resolver._tick == 0


def test_pool_reset_resets_the_resolver() -> None:
    pool = VehiclePool()
    pool._predictive._entry_order["x"] = 1
    pool._predictive._priority[frozenset(("x", "y"))] = ("x", 1)
    pool.reset()
    assert not pool._predictive._entry_order
    assert not pool._predictive._priority


def test_a_decision_survives_a_brief_gap_in_the_conflict() -> None:
    """The inversion that re-locked the ring after the first version of the fix.

    A yielder that has braked hard can drop out of conflict for a tick or two
    (its arrival time slips past the safe headway) and drop back in. The
    decision used to be forgotten in between, then re-made from the changed
    situation — the other way round — so the vehicle that had been told to go
    was told to stop, while the router's own proximity layer held the other.
    """
    network = _network()
    resolver = PredictiveConflictResolver()
    inner, outer = _mouth_pair(network)

    first, _ = resolver._select_yielder(inner, outer, 2.0, 2.0)
    assert first is inner

    # The pair leaves conflict for a while (nobody asks about it)...
    for _ in range(_DECISION_MEMORY_TICKS // 2):
        resolver.compute_braking_distances([inner])

    # ...and comes back looking different: the yielder now seems the closer one.
    again, _ = resolver._select_yielder(inner, outer, 1.0, 9.0)
    assert again is first


def test_decisions_do_not_outlive_their_vehicles_or_their_time() -> None:
    """Nothing leaks: gone vehicles and long-separated pairs are forgotten."""
    network = _network()
    resolver = PredictiveConflictResolver()
    inner, outer = _mouth_pair(network)
    resolver._select_yielder(inner, outer, 2.0, 2.0)
    assert resolver._priority

    # One of the pair is gone: the entry goes at once.
    resolver.compute_braking_distances([inner])
    assert not resolver._priority

    # Both still here, but nothing has asked about the pair for longer than the
    # memory window (i.e. they have stayed out of conflict).
    resolver._select_yielder(inner, outer, 2.0, 2.0)
    for _ in range(_DECISION_MEMORY_TICKS):
        resolver._refresh_vehicle_state([inner, outer])
    assert resolver._priority, "still within the memory window"
    resolver._refresh_vehicle_state([inner, outer])
    assert not resolver._priority


# ── 5. The lock-up itself, end to end ─────────────────────────────────────


def _step_pool(pool: VehiclePool, network: RoadNetwork, ticks: int) -> List[float]:
    """Advance ``ticks`` steps and return the fastest speed each vehicle reached.

    Keyed off the vehicles present at the start: one that has driven off the
    end of its route is no longer active, but still got going.
    """
    engine: Any = SimpleNamespace(
        config={"geometry": {"intersectionType": "roundabout"}},
        network=network,
        clock=None,
    )
    ids = [v.vehicle_id for v in pool.active_vehicles]
    peak: Dict[str, float] = {vid: 0.0 for vid in ids}
    for _ in range(ticks):
        pool.update(DT, engine)
        for v in pool.active_vehicles:
            peak[v.vehicle_id] = max(peak[v.vehicle_id], v.speed)
    return [peak[vid] for vid in ids]


def test_two_vehicles_creeping_out_of_adjacent_lanes_do_not_lock_up() -> None:
    """The state captured two seconds before the first recorded collision.

    ``veh_11`` (inner lane, left turn) and ``veh_9`` (outer lane, straight) sit
    side by side in the west mouth at ~0.2 m/s. Before the fix each was braked
    every other tick, they crept for ~25 s, and the swinging boxes finally
    touched.
    """
    network = _network()
    pool = VehiclePool()
    veh_11 = _vehicle(
        network, "veh_11", Direction.WEST, 0, TurnIntent.LEFT,
        on_approach=False, position=2.1, speed=0.0,
    )  # fmt: skip
    veh_9 = _vehicle(
        network, "veh_9", Direction.WEST, 1, TurnIntent.STRAIGHT,
        on_approach=False, position=3.8, speed=0.2,
    )  # fmt: skip
    pool.add_vehicle(veh_11)
    pool.add_vehicle(veh_9)

    peaks = _step_pool(pool, network, ticks=200)  # 20 s

    assert pool.collision_count == 0
    # Both got up to circulating speed and, in 20 s, well clear of the mouth.
    assert min(peaks) > 2.0, f"a vehicle never got going: peaks={peaks}"


@pytest.mark.parametrize("origin", [Direction.NORTH, Direction.EAST, Direction.SOUTH])
def test_mouth_pair_does_not_lock_up_from_any_approach(origin: Direction) -> None:
    """The mouth geometry is rotationally symmetric; so must the outcome be."""
    network = _network()
    pool = VehiclePool()
    inner = _vehicle(
        network, "inner", origin, 0, TurnIntent.LEFT,
        on_approach=False, position=2.1, speed=0.0,
    )  # fmt: skip
    outer = _vehicle(
        network, "outer", origin, 1, TurnIntent.STRAIGHT,
        on_approach=False, position=3.8, speed=0.2,
    )  # fmt: skip
    pool.add_vehicle(inner)
    pool.add_vehicle(outer)

    peaks = _step_pool(pool, network, ticks=200)

    assert pool.collision_count == 0
    assert min(peaks) > 2.0, f"a vehicle never got going: peaks={peaks}"
