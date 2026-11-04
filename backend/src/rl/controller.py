"""A two-phase signal controller whose green is chosen from outside.

Plan: ``0 = north-south green``, ``1 = east-west green``. Switching from one to
the other always runs the stage's yellow and an all-red clearance first, and a
green is held for at least ``min_green`` seconds, so the agent can neither skip
the clearance nor flicker the lights. Signal heads are applied by the inherited
``_apply_signals`` (virtual stop-line obstacles); whether a released vehicle may
enter is still decided by the conflict manager, exactly as for fixed-time.
"""

from __future__ import annotations

from typing import Any, Dict, List

from src.controllers.fixed_time_signal import FixedTimeSignalController
from src.roads.network import RoadNetwork
from src.vehicles.vehicle import Vehicle

PLAN = ["ns_green", "ns_yellow", "all_red", "ew_green", "ew_yellow", "all_red"]
# Index into PLAN of each selectable green, and of the yellow that ends it.
_GREEN_IDX = (0, 3)
_YELLOW_IDX = (1, 4)
_RED_IDX = (2, 5)


class ExternalPhaseController(FixedTimeSignalController):
    """Holds a green until ``request_green`` asks for the other one."""

    SIGNAL_CONTROL = "external"

    def __init__(
        self,
        config: Dict[str, Any],
        network: RoadNetwork,
        min_green: float = 5.0,
    ) -> None:
        cfg = dict(config)
        ctrl = dict(cfg.get("controller") or {})
        ctrl["phaseSequence"] = list(PLAN)
        ctrl.pop("offset", None)
        cfg["controller"] = ctrl
        self.min_green = float(min_green)
        self._requested: int = 0
        super().__init__(cfg, network)

    def reset(self) -> None:
        self._requested = 0
        super().reset()
        self.switches: int = 0

    @property
    def active_green(self) -> int:
        """0 / 1 for the green on (or last on) the lights; see ``in_transition``."""
        return 0 if self.current_phase_idx in (0, 1, 2) else 1

    @property
    def in_transition(self) -> bool:
        return self.current_phase_idx not in _GREEN_IDX

    def request_green(self, which: int) -> None:
        if which not in (0, 1):
            raise ValueError("green must be 0 (north-south) or 1 (east-west)")
        self._requested = which

    def update(self, delta_time: float, active_vehicles: List[Vehicle]) -> None:
        self.time_in_current_state += delta_time
        idx = self.current_phase_idx
        if idx in _GREEN_IDX:
            held = 0 if idx == _GREEN_IDX[0] else 1
            if self._requested != held and self.time_in_current_state >= self.min_green:
                self.current_phase_idx = _YELLOW_IDX[held]
                self.time_in_current_state = 0.0
                self.switches += 1
        elif self.time_in_current_state >= self.current_phase.duration:
            self.time_in_current_state -= self.current_phase.duration
            if idx in _YELLOW_IDX:
                self.current_phase_idx = _RED_IDX[_YELLOW_IDX.index(idx)]
            else:
                # Out of the all-red: whichever green is wanted now.
                self.current_phase_idx = _GREEN_IDX[self._requested]
                self.time_in_current_state = 0.0
        self._apply_signals()

    def get_state(self) -> Dict[str, Any]:
        state = super().get_state()
        state["signalControl"] = "external"
        state["requestedGreen"] = self._requested
        return state
