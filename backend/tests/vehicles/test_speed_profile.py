"""Shared speed assumptions (src/vehicles/speed_profile.py).

The signal and the roundabout must drive the same vehicle population under
the same physical rules: desired speed from the road's speed limit, and one
lateral-acceleration limit on every curved path.
"""

import math

import pytest

from src.core.enums import Direction, TurnIntent
from src.roads.network import RoadNetwork
from src.vehicles.spawner import VehicleSpawner
from src.vehicles.speed_profile import (
    DEFAULT_MAX_LATERAL_ACCELERATION,
    curve_speed_ceiling,
    curve_speed_samples,
    resolve_desired_speed_range,
)
from src.vehicles.vehicle import Vehicle


def _network(roundabout: bool, lanes: int = 1) -> RoadNetwork:
    net = RoadNetwork()
    net.setup_default_intersection(
        approach_length=200.0,
        lane_width=3.5,
        lanes_per_approach=lanes,
        is_roundabout=roundabout,
    )
    return net


def test_desired_speed_follows_the_speed_limit() -> None:
    lo, hi = resolve_desired_speed_range({})
    assert (lo, hi) == pytest.approx((13.89 * 0.85, 13.89 * 1.05))
    lo, hi = resolve_desired_speed_range({"roads": {"speedLimit": 8.33}})
    assert hi < 9.0
    # An explicit range still wins.
    explicit = {"vehicleGeneration": {"desiredSpeed": {"min": 10.0, "max": 11.0}}}
    assert resolve_desired_speed_range(explicit) == (10.0, 11.0)


def test_spawned_vehicles_use_the_speed_limit_range() -> None:
    config = {
        "simulation": {"randomSeed": 7},
        "traffic": {"arrivalRate": 2.0, "totalVehicles": 50},
        "roads": {"lanesPerApproach": 1},
    }
    spawner = VehicleSpawner(config, _network(False))
    speeds = []
    for _ in range(600):
        speeds.extend(v.desired_speed for v in spawner.step(0.1))
    assert speeds
    assert min(speeds) >= 13.89 * 0.85 - 1e-9
    assert max(speeds) <= 13.89 * 1.05 + 1e-9


def test_same_seed_gives_both_geometries_the_same_drivers() -> None:
    """Desired speeds are drawn identically for the two geometries."""
    base = {
        "simulation": {"randomSeed": 3},
        "traffic": {"arrivalRate": 1.0, "totalVehicles": 40},
        "roads": {"lanesPerApproach": 1},
    }
    out = []
    for roundabout in (False, True):
        spawner = VehicleSpawner(
            {k: dict(v) for k, v in base.items()}, _network(roundabout)
        )
        drawn = []
        for _ in range(300):
            drawn.extend(round(v.desired_speed, 9) for v in spawner.step(0.1))
        out.append(drawn)
    assert out[0] == out[1]


def test_straight_lanes_have_no_curve_limit() -> None:
    net = _network(False)
    straight = net._get_or_create_connection_lane(
        Direction.NORTH, 0, TurnIntent.STRAIGHT
    )
    assert curve_speed_samples(straight, 3.0) == []


@pytest.mark.parametrize("roundabout", [False, True])
def test_every_turn_is_slower_than_the_speed_limit(roundabout: bool) -> None:
    """Both geometries' turning paths get a curve limit well below 50 km/h."""
    net = _network(roundabout)
    for turn in (TurnIntent.LEFT, TurnIntent.RIGHT):
        lane = net._get_or_create_connection_lane(Direction.NORTH, 0, turn)
        samples = curve_speed_samples(lane, DEFAULT_MAX_LATERAL_ACCELERATION)
        assert samples, f"{turn} path has no curvature samples"
        assert 2.0 < min(samples) < 9.0


def test_ring_speed_matches_its_radius() -> None:
    """On the steady part of the ring the limit is sqrt(a_lat * R)."""
    net = _network(True)
    lane = net._get_or_create_connection_lane(Direction.NORTH, 0, TurnIntent.LEFT)
    samples = curve_speed_samples(lane, 3.0)
    mid = samples[len(samples) // 2]
    assert mid == pytest.approx(math.sqrt(3.0 * lane.circulating_radius), rel=0.05)


def test_vehicle_brakes_for_the_curve_before_reaching_it() -> None:
    """On the approach the ceiling tapers down towards the turn's limit."""
    net = _network(False)
    route = net.generate_route(Direction.NORTH, 0, TurnIntent.RIGHT)
    far = Vehicle("a", 4.5, 1.9, 14.0, route, start_position=10.0, initial_speed=14.0)
    near = Vehicle(
        "b",
        4.5,
        1.9,
        14.0,
        route,
        start_position=route[0].length - 2.0,
        initial_speed=5.0,
    )
    turn_limit = min(curve_speed_samples(route[1], 3.0))
    assert curve_speed_ceiling(far, 3.0, 3.0) > 14.0
    assert curve_speed_ceiling(near, 3.0, 3.0) < turn_limit + 3.0
