"""Entry metering phase plan model, resolver, and cursor (W2 Step S3).

Implements the phase timing engine for signalised roundabouts (SR-08, SR-09,
SR-10, SR-19; strategy 13.3). Reuses the existing Phase descriptor from
FixedTimeSignalController. For each configured plan phase, expands into:
    green (scheduled duration) -> yellow -> allRed (clearance)
with carry-over arithmetic matching FixedTimeSignalController.update and
zero randomness.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Set, Tuple

from src.controllers.fixed_time_signal import Phase
from src.core.enums import Direction, TurnIntent

DEFAULT_YELLOW: float = 3.0
DEFAULT_ALL_RED: float = 2.0
DEFAULT_OFFSET: float = 0.0

# Precedent bounds from Section 5.3 of the V3 W2 engineering plan:
METERING_BOUNDS: Dict[str, Tuple[float, float]] = {
    "green": (5.0, 120.0),  # 5 < x <= 120 s
    "minGreen": (5.0, 60.0),  # 5 <= x <= 60 s
    "maxGreen": (10.0, 180.0),  # 10 <= x <= 180 s
    "yellow": (2.0, 8.0),  # 2 < x <= 8 s
    "allRed": (0.0, 5.0),  # 0 <= x <= 5 s
    "stoppedThreshold": (1.0, 20.0),
    "maxHold": (0.0, 60.0),
    "queueCapVehicles": (1.0, 50.0),
}

_ALL_TURNS: Tuple[TurnIntent, ...] = (
    TurnIntent.LEFT,
    TurnIntent.STRAIGHT,
    TurnIntent.RIGHT,
    TurnIntent.UTURN,
)


@dataclass(frozen=True)
class MeteredPhaseSpec:
    """Specification of one green phase in an entry-metering plan.

    Attributes:
        entries: Approaches released during this green phase.
        green: Scheduled green duration in seconds.
        min_green: Minimum green duration (queue-cap cannot cut green below this).
        max_green: Maximum green duration (upper bound for extensions).
    """

    entries: Tuple[Direction, ...]
    green: float
    min_green: float
    max_green: float

    def __post_init__(self) -> None:
        if not self.entries:
            raise ValueError("MeteredPhaseSpec must have at least one entry")
        if self.green <= 0:
            raise ValueError(f"green duration must be positive, got {self.green}")
        if self.min_green <= 0:
            raise ValueError(f"min_green must be positive, got {self.min_green}")
        if self.max_green <= 0:
            raise ValueError(f"max_green must be positive, got {self.max_green}")
        if self.min_green > self.max_green:
            raise ValueError(
                f"min_green ({self.min_green}) cannot exceed max_green ({self.max_green})"
            )
        if self.green < self.min_green:
            raise ValueError(
                f"green ({self.green}) cannot be less than min_green ({self.min_green})"
            )
        if self.green > self.max_green:
            raise ValueError(
                f"green ({self.green}) cannot exceed max_green ({self.max_green})"
            )


@dataclass(frozen=True)
class SpillbackGuardConfig:
    """Downstream ring spillback guard parameters (SR-11, D-W2-5)."""

    enabled: bool = False
    stopped_threshold: int = 2
    max_hold: float = 10.0


@dataclass(frozen=True)
class QueueCapConfig:
    """Approach standing-queue cap parameters (SR-12, D-W2-4)."""

    enabled: bool = False
    vehicles: int = 8


@dataclass(frozen=True)
class EntryMeteringPlan:
    """Resolved cyclic phase plan for signalised roundabout entry metering.

    Attributes:
        phases: Sequence of Phase descriptors (green -> yellow -> all-red).
        specs: Input MeteredPhaseSpec objects for each green phase.
        phase_to_spec_idx: Maps each phase index in `phases` to its spec index.
        metered_entries: Set of all Direction entries controlled by this plan.
        yellow: Yellow duration applied to each phase.
        all_red: All-red clearance duration applied to each phase.
        offset: Initial offset applied at reset.
        cycle_duration: Exact sum of all phase durations in the cycle.
        spillback_guard: Spillback guard configuration.
        queue_cap: Queue cap configuration.
    """

    phases: Tuple[Phase, ...]
    specs: Tuple[MeteredPhaseSpec, ...]
    phase_to_spec_idx: Tuple[int, ...]
    metered_entries: FrozenSet[Direction]
    yellow: float
    all_red: float
    offset: float
    cycle_duration: float
    spillback_guard: SpillbackGuardConfig = field(default_factory=SpillbackGuardConfig)
    queue_cap: QueueCapConfig = field(default_factory=QueueCapConfig)

    def planned_red_for(self, approach: Direction) -> float:
        """Total scheduled red time per cycle for an approach."""
        if approach not in self.metered_entries:
            return 0.0
        return sum(p.duration for p in self.phases if approach not in p.directions)

    def planned_green_for(self, approach: Direction) -> float:
        """Total scheduled green time per cycle for an approach."""
        if approach not in self.metered_entries:
            return self.cycle_duration
        return sum(
            p.duration
            for p in self.phases
            if approach in p.directions and p.color == "green"
        )


def _parse_direction(val: Any) -> Direction:
    if isinstance(val, Direction):
        return val
    if isinstance(val, str):
        try:
            return Direction(val.strip().lower())
        except ValueError:
            raise ValueError(f"cannot parse {val!r} as Direction") from None
    raise ValueError(f"cannot parse {val!r} as Direction")


def build_metering_plan(config: Dict[str, Any]) -> EntryMeteringPlan:
    """Build an EntryMeteringPlan from raw dictionary configuration.

    Accepts full scenario config, a controller section, or the entryMetering dict.
    """
    if "entryMetering" in config and isinstance(config["entryMetering"], dict):
        cfg = config["entryMetering"]
    elif (
        "controller" in config
        and isinstance(config["controller"], dict)
        and "entryMetering" in config["controller"]
        and isinstance(config["controller"]["entryMetering"], dict)
    ):
        cfg = config["controller"]["entryMetering"]
    else:
        cfg = config

    raw_phases = cfg.get("phases")
    if not isinstance(raw_phases, list) or not raw_phases:
        raise ValueError("entryMetering must define a non-empty list of phases")

    yellow = float(cfg.get("yellow", DEFAULT_YELLOW))
    if yellow < 0:
        raise ValueError(f"yellow duration cannot be negative, got {yellow}")

    all_red_val = cfg.get("allRed")
    if all_red_val is None:
        all_red_val = cfg.get("all_red", DEFAULT_ALL_RED)
    all_red = float(all_red_val)
    if all_red < 0:
        raise ValueError(f"allRed duration cannot be negative, got {all_red}")

    offset = float(cfg.get("offset", DEFAULT_OFFSET))
    if offset < 0:
        raise ValueError(f"offset cannot be negative, got {offset}")

    specs: List[MeteredPhaseSpec] = []
    for p_idx, p in enumerate(raw_phases):
        if not isinstance(p, dict):
            raise ValueError(f"phase at index {p_idx} must be a dictionary")
        raw_entries = p.get("entries")
        if not isinstance(raw_entries, (list, tuple)) or not raw_entries:
            raise ValueError(f"phase at index {p_idx} must have non-empty entries list")

        entries_list: List[Direction] = []
        seen_in_phase: Set[Direction] = set()
        for e in raw_entries:
            d = _parse_direction(e)
            if d in seen_in_phase:
                raise ValueError(f"duplicate entry '{d.value}' in phase {p_idx}")
            seen_in_phase.add(d)
            entries_list.append(d)

        green = float(p.get("green", 0))
        if green <= 0:
            raise ValueError(f"phase {p_idx} green must be positive, got {green}")

        min_green_val = p.get("minGreen", p.get("min_green"))
        min_green = (
            float(min_green_val) if min_green_val is not None else min(green, 8.0)
        )

        max_green_val = p.get("maxGreen", p.get("max_green"))
        max_green = (
            float(max_green_val) if max_green_val is not None else max(green, 40.0)
        )

        specs.append(
            MeteredPhaseSpec(
                entries=tuple(entries_list),
                green=green,
                min_green=min_green,
                max_green=max_green,
            )
        )

    phases: List[Phase] = []
    phase_to_spec_idx: List[int] = []

    for s_idx, spec in enumerate(specs):
        prefix = "_".join(d.value for d in spec.entries)

        # 1. Green
        phases.append(
            Phase(
                name=f"{prefix}_green",
                directions=spec.entries,
                allowed_turns=_ALL_TURNS,
                duration=spec.green,
                color="green",
            )
        )
        phase_to_spec_idx.append(s_idx)

        # 2. Yellow
        if yellow > 0:
            phases.append(
                Phase(
                    name=f"{prefix}_yellow",
                    directions=spec.entries,
                    allowed_turns=_ALL_TURNS,
                    duration=yellow,
                    color="yellow",
                )
            )
            phase_to_spec_idx.append(s_idx)

        # 3. All-Red clearance
        if all_red > 0:
            phases.append(
                Phase(
                    name=f"{prefix}_all_red",
                    directions=(),
                    allowed_turns=(),
                    duration=all_red,
                    color="red",
                )
            )
            phase_to_spec_idx.append(s_idx)

    cycle_duration = sum(p.duration for p in phases)
    metered_entries = frozenset(d for spec in specs for d in spec.entries)

    # Spillback guard config
    sg_raw = cfg.get("spillbackGuard") or {}
    spillback_guard = SpillbackGuardConfig(
        enabled=bool(sg_raw.get("enabled", False)),
        stopped_threshold=int(sg_raw.get("stoppedThreshold", 2)),
        max_hold=float(sg_raw.get("maxHold", 10.0)),
    )

    # Queue cap config
    qc_raw = cfg.get("queueCap") or {}
    queue_cap = QueueCapConfig(
        enabled=bool(qc_raw.get("enabled", False)),
        vehicles=int(qc_raw.get("vehicles", 8)),
    )

    return EntryMeteringPlan(
        phases=tuple(phases),
        specs=tuple(specs),
        phase_to_spec_idx=tuple(phase_to_spec_idx),
        metered_entries=metered_entries,
        yellow=yellow,
        all_red=all_red,
        offset=offset,
        cycle_duration=cycle_duration,
        spillback_guard=spillback_guard,
        queue_cap=queue_cap,
    )


class MeteringPhaseCursor:
    """Deterministic phase cursor over an EntryMeteringPlan.

    Advances the phase cycle with carry-over timing arithmetic identical to
    FixedTimeSignalController.update, supporting offsets, early termination
    (queue-cap), and per-approach color lookup. Zero randomness.
    """

    def __init__(self, plan: EntryMeteringPlan) -> None:
        if not plan.phases:
            raise ValueError("EntryMeteringPlan has no phases")
        self.plan = plan
        self.phases = plan.phases
        self.current_phase_idx: int = 0
        self.time_in_current_state: float = 0.0
        self.cycle_number: int = 0
        self.reset()

    def reset(self) -> None:
        """Reset cursor to t=0, applying configured offset."""
        self.current_phase_idx = 0
        self.time_in_current_state = 0.0
        self.cycle_number = 0
        if self.plan.offset > 0 and self.plan.cycle_duration > 0:
            self._advance_by(self.plan.offset % self.plan.cycle_duration)

    def _advance_by(self, seconds: float) -> None:
        """Advance cursor by `seconds` using carry-over arithmetic."""
        remaining = seconds
        while remaining > 0:
            phase = self.current_phase
            time_left = phase.duration - self.time_in_current_state
            if remaining < time_left:
                self.time_in_current_state += remaining
                remaining = 0.0
            else:
                remaining -= time_left
                self.time_in_current_state = 0.0
                old_idx = self.current_phase_idx
                self.current_phase_idx = (self.current_phase_idx + 1) % len(self.phases)
                if self.current_phase_idx < old_idx:
                    self.cycle_number += 1

    def advance(self, delta_time: float) -> None:
        """Advance cursor by delta_time."""
        if delta_time < 0:
            raise ValueError(f"delta_time must be non-negative, got {delta_time}")
        if delta_time == 0:
            return
        self.time_in_current_state += delta_time
        while (
            self.current_phase.duration > 0
            and self.time_in_current_state >= self.current_phase.duration
        ):
            self.time_in_current_state -= self.current_phase.duration
            old_idx = self.current_phase_idx
            self.current_phase_idx = (self.current_phase_idx + 1) % len(self.phases)
            if self.current_phase_idx < old_idx:
                self.cycle_number += 1

    def end_green_early(self) -> bool:
        """End the active green phase early (for queue cap, D-W2-4).

        Transitions immediately to the subsequent yellow phase. Returns True
        if a green phase was ended early, False otherwise.
        """
        if self.current_phase.color != "green":
            return False
        self.time_in_current_state = 0.0
        old_idx = self.current_phase_idx
        self.current_phase_idx = (self.current_phase_idx + 1) % len(self.phases)
        if self.current_phase_idx < old_idx:
            self.cycle_number += 1
        return True

    @property
    def current_phase(self) -> Phase:
        return self.phases[self.current_phase_idx]

    @property
    def current_spec_idx(self) -> int:
        return self.plan.phase_to_spec_idx[self.current_phase_idx]

    @property
    def current_spec(self) -> MeteredPhaseSpec:
        return self.plan.specs[self.current_spec_idx]

    @property
    def phase_time_remaining(self) -> float:
        return max(0.0, self.current_phase.duration - self.time_in_current_state)

    @property
    def cycle_time_elapsed(self) -> float:
        """Elapsed time within the current cycle."""
        elapsed = sum(self.phases[i].duration for i in range(self.current_phase_idx))
        return elapsed + self.time_in_current_state

    @property
    def cycle_progress(self) -> float:
        """Fraction of current cycle completed in [0.0, 1.0)."""
        if self.plan.cycle_duration <= 0:
            return 0.0
        return (
            self.cycle_time_elapsed % self.plan.cycle_duration
        ) / self.plan.cycle_duration

    def get_color(self, approach: Direction) -> str:
        """Return signal colour ('green', 'yellow', or 'red') for approach.

        Unmetered arms are always 'green' (D-W2-6).
        """
        if approach not in self.plan.metered_entries:
            return "green"
        if approach in self.current_phase.directions:
            return self.current_phase.color
        return "red"

    def is_metered(self, approach: Direction) -> bool:
        return approach in self.plan.metered_entries

    def all_colors(self) -> Dict[Direction, str]:
        """Projected signal colours for all 4 compass directions."""
        return {d: self.get_color(d) for d in Direction}
