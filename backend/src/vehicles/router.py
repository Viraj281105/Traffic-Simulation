from typing import Any, Optional, Tuple

from src.roads.network import RoadNetwork
from src.vehicles.vehicle import Vehicle


def find_leader(
    vehicle: Vehicle, network: Optional[RoadNetwork] = None
) -> Tuple[Optional[Any], float]:
    """Finds the leading vehicle (or virtual obstacle) for a given vehicle along its route.

    Returns:
        A tuple of (leader_vehicle, gap_distance).
        If no leader is found, returns (None, float('inf')).
    """
    if vehicle.lane is None or not vehicle.route:
        return None, float("inf")

    try:
        curr_idx = vehicle.route.index(vehicle.lane)
    except ValueError:
        return None, float("inf")

    accumulated_dist = -vehicle.position

    # Search through the remaining route lanes
    for i in range(curr_idx, len(vehicle.route)):
        lane = vehicle.route[i]

        # Check for real vehicles in this lane
        leader = None
        min_lead_dist = float("inf")

        for v in lane.get_vehicles():
            if v == vehicle:
                continue

            # Distance of candidate vehicle from subject vehicle along the route
            v_dist = accumulated_dist + v.position
            if v_dist > 0 and v_dist < min_lead_dist:
                min_lead_dist = v_dist
                leader = v

        if leader is not None:
            # Physical gap: distance between front of trailing and rear of leading
            gap = min_lead_dist - (vehicle.length / 2.0 + leader.length / 2.0)
            return leader, max(0.0, gap)

        # Advance accumulated distance by the lane's length
        accumulated_dist += lane.length

    # If no real vehicle was found, we check if there are virtual leaders.
    # Virtual leaders can be injected via custom properties on the lane,
    # e.g., if lane has a virtual stop line or signal.
    # For Sprint 2 core implementation, we support returning them if set.
    # Active controllers (sprint 3/4) will set/inject these virtual obstacles
    # or flags on the lanes.
    if (
        hasattr(vehicle.lane, "virtual_obstacle")
        and vehicle.lane.virtual_obstacle is not None
    ):
        obstacle = vehicle.lane.virtual_obstacle
        # distance of obstacle along route
        obs_dist = -vehicle.position + obstacle.position
        if obs_dist > 0:
            gap = obs_dist - (vehicle.length / 2.0 + obstacle.length / 2.0)
            return obstacle, max(0.0, gap)

    return None, float("inf")
