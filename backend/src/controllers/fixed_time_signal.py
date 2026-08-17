from typing import Any, Dict, List

from src.controllers.base import BaseController
from src.core.enums import Direction
from src.roads.network import RoadNetwork
from src.vehicles.vehicle import Vehicle


class VirtualObstacle:
    def __init__(
        self, position: float, speed: float = 0.0, length: float = 0.0
    ) -> None:
        self.position: float = position
        self.speed: float = speed
        self.length: float = length
        self.vehicle_id: str = "virtual_stop_line"


class FixedTimeSignalController(BaseController):
    """Controls intersection traffic using a fixed-time cyclic phase transition state machine."""

    def __init__(self, config: Dict[str, Any], network: RoadNetwork) -> None:
        self.config: Dict[str, Any] = config
        self.network: RoadNetwork = network

        ctrl_cfg = config.get("controller", {})
        self.green_time: float = ctrl_cfg.get("greenTime", 30.0)
        self.yellow_time: float = ctrl_cfg.get("yellowTime", 4.0)
        self.all_red_time: float = ctrl_cfg.get("allRedTime", 2.0)

        self.phase_sequence: List[str] = ctrl_cfg.get(
            "phaseSequence",
            ["ns_green", "ns_yellow", "all_red", "ew_green", "ew_yellow", "all_red"],
        )

        self.time_in_current_state: float = 0.0
        self.cycle_number: int = 0
        self.current_phase_idx: int = 0

        self.reset()

    def reset(self) -> None:
        self.time_in_current_state = 0.0
        self.cycle_number = 0
        self.current_phase_idx = 0
        self._apply_signals()

    @property
    def current_phase(self) -> str:
        if not self.phase_sequence:
            return "all_red"
        return self.phase_sequence[self.current_phase_idx]

    @property
    def phase_time_remaining(self) -> float:
        phase = self.current_phase
        total_time = self._get_phase_duration(phase)
        return max(0.0, total_time - self.time_in_current_state)

    def _get_phase_duration(self, phase: str) -> float:
        if "green" in phase:
            return self.green_time
        elif "yellow" in phase:
            return self.yellow_time
        return self.all_red_time

    def update(self, delta_time: float, active_vehicles: List[Vehicle]) -> None:
        self.time_in_current_state += delta_time
        phase = self.current_phase
        duration = self._get_phase_duration(phase)

        if self.time_in_current_state >= duration:
            # Transition to next phase
            self.time_in_current_state -= duration
            old_idx = self.current_phase_idx
            self.current_phase_idx = (self.current_phase_idx + 1) % len(
                self.phase_sequence
            )

            # Increment cycle count if completed whole sequence
            if self.current_phase_idx < old_idx:
                self.cycle_number += 1

        self._apply_signals()

    def _apply_signals(self) -> None:
        phase = self.current_phase

        # Determine signal colors for North-South and East-West
        ns_color = "red"
        ew_color = "red"

        if phase == "ns_green":
            ns_color = "green"
        elif phase == "ns_yellow":
            ns_color = "yellow"
        elif phase == "ew_green":
            ew_color = "green"
        elif phase == "ew_yellow":
            ew_color = "yellow"

        # Apply stop constraints based on colors
        self._apply_direction_signal(Direction.NORTH, ns_color)
        self._apply_direction_signal(Direction.SOUTH, ns_color)
        self._apply_direction_signal(Direction.EAST, ew_color)
        self._apply_direction_signal(Direction.WEST, ew_color)

    def _apply_direction_signal(self, direction: Direction, color: str) -> None:
        try:
            approach = self.network.get_incoming_approach(direction)
            for lane in approach.get_lanes():
                if color in ("red", "yellow"):
                    # Stop obstacle at the end of the lane
                    lane.virtual_obstacle = VirtualObstacle(position=lane.length)  # type: ignore[attr-defined]
                else:
                    # Clear obstacle
                    lane.virtual_obstacle = None  # type: ignore[attr-defined]
        except KeyError:
            pass

    def get_state(self) -> Dict[str, Any]:
        phase = self.current_phase
        ns_color = "red"
        ew_color = "red"

        if phase == "ns_green":
            ns_color = "green"
        elif phase == "ns_yellow":
            ns_color = "yellow"
        elif phase == "ew_green":
            ew_color = "green"
        elif phase == "ew_yellow":
            ew_color = "yellow"

        signals = [
            {"direction": "north", "color": ns_color},
            {"direction": "south", "color": ns_color},
            {"direction": "east", "color": ew_color},
            {"direction": "west", "color": ew_color},
        ]

        return {
            "type": "fixed_time_signal",
            "timeInCurrentState": round(self.time_in_current_state, 2),
            "currentPhase": phase,
            "phaseTimeRemaining": round(self.phase_time_remaining, 2),
            "cycleNumber": self.cycle_number,
            "signals": signals,
        }
