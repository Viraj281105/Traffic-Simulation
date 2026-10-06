"""Where a vehicle's body is, given where it is along its route (V1.1).

A vehicle's longitudinal state is one number — its centre's distance along
the route. Its *body* (the rectangle the collision audit and the predictive
layer test) has to be placed from that.

V1.0 placed the rectangle with its centre on the path and its long axis along
the path's tangent at the centre. For a passenger car that is a fine
approximation, and it is kept unchanged for every vehicle up to
:data:`LONG_VEHICLE_THRESHOLD`. For a long vehicle on a tight curve it is not:
an 8-12 m rectangle laid tangent to a 5-15 m radius bend has its ends metres
outside the path, so a turning truck's nose swept across the stop line of the
next approach and an exiting bus's tail swung over the roundabout's splitter
island — collisions with vehicles that were correctly where they should be.

Real vehicles do the opposite. Both axles stay on the path the driver steers
and the body cuts the *inside* of the bend (off-tracking). So a long vehicle's
body is placed on the chord between its front and rear axle points, both on
the route ``wheelbase / 2`` either side of the centre: the body centre is the
chord's midpoint and its heading the chord's direction. On a straight road
that is exactly the V1.0 pose.
"""

from __future__ import annotations

import math
from typing import List, Sequence, Tuple

from src.roads.lane import Lane
from src.vehicles.vehicle_types import REFERENCE_VEHICLE_LENGTH

# Vehicles longer than this are posed on their axle chord; up to it, exactly
# as in V1.0.
LONG_VEHICLE_THRESHOLD: float = REFERENCE_VEHICLE_LENGTH

# Wheelbase as a fraction of overall length — typical of rigid trucks and
# single-deck buses (e.g. a 12 m bus has a ~7 m wheelbase).
WHEELBASE_FRACTION: float = 0.6

Pose = Tuple[float, float, float]  # x, y, heading (degrees, 0 = +y)


def route_point(
    route: Sequence[Lane], lane_index: int, distance: float
) -> Tuple[float, float]:
    """Point ``distance`` metres along the route from the start of lane
    ``lane_index`` (negative or beyond the route's end: extrapolated along
    the first/last lane's direction, so a pose is defined everywhere)."""
    idx = lane_index
    s = distance
    while s < 0.0 and idx > 0:
        idx -= 1
        s += route[idx].length
    while s > route[idx].length and idx < len(route) - 1:
        s -= route[idx].length
        idx += 1
    lane = route[idx]
    if s < 0.0:
        heading = math.radians(lane.get_heading_at_distance(0.0))
        x, y = lane.start_coords
        return (x + s * math.sin(heading), y + s * math.cos(heading))
    if s > lane.length:
        heading = math.radians(lane.get_heading_at_distance(lane.length))
        x, y = lane.end_coords
        over = s - lane.length
        return (x + over * math.sin(heading), y + over * math.cos(heading))
    return lane.get_point_at_distance(s)


def body_pose(
    route: Sequence[Lane], lane_index: int, position: float, length: float
) -> Pose:
    """Centre and heading of the body of a vehicle ``length`` metres long whose
    centre is ``position`` metres along route lane ``lane_index``."""
    lane = route[lane_index]
    if length <= LONG_VEHICLE_THRESHOLD:
        x, y = lane.get_point_at_distance(position)
        return (x, y, lane.get_heading_at_distance(position))
    half_wheelbase = WHEELBASE_FRACTION * length / 2.0
    fx, fy = route_point(route, lane_index, position + half_wheelbase)
    rx, ry = route_point(route, lane_index, position - half_wheelbase)
    dx, dy = fx - rx, fy - ry
    if dx == 0.0 and dy == 0.0:
        x, y = lane.get_point_at_distance(position)
        return (x, y, lane.get_heading_at_distance(position))
    heading = (math.degrees(math.atan2(dx, dy)) + 360.0) % 360.0
    return ((fx + rx) / 2.0, (fy + ry) / 2.0, heading)


Point = Tuple[float, float]


def polygons_overlap(poly_a: Sequence[Point], poly_b: Sequence[Point]) -> bool:
    """Separating-axis test for two convex polygons (touching counts)."""
    for poly in (poly_a, poly_b):
        n = len(poly)
        for i in range(n):
            x1, y1 = poly[i]
            x2, y2 = poly[(i + 1) % n]
            ax, ay = y1 - y2, x2 - x1
            if ax == 0.0 and ay == 0.0:
                continue
            proj_a = [px * ax + py * ay for px, py in poly_a]
            proj_b = [px * ax + py * ay for px, py in poly_b]
            if max(proj_a) < min(proj_b) or max(proj_b) < min(proj_a):
                return False
    return True


def forward_probe(
    x: float,
    y: float,
    heading_deg: float,
    length: float,
    width: float,
    reach: float,
    side_margin: float,
) -> List[Point]:
    """Corners of a vehicle's box stretched ``reach`` metres forward and
    widened by ``side_margin`` per side: the space it is about to occupy."""
    h = math.radians(heading_deg)
    fx, fy = math.sin(h), math.cos(h)
    rx, ry = fy, -fx
    back, front = -length / 2.0, length / 2.0 + reach
    half_w = width / 2.0 + side_margin
    return [
        (x + front * fx - half_w * rx, y + front * fy - half_w * ry),
        (x + front * fx + half_w * rx, y + front * fy + half_w * ry),
        (x + back * fx + half_w * rx, y + back * fy + half_w * ry),
        (x + back * fx - half_w * rx, y + back * fy - half_w * ry),
    ]
