"""Vehicle-actuated (adaptive) signal control (V1.3).

The adaptive signal runs the same phase plan, lane heads and clearance phases
as :class:`FixedTimeSignalController`; it differs only in *when* a green ends.
Instead of a predetermined duration, each green is timed from what stop-line
detection observes, using the standard actuated-control rules (FHWA Signal
Timing Manual, ch. 5):

* **Minimum green** -- a green never ends before ``minGreen`` seconds, so a
  standing queue always gets moving and the signal cannot flicker.
* **Extension (gap-out)** -- after the minimum, the green is held while
  traffic keeps flowing: every vehicle passing through the last
  ``detectionDistance`` metres before the stop line, on a lane the phase
  releases, restarts a gap timer, and the green ends once nobody has passed
  for ``extensionStep`` seconds. A vehicle standing still in the zone does
  not extend the green (see ``signal_detection``).
* **Maximum green (max-out)** -- once a conflicting movement is waiting, the
  green can continue for at most ``maxGreen`` seconds, however busy it is.
* **Calls** -- a green only ends when another phase has demand: at least
  ``demandThreshold`` vehicles detected on lanes only that phase releases.
  With nobody waiting elsewhere the green rests (stays green).
* **Order** -- the next phase is the first phase *with* demand in the plan's
  own cyclic order; phases without demand are skipped. Cyclic order and the
  maximum green bound how long any waiting movement can be kept waiting.

Safety is unchanged from the fixed-time signal and stays authoritative:

* A green that ends always runs its stage's configured yellow and all-red
  phases at their configured durations before any other approach gets a
  green. The only direct green-to-green step is between greens of the *same*
  approach(es) within one stage (straight+right then protected left in the
  one-direction-at-a-time plan), which the fixed-time cycle takes as well.
* Signal heads are applied by the inherited ``_apply_signals``: the same
  virtual stop-line obstacles, lane by lane. Whether a released vehicle may
  actually enter is still decided by the conflict manager and the collision
  checks in ``VehiclePool``; this controller only decides *when* a phase
  changes.

Detection (``signal_detection.StopLineDetection``) reads each incoming lane's
own vehicle list, so a decision costs a few dozen comparisons per tick,
independent of how many vehicles are elsewhere in the network.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, List, Optional, Sequence, Tuple

from src.controllers.fixed_time_signal import FixedTimeSignalController, Phase
from src.controllers.signal_detection import StopLineDetection
from src.core.enums import Direction
from src.roads.network import RoadNetwork
from src.vehicles.vehicle import Vehicle

# Defaults (seconds / metres / vehicles). Chosen from common actuated-control
# practice for an urban through phase with stop-line presence detection: a
# 10 s minimum lets a standing queue start; 50 s maximum is in the 30-60 s
# range typical for a major through movement; a 2.5 s passage time over a
# 30 m zone ends the green once arrivals are sparser than about one every
# 4-5 s on the released lanes.
DEFAULT_ADAPTIVE: Dict[str, float] = {
    "minGreen": 10.0,
    "maxGreen": 50.0,
    "extensionStep": 2.5,
    "detectionDistance": 30.0,
    "demandThreshold": 1,
}

# Bounds shared with config_models.AdaptiveSignalSection and the schema.
ADAPTIVE_BOUNDS: Dict[str, Tuple[float, float]] = {
    "minGreen": (5.0, 60.0),
    "maxGreen": (10.0, 180.0),
    "extensionStep": (0.5, 10.0),
    "detectionDistance": (5.0, 200.0),
    "demandThreshold": (1, 20),
}

SIGNAL_CONTROL_MODES = ("fixed_time", "adaptive")

# Decisions kept for the live view and the Research Lab.
_RECENT_DECISIONS = 12


def resolve_adaptive_settings(ctrl_cfg: Dict[str, Any]) -> Dict[str, float]:
    """``controller.adaptive`` with every unset field at its default."""
    raw = ctrl_cfg.get("adaptive") or {}
    settings = dict(DEFAULT_ADAPTIVE)
    for key in DEFAULT_ADAPTIVE:
        value = raw.get(key)
        if value is not None:
            settings[key] = value
    return settings


def is_adaptive(config: Dict[str, Any]) -> bool:
    ctrl = config.get("controller") or {}
    return isinstance(ctrl, dict) and ctrl.get("signalControl") == "adaptive"


@dataclass(frozen=True)
class _Stage:
    """Greens of one approach group followed by their clearance phases."""

    greens: Tuple[int, ...]
    clearances: Tuple[int, ...]


def _split_stages(phases: Sequence[Phase]) -> List[_Stage]:
    """Group a cyclic phase list into stages: one or more consecutive greens,
    then every non-green phase up to the next green. Raises ValueError for a
    plan an adaptive signal cannot run safely (see ``adaptive_plan_errors``)."""
    n = len(phases)
    greens = [i for i, p in enumerate(phases) if p.color == "green"]
    if not greens:
        raise ValueError("the phase plan has no green phase")
    # A stage starts at a green whose predecessor (cyclically) is not green.
    starts = [i for i in greens if phases[(i - 1) % n].color != "green"]
    if not starts:
        raise ValueError(
            "the phase plan has no yellow or all-red phase between its greens"
        )
    stages: List[_Stage] = []
    for k, start in enumerate(starts):
        end = starts[(k + 1) % len(starts)]
        span = []
        i = start
        while True:
            span.append(i)
            i = (i + 1) % n
            if i == end:
                break
        stage_greens = tuple(j for j in span if phases[j].color == "green")
        clearances = tuple(j for j in span if phases[j].color != "green")
        stages.append(_Stage(stage_greens, clearances))
    for stage in stages:
        dirs = {phases[g].directions for g in stage.greens}
        if len(dirs) != 1:
            names = ", ".join(phases[g].name for g in stage.greens)
            raise ValueError(
                f"consecutive greens {names} release different approaches "
                "without a yellow and all-red between them"
            )
        green_dirs = set(next(iter(dirs)))
        yellows = [phases[c] for c in stage.clearances if phases[c].color == "yellow"]
        if not yellows or not any(green_dirs <= set(y.directions) for y in yellows):
            raise ValueError(
                f"green {phases[stage.greens[0]].name} is not followed by a "
                "yellow for the same approaches"
            )
        if not any(phases[c].name == "all_red" for c in stage.clearances):
            raise ValueError(
                f"green {phases[stage.greens[0]].name} is not followed by an "
                "all-red clearance"
            )
    return stages


def adaptive_plan_errors(phase_sequence: Optional[List[str]]) -> List[str]:
    """Why a configured ``phaseSequence`` cannot run adaptively (empty if it can).

    Every stage must end with a yellow covering its approaches and an all-red,
    and greens that follow each other directly must release the same
    approaches -- otherwise ending a green early would take a movement from
    green to red with no clearance. The one-direction-at-a-time default plan
    (no ``phaseSequence``) always qualifies.
    """
    if not phase_sequence:
        return []
    try:
        probe = FixedTimeSignalController.__new__(FixedTimeSignalController)
        probe.straight_right_duration = 30.0
        probe.yellow_duration = 4.0
        probe.all_red_duration = 2.0
        probe.ns_green_duration = None
        probe.ew_green_duration = None
        probe._uturn = ()
        phases = probe._build_phase_sequence_from_names(list(phase_sequence))
        _split_stages(phases)
    except ValueError as exc:
        return [f"controller.phaseSequence cannot run adaptively: {exc}"]
    return []


class AdaptiveSignalController(FixedTimeSignalController):
    """Fixed-time phase plan, green durations decided by detected demand."""

    SIGNAL_CONTROL = "adaptive"

    def __init__(self, config: Dict[str, Any], network: RoadNetwork) -> None:
        ctrl_cfg = config.get("controller") or {}
        settings = resolve_adaptive_settings(ctrl_cfg)
        self.min_green: float = float(settings["minGreen"])
        self.max_green: float = float(settings["maxGreen"])
        self.extension_step: float = float(settings["extensionStep"])
        self.detection_distance: float = float(settings["detectionDistance"])
        self.demand_threshold: int = int(settings["demandThreshold"])
        if not self.max_green > self.min_green:
            raise ValueError("adaptive maxGreen must be greater than minGreen")
        # FixedTimeSignalController.__init__ builds the plan and calls reset().
        super().__init__(config, network)
        self.stages: List[_Stage] = _split_stages(self.phases)
        self._stage_of: Dict[int, int] = {}
        for s, stage in enumerate(self.stages):
            for i in stage.greens + stage.clearances:
                self._stage_of[i] = s
        self.reset()

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    def reset(self) -> None:
        # The coordination offset is a fixed-time concept (config validation
        # rejects it for adaptive control); start the plan at its first phase.
        self.offset = 0.0
        self._clock: float = 0.0
        self._gap_timer: float = 0.0
        self._max_timer_start: Optional[float] = None
        self._target: Optional[int] = None
        self._extended: bool = False
        self._status: str = "min_green"
        self._served_count: int = 0
        self._calls: Dict[int, int] = {}
        self._detected: Dict[str, int] = {d.value: 0 for d in Direction}
        self.decisions: Dict[str, int] = {"gapOut": 0, "maxOut": 0}
        self.greens_started: int = 1
        self.greens_extended: int = 0
        self.phases_skipped: int = 0
        self.rest_seconds: float = 0.0
        self.recent_decisions: Deque[Dict[str, Any]] = deque(maxlen=_RECENT_DECISIONS)
        super().reset()
        # Built after the plan exists (FixedTimeSignalController.__init__
        # calls reset() once the phases are built).
        self._detection = StopLineDetection(self, self.detection_distance)

    def _observe(self) -> Tuple[int, int, Dict[int, int]]:
        """Vehicles detected and passing on the current green's lanes, and
        the calls of every other green phase (``StopLineDetection.observe``)."""
        obs = self._detection.observe(self.current_phase_idx)
        self._detected = obs.per_direction
        return obs.served, obs.passing, obs.calls

    # ------------------------------------------------------------------
    # Decisions
    # ------------------------------------------------------------------

    def update(self, delta_time: float, active_vehicles: List[Vehicle]) -> None:
        self._clock += delta_time
        self.time_in_current_state += delta_time
        phase = self.current_phase
        if phase.color == "green":
            self._update_green(delta_time)
        elif self.time_in_current_state >= phase.duration:
            # Clearance phases run their full configured duration.
            self.time_in_current_state -= phase.duration
            self._after_clearance()
        else:
            self._status = "clearance"
        self._apply_signals()

    def _update_green(self, delta_time: float) -> None:
        served, passing, calls = self._observe()
        self._served_count = served
        self._calls = calls
        waiting = {i: c for i, c in calls.items() if c >= self.demand_threshold}
        if passing > 0:
            self._gap_timer = 0.0
        else:
            self._gap_timer += delta_time
        t = self.time_in_current_state
        if waiting and self._max_timer_start is None:
            self._max_timer_start = max(0.0, t - delta_time)

        if t < self.min_green:
            self._status = "min_green"
            return
        if not waiting:
            # Nobody else to serve: keep the green (rest in green).
            self._status = "extending" if passing else "resting"
            if not passing:
                self.rest_seconds += delta_time
            return
        if self._gap_timer >= self.extension_step:
            self._terminate("gapOut", waiting)
        elif t - (self._max_timer_start or 0.0) >= self.max_green:
            self._terminate("maxOut", waiting)
        else:
            self._status = "extending"
            if not self._extended:
                self._extended = True
                self.greens_extended += 1

    def _order_after(self, idx: int) -> List[int]:
        """Green phases in cyclic plan order after ``idx`` (excluding it)."""
        n = len(self.phases)
        return [
            (idx + k) % n
            for k in range(1, n)
            if self.phases[(idx + k) % n].color == "green"
        ]

    def _terminate(self, reason: str, waiting: Dict[int, int]) -> None:
        current = self.current_phase_idx
        target = next(i for i in self._order_after(current) if i in waiting)
        stage = self.stages[self._stage_of[current]]
        later_in_stage = [g for g in stage.greens if g > current]
        same_stage = target in later_in_stage
        self.decisions[reason] += 1
        self.recent_decisions.append(
            {
                "time": round(self._clock, 1),
                "phase": self.phases[current].name,
                "decision": reason,
                "greenSeconds": round(self.time_in_current_state, 1),
                "next": self.phases[target].name,
                "waiting": int(waiting[target]),
            }
        )
        if same_stage:
            # Another green of the same approach(es): no clearance needed,
            # exactly as the fixed-time cycle steps straight from one to it.
            self.phases_skipped += later_in_stage.index(target)
            self._enter_green(target)
        else:
            self.phases_skipped += len(later_in_stage)
            self._target = target
            self.current_phase_idx = stage.clearances[0]
            self.time_in_current_state = 0.0
            self._status = "clearance"

    def _after_clearance(self) -> None:
        idx = self.current_phase_idx
        stage = self.stages[self._stage_of[idx]]
        pos = stage.clearances.index(idx)
        if pos + 1 < len(stage.clearances):
            self.current_phase_idx = stage.clearances[pos + 1]
            self._status = "clearance"
            return
        target = self._target
        if target is None:
            # A plan that starts in a clearance phase: its next green.
            target = self._order_after(idx)[0]
        self._target = None
        # Stages passed over without demand are skipped whole, clearance
        # included: a yellow is never shown to an approach that was red.
        next_stage = (self._stage_of[idx] + 1) % len(self.stages)
        skipped = 0
        s = next_stage
        while s != self._stage_of[target]:
            skipped += len(self.stages[s].greens)
            s = (s + 1) % len(self.stages)
        target_stage = self.stages[self._stage_of[target]]
        skipped += target_stage.greens.index(target)
        self.phases_skipped += skipped
        carry = self.time_in_current_state
        self._enter_green(target)
        self.time_in_current_state = carry

    def _enter_green(self, idx: int) -> None:
        if idx <= self.current_phase_idx:
            self.cycle_number += 1
        self.current_phase_idx = idx
        self.time_in_current_state = 0.0
        self._gap_timer = 0.0
        self._max_timer_start = None
        self._extended = False
        self._status = "min_green"
        self.greens_started += 1

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    @property
    def phase_time_remaining(self) -> float:
        """Upper bound on the current phase's remaining time.

        Clearance phases have a fixed duration. A green's end is decided by
        traffic: before the minimum the time to the minimum is reported;
        after it, the time to the maximum once someone is waiting, and 0
        while it rests with nobody waiting.
        """
        phase = self.current_phase
        t = self.time_in_current_state
        if phase.color != "green":
            return max(0.0, phase.duration - t)
        if t < self.min_green:
            return self.min_green - t
        if self._max_timer_start is None:
            return 0.0
        return max(0.0, self._max_timer_start + self.max_green - t)

    def get_state(self) -> Dict[str, Any]:
        state = super().get_state()
        phase = self.current_phase
        is_green = phase.color == "green"
        waiting = (
            sum(1 for c in self._calls.values() if c >= self.demand_threshold)
            if is_green
            else 0
        )
        state["signalControl"] = "adaptive"
        state["adaptive"] = {
            "status": self._status,
            "minGreen": self.min_green,
            "maxGreen": self.max_green,
            "extensionStep": self.extension_step,
            "detectionDistance": self.detection_distance,
            "demandThreshold": self.demand_threshold,
            "greenElapsed": round(self.time_in_current_state, 2) if is_green else 0.0,
            "gapTimer": round(min(self._gap_timer, self.extension_step), 2)
            if is_green
            else 0.0,
            "servedDemand": self._served_count if is_green else 0,
            "phasesWaiting": waiting,
            "detected": dict(self._detected),
            "nextPhase": self.phases[self._target].name
            if self._target is not None
            else None,
            "decisions": {
                "greens": self.greens_started,
                "gapOuts": self.decisions["gapOut"],
                "maxOuts": self.decisions["maxOut"],
                "greensExtended": self.greens_extended,
                "phasesSkipped": self.phases_skipped,
                "restSeconds": round(self.rest_seconds, 1),
            },
            "recentDecisions": list(self.recent_decisions),
        }
        return state
