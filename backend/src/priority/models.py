"""Inputs of the priority package (F12): emergency vehicles, pre-emption,
yielding and transit priority. Plain frozen dataclasses with explicit bounds, so
a request can never ask for an unbounded run.

Everything here is a model input, not a finding: the numbers are plausible
urban defaults and results computed from them are in-model only.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

APPROACHES: Tuple[str, ...] = ("north", "south", "east", "west")
TURNS: Tuple[str, ...] = ("left", "straight", "right")

#: Hard bounds enforced for every run built by this package.
MAX_DURATION_S: float = 900.0
MIN_DURATION_S: float = 60.0
MAX_SEEDS: int = 20
MIN_SEEDS: int = 2
#: seeds x duration, per arm, a request may ask for (keeps a request to seconds).
MAX_SEED_SECONDS: float = 2000.0
MAX_EMERGENCY_VEHICLES: int = 8
MAX_TRANSIT_LINES: int = 4
MAX_TRANSIT_TRIPS_PER_LINE: int = 30
MIN_TIME_STEP_S: float = 0.1
MAX_TIME_STEP_S: float = 0.2


def _finite(value: float, name: str) -> float:
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    return float(value)


def _within(value: float, name: str, low: float, high: float) -> float:
    number = _finite(value, name)
    if not low <= number <= high:
        raise ValueError(f"{name} must be between {low:g} and {high:g}")
    return number


@dataclass(frozen=True)
class EmergencySpec:
    """One emergency vehicle to inject: what, where from, where to, and when."""

    kind: str
    approach: str
    turn: str
    time_s: float
    #: Entry lane index on the approach; None picks the lane the turn uses.
    lane: Optional[int] = None

    def validate(self, kinds: Dict[str, object], duration_s: float) -> None:
        if self.kind not in kinds:
            raise ValueError(f"emergency kind must be one of {sorted(kinds)}")
        if self.approach not in APPROACHES:
            raise ValueError(f"approach must be one of {list(APPROACHES)}")
        if self.turn not in TURNS:
            raise ValueError(f"turn must be one of {list(TURNS)}")
        _within(self.time_s, "emergency time", 0.0, max(0.0, duration_s - 20.0))
        if self.lane is not None and not 0 <= self.lane <= 5:
            raise ValueError("lane must be between 0 and 5")


@dataclass(frozen=True)
class PreemptionConfig:
    """Signal pre-emption. See ``controller.PriorityController`` for the rules.

    ``detection_distance_m`` and ``detection_time_s`` are alternatives: an
    emergency vehicle is detected when it is closer to its stop line than the
    distance, or (moving) will reach it within the time. Either may be None.
    """

    enabled: bool = True
    detection_distance_m: Optional[float] = 150.0
    detection_time_s: Optional[float] = 12.0
    #: A green is never cut shorter than this (safety minimum green).
    min_green_s: float = 7.0
    #: The pre-empted green is released after this long even if the vehicle
    #: has not cleared (bounded hold).
    max_hold_s: float = 45.0
    #: After the plan is restored, no new pre-emption starts for this long.
    min_recovery_s: float = 10.0

    def validate(self) -> None:
        if self.detection_distance_m is None and self.detection_time_s is None:
            raise ValueError("give a detection distance, a detection time, or both")
        if self.detection_distance_m is not None:
            _within(self.detection_distance_m, "detection distance", 20.0, 1000.0)
        if self.detection_time_s is not None:
            _within(self.detection_time_s, "detection time", 1.0, 60.0)
        _within(self.min_green_s, "minimum green", 1.0, 30.0)
        _within(self.max_hold_s, "maximum hold", 5.0, 120.0)
        if self.max_hold_s < self.min_green_s:
            raise ValueError("maximum hold must be at least the minimum green")
        _within(self.min_recovery_s, "minimum recovery", 0.0, 120.0)


@dataclass(frozen=True)
class YieldConfig:
    """Yielding and clearance of vehicles ahead of an emergency vehicle.

    The micro-model has no shoulder and no free lateral movement, so a driver
    cannot pull over. Drivers ahead of the emergency vehicle in its lane, within
    ``distance_m``, instead *clear the way*: they close up and move off
    promptly (shorter desired headway, stronger acceleration) and do not hold
    the lane below ``speed_floor_factor`` x the speed limit. Both are restored
    when the vehicle is no longer within the distance.
    """

    enabled: bool = True
    distance_m: float = 120.0
    headway_factor: float = 0.6
    acceleration_factor: float = 1.3
    speed_floor_factor: float = 1.0

    def validate(self) -> None:
        _within(self.distance_m, "yield distance", 10.0, 400.0)
        _within(self.headway_factor, "headway factor", 0.3, 1.0)
        _within(self.acceleration_factor, "acceleration factor", 1.0, 2.0)
        _within(self.speed_floor_factor, "speed floor factor", 0.5, 1.2)


@dataclass(frozen=True)
class TransitLineSpec:
    """A bus line through the junction: a trip every ``headway_s``."""

    line_id: str
    approach: str
    turn: str
    headway_s: float
    first_departure_s: float
    count: int
    dwell_s: float = 15.0
    #: Distance of the stop from the start of the approach lane; None puts it
    #: 60 m short of the stop line.
    stop_position_m: Optional[float] = None

    def validate(self, duration_s: float) -> None:
        if not self.line_id or len(self.line_id) > 24:
            raise ValueError("line id must be 1 to 24 characters")
        if self.approach not in APPROACHES:
            raise ValueError(f"approach must be one of {list(APPROACHES)}")
        if self.turn not in TURNS:
            raise ValueError(f"turn must be one of {list(TURNS)}")
        _within(self.headway_s, "headway", 30.0, 900.0)
        _within(self.first_departure_s, "first departure", 0.0, duration_s)
        _within(self.dwell_s, "dwell", 0.0, 60.0)
        if not 1 <= self.count <= MAX_TRANSIT_TRIPS_PER_LINE:
            raise ValueError(
                f"count must be between 1 and {MAX_TRANSIT_TRIPS_PER_LINE}"
            )
        if self.stop_position_m is not None:
            _within(self.stop_position_m, "stop position", 20.0, 400.0)


@dataclass(frozen=True)
class TransitPriorityConfig:
    """Conditional transit signal priority: green extension and early green,
    each bounded, granted only to a bus that is behind schedule (unless
    ``conditional`` is False)."""

    enabled: bool = True
    detection_distance_m: float = 120.0
    #: A bus is "behind schedule" when its predicted arrival at the stop line
    #: is later than the timetable by at least this much.
    lateness_threshold_s: float = 15.0
    #: Timetable slack on top of free-flow running time and dwell.
    schedule_padding_s: float = 10.0
    max_extension_s: float = 10.0
    max_early_green_s: float = 10.0
    min_green_s: float = 7.0
    #: After a priority action no other one starts for this long.
    min_spacing_s: float = 30.0
    conditional: bool = True

    def validate(self) -> None:
        _within(self.detection_distance_m, "detection distance", 20.0, 400.0)
        _within(self.lateness_threshold_s, "lateness threshold", 0.0, 300.0)
        _within(self.schedule_padding_s, "schedule padding", 0.0, 300.0)
        _within(self.max_extension_s, "maximum extension", 0.0, 20.0)
        _within(self.max_early_green_s, "maximum early green", 0.0, 20.0)
        _within(self.min_green_s, "minimum green", 1.0, 30.0)
        _within(self.min_spacing_s, "minimum spacing", 0.0, 300.0)


@dataclass(frozen=True)
class ScenarioSpec:
    """The single junction the comparisons run on."""

    duration_s: float = 200.0
    arrival_rate: float = 1.2
    lanes_per_approach: int = 2
    approach_length_m: float = 200.0
    speed_limit_mps: float = 13.89
    green_s: float = 30.0
    yellow_s: float = 4.0
    all_red_s: float = 2.0
    time_step_s: float = 0.1
    car_occupancy: float = 1.3
    bus_occupancy: float = 35.0

    def validate(self) -> None:
        _within(self.duration_s, "duration", MIN_DURATION_S, MAX_DURATION_S)
        _within(self.arrival_rate, "arrival rate", 0.05, 2.0)
        if not 1 <= self.lanes_per_approach <= 3:
            raise ValueError("lanes per approach must be between 1 and 3")
        _within(self.approach_length_m, "approach length", 100.0, 500.0)
        _within(self.speed_limit_mps, "speed limit", 5.0, 25.0)
        _within(self.green_s, "green", 10.0, 90.0)
        _within(self.yellow_s, "yellow", 2.0, 8.0)
        _within(self.all_red_s, "all red", 0.0, 8.0)
        _within(self.time_step_s, "time step", MIN_TIME_STEP_S, MAX_TIME_STEP_S)
        _within(self.car_occupancy, "car occupancy", 1.0, 4.0)
        _within(self.bus_occupancy, "bus occupancy", 5.0, 150.0)


def check_seed_budget(n_seeds: int, duration_s: float) -> None:
    """Reject a request whose seeds x duration exceeds the work budget."""
    if not MIN_SEEDS <= n_seeds <= MAX_SEEDS:
        raise ValueError(f"number of seeds must be between {MIN_SEEDS} and {MAX_SEEDS}")
    if n_seeds * duration_s > MAX_SEED_SECONDS:
        raise ValueError(
            f"seeds x duration must not exceed {MAX_SEED_SECONDS:g} simulated seconds "
            f"per arm (got {n_seeds * duration_s:g})"
        )
