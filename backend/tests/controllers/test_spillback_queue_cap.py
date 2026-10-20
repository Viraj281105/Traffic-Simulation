"""Tests for Spillback Guard and Queue Cap (W2 Step S5).

Covers:
- SR-11, D-W2-5: Downstream ring and exit spillback guard.
- SR-12, D-W2-4: Standing queue cap and early green termination.
- D-W2-3, SR-19: Starvation bounds under guard holds (maxRed = plannedRed + maxHold).
- Minimum-green protection (queue cap cannot cut green below minGreen).
- Gate transition events and snapshot telemetry ('ring_spillback_hold', 'queue_cap').
- Reset determinism and zero production randomness.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List

import pytest

from src.controllers.entry_metering import (
    MeteringPhaseCursor,
    QueueCap,
    QueueCapConfig,
    SpillbackGuard,
    SpillbackGuardConfig,
    build_metering_plan,
)
from src.controllers.signalised_roundabout import SignalisedRoundaboutController
from src.core.enums import Direction
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


_S5_BASE_CONFIG: Dict[str, Any] = {
    "phases": [
        {
            "entries": ["north", "south"],
            "green": 20.0,
            "minGreen": 8.0,
            "maxGreen": 40.0,
        },
        {
            "entries": ["east", "west"],
            "green": 15.0,
            "minGreen": 6.0,
            "maxGreen": 30.0,
        },
    ],
    "yellow": 3.0,
    "allRed": 2.0,
    "offset": 0.0,
    "spillbackGuard": {
        "enabled": True,
        "stoppedThreshold": 2,
        "maxHold": 10.0,
    },
    "queueCap": {
        "enabled": True,
        "vehicles": 6,
    },
}


# ===========================================================================
# 1. Configuration bounds validation (SR-14, Plan Section 5.3)
# ===========================================================================


def test_spillback_guard_config_bounds() -> None:
    # Valid bounds
    cfg = SpillbackGuardConfig(enabled=True, stopped_threshold=2, max_hold=10.0)
    assert cfg.stopped_threshold == 2
    assert cfg.max_hold == 10.0

    # Bounds: stopped_threshold in 1..20
    with pytest.raises(ValueError, match="stopped_threshold must be in 1..20"):
        SpillbackGuardConfig(stopped_threshold=0)
    with pytest.raises(ValueError, match="stopped_threshold must be in 1..20"):
        SpillbackGuardConfig(stopped_threshold=21)

    # Bounds: max_hold in 0..60
    with pytest.raises(ValueError, match="max_hold must be in 0..60"):
        SpillbackGuardConfig(max_hold=-0.1)
    with pytest.raises(ValueError, match="max_hold must be in 0..60"):
        SpillbackGuardConfig(max_hold=60.1)


def test_queue_cap_config_bounds() -> None:
    # Valid bounds
    cfg = QueueCapConfig(enabled=True, vehicles=8)
    assert cfg.vehicles == 8

    # Bounds: vehicles in 1..50
    with pytest.raises(ValueError, match="vehicles must be in 1..50"):
        QueueCapConfig(vehicles=0)
    with pytest.raises(ValueError, match="vehicles must be in 1..50"):
        QueueCapConfig(vehicles=51)


# ===========================================================================
# 2. Spillback Guard: Sector Caching & Stopped Vehicle Counting (D-W2-5)
# ===========================================================================


def test_spillback_guard_sector_caching_4arm() -> None:
    net = _setup_roundabout_network()
    plan = build_metering_plan(_S5_BASE_CONFIG)
    guard = SpillbackGuard(plan, net)

    # All metered entries must have cached sector geometry
    for d in plan.metered_entries:
        assert d in guard._sector_cache
        theta_entry, width, next_exit = guard._sector_cache[d]
        assert width > 0.0

    # In standard 4-arm counter-clockwise:
    # North downstream exit is West
    assert guard._sector_cache[Direction.NORTH][2] == Direction.WEST
    # West downstream exit is South
    assert guard._sector_cache[Direction.WEST][2] == Direction.SOUTH
    # South downstream exit is East
    assert guard._sector_cache[Direction.SOUTH][2] == Direction.EAST
    # East downstream exit is North
    assert guard._sector_cache[Direction.EAST][2] == Direction.NORTH


def test_spillback_guard_stopped_vehicle_counting() -> None:
    net = _setup_roundabout_network()
    plan = build_metering_plan(_S5_BASE_CONFIG)
    guard = SpillbackGuard(plan, net)

    # Create dummy circulating lane
    conn_lane = Lane("conn_dummy_circ", 0.0, 15.0, -15.0, 0.0)
    active_vehicles: List[Vehicle] = []

    # 1. Vehicle stopped on the North->West sector
    v1 = _make_vehicle("v1", conn_lane, position=10.0, speed=0.5)
    active_vehicles.append(v1)

    assert guard.count_stopped_vehicles(Direction.NORTH, active_vehicles) == 1

    # 2. Moving vehicle (speed >= 2.0 m/s) should NOT be counted
    v2 = _make_vehicle("v2", conn_lane, position=15.0, speed=3.0)
    active_vehicles.append(v2)
    assert guard.count_stopped_vehicles(Direction.NORTH, active_vehicles) == 1

    # 3. Vehicle stopped on the first stretch of the West exit lane
    west_out = net.get_outgoing_approach(Direction.WEST)
    exit_lane = west_out.get_lanes()[0]
    v_exit = _make_vehicle("v_exit", exit_lane, position=15.0, speed=0.1)
    active_vehicles.append(v_exit)
    assert guard.count_stopped_vehicles(Direction.NORTH, active_vehicles) == 2

    # 4. Vehicle stopped beyond the first stretch (e.g. at 45m > 30m)
    v_far = _make_vehicle("v_far", exit_lane, position=45.0, speed=0.1)
    active_vehicles.append(v_far)
    assert guard.count_stopped_vehicles(Direction.NORTH, active_vehicles) == 2


# ===========================================================================
# 3. Spillback Guard: Activation, Release, and Hold Budget (SR-11, D-W2-3)
# ===========================================================================


def test_spillback_guard_activation_and_max_hold_enforcement() -> None:
    net = _setup_roundabout_network()
    plan = build_metering_plan(_S5_BASE_CONFIG)  # stoppedThreshold=2, maxHold=10.0
    cursor = MeteringPhaseCursor(plan)
    guard = SpillbackGuard(plan, net)

    conn_lane = Lane("conn_n_circ", 0.0, 15.0, -15.0, 0.0)
    active_vehicles: List[Vehicle] = []

    # Below threshold: 1 vehicle stopped
    v1 = _make_vehicle("v1", conn_lane, position=10.0, speed=0.5)
    active_vehicles.append(v1)

    held = guard.update(cursor, delta_time=1.0, active_vehicles=active_vehicles)
    assert Direction.NORTH not in held
    assert guard.cycle_hold_time[Direction.NORTH] == 0.0

    # Reach threshold: 2 vehicles stopped
    v2 = _make_vehicle("v2", conn_lane, position=20.0, speed=0.8)
    active_vehicles.append(v2)

    # 1. Guard activates!
    held = guard.update(cursor, delta_time=2.0, active_vehicles=active_vehicles)
    assert Direction.NORTH in held
    assert pytest.approx(guard.cycle_hold_time[Direction.NORTH], 0.01) == 2.0

    # 2. Hold budget accumulates
    held = guard.update(cursor, delta_time=5.0, active_vehicles=active_vehicles)
    assert Direction.NORTH in held
    assert pytest.approx(guard.cycle_hold_time[Direction.NORTH], 0.01) == 7.0

    # 3. Reaching and exceeding maxHold (10.0s)
    held = guard.update(cursor, delta_time=3.0, active_vehicles=active_vehicles)
    assert Direction.NORTH in held
    assert pytest.approx(guard.cycle_hold_time[Direction.NORTH], 0.01) == 10.0

    # 4. Budget exhausted: hold is released!
    held = guard.update(cursor, delta_time=1.0, active_vehicles=active_vehicles)
    assert Direction.NORTH not in held
    assert pytest.approx(guard.cycle_hold_time[Direction.NORTH], 0.01) == 10.0


def test_spillback_guard_hold_budget_resets_on_new_cycle() -> None:
    net = _setup_roundabout_network()
    plan = build_metering_plan(_S5_BASE_CONFIG)
    cursor = MeteringPhaseCursor(plan)
    guard = SpillbackGuard(plan, net)

    # Exhaust budget in cycle 0
    guard.cycle_hold_time[Direction.NORTH] = 10.0
    assert guard.cycle_hold_time[Direction.NORTH] == 10.0

    # Advance cursor across entire cycle into cycle 1
    cursor.advance(plan.cycle_duration + 1.0)
    assert cursor.cycle_number >= 1

    # Update guard: hold budget for North must reset to 0.0
    conn_lane = Lane("conn_test", 0.0, 15.0, -15.0, 0.0)
    v1 = _make_vehicle("v1", conn_lane, 10.0, 0.5)
    v2 = _make_vehicle("v2", conn_lane, 20.0, 0.5)

    held = guard.update(cursor, delta_time=1.0, active_vehicles=[v1, v2])
    # Should be held again with fresh budget
    assert Direction.NORTH in held
    assert pytest.approx(guard.cycle_hold_time[Direction.NORTH], 0.01) == 1.0


# ===========================================================================
# 4. Queue Cap: Disabled Behavior, Min-Green Protection, & Trigger (SR-12, D-W2-4)
# ===========================================================================


def test_queue_cap_disabled_behavior() -> None:
    cfg = copy.deepcopy(_S5_BASE_CONFIG)
    cfg["queueCap"]["enabled"] = False
    plan = build_metering_plan(cfg)
    net = _setup_roundabout_network()
    cursor = MeteringPhaseCursor(plan)
    qc = QueueCap(plan, net)

    # Populate red East approach with 10 stopped vehicles
    east_in = net.get_incoming_approach(Direction.EAST)
    lane = east_in.get_lanes()[0]
    for i in range(10):
        _make_vehicle(f"east_{i}", lane, position=50.0 - i * 5.0, speed=0.0)

    # Cursor in Phase 0 Green (North/South), East is Red
    cursor.advance(10.0)
    assert cursor.get_color(Direction.EAST) == "red"
    assert cursor.time_in_current_state >= 8.0

    # Queue cap is disabled: must return None and cursor stays green
    res = qc.check_and_trigger(cursor)
    assert res is None
    assert cursor.current_phase.color == "green"


def test_queue_cap_minimum_green_protection() -> None:
    plan = build_metering_plan(_S5_BASE_CONFIG)  # minGreen=8.0 for Phase 0
    net = _setup_roundabout_network()
    cursor = MeteringPhaseCursor(plan)
    qc = QueueCap(plan, net)

    east_in = net.get_incoming_approach(Direction.EAST)
    lane = east_in.get_lanes()[0]
    # Place 8 stopped vehicles (exceeds cap of 6)
    for i in range(8):
        _make_vehicle(f"east_{i}", lane, position=80.0 - i * 6.0, speed=0.0)

    # 1. At t=4.0s (less than minGreen 8.0s): cannot terminate early
    cursor.advance(4.0)
    assert cursor.current_phase.color == "green"
    assert cursor.time_in_current_state < 8.0

    res = qc.check_and_trigger(cursor)
    assert res is None
    assert cursor.current_phase.color == "green"

    # 2. Advance to t=8.0s (minGreen met): terminates green early!
    cursor.advance(4.0)
    assert cursor.time_in_current_state >= 8.0

    triggered_arm = qc.check_and_trigger(cursor)
    assert triggered_arm == Direction.EAST
    # Cursor has immediately transitioned to yellow
    assert cursor.current_phase.color == "yellow"
    assert cursor.time_in_current_state == 0.0


def test_queue_cap_no_retrigger_during_yellow_or_red() -> None:
    plan = build_metering_plan(_S5_BASE_CONFIG)
    net = _setup_roundabout_network()
    cursor = MeteringPhaseCursor(plan)
    qc = QueueCap(plan, net)

    east_in = net.get_incoming_approach(Direction.EAST)
    lane = east_in.get_lanes()[0]
    for i in range(8):
        _make_vehicle(f"east_{i}", lane, position=80.0 - i * 6.0, speed=0.0)

    # Advance cursor directly to yellow
    cursor.advance(20.0)  # green was 20s
    assert cursor.current_phase.color == "yellow"

    # Must not trigger during yellow
    assert qc.check_and_trigger(cursor) is None
    assert cursor.current_phase.color == "yellow"


# ===========================================================================
# 5. Full Controller Integration: Spillback Holds & Queue Cap (SR-11..13)
# ===========================================================================


def _make_full_controller_config(
    spillback_enabled: bool = True, queue_cap_enabled: bool = True
) -> Dict[str, Any]:
    cfg = copy.deepcopy(_S5_BASE_CONFIG)
    cfg["spillbackGuard"]["enabled"] = spillback_enabled
    cfg["queueCap"]["enabled"] = queue_cap_enabled
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
            "entryMetering": cfg,
        },
        "simulation": {"duration": 60.0, "timeStep": 0.1, "randomSeed": 42},
    }


def test_controller_spillback_hold_blocks_entry_and_records_telemetry() -> None:
    net = _setup_roundabout_network()
    ctrl_cfg = _make_full_controller_config(
        spillback_enabled=True, queue_cap_enabled=False
    )
    controller = SignalisedRoundaboutController(ctrl_cfg, net)

    north_in = net.get_incoming_approach(Direction.NORTH)
    north_lane = north_in.get_lanes()[0]
    head = _make_vehicle("head_north", north_lane, position=95.0, speed=5.0)

    # Simulate downstream ring blockage (2 stopped vehicles on North->West sector)
    conn_lane = Lane("conn_circ", 0.0, 15.0, -15.0, 0.0)
    c1 = _make_vehicle("c1", conn_lane, 10.0, 0.5)
    c2 = _make_vehicle("c2", conn_lane, 20.0, 0.5)
    active_vehicles = [head, c1, c2]

    # Tick controller: North is in green phase, but spillback guard holds it red!
    controller.update(0.1, active_vehicles)

    # 1. Gate reason must be ring_spillback_hold
    assert controller.gate.get_arm_reason(Direction.NORTH) == "ring_spillback_hold"
    # 2. Gate decision must be closed
    dec = controller.gate.allows(Direction.NORTH, north_lane, 0.1)
    assert dec.open is False
    assert dec.reason == "ring_spillback_hold"
    # 3. Virtual obstacle placed at give-way line
    assert north_lane.virtual_obstacle is not None
    assert north_lane.virtual_obstacle.position == north_lane.length
    # 4. Displayed signal colour must be 'red'
    assert controller.signals_state()[Direction.NORTH] == "red"
    # 5. Snapshot telemetry reflects spillback hold
    st = controller.get_state()
    arm_data = next(a for a in st["metering"]["arms"] if a["direction"] == "north")
    assert arm_data["color"] == "red"
    assert arm_data["reason"] == "ring_spillback_hold"
    assert st["metering"]["decisions"]["ring_spillback_hold"] >= 1


def test_controller_queue_cap_early_termination_integration() -> None:
    net = _setup_roundabout_network()
    ctrl_cfg = _make_full_controller_config(
        spillback_enabled=False, queue_cap_enabled=True
    )
    controller = SignalisedRoundaboutController(ctrl_cfg, net)

    # Populate red East approach with 8 stopped vehicles (cap is 6)
    east_in = net.get_incoming_approach(Direction.EAST)
    east_lane = east_in.get_lanes()[0]
    for i in range(8):
        _make_vehicle(f"east_{i}", east_lane, position=85.0 - i * 6.0, speed=0.0)

    # Run for 7.5s (< minGreen 8.0s) in 0.1s steps: stays in green
    for _ in range(75):
        controller.update(0.1, list(east_lane.get_vehicles()))
        assert controller.cursor.current_phase.color == "green"

    # Step at t=8.0s: minGreen reached, queue cap triggers early green termination!
    for _ in range(5):
        controller.update(0.1, list(east_lane.get_vehicles()))

    # Must have transitioned to yellow
    assert controller.cursor.current_phase.color == "yellow"
    # Event logged
    assert controller.gate.decision_counts["queue_cap"] == 1
    assert any(ev["reason"] == "queue_cap" for ev in controller.gate.recent_decisions)


# ===========================================================================
# 6. Starvation bounds under continuous guard holds (SR-19, D-W2-3)
# ===========================================================================


def test_starvation_bounds_under_continuous_guard_holds() -> None:
    """Verify that under 100% continuous ring blockage, an arm's continuous red

    time in any single cycle is strictly bounded by:
        planned_red + max_hold
    as guaranteed by D-W2-3 by construction.
    """
    net = _setup_roundabout_network()
    ctrl_cfg = _make_full_controller_config(
        spillback_enabled=True, queue_cap_enabled=False
    )
    controller = SignalisedRoundaboutController(ctrl_cfg, net)

    # Simulate permanently blocked ring
    conn_lane = Lane("conn_circ", 0.0, 15.0, -15.0, 0.0)
    c1 = _make_vehicle("c1", conn_lane, 10.0, 0.0)
    c2 = _make_vehicle("c2", conn_lane, 20.0, 0.0)
    active = [c1, c2]

    planned_red = controller.plan.planned_red_for(Direction.NORTH)
    max_hold = controller.plan.spillback_guard.max_hold
    yellow = controller.plan.yellow
    # Bound per sprint plan §3.3 (wait <= maxRed + yellow + allRed):
    # maximum continuous signal-denied duration cannot exceed non-green cycle time + max_hold
    max_allowed_denied = (
        controller.plan.cycle_duration
        - controller.plan.planned_green_for(Direction.NORTH)
    ) + max_hold

    dt = 0.5
    total_time = 0.0
    continuous_red_time = 0.0
    max_observed_red = 0.0

    # Run for 3 full cycles
    target_time = controller.plan.cycle_duration * 3.0
    while total_time < target_time:
        controller.update(dt, active)
        total_time += dt

        color = controller.signals_state()[Direction.NORTH]
        reason = controller.gate.get_arm_reason(Direction.NORTH)
        is_denied = (color != "green") or (reason == "ring_spillback_hold")

        if is_denied:
            continuous_red_time += dt
            max_observed_red = max(max_observed_red, continuous_red_time)
        else:
            continuous_red_time = 0.0

    # The maximum observed continuous signal-denied duration must not exceed max_allowed_denied
    assert max_observed_red <= max_allowed_denied + dt, (
        f"Starvation violated: observed red {max_observed_red:.2f}s "
        f"exceeds planned_red ({planned_red:.2f}s) + yellow ({yellow:.2f}s) + max_hold ({max_hold:.2f}s)"
    )


# ===========================================================================
# 7. Reset determinism and repeatability
# ===========================================================================


def test_spillback_and_queue_cap_reset_determinism() -> None:
    net = _setup_roundabout_network()
    ctrl_cfg = _make_full_controller_config(
        spillback_enabled=True, queue_cap_enabled=True
    )
    controller = SignalisedRoundaboutController(ctrl_cfg, net)

    east_in = net.get_incoming_approach(Direction.EAST)
    east_lane = east_in.get_lanes()[0]
    for i in range(8):
        _make_vehicle(f"east_{i}", east_lane, position=85.0 - i * 6.0, speed=0.0)

    # Run for 15s (triggers queue cap)
    for _ in range(150):
        controller.update(0.1, list(east_lane.get_vehicles()))

    state_after_run = copy.deepcopy(controller.get_state())
    assert state_after_run["metering"]["decisions"]["queue_cap"] >= 1

    # Reset
    controller.reset()
    state_after_reset = controller.get_state()

    assert state_after_reset["metering"]["decisions"]["queue_cap"] == 0
    assert state_after_reset["metering"]["recentDecisions"] == []
    assert state_after_reset["metering"]["cycleNumber"] == 0
    assert state_after_reset["metering"]["color"] == "green"
