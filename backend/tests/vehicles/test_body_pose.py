"""Long-vehicle body pose (V1.1): axle chord, not a tangent rectangle."""

import math

import pytest

from src.core.enums import Direction, TurnIntent
from src.roads.lane import Lane
from src.roads.network import RoadNetwork
from src.vehicles.body import (
    LONG_VEHICLE_THRESHOLD,
    WHEELBASE_FRACTION,
    body_pose,
    forward_probe,
    polygons_overlap,
    route_point,
)
from src.vehicles.vehicle import Vehicle


def _right_turn_route() -> list:
    network = RoadNetwork()
    network.setup_default_intersection(approach_length=100.0, lanes_per_approach=1)
    return network.generate_route(Direction.WEST, 0, TurnIntent.RIGHT)


def test_short_vehicle_pose_is_the_v10_pose() -> None:
    route = _right_turn_route()
    for pos in (0.5, 3.0, 6.0):
        x, y, h = body_pose(route, 1, pos, LONG_VEHICLE_THRESHOLD)
        assert (x, y) == route[1].get_point_at_distance(pos)
        assert h == route[1].get_heading_at_distance(pos)


def test_long_vehicle_on_a_straight_lane_is_unchanged() -> None:
    lane = Lane("w_in_0", -100.0, -1.75, -10.0, -1.75)
    x, y, h = body_pose([lane], 0, 40.0, 12.0)
    px, py = lane.get_point_at_distance(40.0)
    assert x == pytest.approx(px)
    assert y == pytest.approx(py)
    assert h == pytest.approx(lane.heading)


def test_long_vehicle_body_cuts_the_inside_of_a_bend() -> None:
    route = _right_turn_route()
    conn = route[1]
    mid = conn.length / 2.0
    on_path = conn.get_point_at_distance(mid)
    x, y, heading = body_pose(route, 1, mid, 12.0)
    # The right turn W->S bends about a centre at (start x, end y), beside the
    # kerb: the body centre sits closer to it than the path point (the body
    # cuts the inside of the bend instead of swinging out of it).
    centre = (conn.start_coords[0], conn.end_coords[1])
    assert math.dist((x, y), centre) < math.dist(on_path, centre)
    # And its heading is the axle chord's, between the entry and exit
    # headings rather than the tangent at the centre.
    half = WHEELBASE_FRACTION * 12.0 / 2.0
    fx, fy = route_point(route, 1, mid + half)
    rx, ry = route_point(route, 1, mid - half)
    expected = (math.degrees(math.atan2(fx - rx, fy - ry)) + 360.0) % 360.0
    assert heading == pytest.approx(expected)


def test_route_point_crosses_lane_boundaries_and_extrapolates() -> None:
    route = _right_turn_route()
    approach, conn = route[0], route[1]
    # Negative distance on lane 1 lands on lane 0.
    assert route_point(route, 1, -2.0) == pytest.approx(
        approach.get_point_at_distance(approach.length - 2.0)
    )
    # Beyond the route end continues straight along the last lane.
    last = route[-1]
    ex, ey = last.end_coords
    px, py = route_point(route, 2, last.length + 3.0)
    assert math.dist((px, py), (ex, ey)) == pytest.approx(3.0)
    assert conn.length > 0


def test_vehicle_uses_the_chord_pose_only_when_long() -> None:
    route = _right_turn_route()
    car = Vehicle("car", 4.5, 1.9, 10.0, route, start_position=2.0)
    bus = Vehicle("bus", 12.0, 2.5, 10.0, list(route), start_position=2.0)
    for v in (car, bus):
        v.lane.remove_vehicle(v)
        v.lane = route[1]
        v.position = 4.0
    assert car.coords == route[1].get_point_at_distance(4.0)
    assert bus.coords != route[1].get_point_at_distance(4.0)
    bx, by, bh = body_pose(route, 1, 4.0, 12.0)
    assert bus.coords == pytest.approx((bx, by))
    assert bus.heading == pytest.approx(bh)


def test_polygon_overlap_and_forward_probe() -> None:
    probe = forward_probe(0.0, 0.0, 0.0, 4.0, 2.0, 2.5, 0.15)
    ys = [p[1] for p in probe]
    assert max(ys) == pytest.approx(4.5)  # front + reach
    assert min(ys) == pytest.approx(-2.0)
    ahead = [(-1.0, 4.0), (1.0, 4.0), (1.0, 6.0), (-1.0, 6.0)]
    beside = [(3.0, 0.0), (4.0, 0.0), (4.0, 1.0), (3.0, 1.0)]
    assert polygons_overlap(probe, ahead)
    assert not polygons_overlap(probe, beside)
