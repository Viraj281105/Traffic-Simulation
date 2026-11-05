"""Yield and clearance behaviour of traffic ahead of an emergency vehicle."""

from typing import List

from src.core.enums import Direction, TurnIntent
from src.priority.models import YieldConfig
from src.priority.vehicles import EMERGENCY_KINDS, EmergencyVehicle, VehicleBase
from src.priority.yielding import YieldManager
from src.roads.network import RoadNetwork
from src.vehicles.vehicle import Vehicle

SPEED_LIMIT = 13.89


def _network() -> RoadNetwork:
    network = RoadNetwork()
    network.setup_default_intersection(
        approach_length=200.0, lane_width=3.5, lanes_per_approach=1
    )
    return network


def _car(
    network: RoadNetwork, vid: str, position: float, desired: float = 10.0
) -> Vehicle:
    route = network.generate_route(Direction.NORTH, 0, TurnIntent.STRAIGHT)
    return Vehicle(
        vid, 4.5, 2.0, desired, route, start_position=position, initial_speed=0.0
    )


def _ambulance(network: RoadNetwork, position: float) -> EmergencyVehicle:
    kind = EMERGENCY_KINDS["ambulance"]
    params = kind.params(SPEED_LIMIT)
    route = network.generate_route(Direction.NORTH, 0, TurnIntent.STRAIGHT)
    base = VehicleBase(
        "ev_0",
        kind.length,
        kind.width,
        params.desired_speed_range[0],
        route,
        position,
        5.0,
        TurnIntent.STRAIGHT,
        0.0,
        0.5,
        params,
    )
    return EmergencyVehicle(base, "ambulance", "north", "straight", 0.0)


def test_vehicles_ahead_within_distance_clear_the_way_and_are_restored() -> None:
    network = _network()
    ev = _ambulance(network, 20.0)
    near = _car(network, "near", 60.0)
    far = _car(network, "far", 180.0)
    behind = _car(network, "behind", 5.0)
    manager = YieldManager(YieldConfig(distance_m=100.0), SPEED_LIMIT)
    vehicles: List[Vehicle] = [ev, near, far, behind]

    manager.update([ev], vehicles)

    assert near.driver_factors is not None
    headway, accel, decel = near.driver_factors
    assert headway < 1.0 and accel > 1.0 and decel == 1.0
    assert near.desired_speed >= SPEED_LIMIT
    # Out of range, behind the emergency vehicle: untouched.
    assert far.driver_factors is None and far.desired_speed == 10.0
    assert behind.driver_factors is None and behind.desired_speed == 10.0
    assert manager.active_count == 1

    ev.position = 175.0  # 'near' is now behind it; 'far' is ahead and in range
    manager.update([ev], vehicles)
    assert near.driver_factors is None and near.desired_speed == 10.0
    assert far.driver_factors is not None
    assert manager.yielded_ids == {"near", "far"}

    manager.restore_all()
    assert far.driver_factors is None and far.desired_speed == 10.0


def test_the_yield_model_is_the_vehicles_own_idm() -> None:
    """The factors change what the car-following model returns, not a side channel."""
    network = _network()
    ev = _ambulance(network, 20.0)
    car = _car(network, "lead", 50.0)
    manager = YieldManager(YieldConfig(), SPEED_LIMIT)
    from src.vehicles.idm import IntelligentDriverModel

    idm = IntelligentDriverModel(2.0, 3.0, 1.5, 2.0, 4.0)
    before = car.driver_idm(idm)
    manager.update([ev], [ev, car])
    after = car.driver_idm(idm)
    assert before is idm
    assert after is not idm
    assert after._desired_time_headway < idm._desired_time_headway
    assert after._max_acceleration > idm._max_acceleration
    manager.restore_all()
    assert car.driver_idm(idm) is idm


def test_existing_driver_traits_are_composed_and_restored() -> None:
    network = _network()
    ev = _ambulance(network, 20.0)
    car = _car(network, "lead", 50.0)
    car.driver_factors = (1.2, 0.9, 1.1)
    manager = YieldManager(
        YieldConfig(headway_factor=0.5, acceleration_factor=2.0), SPEED_LIMIT
    )
    manager.update([ev], [ev, car])
    assert car.driver_factors == (1.2 * 0.5, 0.9 * 2.0, 1.1)
    manager.restore_all()
    assert car.driver_factors == (1.2, 0.9, 1.1)


def test_disabled_yielding_changes_nothing() -> None:
    network = _network()
    ev = _ambulance(network, 20.0)
    car = _car(network, "lead", 50.0)
    manager = YieldManager(YieldConfig(enabled=False), SPEED_LIMIT)
    manager.update([ev], [ev, car])
    assert car.driver_factors is None and manager.active_count == 0


def test_emergency_vehicles_do_not_yield_to_each_other() -> None:
    network = _network()
    first = _ambulance(network, 20.0)
    second = _ambulance(network, 60.0)
    manager = YieldManager(YieldConfig(), SPEED_LIMIT)
    manager.update([first, second], [first, second])
    assert second.driver_factors is None
