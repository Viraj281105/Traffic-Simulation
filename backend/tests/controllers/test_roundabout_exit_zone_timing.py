"""V1.4 exit convergence zones: a vehicle inside a zone is first, not a wall.

A vehicle from the other ring lane already inside the zone used to conflict
whatever the timing, so every vehicle within the 40 m horizon braked for a
zone that would be clear seconds before it arrived. It is now ordered like
any earlier arrival: a conflict only if this vehicle would get there before
the one inside has left, plus the safety headway.
"""

from types import SimpleNamespace
from typing import Any

from src.controllers.roundabout import RoundaboutController, _ZoneVehicle
from src.core.enums import Direction
from src.roads.network import RoadNetwork


def _controller() -> RoundaboutController:
    network = RoadNetwork()
    network.setup_default_intersection(
        approach_length=200.0,
        lanes_per_approach=2,
        is_roundabout=True,
        circulating_lanes=2,
    )
    return RoundaboutController({}, network)


def _zv(name: str, ring: int, front: float, speed: float, length: float = 4.5) -> Any:
    vehicle = SimpleNamespace(vehicle_id=name, speed=speed, params=None, length=length)
    return _ZoneVehicle(
        vehicle, None, ring, Direction.NORTH, front, front - length, 10.0, 18.0
    )


def test_a_vehicle_far_from_an_occupied_zone_is_not_held() -> None:
    controller = _controller()
    inside = _zv("inside", 1, front=14.0, speed=6.0)  # clears in ~1.4 s
    far = _zv("far", 0, front=-20.0, speed=6.0)  # arrives in 5 s
    assert not controller._zone_conflict(far, [inside])


def test_a_vehicle_close_to_an_occupied_zone_is_held() -> None:
    controller = _controller()
    inside = _zv("inside", 1, front=14.0, speed=6.0)
    near = _zv("near", 0, front=6.0, speed=6.0)  # arrives in under 1 s
    assert controller._zone_conflict(near, [inside])


def test_a_stopped_vehicle_inside_holds_vehicles_well_out() -> None:
    controller = _controller()
    # Stopped inside, it needs several seconds to clear from a standstill.
    stopped = _zv("stopped", 1, front=12.0, speed=0.0)
    out = _zv("out", 0, front=-4.0, speed=6.0)  # arrives in ~2.3 s
    assert controller._zone_conflict(out, [stopped])


def test_the_same_ring_lane_never_conflicts() -> None:
    controller = _controller()
    inside = _zv("inside", 0, front=14.0, speed=0.0)
    behind = _zv("behind", 0, front=8.0, speed=6.0)
    assert not controller._zone_conflict(behind, [inside])
