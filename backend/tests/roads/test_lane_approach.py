import pytest

from src.core.enums import Direction
from src.roads.approach import Approach
from src.roads.lane import Lane


# Stub vehicle for testing
class StubVehicle:
    pass


def test_lane_initialization() -> None:
    lane = Lane(
        "lane_1", start_x=0.0, start_y=10.0, end_x=0.0, end_y=110.0, speed_limit=15.0
    )
    assert lane.lane_id == "lane_1"
    assert lane.start_coords == (0.0, 10.0)
    assert lane.end_coords == (0.0, 110.0)
    assert lane.speed_limit == 15.0
    assert lane.length == 100.0
    assert lane.vector == (0.0, 100.0)
    assert pytest.approx(lane.heading) == 0.0  # Facing North (positive Y)


def test_lane_invalid_initialization() -> None:
    # Identical start/end coordinates
    msg = "Lane start and end points cannot be identical"
    with pytest.raises(ValueError, match=msg):
        Lane("lane_err", 5.0, 5.0, 5.0, 5.0)
    # Invalid speed limits
    with pytest.raises(ValueError, match="Speed limit must be greater than zero"):
        Lane("lane_err", 0.0, 0.0, 0.0, 10.0, speed_limit=0.0)
    with pytest.raises(ValueError, match="Speed limit must be greater than zero"):
        Lane("lane_err", 0.0, 0.0, 0.0, 10.0, speed_limit=-1.0)


def test_lane_headings() -> None:
    # Eastbound (dx=10, dy=0)
    lane_east = Lane("east", 0.0, 0.0, 10.0, 0.0)
    assert pytest.approx(lane_east.heading) == 90.0

    # Southbound (dx=0, dy=-10)
    lane_south = Lane("south", 0.0, 0.0, 0.0, -10.0)
    assert pytest.approx(lane_south.heading) == 180.0

    # Westbound (dx=-10, dy=0)
    lane_west = Lane("west", 0.0, 0.0, -10.0, 0.0)
    assert pytest.approx(lane_west.heading) == 270.0


def test_lane_get_point_at_distance() -> None:
    lane = Lane("lane", 0.0, 0.0, 30.0, 40.0)  # Length 50.0 (3-4-5 triangle)
    assert lane.length == 50.0

    # Test exact bounds
    assert lane.get_point_at_distance(0.0) == (0.0, 0.0)
    assert lane.get_point_at_distance(25.0) == (15.0, 20.0)
    assert lane.get_point_at_distance(50.0) == (30.0, 40.0)

    # Test out of bounds capping
    assert lane.get_point_at_distance(-10.0) == (0.0, 0.0)
    assert lane.get_point_at_distance(60.0) == (30.0, 40.0)


def test_lane_vehicle_tracking() -> None:
    lane = Lane("lane", 0.0, 0.0, 0.0, 10.0)
    vehicle_1 = StubVehicle()  # type: ignore
    vehicle_2 = StubVehicle()  # type: ignore

    assert len(lane.get_vehicles()) == 0
    lane.add_vehicle(vehicle_1)  # type: ignore
    assert lane.get_vehicles() == [vehicle_1]

    # Do not add duplicates
    lane.add_vehicle(vehicle_1)  # type: ignore
    assert lane.get_vehicles() == [vehicle_1]

    lane.add_vehicle(vehicle_2)  # type: ignore
    assert lane.get_vehicles() == [vehicle_1, vehicle_2]

    lane.remove_vehicle(vehicle_1)  # type: ignore
    assert lane.get_vehicles() == [vehicle_2]

    # Safe removal if not present
    lane.remove_vehicle(vehicle_1)  # type: ignore
    assert lane.get_vehicles() == [vehicle_2]


def test_approach_initialization() -> None:
    approach = Approach(Direction.NORTH, speed_limit=12.0)
    assert approach.direction == Direction.NORTH
    assert approach.speed_limit == 12.0
    assert len(approach.get_lanes()) == 0


def test_approach_invalid_initialization() -> None:
    with pytest.raises(ValueError, match="Speed limit must be greater than zero"):
        Approach(Direction.EAST, speed_limit=0.0)
    with pytest.raises(ValueError, match="Speed limit must be greater than zero"):
        Approach(Direction.WEST, speed_limit=-5.0)


def test_approach_lanes_and_vehicles() -> None:
    approach = Approach(Direction.SOUTH)
    lane_1 = Lane("lane_1", 0.0, 0.0, 0.0, 10.0)
    lane_2 = Lane("lane_2", 3.5, 0.0, 3.5, 10.0)

    approach.add_lane(lane_1)
    approach.add_lane(lane_2)

    # Test duplicate prevention
    approach.add_lane(lane_1)

    assert approach.get_lanes() == [lane_1, lane_2]

    vehicle_1 = StubVehicle()  # type: ignore
    vehicle_2 = StubVehicle()  # type: ignore

    lane_1.add_vehicle(vehicle_1)  # type: ignore
    lane_2.add_vehicle(vehicle_2)  # type: ignore

    assert approach.get_active_vehicles() == [vehicle_1, vehicle_2]
