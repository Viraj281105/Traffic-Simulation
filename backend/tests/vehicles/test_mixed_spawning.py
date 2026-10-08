"""V1.1 type-aware spawning, and the long-vehicle safety rules it relies on."""

import random
from collections import Counter
from typing import Any, Dict, List

import pytest

from src.controllers.roundabout import RoundaboutController
from src.core.enums import Direction, TurnIntent
from src.intersection.conflict_manager import (
    ConflictManager,
    _body_radius,
    conflict_clearance_for,
)
from src.roads.network import RoadNetwork
from src.vehicles.spawner import VehicleSpawner
from src.vehicles.vehicle import Vehicle
from src.vehicles.vehicle_types import DEFAULT_PROFILES

MIX = {"car": 0.5, "suv": 0.2, "bus": 0.1, "truck": 0.1, "motorcycle": 0.1}


def _config(seed: int = 7, mix: Any = MIX) -> Dict[str, Any]:
    config: Dict[str, Any] = {
        "simulation": {"randomSeed": seed},
        "traffic": {"arrivalRate": 2.0, "totalVehicles": 5000},
        "roads": {"lanesPerApproach": 1},
    }
    if mix is not None:
        config["vehicleGeneration"] = {"vehicleMix": dict(mix)}
    return config


def _network(lanes: int = 1) -> RoadNetwork:
    network = RoadNetwork()
    network.setup_default_intersection(approach_length=200.0, lanes_per_approach=lanes)
    return network


def _spawn(spawner: VehicleSpawner, count: int) -> List[Vehicle]:
    """Spawn ``count`` vehicles, clearing entries so nothing blocks."""
    out: List[Vehicle] = []
    while len(out) < count:
        for v in spawner.step(0.5):
            out.append(v)
            v.detach()
    return out


def test_mixed_population_follows_the_configured_shares() -> None:
    vehicles = _spawn(VehicleSpawner(_config(), _network()), 2000)
    counts = Counter(v.vehicle_type for v in vehicles)
    for type_id, share in MIX.items():
        assert counts[type_id] / len(vehicles) == pytest.approx(share, abs=0.03)


def test_spawned_vehicles_carry_their_class_parameters() -> None:
    vehicles = _spawn(VehicleSpawner(_config(), _network()), 400)
    for v in vehicles:
        profile = DEFAULT_PROFILES[v.vehicle_type]
        assert v.params is not None and v.params.type_id == v.vehicle_type
        if v.vehicle_type != "car":
            assert profile.length[0] <= v.length <= profile.length[1]
            assert profile.width[0] <= v.width <= profile.width[1]
        lo, hi = v.params.desired_speed_range
        assert lo <= v.desired_speed <= hi
        assert v.comfort_deceleration == v.params.comfort_deceleration


def test_mixed_spawning_is_deterministic_per_seed() -> None:
    def signature(seed: int) -> List[Any]:
        vehicles = _spawn(VehicleSpawner(_config(seed), _network()), 200)
        return [(v.vehicle_type, round(v.length, 9), v.turn_intent) for v in vehicles]

    assert signature(11) == signature(11)
    assert signature(11) != signature(12)


def test_legacy_population_has_no_profiles_and_the_v10_random_stream() -> None:
    spawner = VehicleSpawner(_config(mix=None), _network())
    assert spawner.population is None
    vehicles = _spawn(spawner, 50)
    assert all(v.params is None and v.vehicle_type == "car" for v in vehicles)
    assert all(4.0 <= v.length <= 5.0 for v in vehicles)


def test_blocked_arrival_keeps_its_class() -> None:
    network = _network()
    spawner = VehicleSpawner(_config(), network)
    # Force every direction to be due, with a stationary vehicle on each
    # entry so nothing can be placed.
    for d in Direction:
        lane = network.get_incoming_approach(d).get_lanes()[0]
        Vehicle(f"wall_{d.value}", 4.5, 2.0, 10.0, [lane], start_position=3.0)
        spawner.timers[d] = 0.0
    assert spawner.step(0.1) == []
    pending = dict(spawner._pending_type)
    assert set(pending) == set(Direction)
    for _ in range(5):
        assert spawner.step(0.1) == []
    assert spawner._pending_type == pending


def test_long_vehicles_need_a_longer_clear_entry() -> None:
    network = _network()
    lane = network.get_incoming_approach(Direction.NORTH).get_lanes()[0]
    # Clear space behind a queued car: enough for a car, not for a bus.
    Vehicle("queued", 4.5, 2.0, 10.0, [lane], start_position=10.5, initial_speed=0.0)
    spawner = VehicleSpawner(_config(mix={"bus": 1.0}), network)
    spawner.rng = random.Random(0)
    assert spawner._attempt_spawn(Direction.NORTH) is None
    car_spawner = VehicleSpawner(_config(mix={"car": 1.0}), network)
    assert car_spawner._attempt_spawn(Direction.NORTH) is not None


def test_conflict_body_radius_grows_only_beyond_the_reference_car() -> None:
    assert _body_radius(4.5) == 3.0
    assert _body_radius(5.0) == 3.0
    assert _body_radius(12.0) == pytest.approx(6.5)
    assert conflict_clearance_for(0.0) == 3.0
    assert conflict_clearance_for(7.0) == pytest.approx(6.5)


def test_committed_long_vehicle_keeps_precedence_at_admission() -> None:
    network = _network()
    manager = ConflictManager()
    for lane in network.get_all_connection_lanes():
        manager.register_connection_lane(lane)
    manager.compute_conflict_points()
    # A vehicle already inside the junction on a left turn, short of its
    # crossing with the opposing through movement.
    left = network.generate_route(Direction.SOUTH, 0, TurnIntent.LEFT)[1]
    through = network.generate_route(Direction.NORTH, 0, TurnIntent.STRAIGHT)[1]
    key = (min(left.lane_id, through.lane_id), max(left.lane_id, through.lane_id))
    assert key in manager._conflict_points
    committed = [
        {
            "vehicle_id": "inside",
            "turn_intent": TurnIntent.LEFT,
            "connection_lane_id": left.lane_id,
            "position_on_lane": 0.5,
            "speed": 4.0,
            "length": 12.0,
        }
    ]
    kwargs = dict(
        vehicle_turn_intent=TurnIntent.STRAIGHT,
        connection_lane_id=through.lane_id,
        vehicle_position_on_lane=0.0,
        current_time=1.0,
        all_vehicles_info=committed,
        vehicle_speed=8.0,
        on_connection_lane=False,
    )
    # The approaching car is held at the stop line because the committed
    # vehicle is a 12 m bus...
    assert (
        manager.get_conflict_distance(vehicle_id="car", vehicle_length=4.5, **kwargs)
        == 0.0
    )
    # ...and with a car in its place the V1.0 rule (proximity arbitration
    # only) applies unchanged.
    committed[0]["length"] = 4.5
    manager.reset_reservations()
    assert manager.get_conflict_distance(
        vehicle_id="car2", vehicle_length=4.5, **kwargs
    ) == float("inf")


def _roundabout(lanes: int = 1) -> RoadNetwork:
    network = RoadNetwork()
    network.setup_default_intersection(
        approach_length=200.0, lanes_per_approach=lanes, is_roundabout=True
    )
    return network


def _yield_positions(length: float) -> List[float]:
    """Positions of a circulating vehicle (S->W, passing the north entry)
    at which the north entry is closed, with a vehicle of ``length`` at its
    head."""
    closed: List[float] = []
    network = _roundabout()
    controller = RoundaboutController({"controller": {}}, network)
    entry = network.get_incoming_approach(Direction.NORTH).get_lanes()[0]
    head_route = network.generate_route(Direction.NORTH, 0, TurnIntent.STRAIGHT)
    head = Vehicle(
        "head",
        length,
        2.5,
        10.0,
        head_route,
        start_position=entry.length - length / 2.0 - 3.0,
    )
    ring = network.generate_route(Direction.SOUTH, 0, TurnIntent.LEFT)
    circ = Vehicle("circ", 4.5, 2.0, 8.0, ring, initial_speed=8.0)
    circ.lane.remove_vehicle(circ)
    circ.lane = ring[1]
    ring[1].add_vehicle(circ)
    steps = int(ring[1].length)
    for step in range(steps):
        circ.position = float(step)
        controller.reset()
        controller.update(0.1, [head, circ])
        if entry.virtual_obstacle is not None:
            closed.append(circ.position)
    return closed


def test_roundabout_long_vehicle_needs_a_longer_gap() -> None:
    car = _yield_positions(4.5)
    bus = _yield_positions(12.0)
    assert car, "the circulating vehicle must close the entry somewhere"
    # A bus needs (12 - 5) m / 5 m/s = 1.4 s more gap: every position that
    # stops a car stops a bus, and some positions stop only the bus.
    assert set(car) < set(bus)


def _mouth_case(entering_length: float, waiting_length: float) -> bool:
    """Is west lane 1 held while a vehicle from west lane 0 is in the mouth?"""
    network = _roundabout(lanes=2)
    controller = RoundaboutController({"controller": {}}, network)
    lanes = network.get_incoming_approach(Direction.WEST).get_lanes()
    entering_route = network.generate_route(Direction.WEST, 0, TurnIntent.STRAIGHT)
    entering = Vehicle("in_mouth", entering_length, 2.5, 8.0, entering_route)
    entering.lane.remove_vehicle(entering)
    entering.lane = entering_route[1]
    entering_route[1].add_vehicle(entering)
    entering.position = entering_length / 2.0 + 1.0
    waiting_route = network.generate_route(Direction.WEST, 1, TurnIntent.STRAIGHT)
    waiting = Vehicle(
        "waiting",
        waiting_length,
        2.0,
        8.0,
        waiting_route,
        start_position=lanes[1].length - waiting_length / 2.0 - 2.5,
    )
    controller.update(0.1, [entering, waiting])
    return lanes[1].virtual_obstacle is not None


def test_long_vehicle_takes_the_whole_roundabout_mouth() -> None:
    # Cars enter side by side, exactly as in V1.0.
    assert _mouth_case(4.5, 4.5) is False
    # A bus swinging in from the next lane holds this one at the line...
    assert _mouth_case(12.0, 4.5) is True
    # ...and a bus waiting at the line does not pull out beside a car that is
    # still in the mouth.
    assert _mouth_case(4.5, 12.0) is True


def _heads_at_line(first_length: float, second_length: float) -> List[bool]:
    """Entry state (closed?) of west lanes 0 and 1 when lane 0's vehicle
    reached the line one tick before lane 1's."""
    network = _roundabout(lanes=2)
    controller = RoundaboutController({"controller": {}}, network)
    lanes = network.get_incoming_approach(Direction.WEST).get_lanes()

    def at_line(vid: str, idx: int, length: float) -> Vehicle:
        route = network.generate_route(Direction.WEST, idx, TurnIntent.STRAIGHT)
        return Vehicle(
            vid,
            length,
            2.5,
            8.0,
            route,
            start_position=lanes[idx].length - length / 2.0 - 2.0,
        )

    first = at_line("first", 0, first_length)
    controller.update(0.1, [first])
    second = at_line("second", 1, second_length)
    controller.update(0.1, [first, second])
    return [lane.virtual_obstacle is not None for lane in lanes]


def test_adjacent_entry_lanes_take_turns_when_a_long_vehicle_is_involved() -> None:
    # Cars: both entries open, side by side as in V1.0.
    assert _heads_at_line(4.5, 4.5) == [False, False]
    # With a bus at either line, the later arrival waits for the earlier.
    assert _heads_at_line(12.0, 4.5) == [False, True]
    assert _heads_at_line(4.5, 12.0) == [False, True]


def _merge_manager(merge_in_order: bool) -> Any:
    network = _network(lanes=3)
    manager = ConflictManager()
    for lane in network.get_all_connection_lanes():
        manager.register_connection_lane(lane)
    manager.compute_conflict_points()
    manager.merge_in_position_order = merge_in_order
    return manager


def test_committed_vehicles_merge_onto_one_exit_lane_in_physical_order() -> None:
    # East lane 0 turning left and north lane 0 going straight both end on
    # the south exit's lane 0: a merge, not a crossing.
    left, through = "conn_east_0_left", "conn_north_0_straight"
    key = (min(left, through), max(left, through))
    for merge_in_order, expected in ((True, float("inf")), (False, None)):
        manager = _merge_manager(merge_in_order)
        assert key in manager._merge_keys
        cp = manager._conflict_points[key]
        through_end = cp.dist_on_a if cp.lane_id_a == through else cp.dist_on_b
        left_end = cp.dist_on_a if cp.lane_id_a == left else cp.dist_on_b
        # The through vehicle, 12 m from the merge, already holds it.
        manager._acquire(key, "holder", through, 0.0)
        info = [
            {
                "vehicle_id": "holder",
                "turn_intent": TurnIntent.STRAIGHT,
                "connection_lane_id": through,
                "position_on_lane": through_end - 12.0,
                "speed": 0.0,
                "length": 4.4,
            }
        ]
        # The left-turner is 10 m from the merge: physically in front.
        dist = manager.get_conflict_distance(
            vehicle_id="ahead",
            vehicle_turn_intent=TurnIntent.LEFT,
            connection_lane_id=left,
            vehicle_position_on_lane=left_end - 10.0,
            current_time=1.0,
            all_vehicles_info=info,
            vehicle_speed=0.0,
            on_connection_lane=True,
            vehicle_length=4.7,
        )
        if expected is None:
            # V1.0 arbitration (cars-only junctions): held by the claim.
            assert dist < float("inf")
        else:
            assert dist == expected
