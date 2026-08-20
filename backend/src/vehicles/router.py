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

        # Check for virtual obstacles (e.g., stop signals) in this lane
        if hasattr(lane, "virtual_obstacle") and lane.virtual_obstacle is not None:
            obstacle = lane.virtual_obstacle
            obs_dist = accumulated_dist + obstacle.position
            if obs_dist > 0 and obs_dist < min_lead_dist:
                min_lead_dist = obs_dist
                leader = obstacle

        if leader is not None:
            # Physical gap: distance between front of trailing and rear of leading
            gap = min_lead_dist - (vehicle.length / 2.0 + leader.length / 2.0)
            return leader, max(0.0, gap)

        # Advance accumulated distance by the lane's length
        accumulated_dist += lane.length

    return None, float("inf")
