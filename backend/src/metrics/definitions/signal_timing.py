"""How a signal used its green time (V1.3), fixed-time and adaptive alike.

Measured, post-warm-up, from the controller's own phase state and the shared
stop-line detection (controllers/signal_detection.py), with one detection
distance for both kinds of signal so they are measured identically. Nothing
here feeds back into the simulation.

* ``phaseChanges`` -- greens started (a change to a green phase).
* ``greenSeconds`` -- time any phase was green.
* ``averageGreenDuration`` -- mean length of the greens that ended after
  warm-up (a green still running at the end is not counted; None if none).
* ``unusedGreenSeconds`` -- green time with nobody detected on the lanes the
  green releases while vehicles were detected waiting on another phase: time
  the junction held a green for no one while someone else waited.
  A green resting with nobody waiting anywhere is not counted.
  Presence, not passage, decides "nobody": a vehicle standing at a green
  (a left-turner yielding to oncoming traffic) is using it.
* ``greenUtilisation`` -- 1 - unusedGreenSeconds / greenSeconds (None before
  any green time).
* ``signalControl`` -- ``fixed_time`` or ``adaptive``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional

from src.controllers.signal_detection import StopLineDetection

if TYPE_CHECKING:
    from src.controllers.fixed_time_signal import FixedTimeSignalController

# Detection used to *measure* signals that have no detectors of their own
# (fixed-time); the adaptive default, so both are measured the same way.
MEASUREMENT_DETECTION_DISTANCE = 30.0


class SignalTimingTracker:
    def __init__(self, controller: "FixedTimeSignalController") -> None:
        self.controller = controller
        self.signal_control: str = getattr(controller, "SIGNAL_CONTROL", "fixed_time")
        self.detection = StopLineDetection(controller, MEASUREMENT_DETECTION_DISTANCE)
        self.phase_changes = 0
        self.green_seconds = 0.0
        self.unused_green_seconds = 0.0
        self._completed_greens = 0
        self._completed_green_seconds = 0.0
        self._last_idx: Optional[int] = None
        self._run_seconds = 0.0
        self._run_counted = False

    def update(self, dt: float) -> None:
        ctl = self.controller
        idx = ctl.current_phase_idx
        is_green = ctl.current_phase.color == "green"
        if idx != self._last_idx:
            if self._last_idx is not None and self._run_counted:
                self._completed_greens += 1
                self._completed_green_seconds += self._run_seconds
            self._run_seconds = 0.0
            # A green already running when measurement starts is not a change
            # the measurement saw, and its length is unknown.
            self._run_counted = is_green and self._last_idx is not None
            if self._run_counted:
                self.phase_changes += 1
            self._last_idx = idx
        if not is_green:
            return
        self._run_seconds += dt
        self.green_seconds += dt
        obs = self.detection.observe(idx)
        if obs.served == 0 and any(c > 0 for c in obs.calls.values()):
            self.unused_green_seconds += dt

    def summary(self) -> Dict[str, Any]:
        green = self.green_seconds
        return {
            "signalControl": self.signal_control,
            "phaseChanges": self.phase_changes,
            "greenSeconds": round(green, 1),
            "averageGreenDuration": (
                round(self._completed_green_seconds / self._completed_greens, 2)
                if self._completed_greens
                else None
            ),
            "unusedGreenSeconds": round(self.unused_green_seconds, 1),
            "greenUtilisation": (
                round(1.0 - self.unused_green_seconds / green, 4) if green > 0 else None
            ),
            "detectionDistance": MEASUREMENT_DETECTION_DISTANCE,
        }
