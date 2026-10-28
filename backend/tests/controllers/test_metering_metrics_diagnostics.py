"""Tests for metering metrics, decision events, and diagnostics (W2 S6).

Covers:
- SR-13: Decision events recorded on state transitions (red, yellow, ring_spillback_hold, queue_cap).
- Dilemma zone yellow commitment event and counter tracking.
- Entry denial accounting by reason and total.
- Spillback guard hold-duration accounting, activations, and budget exhaustion events.
- Queue-cap trigger accounting and early-green termination diagnostics.
- Signal-state reporting: real colours on metered approaches, green projection on unmetered approaches (D-W2-6).
- Distinguishability of guard-induced red from planned red.
- Idle-loss calculation integration with signals_state (D-W2-6).
- Reset determinism and snapshot serialization compatibility.
"""

from __future__ import annotations

import copy
from typing import Any, Dict

import pytest

from src.controllers.entry_metering import (
    MeteringPhaseCursor,
    QueueCap,
    SpillbackGuard,
    build_metering_plan,
)
from src.controllers.factory import derive_signals_state
from src.controllers.roundabout import RoundaboutController
from src.controllers.signalised_roundabout import SignalisedRoundaboutController
from src.core.enums import Direction
from src.metrics.definitions.idle_loss import calculate_idle_loss_tick
from src.roads.lane import Lane
from src.roads.network import RoadNetwork
from src.vehicles.vehicle import Vehicle


def _make_vehicle(
    name: str,
    lane: Lane,
    position: float,
    speed: float,
    length: float = 4.5,
) -> Vehicle:
    v = Vehicle(
        name,
        length=length,
        width=2.0,
        desired_speed=13.89,
        route=[lane],
        start_position=position,
        initial_speed=speed,
    )
    v.speed = speed
    v.position = position
    v.lane = lane
    lane.add_vehicle(v)
    return v


def _setup_roundabout_network() -> RoadNetwork:
    net = RoadNetwork()
    net.setup_default_intersection(
        approach_length=100.0,
        lane_width=3.5,
        lanes_per_approach=1,
    )
    return net


def _make_s6_config(
    spillback_enabled: bool = True,
    queue_cap_enabled: bool = True,
    max_hold: float = 10.0,
    stopped_threshold: int = 2,
    queue_cap_vehicles: int = 6,
) -> Dict[str, Any]:
    metering_cfg: Dict[str, Any] = {
        "phases": [
            {
                "entries": ["north"],
                "green": 20.0,
                "minGreen": 8.0,
                "maxGreen": 40.0,
            },
            {
                "entries": ["east"],
                "green": 15.0,
                "minGreen": 6.0,
                "maxGreen": 30.0,
            },
        ],
        "yellow": 3.0,
        "allRed": 2.0,
        "offset": 0.0,
        "spillbackGuard": {
            "enabled": spillback_enabled,
            "stoppedThreshold": stopped_threshold,
            "maxHold": max_hold,
        },
        "queueCap": {
            "enabled": queue_cap_enabled,
            "vehicles": queue_cap_vehicles,
        },
    }
    return {
        "geometry": {
            "intersectionType": "roundabout",
            "lanesPerApproach": 1,
            "circulatingLanes": 1,
        },
        "controller": {
            "innerRadius": 10.0,
            "outerRadius": 20.0,
            "criticalGap": 4.0,
            "followUpTime": 2.5,
            "entrySpeed": 5.0,
            "circulatingSpeed": 8.0,
            "entryControl": "metered_entry",
            "entryMetering": metering_cfg,
        },
        "simulation": {"duration": 60.0, "timeStep": 0.1, "randomSeed": 42},
    }


# ===========================================================================
# 1. Signal-state reporting & Green projection on unmetered arms (D-W2-6)
# ===========================================================================


def test_signals_state_metered_and_unmetered_projection() -> None:
    """Metered arms report actual signal colors; unmetered arms retain green projection."""
    net = _setup_roundabout_network()
    cfg = _make_s6_config()  # North and East metered; South and West unmetered
    controller = SignalisedRoundaboutController(cfg, net)

    # In Phase 0 Green: North is green, East is red
    signals = controller.signals_state()
    assert signals[Direction.NORTH] == "green"
    assert signals[Direction.EAST] == "red"
    # Unmetered arms must project green per D-W2-6
    assert signals[Direction.SOUTH] == "green"
    assert signals[Direction.WEST] == "green"

    # Advance into North yellow
    controller.cursor.advance(20.0)
    signals = controller.signals_state()
    assert signals[Direction.NORTH] == "yellow"
    assert signals[Direction.EAST] == "red"
    assert signals[Direction.SOUTH] == "green"
    assert signals[Direction.WEST] == "green"

    # Advance into all-red clearance
    controller.cursor.advance(3.0)
    signals = controller.signals_state()
    assert signals[Direction.NORTH] == "red"
    assert signals[Direction.EAST] == "red"
    assert signals[Direction.SOUTH] == "green"
    assert signals[Direction.WEST] == "green"

    # Advance into Phase 1 Green (East green)
    controller.cursor.advance(2.0)
    signals = controller.signals_state()
    assert signals[Direction.NORTH] == "red"
    assert signals[Direction.EAST] == "green"
    assert signals[Direction.SOUTH] == "green"
    assert signals[Direction.WEST] == "green"


def test_signals_state_distinguishes_guard_held_from_planned_red() -> None:
    """Guard-induced red is distinguishable from planned red via get_arm_reason."""
    net = _setup_roundabout_network()
    cfg = _make_s6_config(spillback_enabled=True, queue_cap_enabled=False)
    controller = SignalisedRoundaboutController(cfg, net)

    # Phase 0: North is planned green, East is planned red
    assert controller.cursor.get_color(Direction.NORTH) == "green"
    assert controller.cursor.get_color(Direction.EAST) == "red"

    # Under normal condition: North gate reason is None (open), East is "red"
    assert controller.gate.get_arm_reason(Direction.NORTH) is None
    assert controller.gate.get_arm_reason(Direction.EAST) == "red"

    # Introduce downstream blockage for North
    conn_lane = Lane("conn_circ", 0.0, 15.0, -15.0, 0.0)
    c1 = _make_vehicle("c1", conn_lane, 10.0, 0.5)
    c2 = _make_vehicle("c2", conn_lane, 20.0, 0.5)
    controller.update(0.1, [c1, c2])

    # North is held by spillback guard:
    # 1. signals_state() displays "red"
    assert controller.signals_state()[Direction.NORTH] == "red"
    # 2. get_arm_reason() specifically reports "ring_spillback_hold"
    assert controller.gate.get_arm_reason(Direction.NORTH) == "ring_spillback_hold"
    # 3. East is planned red
    assert controller.signals_state()[Direction.EAST] == "red"
    assert controller.gate.get_arm_reason(Direction.EAST) == "red"


# ===========================================================================
# 2. Decision events, yellow commitments, and entry denials
# ===========================================================================


def test_gate_decision_events_on_state_transitions() -> None:
    """Transitions between green, yellow, all-red, and hold emit decision events."""
    net = _setup_roundabout_network()
    cfg = _make_s6_config(spillback_enabled=False, queue_cap_enabled=False)
    controller = SignalisedRoundaboutController(cfg, net)

    # Initially at t=0: East is red -> closure transition recorded
    controller.update(0.1, [])
    assert any(
        ev["arm"] == "east" and ev["reason"] == "red" and ev["state"] == "closed"
        for ev in controller.gate.recent_decisions
    )

    # Advance to North yellow at t=20.0s
    for _ in range(200):
        controller.update(0.1, [])

    # Yellow transition recorded
    assert controller.gate.decision_counts["yellow"] >= 1
    assert any(
        ev["arm"] == "north" and ev["reason"] == "yellow" and ev["state"] == "closed"
        for ev in controller.gate.recent_decisions
    )

    # Advance through yellow (3.0s) and all-red (2.0s) to Phase 1 Green (East green)
    for _ in range(50):
        controller.update(0.1, [])

    # East turns green -> open transition
    assert any(
        ev["arm"] == "east" and ev["reason"] == "open" and ev["state"] == "open"
        for ev in controller.gate.recent_decisions
    )


def test_yellow_phase_commitment_event_and_counter() -> None:
    """Vehicles in dilemma zone committing through yellow increment yellow_commit and emit an event."""
    net = _setup_roundabout_network()
    cfg = _make_s6_config(spillback_enabled=False, queue_cap_enabled=False)
    controller = SignalisedRoundaboutController(cfg, net)

    # Advance cursor directly to North yellow
    controller.cursor.advance(20.0)
    assert controller.cursor.get_color(Direction.NORTH) == "yellow"

    north_in = net.get_incoming_approach(Direction.NORTH)
    lane = north_in.get_lanes()[0]

    # Vehicle traveling fast near the line (position 97m on 100m lane, speed 12 m/s) -> commits!
    _make_vehicle("fast_car", lane, position=97.0, speed=12.0)

    # Gate evaluation
    dec = controller.gate.allows(Direction.NORTH, lane, 20.1)
    assert dec.open is True
    # yellow_commit counter incremented
    assert controller.gate.decision_counts["yellow_commit"] == 1
    # Decision event recorded
    recent = list(controller.gate.recent_decisions)
    assert any(
        ev["reason"] == "yellow_commit"
        and ev["arm"] == "north"
        and ev["state"] == "committed"
        for ev in recent
    )

    # Same vehicle evaluated again: latched, does not re-increment
    dec2 = controller.gate.allows(Direction.NORTH, lane, 20.2)
    assert dec2.open is True
    assert controller.gate.decision_counts["yellow_commit"] == 1


def test_entry_denials_accounting() -> None:
    """Closed gate increments entry denial counters by reason and in total."""
    net = _setup_roundabout_network()
    cfg = _make_s6_config(spillback_enabled=False, queue_cap_enabled=False)
    controller = SignalisedRoundaboutController(cfg, net)

    east_in = net.get_incoming_approach(Direction.EAST)
    lane = east_in.get_lanes()[0]
    _make_vehicle("stopped_east", lane, position=95.0, speed=0.0)

    # East is red in Phase 0
    assert controller.cursor.get_color(Direction.EAST) == "red"

    # Evaluation denies entry
    dec = controller.gate.allows(Direction.EAST, lane, 1.0)
    assert dec.open is False
    assert dec.reason == "red"

    # Denials counted
    assert controller.gate.denial_counts["red"] == 1
    assert controller.gate.decision_counts["entry_denials"] == 1


# ===========================================================================
# 3. Spillback Guard: Activations, Durations, and Budget Exhaustion
# ===========================================================================


def test_spillback_guard_duration_activations_and_budget_exhaustion() -> None:
    """Spillback guard accurately tracks hold activations, cumulative duration, and exhaustion."""
    net = _setup_roundabout_network()
    plan = build_metering_plan(
        _make_s6_config(max_hold=5.0, stopped_threshold=2)["controller"][
            "entryMetering"
        ]
    )
    cursor = MeteringPhaseCursor(plan)
    guard = SpillbackGuard(plan, net)

    conn_lane = Lane("conn_circ", 0.0, 15.0, -15.0, 0.0)
    c1 = _make_vehicle("c1", conn_lane, 10.0, 0.5)
    c2 = _make_vehicle("c2", conn_lane, 20.0, 0.5)
    active = [c1, c2]

    # Initial state
    assert guard.hold_activations[Direction.NORTH] == 0
    assert guard.cumulative_hold_time[Direction.NORTH] == 0.0
    assert guard.budget_exhaustions[Direction.NORTH] == 0

    # 1. First tick: hold activates
    held = guard.update(cursor, delta_time=2.0, active_vehicles=active)
    assert Direction.NORTH in held
    assert guard.hold_activations[Direction.NORTH] == 1
    assert pytest.approx(guard.cumulative_hold_time[Direction.NORTH], 0.01) == 2.0
    assert guard.budget_exhaustions[Direction.NORTH] == 0

    # 2. Second tick: hold continues (activation count does not increase)
    held = guard.update(cursor, delta_time=2.0, active_vehicles=active)
    assert Direction.NORTH in held
    assert guard.hold_activations[Direction.NORTH] == 1
    assert pytest.approx(guard.cumulative_hold_time[Direction.NORTH], 0.01) == 4.0

    # 3. Third tick: hold hits max_hold (5.0s) -> remaining budget is 1.0s
    held = guard.update(cursor, delta_time=2.0, active_vehicles=active)
    assert Direction.NORTH in held
    assert pytest.approx(guard.cumulative_hold_time[Direction.NORTH], 0.01) == 5.0
    assert guard.cycle_hold_time[Direction.NORTH] == 5.0

    # 4. Fourth tick: budget exhausted while blockage persists -> release and exhaust
    held = guard.update(cursor, delta_time=1.0, active_vehicles=active)
    assert Direction.NORTH not in held
    assert Direction.NORTH in guard.exhausted_this_tick
    assert guard.budget_exhaustions[Direction.NORTH] == 1
    # Cumulative hold time remains capped at 5.0s
    assert pytest.approx(guard.cumulative_hold_time[Direction.NORTH], 0.01) == 5.0


def test_controller_records_spillback_exhausted_event() -> None:
    """When spillback budget runs out, controller emits spillback_exhausted decision event."""
    net = _setup_roundabout_network()
    cfg = _make_s6_config(spillback_enabled=True, queue_cap_enabled=False, max_hold=3.0)
    controller = SignalisedRoundaboutController(cfg, net)

    conn_lane = Lane("conn_circ", 0.0, 15.0, -15.0, 0.0)
    c1 = _make_vehicle("c1", conn_lane, 10.0, 0.5)
    c2 = _make_vehicle("c2", conn_lane, 20.0, 0.5)
    active = [c1, c2]

    # Run for 3.0s (accumulating max_hold)
    for _ in range(30):
        controller.update(0.1, active)

    assert controller.spillback_guard.cycle_hold_time[Direction.NORTH] == 3.0

    # Next step: budget is exhausted
    controller.update(0.1, active)

    assert controller.gate.decision_counts["spillback_exhausted"] == 1
    assert any(
        ev["reason"] == "spillback_exhausted"
        and ev["arm"] == "north"
        and ev["state"] == "released"
        for ev in controller.gate.recent_decisions
    )


# ===========================================================================
# 4. Queue Cap: Trigger Accounting and Diagnostics
# ===========================================================================


def test_queue_cap_trigger_accounting() -> None:
    """QueueCap tracks per-arm trigger counts accurately."""
    net = _setup_roundabout_network()
    plan = build_metering_plan(
        _make_s6_config(queue_cap_vehicles=4)["controller"]["entryMetering"]
    )
    cursor = MeteringPhaseCursor(plan)
    qc = QueueCap(plan, net)

    east_in = net.get_incoming_approach(Direction.EAST)
    lane = east_in.get_lanes()[0]
    for i in range(5):
        _make_vehicle(f"east_{i}", lane, position=80.0 - i * 5.0, speed=0.0)

    # Phase 0 green for North, red for East; advance past minGreen (8.0s)
    cursor.advance(8.5)
    assert cursor.current_phase.color == "green"
    assert qc.triggers[Direction.EAST] == 0

    triggered_arm = qc.check_and_trigger(cursor)
    assert triggered_arm == Direction.EAST
    assert qc.triggers[Direction.EAST] == 1


# ===========================================================================
# 5. Snapshot serialization & telemetry schema
# ===========================================================================


def test_controller_get_state_telemetry_schema() -> None:
    """get_state() contains complete metering, spillbackGuard, and queueCap telemetry."""
    net = _setup_roundabout_network()
    cfg = _make_s6_config(spillback_enabled=True, queue_cap_enabled=True)
    controller = SignalisedRoundaboutController(cfg, net)

    controller.update(0.1, [])
    st = controller.get_state()

    assert st["type"] == "roundabout"
    assert st["entryControl"] == "metered_entry"
    assert "metering" in st

    m = st["metering"]
    assert "currentPhase" in m
    assert "color" in m
    assert "timeRemaining" in m
    assert "cycleNumber" in m
    assert "cycleProgress" in m
    assert "arms" in m
    assert "decisions" in m
    assert "recentDecisions" in m
    assert "spillbackGuard" in m
    assert "queueCap" in m

    # Validate spillbackGuard diagnostics
    sg = m["spillbackGuard"]
    assert sg["enabled"] is True
    assert "north" in sg["cumulativeHoldTime"]
    assert "north" in sg["activations"]
    assert "north" in sg["budgetExhaustions"]

    # Validate queueCap diagnostics
    qc = m["queueCap"]
    assert qc["enabled"] is True
    assert "north" in qc["triggers"]
    assert "east" in qc["triggers"]


# ===========================================================================
# 6. Idle Opportunity Loss & Conventional Roundabout Compatibility (D-W2-6)
# ===========================================================================


def test_idle_loss_with_derive_signals_state_metered_roundabout() -> None:
    """Idle loss is correctly computed for metered roundabouts using derive_signals_state."""
    net = _setup_roundabout_network()
    cfg = _make_s6_config()
    controller = SignalisedRoundaboutController(cfg, net)

    east_in = net.get_incoming_approach(Direction.EAST)
    east_lane = east_in.get_lanes()[0]
    # Stopped vehicle on red East approach
    v_east = _make_vehicle("east_waiting", east_lane, position=90.0, speed=0.0)

    # North approach (green) has no queued vehicles
    active_vehicles = [v_east]

    signals = derive_signals_state(controller)
    assert signals[Direction.NORTH] == "green"
    assert signals[Direction.EAST] == "red"

    # Idle loss condition: red approach has queued vehicles, green approaches are empty
    is_idle_loss = calculate_idle_loss_tick(
        active_vehicles, signals, wait_speed_threshold=0.5
    )
    assert is_idle_loss is True


def test_idle_loss_structurally_zero_for_conventional_roundabout() -> None:
    """Conventional roundabout has empty signals_state so idle loss is structurally False."""
    net = _setup_roundabout_network()
    cfg = copy.deepcopy(_make_s6_config())
    cfg["controller"]["entryControl"] = "none"
    controller = RoundaboutController(cfg["controller"], net)

    east_in = net.get_incoming_approach(Direction.EAST)
    east_lane = east_in.get_lanes()[0]
    v_east = _make_vehicle("east_waiting", east_lane, position=90.0, speed=0.0)

    signals = derive_signals_state(controller)
    assert signals == {d: "green" for d in Direction}

    # Structurally zero for conventional roundabout (no red approach exists)
    is_idle_loss = calculate_idle_loss_tick([v_east], signals, wait_speed_threshold=0.5)
    assert is_idle_loss is False


# ===========================================================================
# 7. Reset determinism & reproducibility
# ===========================================================================


def test_metering_metrics_reset_determinism() -> None:
    """Reset cleanly resets all decision counts, hold timers, and trigger counters."""
    net = _setup_roundabout_network()
    cfg = _make_s6_config(spillback_enabled=True, queue_cap_enabled=True)
    controller = SignalisedRoundaboutController(cfg, net)

    # Run for 25 seconds
    for _ in range(250):
        controller.update(0.1, [])

    state_run = controller.get_state()
    assert state_run["metering"]["cycleNumber"] >= 0

    # Reset
    controller.reset()
    state_reset = controller.get_state()

    m = state_reset["metering"]
    assert m["cycleNumber"] == 0
    assert m["recentDecisions"] == []
    for k in m["decisions"]:
        assert m["decisions"][k] == 0
    for d in cfg["controller"]["entryMetering"]["phases"][0]["entries"]:
        assert m["spillbackGuard"]["cumulativeHoldTime"][d] == 0.0
        assert m["spillbackGuard"]["activations"][d] == 0
        assert m["spillbackGuard"]["budgetExhaustions"][d] == 0
        assert m["queueCap"]["triggers"][d] == 0
