"""Cursor control over a fixed-time signal plan.

:class:`PhaseDriver` is the only place that moves the wrapped controller's phase
cursor. It never builds a signal state of its own: it sets the cursor and lets the
wrapped controller's own ``_apply_signals`` put the plan's phase on the lanes, so
the colours, virtual stop lines and yellow dilemma-zone behaviour are exactly
the plan's. Every phase it jumps to is a phase of the plan, so the plan's
yellow and all-red durations are always served in full.
"""

from __future__ import annotations

from typing import Callable, List, Optional, Tuple

from src.controllers.fixed_time_signal import FixedTimeSignalController, Phase
from src.core.enums import Direction, TurnIntent

NextSelector = Callable[[int], int]


class PhaseDriver:
    def __init__(self, base: FixedTimeSignalController) -> None:
        if type(base) is not FixedTimeSignalController:
            raise ValueError(
                "priority works on a fixed-time signal plan; adaptive and "
                "roundabout controllers are not supported"
            )
        self.base = base

    # -- reading ---------------------------------------------------------

    @property
    def phases(self) -> List[Phase]:
        return self.base.phases

    @property
    def index(self) -> int:
        return self.base.current_phase_idx

    @property
    def phase(self) -> Phase:
        return self.base.current_phase

    @property
    def elapsed(self) -> float:
        return self.base.time_in_current_state

    @property
    def remaining(self) -> float:
        return self.base.phase_time_remaining

    def is_green(self, idx: Optional[int] = None) -> bool:
        return self.phases[self.index if idx is None else idx].color == "green"

    def serves(self, idx: int, direction: Direction, turn: TurnIntent) -> bool:
        phase = self.phases[idx]
        return (
            phase.color == "green"
            and direction in phase.directions
            and turn in phase.allowed_turns
        )

    def find_green(self, direction: Direction, turn: TurnIntent) -> Optional[int]:
        """The next green phase (from the cursor, cyclically) that releases the movement."""
        n = len(self.phases)
        for step in range(n):
            idx = (self.index + step) % n
            if self.serves(idx, direction, turn):
                return idx
        return None

    def next_green(
        self, after: int, exclude: Optional[Tuple[Direction, ...]] = None
    ) -> Optional[int]:
        """First green phase after ``after`` whose directions differ from ``exclude``."""
        n = len(self.phases)
        for step in range(1, n + 1):
            idx = (after + step) % n
            phase = self.phases[idx]
            if phase.color == "green" and (
                exclude is None or phase.directions != exclude
            ):
                return idx
        return None

    def clearance_start(self, green_idx: int) -> Optional[int]:
        """The first yellow or red phase after a green block, i.e. where the
        plan begins to clear that green. None if another green follows
        directly (the plan has no clearance there)."""
        n = len(self.phases)
        directions = self.phases[green_idx].directions
        for step in range(1, n + 1):
            idx = (green_idx + step) % n
            phase = self.phases[idx]
            if phase.color == "green" and phase.directions == directions:
                continue
            return idx if phase.color != "green" else None
        return None

    # -- moving ----------------------------------------------------------

    def jump(self, idx: int) -> None:
        """Enter phase ``idx`` now, from its start."""
        old = self.base.current_phase_idx
        self.base.current_phase_idx = idx
        self.base.time_in_current_state = 0.0
        if idx < old:
            self.base.cycle_number += 1
        self.base._apply_signals()

    def advance(self, dt: float, select: Optional[NextSelector] = None) -> None:
        """Advance the plan by ``dt`` exactly as ``FixedTimeSignalController.update``
        does, except that the phase entered when one ends is ``select(old)``."""
        base = self.base
        base.time_in_current_state += dt
        n = len(self.phases)
        for _ in range(n):
            phase = base.current_phase
            if base.time_in_current_state < phase.duration:
                break
            base.time_in_current_state -= phase.duration
            old = base.current_phase_idx
            new = (old + 1) % n if select is None else select(old)
            base.current_phase_idx = new
            if new < old:
                base.cycle_number += 1
        base._apply_signals()

    def skip_ahead(self, seconds: float) -> None:
        """Shorten the current phase by ``seconds`` (never past its end)."""
        base = self.base
        base.time_in_current_state = min(
            base.time_in_current_state + max(0.0, seconds),
            max(0.0, base.current_phase.duration - 1e-6),
        )
