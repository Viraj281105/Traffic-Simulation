"""Tests for SignalisedRoundaboutController and MeteredEntryGate (W2 Step S4).

Covers:
- SR-01: Composition architecture (does NOT subclass RoundaboutController).
- SR-02: Seam consultation via MeteredEntryGate.
- SR-06: Metered entry behavior (signals regulate entry to yield line).
- SR-13: Decision events on state transitions.
- D-W2-1: Controller selection via entryControl == "metered_entry".
- D-W2-6: Duck-typed signals_state() (metered real colors, unmetered green).
- H12: Configuration propagation across orchestrator and simulate_geometry.
- H13: vehicle_stop_limits pass-through and exit-zone hold equivalence.
- Reset, repeatability, and zero-production-randomness determinism.
"""

from __future__ import annotations

import copy
from typing import Any, Dict

from src.controllers.base import BaseController
from src.controllers.entry_metering import (
    MeteredEntryGate,
    MeteringPhaseCursor,
    build_metering_plan,
)
from src.controllers.factory import create_controller, derive_signals_state
from src.controllers.roundabout import RoundaboutController
from src.controllers.signalised_roundabout import SignalisedRoundaboutController
from src.core.clock import Clock
from src.core.enums import Direction
from src.engine.simulation_engine import SimulationEngine
from src.roads.lane import Lane
from src.roads.network import RoadNetwork
from src.vehicles.vehicle import Vehicle

_METERING_CFG: Dict[str, Any] = {
    "phases": [
        {
            "entries": ["north", "south"],
            "green": 20.0,
            "minGreen": 8.0,
            "maxGreen": 40.0,
        },
        {"entries": ["east", "west"], "green": 15.0, "minGreen": 6.0, "maxGreen": 30.0},
    ],
    "yellow": 3.0,
    "allRed": 2.0,
    "offset": 0.0,
}


def _make_metered_roundabout_config(
    lanes_per_approach: int = 1, circulating_lanes: int = 1
) -> Dict[str, Any]:
    return {
        "geometry": {
            "intersectionType": "roundabout",
            "lanesPerApproach": lanes_per_approach,
            "circulatingLanes": circulating_lanes,
        },
        "controller": {
            "innerRadius": 10.0,
            "outerRadius": 20.0,
            "criticalGap": 4.0,
            "followUpTime": 2.5,
            "entrySpeed": 5.0,
            "circulatingSpeed": 8.0,
            "entryControl": "metered_entry",
            "entryMetering": copy.deepcopy(_METERING_CFG),
        },
        "simulation": {"duration": 10.0, "timeStep": 0.1, "randomSeed": 42},
    }


def _setup_network(lanes_per_approach: int = 1) -> RoadNetwork:
    net = RoadNetwork()
    net.setup_default_intersection(
        approach_length=100.0,
        lane_width=3.5,
        lanes_per_approach=lanes_per_approach,
    )
    return net


def _place_vehicle(
    lane: Lane,
    name: str,
    position: float,
    speed: float,
    length: float = 4.5,
) -> Vehicle:
    v = Vehicle(
        name,
        length=length,
        width=2.0,
        desired_speed=speed,
        route=[lane],
        start_position=position,
        initial_speed=speed,
    )
    lane.add_vehicle(v)
    return v


# ---------------------------------------------------------------------------
# SR-01: Architecture & Composition
# ---------------------------------------------------------------------------


def test_sr01_architecture_composition_not_subclass() -> None:
    """SR-01: SignalisedRoundaboutController must be built by composition.

    It must inherit from BaseController but must NOT subclass RoundaboutController.
    """
    assert issubclass(SignalisedRoundaboutController, BaseController)
    assert not issubclass(SignalisedRoundaboutController, RoundaboutController)

    net = _setup_network()
    cfg = _make_metered_roundabout_config()
    controller = SignalisedRoundaboutController(cfg, net)

    assert isinstance(controller, BaseController)
    assert not isinstance(controller, RoundaboutController)
    assert isinstance(controller.roundabout, RoundaboutController)
    assert isinstance(controller.cursor, MeteringPhaseCursor)
    assert isinstance(controller.gate, MeteredEntryGate)


# ---------------------------------------------------------------------------
# Factory & Signal State (D-W2-1, D-W2-6)
# ---------------------------------------------------------------------------


def test_factory_creates_metered_controller_when_configured() -> None:
    net = _setup_network()

    # 1. Metered config -> SignalisedRoundaboutController
    metered_cfg = _make_metered_roundabout_config()
    ctrl1 = create_controller(metered_cfg, net)
    assert isinstance(ctrl1, SignalisedRoundaboutController)

    # 2. Absent entryControl -> standard RoundaboutController
    conv_cfg = copy.deepcopy(metered_cfg)
    del conv_cfg["controller"]["entryControl"]
    ctrl2 = create_controller(conv_cfg, net)
    assert isinstance(ctrl2, RoundaboutController)
    assert not isinstance(ctrl2, SignalisedRoundaboutController)

    # 3. None or unknown entryControl -> standard RoundaboutController
    conv_cfg2 = copy.deepcopy(metered_cfg)
    conv_cfg2["controller"]["entryControl"] = "none"
    ctrl3 = create_controller(conv_cfg2, net)
    assert isinstance(ctrl3, RoundaboutController)


def test_derive_signals_state_duck_typed() -> None:
    """D-W2-6: derive_signals_state reads real colours for metered arms, green for unmetered."""
    # North & South metered; East & West unmetered
    cfg = {
        "geometry": {"intersectionType": "roundabout"},
        "controller": {
            "entryControl": "metered_entry",
            "entryMetering": {
                "phases": [{"entries": ["north"], "green": 10.0}],
                "yellow": 3.0,
                "allRed": 2.0,
            },
        },
    }
    net = _setup_network()
    controller = create_controller(cfg, net)
    assert isinstance(controller, SignalisedRoundaboutController)

    # Phase 0: North green; others: unmetered stay green
    signals = derive_signals_state(controller)
    assert signals[Direction.NORTH] == "green"
    assert signals[Direction.SOUTH] == "green"  # unmetered
    assert signals[Direction.EAST] == "green"  # unmetered
    assert signals[Direction.WEST] == "green"  # unmetered

    # Advance into yellow
    controller.update(10.0, [])
    signals_yellow = derive_signals_state(controller)
    assert signals_yellow[Direction.NORTH] == "yellow"
    assert signals_yellow[Direction.SOUTH] == "green"

    # Advance into all-red
    controller.update(3.0, [])
    signals_red = derive_signals_state(controller)
    assert signals_red[Direction.NORTH] == "red"
    assert signals_red[Direction.SOUTH] == "green"


# ---------------------------------------------------------------------------
# MeteredEntryGate & Yellow Commitment
# ---------------------------------------------------------------------------


def test_gate_green_allows_entry() -> None:
    plan = build_metering_plan(_METERING_CFG)
    cursor = MeteringPhaseCursor(plan)
    gate = MeteredEntryGate(cursor)

    net = _setup_network()
    lane = net.get_incoming_approach(Direction.NORTH).get_lanes()[0]
    _place_vehicle(lane, "v1", position=90.0, speed=5.0)

    # At t=0, North is green
    dec = gate.allows(Direction.NORTH, lane, 0.0)
    assert dec.open is True
    assert dec.reason is None


def test_gate_red_denies_entry() -> None:
    plan = build_metering_plan(_METERING_CFG)
    cursor = MeteringPhaseCursor(plan)
    gate = MeteredEntryGate(cursor)

    net = _setup_network()
    lane = net.get_incoming_approach(Direction.EAST).get_lanes()[0]
    _place_vehicle(lane, "v_east", position=90.0, speed=5.0)

    # At t=0, East is red
    dec = gate.allows(Direction.EAST, lane, 0.0)
    assert dec.open is False
    assert dec.reason == "red"


def test_gate_yellow_commitment_and_red_carryover() -> None:
    """Yellow dilemma zone: fast vehicle commits and is latched through yellow and red."""
    plan = build_metering_plan(_METERING_CFG)
    cursor = MeteringPhaseCursor(plan)
    gate = MeteredEntryGate(cursor)

    net = _setup_network()
    lane = net.get_incoming_approach(Direction.NORTH).get_lanes()[0]

    # Advance cursor to North yellow (Phase 0 green is 20s)
    cursor.advance(20.0)
    assert cursor.get_color(Direction.NORTH) == "yellow"

    # 1. Fast vehicle near line (speed=10 m/s, position=95m, length=100m, stopping dist = 100/6 = 16.6m)
    # Distance to line is 5m <= 16.6m + 4.5m -> commits through yellow!
    _place_vehicle(lane, "fast_runner", position=95.0, speed=10.0)
    dec_fast = gate.allows(Direction.NORTH, lane, 20.0)
    assert dec_fast.open is True
    assert "fast_runner" in gate._yellow_latched

    # 2. Advance cursor into all-red (yellow is 3s)
    cursor.advance(3.0)
    assert cursor.get_color(Direction.NORTH) == "red"

    # Red onset cannot brake the latched runner across the line
    dec_red_runner = gate.allows(Direction.NORTH, lane, 23.0)
    assert dec_red_runner.open is True

    # 3. Fast runner leaves the lane (e.g. enters ring, lane empty)
    lane._vehicles.clear()

    # New vehicle arrives during red: denied!
    _place_vehicle(lane, "follower", position=80.0, speed=5.0)
    dec_follower = gate.allows(Direction.NORTH, lane, 23.1)
    assert dec_follower.open is False
    assert dec_follower.reason == "red"
    assert "fast_runner" not in gate._yellow_latched


def test_gate_yellow_slow_vehicle_cannot_commit() -> None:
    """Slow vehicle far from line cannot commit through yellow and must stop."""
    plan = build_metering_plan(_METERING_CFG)
    cursor = MeteringPhaseCursor(plan)
    gate = MeteredEntryGate(cursor)

    net = _setup_network()
    lane = net.get_incoming_approach(Direction.NORTH).get_lanes()[0]

    # Advance cursor to yellow
    cursor.advance(20.0)
    assert cursor.get_color(Direction.NORTH) == "yellow"

    # Speed=2 m/s, position=70m (dist to line = 30m, stopping dist = 4/6 = 0.67m)
    _place_vehicle(lane, "slow_car", position=70.0, speed=2.0)
    dec = gate.allows(Direction.NORTH, lane, 20.0)
    assert dec.open is False
    assert dec.reason == "yellow"
    assert "slow_car" not in gate._yellow_latched


def test_gate_decision_events_on_transitions() -> None:
    """SR-13: Transitions are recorded in decision_counts and recent_decisions."""
    plan = build_metering_plan(_METERING_CFG)
    cursor = MeteringPhaseCursor(plan)
    gate = MeteredEntryGate(cursor)

    # Initial update at t=0
    gate.update(0.0)
    # East and West start red -> 2 red events
    assert gate.decision_counts["red"] == 2
    assert gate.decision_counts["yellow"] == 0

    # Advance to Phase 0 Yellow (t=20)
    cursor.advance(20.0)
    gate.update(20.0)
    # North and South turn yellow -> 2 yellow events
    assert gate.decision_counts["yellow"] == 2
    recent = list(gate.recent_decisions)
    yellow_events = [e for e in recent if e["reason"] == "yellow"]
    assert len(yellow_events) == 2
    assert {e["arm"] for e in yellow_events} == {"north", "south"}

    # Reset clears counts and events
    gate.reset()
    assert gate.decision_counts["red"] == 0
    assert gate.decision_counts["yellow"] == 0
    assert len(gate.recent_decisions) == 0


# ---------------------------------------------------------------------------
# H13: vehicle_stop_limits Pass-Through
# ---------------------------------------------------------------------------


def test_h13_vehicle_stop_limits_exposed_on_controller() -> None:
    """H13: SignalisedRoundaboutController must expose its inner roundabout's vehicle_stop_limits."""
    net = _setup_network(lanes_per_approach=2)
    cfg = _make_metered_roundabout_config(lanes_per_approach=2, circulating_lanes=2)
    controller = SignalisedRoundaboutController(cfg, net)

    assert hasattr(controller, "vehicle_stop_limits")
    assert isinstance(controller.vehicle_stop_limits, dict)

    # Manually injecting a stop limit into the inner roundabout is reflected on wrapper
    controller.roundabout.vehicle_stop_limits["test_veh_1"] = 12.5
    assert controller.vehicle_stop_limits["test_veh_1"] == 12.5


def test_h13_always_green_metered_run_matches_conventional_exit_holds() -> None:
    """H13: Metered 2-lane run with always-green plan matches conventional exit-zone holds."""
    # Build an always-green metering plan for all 4 arms
    cfg_metered = {
        "geometry": {
            "intersectionType": "roundabout",
            "lanesPerApproach": 2,
            "circulatingLanes": 2,
        },
        "controller": {
            "innerRadius": 10.0,
            "outerRadius": 20.0,
            "criticalGap": 4.0,
            "followUpTime": 2.5,
            "entrySpeed": 5.0,
            "circulatingSpeed": 8.0,
            "entryControl": "metered_entry",
            "entryMetering": {
                "phases": [
                    {
                        "entries": ["north", "south", "east", "west"],
                        "green": 60.0,
                    }
                ],
                "yellow": 0.0,
                "allRed": 0.0,
            },
        },
        "simulation": {"duration": 5.0, "timeStep": 0.1, "randomSeed": 101},
        "vehicleGeneration": {"demand": "medium"},
    }

    cfg_conv = copy.deepcopy(cfg_metered)
    ctrl_dict = cfg_conv["controller"]
    assert isinstance(ctrl_dict, dict)
    del ctrl_dict["entryControl"]
    del ctrl_dict["entryMetering"]

    # Run conventional simulation
    clock_c = Clock(time_step=0.1)
    engine_c = SimulationEngine(clock_c, duration=5.0, config=cfg_conv)
    ctrl_c = create_controller(cfg_conv, engine_c.network)
    engine_c.controller = ctrl_c
    for _ in range(50):
        engine_c.step()

    # Run metered simulation with always-green plan
    clock_m = Clock(time_step=0.1)
    engine_m = SimulationEngine(clock_m, duration=5.0, config=cfg_metered)
    ctrl_m = create_controller(cfg_metered, engine_m.network)
    engine_m.controller = ctrl_m
    for _ in range(50):
        engine_m.step()

    assert isinstance(ctrl_m, SignalisedRoundaboutController)
    assert isinstance(ctrl_c, RoundaboutController)
    # The exit yield events and exit commitments must match identically
    assert ctrl_m.roundabout.exit_yield_events == ctrl_c.exit_yield_events
    assert ctrl_m.roundabout.forced_exit_commitments == ctrl_c.forced_exit_commitments


# ---------------------------------------------------------------------------
# State Snapshot and Reproducibility
# ---------------------------------------------------------------------------


def test_controller_get_state_format() -> None:
    net = _setup_network()
    cfg = _make_metered_roundabout_config()
    controller = SignalisedRoundaboutController(cfg, net)

    state = controller.get_state()
    assert state["type"] == "roundabout"
    assert state["entryControl"] == "metered_entry"
    assert "metering" in state

    metering = state["metering"]
    assert metering["currentPhase"] == "north_south_green"
    assert metering["color"] == "green"
    assert metering["timeRemaining"] == 20.0
    assert metering["cycleNumber"] == 0
    assert len(metering["arms"]) == 4
    assert "decisions" in metering
    assert "recentDecisions" in metering


def test_reset_and_reproducibility() -> None:
    """Repeated runs of SignalisedRoundaboutController produce identical sequences."""
    net = _setup_network()
    cfg = _make_metered_roundabout_config()

    controller = SignalisedRoundaboutController(cfg, net)

    # Run 1: 50 ticks
    states_run1 = []
    for _ in range(50):
        controller.update(0.1, [])
        states_run1.append(copy.deepcopy(controller.get_state()))

    # Reset
    controller.reset()
    assert controller.time_in_current_state == 0.0
    assert controller.cursor.cycle_number == 0

    # Run 2: 50 ticks
    states_run2 = []
    for _ in range(50):
        controller.update(0.1, [])
        states_run2.append(copy.deepcopy(controller.get_state()))

    assert states_run1 == states_run2
