from abc import ABC, abstractmethod
from typing import Any, Dict, List

from src.vehicles.vehicle import Vehicle


class BaseController(ABC):
    """Abstract Base Class defining the interface for all traffic controllers."""

    @abstractmethod
    def update(self, delta_time: float, active_vehicles: List[Vehicle]) -> None:
        """Ticks the controller state machine and updates visual/physical boundaries."""
        pass

    @abstractmethod
    def get_state(self) -> Dict[str, Any]:
        """Returns the current state of the controller formatted for snapshot schema."""
        pass

    @abstractmethod
    def reset(self) -> None:
        """Resets the controller to its initial state."""
        pass
