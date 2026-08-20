import math
from typing import Any, List, Optional, Tuple

from src.roads.network import RoadNetwork
from src.vehicles.vehicle import Vehicle


class VirtualObstacle:
    def __init__(self, position: float, speed: float = 0.0, length: float = 0.0) -> None:
        self.position: float = position
        self.speed: float = speed
        self.length: float = length
        self.vehicle_id: str = "virtual_stop_line"


def line_intersection(
    p0: Tuple[float, float], p1: Tuple[float, float],
    p2: Tuple[float, float], p3: Tuple[float, float]
) -> Optional[Tuple[float, float]]:
    """Calculates the intersection point of two line segments p0->p1 and p2->p3."""
    s1_x = p1[0] - p0[0]
    s1_y = p1[1] - p0[1]
    s2_x = p3[0] - p2[0]
    s2_y = p3[1] - p2[1]

    denom = (-s2_x * s1_y + s1_x * s2_y)
    if abs(denom) < 1e-9:
        return None  # Parallel or collinear

    s = (-s1_y * (p0[0] - p2[0]) + s1_x * (p0[1] - p2[1])) / denom
    t = ( s2_x * (p0[1] - p2[1]) - s2_y * (p0[0] - p2[0])) / denom

    if 0.0 <= s <= 1.0 and 0.0 <= t <= 1.0:
        return (p0[0] + (t * s1_x), p0[1] + (t * s1_y))
    return None


def get_distance_to_point_on_route(v: Vehicle, target_lane: Any, pt: Tuple[float, float]) -> float:
    """Calculates route distance from vehicle's current position to a point on a target lane."""
    try:
        curr_idx = v.route.index(v.lane)
        target_idx = v.route.index(target_lane)
    except ValueError:
        return -1.0

    if target_idx < curr_idx:
        return -1.0

    dist = -v.position
    for idx in range(curr_idx, target_idx):
        dist += v.route[idx].length

    start_x, start_y = target_lane.start_coords
    dist_on_lane = math.sqrt((pt[0] - start_x) ** 2 + (pt[1] - start_y) ** 2)
    dist += dist_on_lane
    return dist


def find_leader(
    vehicle: Vehicle,
    network: Optional[RoadNetwork] = None,
    active_vehicles: Optional[List[Vehicle]] = None,
) -> Tuple[Optional[Any], float]:
    """Finds the leading vehicle (or virtual obstacle/crossing conflict) for a vehicle along its route."""
    if vehicle.lane is None or not vehicle.route:
        return None, float("inf")

    try:
        curr_idx = vehicle.route.index(vehicle.lane)
    except ValueError:
        return None, float("inf")

    # 1. Lane-following leader detection (checking vehicles on the same or subsequent route lanes)
    leader: Optional[Any] = None
    min_lead_dist = float("inf")
    accumulated_dist = -vehicle.position

    for i in range(curr_idx, len(vehicle.route)):
        lane = vehicle.route[i]

        for v in lane.get_vehicles():
            if v == vehicle:
                continue
            v_dist = accumulated_dist + v.position
            if 0 < v_dist < min_lead_dist:
                min_lead_dist = v_dist
                leader = v

        # Check for virtual obstacles (e.g., stop signals) in this lane
        if hasattr(lane, "virtual_obstacle") and lane.virtual_obstacle is not None:
            obstacle = lane.virtual_obstacle
            obs_dist = accumulated_dist + obstacle.position
            if 0 < obs_dist < min_lead_dist:
                min_lead_dist = obs_dist
                leader = obstacle

        if leader is not None:
            gap = min_lead_dist - (vehicle.length / 2.0 + leader.length / 2.0)
            return leader, max(0.0, gap)

        accumulated_dist += lane.length

    # 2. 360-degree sensor view & crossing conflict yielding
    if active_vehicles:
        my_x, my_y = vehicle.coords
        sensor_range = 25.0
        
        for other in active_vehicles:
            if other == vehicle or other.lane is None:
                continue

            # Compute Euclidean distance (360-degree check)
            ox, oy = other.coords
            dist_to_other = math.sqrt((ox - my_x) ** 2 + (oy - my_y) ** 2)
            if dist_to_other > sensor_range:
                continue

            # Scan future intersecting routes
            try:
                other_curr_idx = other.route.index(other.lane)
            except ValueError:
                continue

            for my_lane_idx in range(curr_idx, len(vehicle.route)):
                my_lane = vehicle.route[my_lane_idx]
                for other_lane_idx in range(other_curr_idx, len(other.route)):
                    other_lane = other.route[other_lane_idx]

                    if my_lane.lane_id == other_lane.lane_id:
                        continue

                    # Check segment intersection
                    pt = line_intersection(
                        my_lane.start_coords, my_lane.end_coords,
                        other_lane.start_coords, other_lane.end_coords
                    )
                    if pt is not None:
                        dist_to_pt_self = get_distance_to_point_on_route(vehicle, my_lane, pt)
                        dist_to_pt_other = get_distance_to_point_on_route(other, other_lane, pt)

                        if dist_to_pt_self > 0 and dist_to_pt_other > 0:
                            # Whichever vehicle is closer to the conflict point has right of way
                            if dist_to_pt_other < dist_to_pt_self:
                                gap = dist_to_pt_self - vehicle.length / 2.0
                                if gap < min_lead_dist:
                                    min_lead_dist = gap
                                    # Treat the crossing vehicle as the pseudo-leader
                                    leader = other

        if leader is not None:
            return leader, max(0.0, min_lead_dist)

    return None, float("inf")
