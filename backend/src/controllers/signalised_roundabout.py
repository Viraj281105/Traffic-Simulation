"""Signalised roundabout controller (V3.0 W2 S4/S5).

Composes RoundaboutController with MeteringPhaseCursor, MeteredEntryGate,
SpillbackGuard, and QueueCap (SR-01, SR-02, SR-06, SR-11, SR-12, SR-13;
ADR-014; D-W2-1, D-W2-3, D-W2-4, D-W2-5, D-W2-6).

Composition design:
- Does NOT subclass RoundaboutController (SR-01).
- Owns an instance of RoundaboutController, injecting MeteredEntryGate as its
  entry_gate extension point.
- Owns MeteringPhaseCursor, advancing it with the simulation timestep.
- Owns SpillbackGuard, enforcing ring sector spillback holds bounded by maxHold.
- Owns QueueCap, triggering early green termination while protecting minGreen.
- Exposes vehicle_stop_limits from the inner roundabout, preserving two-lane
  exit-zone arbitration under composition (hazard H13).
- Exposes signals_state() returning per-direction colors (metered arms real
  colors, unmetered arms green per D-W2-6; arms in spillback hold are red).
"""

from __future__ import annotations

from typing import Any, Dict, List

from src.controllers.base import BaseController
from src.controllers.entry_metering import (
    EntryMeteringPlan,
    MeteredEntryGate,
    MeteringPhaseCursor,
    QueueCap,
    SpillbackGuard,
    build_metering_plan,
)
from src.controllers.roundabout import RoundaboutController
from src.core.enums import Direction
from src.roads.network import RoadNetwork
from src.vehicles.vehicle import Vehicle


class SignalisedRoundaboutController(BaseController):
    """Controls a signalised roundabout via composition over RoundaboutController.

    Owns a RoundaboutController and a MeteringPhaseCursor, connecting them
    via MeteredEntryGate, SpillbackGuard, and QueueCap. Does not subclass
    RoundaboutController.
    """

    def __init__(self, config: Dict[str, Any], network: RoadNetwork) -> None:
        self.config: Dict[str, Any] = config
        self.network: RoadNetwork = network

        self.plan: EntryMeteringPlan = build_metering_plan(config)
        self.cursor: MeteringPhaseCursor = MeteringPhaseCursor(self.plan)
        self.gate: MeteredEntryGate = MeteredEntryGate(self.cursor)
        self.spillback_guard: SpillbackGuard = SpillbackGuard(self.plan, self.network)
        self.queue_cap: QueueCap = QueueCap(self.plan, self.network)

        # The inner RoundaboutController is composed, receiving our metered gate
        self.roundabout: RoundaboutController = RoundaboutController(
            config, network, entry_gate=self.gate
        )

    def reset(self) -> None:
        """Reset cursor, gate, spillback guard, and the inner roundabout."""
        self.cursor.reset()
        self.gate.reset()
        self.spillback_guard.reset()
        self.roundabout.reset()

    def update(self, delta_time: float, active_vehicles: List[Vehicle]) -> None:
        """Advance cursor, evaluate queue cap & spillback guard, update gate events, and tick inner roundabout."""
        self.cursor.advance(delta_time)
        now = self.roundabout.time_in_current_state + delta_time

        # 1. Queue cap check (D-W2-4): triggers early green termination if min_green satisfied
        qc_arm = self.queue_cap.check_and_trigger(self.cursor, active_vehicles)
        if qc_arm is not None:
            self.gate.record_queue_cap_event(qc_arm, now)

        # 2. Spillback guard check (D-W2-5, D-W2-3): holds green arms red when downstream ring blocked
        held_arms = self.spillback_guard.update(
            self.cursor, delta_time, active_vehicles
        )
        self.gate.set_spillback_holds(held_arms)

        # 3. Gate transition updates
        self.gate.update(now)

        # 4. Composed inner roundabout update
        self.roundabout.update(delta_time, active_vehicles)

    def signals_state(self) -> Dict[Direction, str]:
        """Current per-direction signal colours for MetricCollector and reproduction (D-W2-6)."""
        colors = self.cursor.all_colors()
        for d in self.gate.spillback_holds:
            colors[d] = "red"
        return colors

    @property
    def vehicle_stop_limits(self) -> Dict[str, float]:
        """Expose inner roundabout's vehicle_stop_limits for V1.4 exit zones (H13)."""
        return self.roundabout.vehicle_stop_limits

    @property
    def time_in_current_state(self) -> float:
        return self.roundabout.time_in_current_state

    def update_active_vehicles_ref(self, active_vehicles: List[Vehicle]) -> None:
        self.roundabout.update_active_vehicles_ref(active_vehicles)

    def get_state(self) -> Dict[str, Any]:
        """Return combined controller state formatted for snapshot schema."""
        state = self.roundabout.get_state()
        state["entryControl"] = "metered_entry"
        signals = self.signals_state()
        state["metering"] = {
            "currentPhase": self.cursor.current_phase.name,
            "color": self.cursor.current_phase.color,
            "timeRemaining": round(self.cursor.phase_time_remaining, 2),
            "cycleNumber": self.cursor.cycle_number,
            "cycleProgress": round(self.cursor.cycle_progress, 4),
            "arms": [
                {
                    "direction": d.value,
                    "metered": self.cursor.is_metered(d),
                    "color": signals[d],
                    "reason": self.gate.get_arm_reason(d),
                }
                for d in Direction
            ],
            "decisions": dict(self.gate.decision_counts),
            "recentDecisions": list(self.gate.recent_decisions),
        }
        return state

    def __getattr__(self, name: str) -> Any:
        """Delegate any unhandled attribute accesses to the inner roundabout controller."""
        return getattr(self.roundabout, name)
