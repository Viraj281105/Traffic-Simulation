"""Entry metering phase plan model, resolver, and cursor (W2 Step S3).

Implements the phase timing engine for signalised roundabouts (SR-08, SR-09,
SR-10, SR-19; strategy 13.3). Reuses the existing Phase descriptor from
FixedTimeSignalController. For each configured plan phase, expands into:
    green (scheduled duration) -> yellow -> allRed (clearance)
with carry-over arithmetic matching FixedTimeSignalController.update and
zero randomness.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple

from src.controllers.entry_gate import OPEN, GateDecision, GateReason
from src.controllers.fixed_time_signal import Phase
from src.core.enums import Direction, TurnIntent
from src.roads.junction_geometry import SLOT_BEARING
from src.roads.network import RoadNetwork
from src.vehicles.router import commits_through_yellow
from src.vehicles.vehicle import Vehicle
from src.vehicles.virtual_obstacle import VirtualObstacle

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
    """Downstream ring spillback guard parameters (SR-11, D-W2-5, D-W2-3)."""

    enabled: bool = False
    stopped_threshold: int = 2
    max_hold: float = 10.0

    def __post_init__(self) -> None:
        if self.stopped_threshold < 1 or self.stopped_threshold > 20:
            raise ValueError(
                f"stopped_threshold must be in 1..20, got {self.stopped_threshold}"
            )
        if self.max_hold < 0.0 or self.max_hold > 60.0:
            raise ValueError(f"max_hold must be in 0..60, got {self.max_hold}")


@dataclass(frozen=True)
class QueueCapConfig:
    """Approach standing-queue cap parameters (SR-12, D-W2-4)."""

    enabled: bool = False
    vehicles: int = 8

    def __post_init__(self) -> None:
        if self.vehicles < 1 or self.vehicles > 50:
            raise ValueError(f"vehicles must be in 1..50, got {self.vehicles}")


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


class MeteredEntryGate:
    """EntryGate protocol implementation for metered roundabout entries (SR-02, SR-06, SR-13).

    Controls vehicle entry release onto the roundabout. Red and yellow lights
    deny entry; on yellow, vehicles in the dilemma zone commit through yellow
    (commits_through_yellow) and are latched until they leave the approach lane.
    Arms held by the spillback guard deny entry with reason 'ring_spillback_hold'.
    Unmetered entries are always open.
    """

    def __init__(self, cursor: MeteringPhaseCursor) -> None:
        self.cursor: MeteringPhaseCursor = cursor
        # vehicle_id -> lane_id mapping for vehicles that committed through yellow
        self._yellow_latched: Dict[str, str] = {}
        # Arms held in red by the spillback guard
        self._spillback_holds: Set[Direction] = set()
        # Track gate state transitions per direction: direction -> reason (or None if open)
        self._last_state: Dict[Direction, Optional[GateReason]] = {}
        self.decision_counts: Dict[str, int] = {
            "red": 0,
            "yellow": 0,
            "ring_spillback_hold": 0,
            "queue_cap": 0,
            "yellow_commit": 0,
            "spillback_exhausted": 0,
            "entry_denials": 0,
        }
        self.denial_counts: Dict[str, int] = {
            "red": 0,
            "yellow": 0,
            "ring_spillback_hold": 0,
        }
        self.recent_decisions: deque[Dict[str, Any]] = deque(maxlen=50)

    def reset(self) -> None:
        """Reset gate state, latched vehicles, and decision counters."""
        self._yellow_latched.clear()
        self._spillback_holds.clear()
        self._last_state.clear()
        for k in self.decision_counts:
            self.decision_counts[k] = 0
        for k in self.denial_counts:
            self.denial_counts[k] = 0
        self.recent_decisions.clear()

    def set_spillback_holds(self, held_arms: Set[Direction]) -> None:
        """Set of arms currently held in red by the spillback guard."""
        self._spillback_holds = set(held_arms)

    @property
    def spillback_holds(self) -> Set[Direction]:
        return self._spillback_holds

    def record_queue_cap_event(self, arm: Direction, now: float) -> None:
        """Record an early-green termination triggered by queue-cap on arm."""
        self.decision_counts["queue_cap"] = self.decision_counts.get("queue_cap", 0) + 1
        self.recent_decisions.append(
            {
                "time": round(now, 2),
                "arm": arm.value,
                "reason": "queue_cap",
                "state": "triggered",
            }
        )

    def record_yellow_commit(self, arm: Direction, vehicle_id: str, now: float) -> None:
        """Record a vehicle commitment through yellow."""
        self.decision_counts["yellow_commit"] = (
            self.decision_counts.get("yellow_commit", 0) + 1
        )
        self.recent_decisions.append(
            {
                "time": round(now, 2),
                "arm": arm.value,
                "reason": "yellow_commit",
                "state": "committed",
                "vehicle": vehicle_id,
            }
        )

    def record_spillback_exhausted_event(self, arm: Direction, now: float) -> None:
        """Record budget exhaustion for an arm under spillback guard."""
        self.decision_counts["spillback_exhausted"] = (
            self.decision_counts.get("spillback_exhausted", 0) + 1
        )
        self.recent_decisions.append(
            {
                "time": round(now, 2),
                "arm": arm.value,
                "reason": "spillback_exhausted",
                "state": "released",
            }
        )

    def record_entry_denial(self, arm: Direction, reason: GateReason) -> None:
        """Record entry denial event count for an approach."""
        self.denial_counts[reason] = self.denial_counts.get(reason, 0) + 1
        self.decision_counts["entry_denials"] = (
            self.decision_counts.get("entry_denials", 0) + 1
        )

    def update(self, now: float) -> None:
        """Update transition events and prune stale latches at simulation time `now`."""
        for d in self.cursor.plan.metered_entries:
            reason = self.get_arm_reason(d)
            prev_reason = self._last_state.get(d)
            if reason != prev_reason:
                self._last_state[d] = reason
                if reason is not None:
                    self.decision_counts[reason] = (
                        self.decision_counts.get(reason, 0) + 1
                    )
                    self.recent_decisions.append(
                        {
                            "time": round(now, 2),
                            "arm": d.value,
                            "reason": reason,
                            "state": "closed",
                        }
                    )
                else:
                    self.recent_decisions.append(
                        {
                            "time": round(now, 2),
                            "arm": d.value,
                            "reason": "open",
                            "state": "open",
                        }
                    )

    def get_arm_reason(self, approach: Direction) -> Optional[GateReason]:
        """Return the current gate closure reason for an approach, or None if open."""
        if approach not in self.cursor.plan.metered_entries:
            return None
        if approach in self._spillback_holds:
            return "ring_spillback_hold"
        color = self.cursor.get_color(approach)
        if color == "yellow":
            return "yellow"
        if color == "red":
            return "red"
        return None

    def allows(self, approach: Direction, lane: Any, now: float) -> GateDecision:
        """Consulted once per entry lane per tick after the roundabout's yield rules."""
        if approach not in self.cursor.plan.metered_entries:
            return OPEN

        if approach in self._spillback_holds:
            self.record_entry_denial(approach, "ring_spillback_hold")
            return GateDecision(open=False, reason="ring_spillback_hold")

        color = self.cursor.get_color(approach)
        if color == "green":
            return OPEN

        # Prune vehicles latched on this lane that have left it
        lane_vehicles = lane.get_vehicles()
        active_ids = {v.vehicle_id for v in lane_vehicles}
        for vid in list(self._yellow_latched.keys()):
            if self._yellow_latched[vid] == lane.lane_id and vid not in active_ids:
                del self._yellow_latched[vid]

        head = max(lane_vehicles, key=lambda hv: hv.position, default=None)

        if color == "yellow":
            if head is not None:
                if head.vehicle_id in self._yellow_latched:
                    return OPEN
                obs = VirtualObstacle(position=lane.length, is_yellow=True)
                if commits_through_yellow(head, obs):
                    self._yellow_latched[head.vehicle_id] = lane.lane_id
                    self.record_yellow_commit(approach, head.vehicle_id, now)
                    return OPEN
            self.record_entry_denial(approach, "yellow")
            return GateDecision(open=False, reason="yellow")

        # Red / all-red
        if head is not None and head.vehicle_id in self._yellow_latched:
            return OPEN

        self.record_entry_denial(approach, "red")
        return GateDecision(open=False, reason="red")


_SPILLBACK_STOPPED_SPEED: float = 2.0  # (m/s) _KEEP_CLEAR_SPEED from D-W2-5
_SPILLBACK_EXIT_STRETCH: float = 30.0  # (m) first stretch of exit lane
_QUEUE_CAP_STOPPED_SPEED: float = 2.0  # (m/s) stopped threshold for standing queue


class SpillbackGuard:
    """Downstream ring and exit spillback guard (SR-11, D-W2-5, D-W2-3).

    For each metered arm that would otherwise be green, counts stopped
    vehicles (speed < 2.0 m/s) in the ring sector from that entry to the
    next exit downstream, plus on the first stretch of that exit lane.
    When the count >= stopped_threshold, holds the arm red (ring_spillback_hold)
    for at most max_hold seconds per cycle.
    """

    def __init__(self, plan: EntryMeteringPlan, network: RoadNetwork) -> None:
        self.plan = plan
        self.network = network
        self.config: SpillbackGuardConfig = plan.spillback_guard
        self.cycle_hold_time: Dict[Direction, float] = {d: 0.0 for d in Direction}
        self.cumulative_hold_time: Dict[Direction, float] = {d: 0.0 for d in Direction}
        self.hold_activations: Dict[Direction, int] = {d: 0 for d in Direction}
        self.budget_exhaustions: Dict[Direction, int] = {d: 0 for d in Direction}
        self.exhausted_this_tick: Set[Direction] = set()
        self._currently_held: Set[Direction] = set()
        self._exhausted_arms: Set[Direction] = set()
        self._last_cycle_number: int = 0
        self._sector_cache: Dict[Direction, Tuple[float, float, Direction]] = {}
        self._init_sectors()

    def _init_sectors(self) -> None:
        """Precompute and cache geometry for the downstream ring sector of each metered arm."""
        present_dirs = [d for d in Direction if self._has_approach(d)]
        if not present_dirs:
            return

        # Measure Cartesian angles (where x=East, y=North) for all present arms
        arm_angles: Dict[Direction, float] = {}
        if hasattr(self.network, "geometry") and getattr(
            self.network.geometry, "arms", None
        ):
            for d in present_dirs:
                if d in self.network.geometry.arms:
                    ux, uy = self.network.geometry.arms[d].unit()
                    arm_angles[d] = math.atan2(uy, ux)

        if len(arm_angles) < len(present_dirs):
            for d in present_dirs:
                if d not in arm_angles:
                    b_rad = math.radians(SLOT_BEARING.get(d, 0.0))
                    # Compass bearing to Cartesian: x = sin(bearing), y = cos(bearing)
                    arm_angles[d] = math.atan2(math.cos(b_rad), math.sin(b_rad))

        for d in self.plan.metered_entries:
            if d not in arm_angles:
                continue
            theta_entry = arm_angles[d]

            # Find the next present downstream arm in counter-clockwise order
            best_diff = float("inf")
            next_exit = d
            for other_d in arm_angles:
                if other_d == d:
                    continue
                diff = (arm_angles[other_d] - theta_entry) % (2 * math.pi)
                if diff > 1e-4 and diff < best_diff:
                    best_diff = diff
                    next_exit = other_d

            sector_width = (arm_angles[next_exit] - theta_entry) % (2 * math.pi)
            self._sector_cache[d] = (theta_entry, sector_width, next_exit)

    def _has_approach(self, d: Direction) -> bool:
        try:
            self.network.get_incoming_approach(d)
            return True
        except KeyError:
            return False

    def reset(self) -> None:
        """Reset hold timers, cumulative accounting, and cycle tracker."""
        for d in Direction:
            self.cycle_hold_time[d] = 0.0
            self.cumulative_hold_time[d] = 0.0
            self.hold_activations[d] = 0
            self.budget_exhaustions[d] = 0
        self.exhausted_this_tick.clear()
        self._currently_held.clear()
        self._exhausted_arms.clear()
        self._last_cycle_number = 0

    def count_stopped_vehicles(
        self, approach: Direction, active_vehicles: List[Vehicle]
    ) -> int:
        """Count stopped vehicles (< 2.0 m/s) in the downstream ring sector and exit lane."""
        if approach not in self._sector_cache:
            return 0
        theta_entry, sector_width, next_exit = self._sector_cache[approach]
        count = 0

        # 1. Ring sector: circulating vehicles on connection lanes
        for v in active_vehicles:
            if v.lane is None:
                continue
            lane_id = v.lane.lane_id.lower()
            if not lane_id.startswith("conn"):
                continue
            if v.speed >= _SPILLBACK_STOPPED_SPEED:
                continue
            cx, cy = v.coords
            theta_v = math.atan2(cy, cx)
            # Check if within sector counter-clockwise with a small tolerance for entry/exit mouths
            angle = (theta_v - theta_entry + 0.1) % (2 * math.pi)
            if angle <= sector_width + 0.2:
                count += 1

        # 2. First stretch of next exit lane
        try:
            outgoing = self.network.get_outgoing_approach(next_exit)
            for lane in outgoing.get_lanes():
                for v in lane.get_vehicles():
                    if (
                        v.speed < _SPILLBACK_STOPPED_SPEED
                        and v.position <= _SPILLBACK_EXIT_STRETCH
                    ):
                        count += 1
        except KeyError:
            pass

        return count

    def update(
        self,
        cursor: MeteringPhaseCursor,
        delta_time: float,
        active_vehicles: List[Vehicle],
    ) -> Set[Direction]:
        """Update spillback state for all metered arms, returning the currently held set."""
        self.exhausted_this_tick.clear()
        if not self.config.enabled:
            self._currently_held.clear()
            return set()

        # Reset per-cycle hold budgets on cycle change
        if cursor.cycle_number != self._last_cycle_number:
            self._last_cycle_number = cursor.cycle_number
            self._exhausted_arms.clear()
            for d in Direction:
                self.cycle_hold_time[d] = 0.0

        held: Set[Direction] = set()
        for d in self.plan.metered_entries:
            # The guard only holds an arm that would otherwise be green
            if cursor.get_color(d) == "green":
                count = self.count_stopped_vehicles(d, active_vehicles)
                if count >= self.config.stopped_threshold:
                    remaining_budget = max(
                        0.0, self.config.max_hold - self.cycle_hold_time[d]
                    )
                    if remaining_budget > 0.0:
                        held.add(d)
                        hold_dt = min(delta_time, remaining_budget)
                        self.cycle_hold_time[d] += hold_dt
                        self.cumulative_hold_time[d] += hold_dt
                        if d not in self._currently_held:
                            self.hold_activations[d] += 1
                    else:
                        # Budget is exhausted for this arm while ring remains blocked
                        if d not in self._exhausted_arms:
                            self._exhausted_arms.add(d)
                            self.budget_exhaustions[d] += 1
                            self.exhausted_this_tick.add(d)

        self._currently_held = set(held)
        return held


class QueueCap:
    """Approach standing-queue cap for metered roundabouts (SR-12, D-W2-4).

    Monitors standing queues on red metered approaches. When a standing queue
    reaches the configured vehicle threshold and the active green phase has
    run for at least its min_green, terminates green early (cursor.end_green_early).
    Only shortens red; never extends a phase.
    """

    def __init__(self, plan: EntryMeteringPlan, network: RoadNetwork) -> None:
        self.plan = plan
        self.network = network
        self.config: QueueCapConfig = plan.queue_cap
        self.triggers: Dict[Direction, int] = {d: 0 for d in Direction}

    def reset(self) -> None:
        """Reset trigger counters."""
        for d in Direction:
            self.triggers[d] = 0

    def count_standing_queue(self, approach: Direction) -> int:
        """Count stopped vehicles (< 2.0 m/s) queued on all incoming lanes of approach."""
        try:
            incoming = self.network.get_incoming_approach(approach)
            return sum(
                1
                for lane in incoming.get_lanes()
                for v in lane.get_vehicles()
                if v.speed < _QUEUE_CAP_STOPPED_SPEED
            )
        except KeyError:
            return 0

    def check_and_trigger(
        self,
        cursor: MeteringPhaseCursor,
        active_vehicles: Optional[List[Vehicle]] = None,
    ) -> Optional[Direction]:
        """Check queue cap conditions; if met, terminate green early and return the arm."""
        if not self.config.enabled:
            return None

        # Can only terminate an active green phase
        if cursor.current_phase.color != "green":
            return None

        # Must have run at least min_green (minimum-green protection)
        if cursor.time_in_current_state < cursor.current_spec.min_green - 1e-6:
            return None

        # Inspect red metered arms in deterministic order
        for d in sorted(self.plan.metered_entries, key=lambda x: x.value):
            if cursor.get_color(d) == "red":
                queue_len = self.count_standing_queue(d)
                if queue_len >= self.config.vehicles:
                    success = cursor.end_green_early()
                    if success:
                        self.triggers[d] += 1
                        return d

        return None
