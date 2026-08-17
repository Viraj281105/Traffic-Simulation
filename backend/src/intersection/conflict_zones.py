from typing import Dict, List, Optional, Tuple

from src.vehicles.vehicle import Vehicle


class ConflictZoneDetector:
    """Detects crossing path overlap points (conflict zones) and computes safety gaps for yielding."""

    def __init__(self) -> None:
        # Maps a pair of connection lane IDs to their intersection point coordinates (x, y)
        self.conflict_points: Dict[Tuple[str, str], Tuple[float, float]] = {}

    def register_conflict(
        self, lane_id_1: str, lane_id_2: str, x: float, y: float
    ) -> None:
        # Store sorted key to handle unordered pairs
        key = (min(lane_id_1, lane_id_2), max(lane_id_1, lane_id_2))
        self.conflict_points[key] = (x, y)

    def _get_intersection_point(
        self, id1: str, id2: str
    ) -> Optional[Tuple[float, float]]:
        key = (min(id1, id2), max(id1, id2))
        return self.conflict_points.get(key)

    def check_conflicts(
        self, vehicle: Vehicle, active_vehicles: List[Vehicle]
    ) -> float:
        """Returns the safety gap to the nearest path competitor in a conflict zone.

        If no conflict requires yielding, returns float('inf').
        """
        if vehicle.lane is None or not vehicle.lane.lane_id.startswith("conn"):
            return float("inf")

        curr_lane_id = vehicle.lane.lane_id
        min_gap = float("inf")

        for other in active_vehicles:
            if other == vehicle or other.lane is None:
                continue

            other_lane_id = other.lane.lane_id
            if not other_lane_id.startswith("conn") or other_lane_id == curr_lane_id:
                continue

            # Check if their connection lanes cross
            pt = self._get_intersection_point(curr_lane_id, other_lane_id)
            if pt is None:
                continue

            # Calculate distance of both vehicles to the crossing point
            # Distance along a line segment from start_coords to crossing point
            lane_start_x, lane_start_y = vehicle.lane.start_coords
            dist_to_pt_self = (
                (pt[0] - lane_start_x) ** 2 + (pt[1] - lane_start_y) ** 2
            ) ** 0.5

            other_start_x, other_start_y = other.lane.start_coords
            dist_to_pt_other = (
                (pt[0] - other_start_x) ** 2 + (pt[1] - other_start_y) ** 2
            ) ** 0.5

            # If other vehicle has already passed the intersection point, no conflict
            if other.position > dist_to_pt_other:
                continue

            # Determine priority (e.g., whoever is closer to the crossing point)
            # In real traffic, the one closer has the right-of-way.
            self_dist_left = dist_to_pt_self - vehicle.position
            other_dist_left = dist_to_pt_other - other.position

            if self_dist_left > 0 and other_dist_left > 0:
                # If other vehicle is closer to the conflict point, we yield
                if other_dist_left < self_dist_left:
                    # Yield gap: distance from our front to the conflict point
                    gap = self_dist_left - vehicle.length / 2.0
                    if gap < min_gap:
                        min_gap = gap

        return min_gap
