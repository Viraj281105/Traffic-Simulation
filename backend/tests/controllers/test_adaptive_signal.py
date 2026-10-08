"""Adaptive (vehicle-actuated) signal control, V1.3: decision rules and safety.

Decision tests drive the controller directly with stand-in vehicles placed on
the real network's incoming lanes, so each rule is exercised in isolation:
minimum and maximum green, gap-out, rest in green, phase order and skipping,
and that every change between approaches runs the configured yellow and
all-red. Safety is also checked on whole simulations in
tests/integration/test_adaptive_signal_runs.py.
"""

from typing import Any, Dict, List, Optional, Tuple

import pytest

from src.controllers.adaptive_signal import (
    AdaptiveSignalController,
    adaptive_plan_errors,
)
from src.controllers.factory import create_controller
from src.controllers.fixed_time_signal import FixedTimeSignalController
from src.controllers.signal_detection import MOVING_SPEED
from src.core.enums import Direction, TurnIntent
from src.roads.lane import Lane
from src.roads.network import RoadNetwork

PAIRED = ["ns_green", "ns_yellow", "all_red", "ew_green", "ew_yellow", "all_red"]
SINGLES = [
    "n_green",
    "n_yellow",
    "all_red",
    "s_green",
    "s_yellow",
    "all_red",
    "e_green",
    "e_yellow",
    "all_red",
    "w_green",
    "w_yellow",
    "all_red",
]
DT = 0.1


class _Stub:
    """Just what stop-line detection reads from a vehicle."""

    def __init__(self, lane: Lane, distance_to_stop: float, speed: float) -> None:
        self.lane = lane
        self.position = lane.length - distance_to_stop
        self.speed = speed


def _network(lanes: int = 1) -> RoadNetwork:
    network = RoadNetwork()
    network.setup_default_intersection(
        approach_length=200.0, lane_width=3.5, lanes_per_approach=lanes
    )
    return network


def _controller(
    plan: Optional[List[str]] = PAIRED,
    lanes: int = 1,
    **adaptive: Any,
) -> AdaptiveSignalController:
    ctrl: Dict[str, Any] = {
        "signalControl": "adaptive",
        "yellowDuration": 4.0,
        "allRedDuration": 2.0,
        "adaptive": {
            "minGreen": 10.0,
            "maxGreen": 30.0,
            "extensionStep": 2.5,
            "detectionDistance": 30.0,
            **adaptive,
        },
    }
    if plan is not None:
        ctrl["phaseSequence"] = plan
    return AdaptiveSignalController({"controller": ctrl}, _network(lanes))


def _lane(ctl: AdaptiveSignalController, d: Direction, idx: int = 0) -> Lane:
    return ctl.network.get_incoming_approach(d).get_lanes()[idx]


def _place(
    ctl: AdaptiveSignalController,
    d: Direction,
    distance: float = 5.0,
    speed: float = 0.0,
    idx: int = 0,
) -> _Stub:
    lane = _lane(ctl, d, idx)
    stub = _Stub(lane, distance, speed)
    lane.add_vehicle(stub)
    return stub


def _remove(stub: _Stub) -> None:
    stub.lane.remove_vehicle(stub)


def _run_until_change(ctl: AdaptiveSignalController, limit: float = 600.0) -> float:
    """Step until the phase changes; the green's length in seconds."""
    start = ctl.current_phase_idx
    t = 0.0
    while ctl.current_phase_idx == start:
        ctl.update(DT, [])
        t += DT
        assert t < limit, "phase never changed"
    return t


# ── Construction ──────────────────────────────────────────────────────────


def test_factory_builds_adaptive_only_when_asked() -> None:
    net = _network()
    fixed = create_controller(
        {"geometry": {"intersectionType": "fixed_time_signal"}, "controller": {}}, net
    )
    assert type(fixed) is FixedTimeSignalController
    explicit_fixed = create_controller(
        {"controller": {"signalControl": "fixed_time"}}, _network()
    )
    assert type(explicit_fixed) is FixedTimeSignalController
    adaptive = create_controller(
        {"controller": {"signalControl": "adaptive", "phaseSequence": PAIRED}},
        _network(),
    )
    assert isinstance(adaptive, AdaptiveSignalController)
    # The geometry gates (PET, conflict manager) treat it as a signal.
    assert isinstance(adaptive, FixedTimeSignalController)


def test_defaults_are_applied() -> None:
    ctl = AdaptiveSignalController(
        {"controller": {"signalControl": "adaptive", "phaseSequence": PAIRED}},
        _network(),
    )
    assert (ctl.min_green, ctl.max_green) == (10.0, 50.0)
    assert ctl.extension_step == 2.5
    assert ctl.detection_distance == 30.0
    assert ctl.demand_threshold == 1


def test_rejects_impossible_timings() -> None:
    with pytest.raises(ValueError, match="maxGreen"):
        _controller(minGreen=20.0, maxGreen=20.0)


@pytest.mark.parametrize(
    "plan,needle",
    [
        (["ns_green", "ew_green", "ns_yellow", "all_red"], "different approaches"),
        (["ns_green", "ns_yellow", "ew_green", "ew_yellow"], "all-red"),
        (["ns_green", "all_red", "ew_green", "ew_yellow", "all_red"], "yellow"),
        (
            ["ns_green", "ew_yellow", "all_red", "ew_green", "ew_yellow", "all_red"],
            "yellow",
        ),
    ],
)
def test_unsafe_plans_are_rejected(plan: List[str], needle: str) -> None:
    errors = adaptive_plan_errors(plan)
    assert errors and needle in errors[0]
    with pytest.raises(ValueError):
        _controller(plan=plan)


def test_supported_plans_are_accepted() -> None:
    assert adaptive_plan_errors(PAIRED) == []
    assert adaptive_plan_errors(SINGLES) == []
    assert adaptive_plan_errors(None) == []
    # Starting in a clearance phase is fine: it belongs to the last stage.
    rotated = PAIRED[2:] + PAIRED[:2]
    assert adaptive_plan_errors(rotated) == []


# ── Detection ─────────────────────────────────────────────────────────────


def test_detection_counts_only_the_zone_and_the_released_lanes() -> None:
    ctl = _controller()
    _place(ctl, Direction.NORTH, distance=10.0, speed=8.0)  # in zone, moving
    _place(ctl, Direction.NORTH, distance=29.0, speed=0.0)  # in zone, stopped
    _place(ctl, Direction.NORTH, distance=60.0, speed=10.0)  # beyond zone
    _place(ctl, Direction.EAST, distance=3.0, speed=0.0)  # other phase
    obs = ctl._detection.observe(ctl.current_phase_idx)  # ns_green
    assert obs.served == 2
    assert obs.passing == 1
    ew_green = PAIRED.index("ew_green")
    assert obs.calls[ew_green] == 1
    assert obs.per_direction["north"] == 2
    assert obs.per_direction["east"] == 1


def test_a_vehicle_mid_lane_change_is_counted_once() -> None:
    ctl = _controller(lanes=2)
    origin, target = _lane(ctl, Direction.NORTH, 0), _lane(ctl, Direction.NORTH, 1)
    stub = _Stub(target, 10.0, 5.0)
    origin.add_vehicle(stub)  # shadow occupancy of the lane it is leaving
    target.add_vehicle(stub)
    obs = ctl._detection.observe(ctl.current_phase_idx)
    assert obs.per_direction["north"] == 1


# ── Green timing ──────────────────────────────────────────────────────────


def test_minimum_green_is_always_served() -> None:
    ctl = _controller()
    _place(ctl, Direction.EAST)  # someone waiting; nobody on north/south
    assert _run_until_change(ctl) == pytest.approx(10.0, abs=DT + 1e-9)
    assert ctl.decisions["gapOut"] == 1


def test_green_rests_while_nobody_else_waits() -> None:
    ctl = _controller()
    for _ in range(int(120 / DT)):  # 4x the maximum green
        ctl.update(DT, [])
    assert ctl.current_phase.name == "ns_green"
    assert ctl.get_state()["adaptive"]["status"] == "resting"
    assert ctl.rest_seconds > 100


def test_passing_traffic_extends_and_a_gap_ends_the_green() -> None:
    ctl = _controller()
    _place(ctl, Direction.EAST)
    flow = _place(ctl, Direction.NORTH, distance=15.0, speed=MOVING_SPEED + 4.0)
    for _ in range(int(18 / DT)):
        ctl.update(DT, [])
    assert ctl.current_phase.name == "ns_green"  # held past the minimum
    assert ctl.get_state()["adaptive"]["status"] == "extending"
    _remove(flow)  # the stream stops
    green = 18.0 + _run_until_change(ctl)
    assert green == pytest.approx(18.0 + 2.5, abs=2 * DT + 1e-9)
    assert ctl.decisions == {"gapOut": 1, "maxOut": 0}
    assert ctl.greens_extended == 1


def test_a_stationary_vehicle_does_not_hold_the_green() -> None:
    """A left-turner standing in the zone (yielding to oncoming traffic) is
    demand, but not a passing vehicle: it cannot keep a green to its max."""
    ctl = _controller()
    _place(ctl, Direction.EAST)
    _place(ctl, Direction.NORTH, distance=2.0, speed=0.0)
    assert _run_until_change(ctl) == pytest.approx(10.0, abs=DT + 1e-9)


def test_maximum_green_bounds_a_busy_green_once_someone_waits() -> None:
    ctl = _controller()
    _place(ctl, Direction.NORTH, distance=15.0, speed=8.0)
    # Nobody waiting: the busy green may run on.
    for _ in range(int(40 / DT)):
        ctl.update(DT, [])
    assert ctl.current_phase.name == "ns_green"
    _place(ctl, Direction.WEST)  # a call arrives at t = 40 s
    extra = _run_until_change(ctl)
    assert extra == pytest.approx(30.0, abs=2 * DT + 1e-9)
    assert ctl.decisions == {"gapOut": 0, "maxOut": 1}


def test_demand_threshold_needs_enough_waiting_vehicles() -> None:
    ctl = _controller(demandThreshold=2)
    _place(ctl, Direction.EAST)
    for _ in range(int(60 / DT)):
        ctl.update(DT, [])
    assert ctl.current_phase.name == "ns_green"  # one vehicle is not a call
    _place(ctl, Direction.WEST, distance=8.0)
    _run_until_change(ctl)
    assert ctl.current_phase.name == "ns_yellow"


# ── Transitions and clearance ─────────────────────────────────────────────


def _trace(ctl: AdaptiveSignalController, seconds: float) -> List[Tuple[str, float]]:
    """Phase sequence with each phase's duration, over ``seconds``."""
    out: List[Tuple[str, float]] = []
    name, start, t = ctl.current_phase.name, 0.0, 0.0
    for _ in range(int(round(seconds / DT))):
        ctl.update(DT, [])
        t += DT
        if ctl.current_phase.name != name:
            out.append((name, round(t - start, 1)))
            name, start = ctl.current_phase.name, t
    return out


def test_every_change_runs_the_configured_yellow_and_all_red() -> None:
    ctl = _controller()
    _place(ctl, Direction.EAST)
    trace = _trace(ctl, 20.0)
    assert [p for p, _ in trace] == ["ns_green", "ns_yellow", "all_red"]
    assert trace[1][1] == pytest.approx(4.0, abs=DT)
    assert trace[2][1] == pytest.approx(2.0, abs=DT)
    assert ctl.current_phase.name == "ew_green"


def test_phases_without_demand_are_skipped_whole() -> None:
    """Only east is waiting: from north the signal goes straight to east;
    south's phase -- and its yellow -- never appear."""
    ctl = _controller(plan=SINGLES)
    _place(ctl, Direction.EAST)
    names = [p for p, _ in _trace(ctl, 20.0)]
    assert names == ["n_green", "n_yellow", "all_red"]
    assert ctl.current_phase.name == "e_green"
    assert ctl.phases_skipped == 1
    assert ctl.recent_decisions[-1]["next"] == "e_green"


def test_waiting_phases_are_served_in_plan_order() -> None:
    """With everyone waiting, every phase is served once per cycle, in the
    plan's order: no approach can be passed over repeatedly."""
    ctl = _controller(plan=SINGLES)
    for d in (Direction.SOUTH, Direction.EAST, Direction.WEST, Direction.NORTH):
        _place(ctl, d)
    greens = [p for p, _ in _trace(ctl, 200.0) if p.endswith("_green")]
    assert greens[:5] == ["n_green", "s_green", "e_green", "w_green", "n_green"]


def test_no_conflicting_greens_and_clearance_on_every_change() -> None:
    """Exhaustive tick-level check on a busy plan: north-south and east-west
    lanes are never released together, and a lane only becomes green after
    an all-red in which every lane was blocked."""
    ctl = _controller(lanes=2)
    for d in Direction:
        _place(ctl, d, distance=12.0, speed=6.0)
        _place(ctl, d, distance=4.0, speed=0.0, idx=1)
    green_dirs_before: set[Direction] = set()
    saw_all_red = True
    for _ in range(int(400 / DT)):
        ctl.update(DT, [])
        green = {
            d
            for d in Direction
            for lane in ctl.network.get_incoming_approach(d).get_lanes()
            if lane.virtual_obstacle is None
        }
        assert not (green & {Direction.NORTH, Direction.SOUTH}) or not (
            green & {Direction.EAST, Direction.WEST}
        )
        newly = green - green_dirs_before
        if newly:
            assert saw_all_red, f"{newly} turned green without an all-red"
            saw_all_red = False
        if ctl.current_phase.name == "all_red":
            assert not green
            saw_all_red = True
        green_dirs_before = green


def test_protected_left_lane_stays_red_during_the_straight_phase() -> None:
    """The one-direction-at-a-time plan's protected left: whatever the
    adaptive timing, lane 0 (the left-turn lane) is only released by its own
    left phase."""
    ctl = _controller(plan=None, lanes=2)
    for d in Direction:
        _place(ctl, d, distance=6.0, speed=0.0, idx=0)
        _place(ctl, d, distance=6.0, speed=0.0, idx=1)
    seen_left = False
    for _ in range(int(300 / DT)):
        ctl.update(DT, [])
        phase = ctl.current_phase
        for d in Direction:
            left, through = ctl.network.get_incoming_approach(d).get_lanes()
            if phase.color == "green" and phase.allowed_turns == (TurnIntent.LEFT,):
                seen_left = True
                assert through.virtual_obstacle is not None
            if phase.color == "green" and TurnIntent.LEFT not in phase.allowed_turns:
                assert left.virtual_obstacle is not None
    assert seen_left


def test_left_phase_is_skipped_when_no_left_turner_waits() -> None:
    ctl = _controller(plan=None, lanes=2)
    _place(ctl, Direction.SOUTH, idx=1)  # south through only
    names = [p for p, _ in _trace(ctl, 25.0)]
    assert names[0] == "north_straight_right"
    assert "north_left" not in names
    assert names[1:3] == ["north_yellow", "all_red"]
    assert ctl.current_phase.name == "south_straight_right"


def test_left_phase_follows_directly_when_only_left_turners_wait() -> None:
    """Same approach, next green of its stage: no clearance needed -- the
    step the fixed-time cycle also takes."""
    ctl = _controller(plan=None, lanes=2)
    _place(ctl, Direction.NORTH, idx=0)  # north left-turner
    names = [p for p, _ in _trace(ctl, 12.0)]
    assert names == ["north_straight_right"]
    assert ctl.current_phase.name == "north_left"


# ── Determinism, reset and state ──────────────────────────────────────────


def _scripted_run(ctl: AdaptiveSignalController) -> List[Tuple[str, float]]:
    _place(ctl, Direction.EAST)
    flow = _place(ctl, Direction.NORTH, distance=15.0, speed=8.0)
    trace = _trace(ctl, 25.0)
    _remove(flow)
    return trace + _trace(ctl, 60.0)


def test_decisions_are_deterministic_and_reset_restores_them() -> None:
    a = _scripted_run(_controller())
    b = _scripted_run(_controller())
    assert a == b
    ctl = _controller()
    first = _scripted_run(ctl)
    for lane_list in (
        ctl.network.get_incoming_approach(d).get_lanes() for d in Direction
    ):
        for lane in lane_list:
            for v in list(lane.get_vehicles()):
                lane.remove_vehicle(v)
    ctl.reset()
    assert ctl.decisions == {"gapOut": 0, "maxOut": 0}
    assert ctl.current_phase.name == "ns_green"
    assert _scripted_run(ctl) == first


def test_state_reports_the_decision_mechanism() -> None:
    ctl = _controller()
    _place(ctl, Direction.EAST)
    _run_until_change(ctl)
    state = ctl.get_state()
    assert state["type"] == "fixed_time_signal"
    assert state["signalControl"] == "adaptive"
    adaptive = state["adaptive"]
    assert adaptive["status"] == "clearance"
    assert adaptive["nextPhase"] == "ew_green"
    assert adaptive["decisions"]["gapOuts"] == 1
    decision = adaptive["recentDecisions"][-1]
    assert decision["phase"] == "ns_green"
    assert decision["decision"] == "gapOut"
    assert decision["next"] == "ew_green"
    assert decision["waiting"] == 1
    # Clearance has a fixed length; a green's is an upper bound.
    assert state["phaseTimeRemaining"] == pytest.approx(4.0, abs=DT)


def test_phase_time_remaining_is_an_upper_bound() -> None:
    ctl = _controller()
    ctl.update(DT, [])
    assert ctl.phase_time_remaining == pytest.approx(10.0 - DT)
    for _ in range(int(15 / DT)):
        ctl.update(DT, [])
    assert ctl.phase_time_remaining == 0.0  # resting, nobody waiting
    _place(ctl, Direction.EAST)
    _place(ctl, Direction.NORTH, distance=15.0, speed=8.0)
    ctl.update(DT, [])
    assert 29.0 < ctl.phase_time_remaining <= 30.0
