import math
from typing import Any, List, Tuple


class Lane:
    """Represents a single lane of a road, defined by start and end coordinates."""

    def __init__(
        self,
        lane_id: str,
        start_x: float,
        start_y: float,
        end_x: float,
        end_y: float,
        speed_limit: float = 13.89,
    ) -> None:
        dx = end_x - start_x
        dy = end_y - start_y
        self.length: float = math.sqrt(dx * dx + dy * dy)

        if self.length == 0:
            raise ValueError("Lane start and end points cannot be identical")
        if speed_limit <= 0:
            raise ValueError("Speed limit must be greater than zero")

        self.lane_id: str = lane_id
        self.start_coords: Tuple[float, float] = (start_x, start_y)
        self.end_coords: Tuple[float, float] = (end_x, end_y)
        self.speed_limit: float = speed_limit
        self.vector: Tuple[float, float] = (dx, dy)

        # Calculate heading in degrees (0 = North/Pos-Y, 90 = East/Pos-X, 180 = South/Neg-Y, 270 = West/Neg-X)
        angle = math.degrees(math.atan2(dx, dy))
        self.heading: float = (angle + 360.0) % 360.0

        self._vehicles: List[Any] = []

    def get_point_at_distance(self, distance: float) -> Tuple[float, float]:
        dist = max(0.0, min(distance, self.length))
        ratio = dist / self.length
        x = self.start_coords[0] + ratio * self.vector[0]
        y = self.start_coords[1] + ratio * self.vector[1]
        return (x, y)

    def add_vehicle(self, vehicle: Any) -> None:
        if vehicle not in self._vehicles:
            self._vehicles.append(vehicle)

    def remove_vehicle(self, vehicle: Any) -> None:
        if vehicle in self._vehicles:
            self._vehicles.remove(vehicle)

    def get_vehicles(self) -> List[Any]:
        return self._vehicles
