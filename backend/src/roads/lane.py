import math
from bisect import bisect_left
from typing import Any, List, Optional, Tuple


class Lane:
    """Represents a single lane of a road, defined by start and end coordinates or a list of waypoints."""

    def __init__(
        self,
        lane_id: str,
        start_x: float,
        start_y: float,
        end_x: float,
        end_y: float,
        speed_limit: float = 13.89,
        waypoints: Optional[List[Tuple[float, float]]] = None,
    ) -> None:
        if speed_limit <= 0:
            raise ValueError("Speed limit must be greater than zero")

        self.lane_id: str = lane_id
        self.speed_limit: float = speed_limit
        self.start_coords: Tuple[float, float] = (start_x, start_y)
        self.end_coords: Tuple[float, float] = (end_x, end_y)

        if waypoints and len(waypoints) >= 2:
            self.waypoints: List[Tuple[float, float]] = waypoints
            # Compute cumulative segment lengths
            self._cum_lengths: List[float] = [0.0]
            total_len = 0.0
            for i in range(len(waypoints) - 1):
                p1 = waypoints[i]
                p2 = waypoints[i + 1]
                seg_len = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
                total_len += seg_len
                self._cum_lengths.append(total_len)
            self.length: float = total_len
            self.start_coords = waypoints[0]
            self.end_coords = waypoints[-1]
        else:
            dx = end_x - start_x
            dy = end_y - start_y
            self.length = math.hypot(dx, dy)
            self.waypoints = [self.start_coords, self.end_coords]
            self._cum_lengths = [0.0, self.length]

        if self.length == 0:
            raise ValueError("Lane start and end points cannot be identical")

        dx = self.end_coords[0] - self.start_coords[0]
        dy = self.end_coords[1] - self.start_coords[1]
        self.vector: Tuple[float, float] = (dx, dy)

        # Base heading in degrees (0 = North/Pos-Y, 90 = East/Pos-X, 180 = South/Neg-Y, 270 = West/Neg-X)
        angle = math.degrees(math.atan2(dx, dy))
        self.heading: float = (angle + 360.0) % 360.0

        # Per-segment values the position/heading lookups need, computed once
        # (a lane's waypoints never change after construction).
        self._seg_vectors: List[Tuple[float, float]] = []
        self._seg_lengths: List[float] = []
        self._seg_headings: List[float] = []
        for i in range(len(self.waypoints) - 1):
            p1, p2 = self.waypoints[i], self.waypoints[i + 1]
            seg_dx, seg_dy = p2[0] - p1[0], p2[1] - p1[1]
            self._seg_vectors.append((seg_dx, seg_dy))
            self._seg_lengths.append(
                max(1e-6, self._cum_lengths[i + 1] - self._cum_lengths[i])
            )
            seg_angle = math.degrees(math.atan2(seg_dx, seg_dy))
            self._seg_headings.append((seg_angle + 360.0) % 360.0)

        self._vehicles: List[Any] = []

        # Explicit lane identity (V1.2), set by RoadNetwork for the lanes it
        # builds: which approach the lane belongs to, its index across that
        # approach (0 = next to the centreline, i.e. the left-most lane of an
        # incoming carriageway in right-hand traffic), and its role
        # ("incoming", "outgoing" or "connection"). None/"" for hand-built
        # lanes, which every consumer must tolerate.
        self.approach: Optional[Any] = None
        self.index: Optional[int] = None
        self.role: str = ""

        # Optional virtual obstacle placed on this lane by a controller (e.g. stop-line)
        self.virtual_obstacle: Optional[Any] = None

        # Steady-state circulating radius, set externally by
        # RoadNetwork._get_or_create_connection_lane for a roundabout
        # connection lane (None for every other lane, including
        # non-roundabout connection lanes and hand-built lanes in tests).
        # Valid only for the lane's steady-state middle arc, not its
        # entry/exit transition zones — see router.find_leader.
        self.circulating_radius: Optional[float] = None

    def _segment(self, distance: float) -> Tuple[int, float]:
        """Index of the waypoint segment holding ``distance`` (clamped to the
        lane): the first segment whose end is at or beyond it, else the last.
        Returns the clamped distance too."""
        length = self.length
        dist = length if length < distance else distance
        if not dist > 0.0:
            dist = 0.0
        return bisect_left(
            self._cum_lengths, dist, 1, len(self._cum_lengths) - 1
        ) - 1, dist

    def get_point_at_distance(self, distance: float) -> Tuple[float, float]:
        # Hot path (called for every vehicle, many times a tick): the clamps
        # are written out rather than max/min calls, and multi-segment lanes
        # find their segment by bisection over the precomputed cumulative
        # lengths instead of a linear scan. Same segment, same arithmetic.
        if len(self.waypoints) == 2:
            length = self.length
            dist = length if length < distance else distance
            if not dist > 0.0:
                dist = 0.0
            ratio = dist / length
            return (
                self.start_coords[0] + ratio * self.vector[0],
                self.start_coords[1] + ratio * self.vector[1],
            )

        i, dist = self._segment(distance)
        seg_start_dist = self._cum_lengths[i]
        seg_ratio = (dist - seg_start_dist) / self._seg_lengths[i]
        if not seg_ratio < 1.0:
            seg_ratio = 1.0
        if not seg_ratio > 0.0:
            seg_ratio = 0.0
        p1 = self.waypoints[i]
        dx, dy = self._seg_vectors[i]
        return (p1[0] + seg_ratio * dx, p1[1] + seg_ratio * dy)

    def get_heading_at_distance(self, distance: float) -> float:
        if len(self.waypoints) == 2:
            return self.heading
        return self._seg_headings[self._segment(distance)[0]]

    def add_vehicle(self, vehicle: Any) -> None:
        if vehicle not in self._vehicles:
            self._vehicles.append(vehicle)

    def remove_vehicle(self, vehicle: Any) -> None:
        if vehicle in self._vehicles:
            self._vehicles.remove(vehicle)

    def get_vehicles(self) -> List[Any]:
        return self._vehicles
