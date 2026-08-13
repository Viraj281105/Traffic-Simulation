from typing import Any, List

from src.core.enums import Direction
from src.roads.lane import Lane


class Approach:
    """Represents a set of incoming or outgoing lanes corresponding to a single approach direction."""

    def __init__(self, direction: Direction, speed_limit: float = 13.89) -> None:
        if speed_limit <= 0:
            raise ValueError("Speed limit must be greater than zero")
        self.direction: Direction = direction
        self.speed_limit: float = speed_limit
        self._lanes: List[Lane] = []

    def add_lane(self, lane: Lane) -> None:
        if lane not in self._lanes:
            self._lanes.append(lane)

    def get_lanes(self) -> List[Lane]:
        return self._lanes

    def get_active_vehicles(self) -> List[Any]:
        vehicles = []
        for lane in self._lanes:
            vehicles.extend(lane.get_vehicles())
        return vehicles
