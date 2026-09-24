import pytest

from src.controllers.base import BaseController
from src.controllers.fixed_time_signal import FixedTimeSignalController
from src.controllers.roundabout import RoundaboutController
from src.core.enums import Direction, TurnIntent
from src.roads.network import RoadNetwork
from src.vehicles.vehicle import Vehicle


def test_fixed_time_signal_transitions() -> None:
    """Test the new multi-phase signal controller cycles through phases correctly."""
    network = RoadNetwork()
    network.setup_default_intersection(
        approach_length=100.0, lane_width=3.5, lanes_per_approach=2
    )

    config = {
        "controller": {
            "straightRightDuration": 10,
            "leftDuration": 5,
            "yellowDuration": 3,
            "allRedDuration": 2,
        }
    }

    controller = FixedTimeSignalController(config, network)

    # Phase 0: north_straight_right (green, 10s)
    phase = controller.current_phase
    assert phase.name == "north_straight_right"
    assert phase.color == "green"
    assert controller.phase_time_remaining == 10.0

    # Advance by 5s — still in north_straight_right
    controller.update(5.0, [])
    assert controller.current_phase.name == "north_straight_right"
    assert controller.phase_time_remaining == 5.0

    # Advance by 5.1s — transition to north_left (5s)
    controller.update(5.1, [])
    assert controller.current_phase.name == "north_left"
    assert controller.current_phase.color == "green"
    assert pytest.approx(controller.phase_time_remaining, abs=0.2) == 4.9

    # Check signal state dictionary
    state = controller.get_state()
    assert state["type"] == "fixed_time_signal"
    assert state["currentPhase"] == "north_left"
    assert state["activeDirection"] == "north"

    # North should be green, others red
    for sig in state["signals"]:
        if sig["direction"] == "north":
            assert sig["color"] == "green"
            assert "left" in sig["allowedTurns"]
        else:
            assert sig["color"] == "red"

    # Advance through rest of north phases and verify south starts
    # north_left: 4.9s remaining
    controller.update(5.0, [])  # → north_yellow (3s)
    assert controller.current_phase.name == "north_yellow"

    controller.update(3.0, [])  # → all_red (2s)
    assert controller.current_phase.name == "all_red"

    controller.update(2.0, [])  # → south_straight_right
    assert controller.current_phase.name == "south_straight_right"
    assert controller.current_phase.color == "green"


def test_roundabout_controller() -> None:
    network = RoadNetwork()
    network.setup_default_intersection(
        approach_length=100.0, lane_width=3.5, lanes_per_approach=2
    )

    config = {
        "controller": {
            "innerRadius": 10.0,
            "outerRadius": 20.0,
            "criticalGap": 4.0,
            "circulatingSpeed": 8.0,
        }
    }

    controller = RoundaboutController(config, network)
    state = controller.get_state()
    assert state["type"] == "roundabout"
    assert state["innerRadius"] == 10.0
    assert state["outerRadius"] == 20.0
    assert state["gapAcceptance"] == 4.0


def test_roundabout_yielding() -> None:
    """Verifies that vehicles yield when time_gap < critical_gap, and proceed when gap > critical_gap."""
    from src.core.enums import Direction
    from src.roads.lane import Lane
    from src.vehicles.vehicle import Vehicle

    network = RoadNetwork()
    network.setup_default_intersection(100.0, 3.5, 2)
    config = {
        "controller": {
            "innerRadius": 10.0,
            "outerRadius": 20.0,
            "criticalGap": 4.0,
            "circulatingSpeed": 8.0,
        }
    }
    controller = RoundaboutController(config, network)

    # Place a circulating vehicle close to North entry point (approx 1.75, 15.0)
    # conn_circ lane ID must start with "conn" so that the controller identifies it as circulating
    conn_lane = Lane("conn_circ", 1.75, 16.0, 10.0, 16.0)
    circ_vehicle = Vehicle(
        "circ_1",
        length=4.5,
        width=2.0,
        desired_speed=8.0,
        route=[conn_lane],
        start_position=0.0,
        initial_speed=8.0,
    )

    # Update controller
    controller.update(0.1, [circ_vehicle])

    # Incoming North lane should have virtual obstacle active (yield)
    lane = network.get_incoming_approach(Direction.NORTH).get_lanes()[0]
    assert lane.virtual_obstacle is not None

    # Move circulating vehicle far away by updating its position along a long route
    conn_lane_far = Lane("conn_circ_far", 100.0, 100.0, 200.0, 100.0)
    circ_vehicle.lane = conn_lane_far
    circ_vehicle.position = 0.0

    controller.update(0.1, [circ_vehicle])

    # Obstacle should be cleared
    assert lane.virtual_obstacle is None


def test_base_controller_abstract_methods() -> None:
    class DummyController(BaseController):
        def update(self, delta_time: float, active_vehicles: list) -> None:
            super().update(delta_time, active_vehicles)

        def get_state(self) -> dict:
            return super().get_state()

        def reset(self) -> None:
            super().reset()

    dummy = DummyController()
    dummy.update(1.0, [])
    assert dummy.get_state() is None
    dummy.reset()


def test_fixed_time_signal_default_durations_match_canonical_contract() -> None:
    """With no duration keys present at all, the controller's fallback
    defaults must match the documented/canonical greenTime=30,
    yellowTime=4, allRedTime=2
    (docs/architecture/06-scenario-configuration-contract.md,
    ControllerSection, CONFIG_SCHEMA) — not the previously-mismatched
    straightRightDuration=15/yellowDuration=3 the controller used to fall
    back to when neither alias was present."""
    network = RoadNetwork()
    network.setup_default_intersection(
        approach_length=100.0, lane_width=3.5, lanes_per_approach=2
    )
    ctrl = FixedTimeSignalController({}, network)
    assert ctrl.straight_right_duration == 30.0
    assert ctrl.yellow_duration == 4.0
    assert ctrl.all_red_duration == 2.0
    assert ctrl.left_duration == 5.0


def test_fixed_time_signal_legacy_config_and_lane_intents() -> None:
    network = RoadNetwork()
    network.setup_default_intersection(
        approach_length=100.0, lane_width=3.5, lanes_per_approach=3
    )

    config_legacy = {
        "controller": {
            "greenDuration": 15.0,
            "yellowTime": 3.5,
            "allRedTime": 1.5,
        }
    }
    ctrl = FixedTimeSignalController(config_legacy, network)
    assert ctrl.straight_right_duration == 15.0
    assert ctrl.yellow_duration == 3.5
    assert ctrl.all_red_duration == 1.5

    config_legacy2 = {
        "controller": {
            "greenTime": 18.0,
        }
    }
    ctrl2 = FixedTimeSignalController(config_legacy2, network)
    assert ctrl2.straight_right_duration == 18.0

    # Test _lane_turn_intent
    assert len(FixedTimeSignalController._lane_turn_intent(0, 1)) == 3
    assert FixedTimeSignalController._lane_turn_intent(0, 2) == (TurnIntent.LEFT,)
    assert FixedTimeSignalController._lane_turn_intent(1, 2) == (
        TurnIntent.STRAIGHT,
        TurnIntent.RIGHT,
    )
    assert FixedTimeSignalController._lane_turn_intent(0, 3) == (TurnIntent.LEFT,)
    assert FixedTimeSignalController._lane_turn_intent(1, 3) == (TurnIntent.STRAIGHT,)
    assert FixedTimeSignalController._lane_turn_intent(2, 3) == (TurnIntent.RIGHT,)


def test_fixed_time_signal_cycle_wrap_and_missing_approach() -> None:
    network = RoadNetwork()
    # Empty network without approaches triggers KeyError in _apply_signals and get_state
    config = {
        "controller": {
            "straightRightDuration": 1.0,
            "leftDuration": 1.0,
            "yellowDuration": 1.0,
            "allRedDuration": 1.0,
        }
    }
    ctrl = FixedTimeSignalController(config, network)
    state = ctrl.get_state()
    assert len(state["signals"]) == 4

    # Advance through each phase step by step to wrap around cycle
    initial_cycles = ctrl.cycle_number
    for p in ctrl.phases:
        ctrl.update(p.duration + 0.01, [])
    assert ctrl.cycle_number > initial_cycles


def test_fixed_time_signal_phase_sequence_single_direction_groups() -> None:
    """phaseSequence entries n/s/e/w each activate exactly one approach."""
    network = RoadNetwork()
    network.setup_default_intersection(
        approach_length=100.0, lane_width=3.5, lanes_per_approach=2
    )
    config = {
        "controller": {
            "straightRightDuration": 10,
            "yellowDuration": 3,
            "allRedDuration": 2,
            "phaseSequence": ["n_green", "n_yellow", "all_red", "e_green"],
        }
    }
    controller = FixedTimeSignalController(config, network)
    names = [p.name for p in controller.phases]
    assert names == ["n_green", "n_yellow", "all_red", "e_green"]
    assert controller.phases[0].directions == (Direction.NORTH,)
    assert controller.phases[0].color == "green"
    assert controller.phases[0].duration == 10.0
    assert controller.phases[1].color == "yellow"
    assert controller.phases[1].duration == 3.0
    assert controller.phases[2].directions == ()
    assert controller.phases[2].duration == 2.0
    assert controller.phases[3].directions == (Direction.EAST,)


def test_fixed_time_signal_phase_sequence_paired_group_synonyms() -> None:
    """ns/sn and ew/we are order-invariant synonyms for the same paired
    approach group."""
    network = RoadNetwork()
    network.setup_default_intersection(
        approach_length=100.0, lane_width=3.5, lanes_per_approach=2
    )
    config = {
        "controller": {
            "phaseSequence": ["ns_green", "sn_green", "ew_green", "we_green"],
        }
    }
    controller = FixedTimeSignalController(config, network)
    assert controller.phases[0].directions == (Direction.NORTH, Direction.SOUTH)
    assert controller.phases[1].directions == (Direction.NORTH, Direction.SOUTH)
    assert controller.phases[2].directions == (Direction.EAST, Direction.WEST)
    assert controller.phases[3].directions == (Direction.EAST, Direction.WEST)
    # All turn intents (including permissive left) are allowed in a paired
    # group phase — arbitrated by ConflictManager, not a protected sub-phase.
    assert set(controller.phases[0].allowed_turns) == {
        TurnIntent.LEFT,
        TurnIntent.STRAIGHT,
        TurnIntent.RIGHT,
    }


def test_fixed_time_signal_phase_sequence_invalid_entry_raises() -> None:
    network = RoadNetwork()
    network.setup_default_intersection(
        approach_length=100.0, lane_width=3.5, lanes_per_approach=2
    )
    config = {"controller": {"phaseSequence": ["ns_green", "bogus_entry"]}}
    with pytest.raises(ValueError, match="Unsupported phaseSequence entry"):
        FixedTimeSignalController(config, network)


def test_fixed_time_signal_offset_shifts_initial_phase() -> None:
    """A non-zero `offset` seeds the controller's phase cursor forward at
    construction time (reset() calls `_advance_by(offset % total_cycle)`),
    so two controllers built from the identical phaseSequence/durations but
    different offsets must actually start the simulation at different
    points in the signal cycle -- not merely store/parse the offset value.

    Cycle: ["ns_green" (10s), "ew_green" (10s)] -> total duration 20s.
    """
    network = RoadNetwork()
    network.setup_default_intersection(
        approach_length=100.0, lane_width=3.5, lanes_per_approach=2
    )

    controller_config = {
        "straightRightDuration": 10.0,
        "phaseSequence": ["ns_green", "ew_green"],
    }

    # No offset: cycle starts at the first configured phase, elapsed 0s.
    baseline = FixedTimeSignalController({"controller": controller_config}, network)
    assert baseline.current_phase_idx == 0
    assert baseline.current_phase.name == "ns_green"
    assert baseline.current_phase.directions == (Direction.NORTH, Direction.SOUTH)
    assert baseline.time_in_current_state == 0.0

    # offset == exactly one full phase duration (10s): the controller must
    # start one phase ahead of the baseline, at 0s elapsed into that phase.
    offset_10 = FixedTimeSignalController(
        {"controller": {**controller_config, "offset": 10.0}}, network
    )
    assert offset_10.current_phase_idx == 1
    assert offset_10.current_phase.name == "ew_green"
    assert offset_10.current_phase.directions == (Direction.EAST, Direction.WEST)
    assert offset_10.time_in_current_state == 0.0
    assert offset_10.phase_time_remaining == 10.0

    # A partial-phase offset (14s = one full phase + 4s) must leave a
    # matching remainder of time_in_current_state within the next phase,
    # not just snap to the next phase boundary.
    offset_14 = FixedTimeSignalController(
        {"controller": {**controller_config, "offset": 14.0}}, network
    )
    assert offset_14.current_phase_idx == 1
    assert offset_14.current_phase.name == "ew_green"
    assert offset_14.time_in_current_state == 4.0
    assert offset_14.phase_time_remaining == 6.0

    # offset wraps modulo the total cycle duration (20s): offset=30
    # (== 20 + 10) must land at exactly the same state as offset=10.
    offset_30 = FixedTimeSignalController(
        {"controller": {**controller_config, "offset": 30.0}}, network
    )
    assert offset_30.current_phase_idx == offset_10.current_phase_idx
    assert offset_30.current_phase.name == offset_10.current_phase.name
    assert offset_30.time_in_current_state == offset_10.time_in_current_state

    # The offset's effect is externally visible through get_state(), which
    # is what the API/frontend actually observe -- not just internal state.
    state = offset_10.get_state()
    assert state["currentPhase"] == "ew_green"
    assert state["activeDirection"] == "east+west"
    for sig in state["signals"]:
        if sig["direction"] in ("east", "west"):
            assert sig["color"] == "green"
        else:
            assert sig["color"] == "red"


def test_fixed_time_signal_ns_ew_override_absent_is_backward_compatible() -> None:
    """Core backward-compatibility guard for asymmetric timing: a config
    that sets neither nsGreenDuration nor ewGreenDuration must build the
    exact same phases (same durations, in both the default cycle and a
    configured phaseSequence) as before those fields existed."""
    network = RoadNetwork()
    network.setup_default_intersection(
        approach_length=100.0, lane_width=3.5, lanes_per_approach=2
    )

    # Default (no phaseSequence) cycle.
    default_ctrl = FixedTimeSignalController(
        {"controller": {"straightRightDuration": 22.0}}, network
    )
    for phase in default_ctrl.phases:
        if phase.name.endswith("_straight_right"):
            assert phase.duration == 22.0

    # phaseSequence-driven cycle.
    seq_ctrl = FixedTimeSignalController(
        {
            "controller": {
                "straightRightDuration": 22.0,
                "phaseSequence": ["ns_green", "ns_yellow", "all_red", "ew_green"],
            }
        },
        network,
    )
    assert seq_ctrl.phases[0].duration == 22.0  # ns_green
    assert seq_ctrl.phases[3].duration == 22.0  # ew_green


def test_fixed_time_signal_asymmetric_ns_ew_default_cycle() -> None:
    """NS legs (north, south) use nsGreenDuration; EW legs (east, west) use
    ewGreenDuration; left/yellow/all-red are untouched by either override."""
    network = RoadNetwork()
    network.setup_default_intersection(
        approach_length=100.0, lane_width=3.5, lanes_per_approach=2
    )
    config = {
        "controller": {
            "straightRightDuration": 30.0,  # must be ignored for N/S/E/W green
            "nsGreenDuration": 30.0,
            "ewGreenDuration": 20.0,
            "leftDuration": 5.0,
            "yellowDuration": 4.0,
            "allRedDuration": 2.0,
        }
    }
    ctrl = FixedTimeSignalController(config, network)

    durations_by_phase = {p.name: p.duration for p in ctrl.phases}
    assert durations_by_phase["north_straight_right"] == 30.0
    assert durations_by_phase["south_straight_right"] == 30.0
    assert durations_by_phase["east_straight_right"] == 20.0
    assert durations_by_phase["west_straight_right"] == 20.0

    # Left/yellow/all-red durations are unaffected by the NS/EW overrides.
    for phase in ctrl.phases:
        if phase.name.endswith("_left"):
            assert phase.duration == 5.0
        elif phase.name.endswith("_yellow"):
            assert phase.duration == 4.0
        elif phase.name == "all_red":
            assert phase.duration == 2.0


def test_fixed_time_signal_asymmetric_ns_ew_phase_sequence() -> None:
    """Paired ns_green/ew_green groups in a configured phaseSequence pick up
    the matching corridor override; yellow/all_red stay uniform."""
    network = RoadNetwork()
    network.setup_default_intersection(
        approach_length=100.0, lane_width=3.5, lanes_per_approach=2
    )
    config = {
        "controller": {
            "nsGreenDuration": 35.0,
            "ewGreenDuration": 18.0,
            "yellowDuration": 4.0,
            "allRedDuration": 2.0,
            "phaseSequence": [
                "ns_green",
                "ns_yellow",
                "all_red",
                "ew_green",
                "ew_yellow",
                "all_red",
            ],
        }
    }
    ctrl = FixedTimeSignalController(config, network)

    assert ctrl.phases[0].name == "ns_green"
    assert ctrl.phases[0].duration == 35.0
    assert ctrl.phases[1].name == "ns_yellow"
    assert ctrl.phases[1].duration == 4.0  # unaffected by nsGreenDuration
    assert ctrl.phases[2].duration == 2.0  # all_red unaffected

    assert ctrl.phases[3].name == "ew_green"
    assert ctrl.phases[3].duration == 18.0
    assert ctrl.phases[4].name == "ew_yellow"
    assert ctrl.phases[4].duration == 4.0


def test_fixed_time_signal_asymmetric_single_direction_groups() -> None:
    """Single-direction phaseSequence groups (n/s/e/w, not just paired
    ns/ew) still resolve to the correct corridor override: n and s both use
    nsGreenDuration, e and w both use ewGreenDuration."""
    network = RoadNetwork()
    network.setup_default_intersection(
        approach_length=100.0, lane_width=3.5, lanes_per_approach=2
    )
    config = {
        "controller": {
            "nsGreenDuration": 25.0,
            "ewGreenDuration": 15.0,
            "phaseSequence": ["n_green", "s_green", "e_green", "w_green"],
        }
    }
    ctrl = FixedTimeSignalController(config, network)
    assert [p.duration for p in ctrl.phases] == [25.0, 25.0, 15.0, 15.0]


def test_fixed_time_signal_asymmetric_phase_transitions() -> None:
    """Dynamic behavioural check: update() must actually honour the
    asymmetric durations tick by tick, not just when phases are built."""
    network = RoadNetwork()
    network.setup_default_intersection(
        approach_length=100.0, lane_width=3.5, lanes_per_approach=2
    )
    config = {
        "controller": {
            "nsGreenDuration": 30.0,
            "ewGreenDuration": 20.0,
            "yellowDuration": 4.0,
            "allRedDuration": 2.0,
            "phaseSequence": [
                "ns_green",
                "ns_yellow",
                "all_red",
                "ew_green",
                "ew_yellow",
                "all_red",
            ],
        }
    }
    ctrl = FixedTimeSignalController(config, network)

    assert ctrl.current_phase.name == "ns_green"
    assert ctrl.phase_time_remaining == 30.0

    ctrl.update(29.9, [])
    assert ctrl.current_phase.name == "ns_green"
    assert pytest.approx(ctrl.phase_time_remaining, abs=1e-6) == 0.1

    ctrl.update(0.1, [])  # exactly the 30s NS-green boundary
    assert ctrl.current_phase.name == "ns_yellow"

    ctrl.update(4.0, [])  # ns_yellow (4s) -> all_red
    assert ctrl.current_phase.name == "all_red"

    ctrl.update(2.0, [])  # all_red (2s) -> ew_green
    assert ctrl.current_phase.name == "ew_green"
    assert ctrl.phase_time_remaining == 20.0

    ctrl.update(19.9, [])
    assert ctrl.current_phase.name == "ew_green"
    ctrl.update(0.1, [])  # exactly the 20s EW-green boundary
    assert ctrl.current_phase.name == "ew_yellow"


def test_fixed_time_signal_offset_with_asymmetric_durations() -> None:
    """The offset math (_advance_by) must work correctly when the two green
    phases it is stepping through have unequal durations -- the existing
    offset test only ever used equal (10s/10s) phases."""
    network = RoadNetwork()
    network.setup_default_intersection(
        approach_length=100.0, lane_width=3.5, lanes_per_approach=2
    )
    controller_config = {
        "nsGreenDuration": 30.0,
        "ewGreenDuration": 20.0,
        "phaseSequence": ["ns_green", "ew_green"],
    }
    # Total cycle = 30 + 20 = 50s.

    # An offset landing inside the (longer) NS phase.
    offset_15 = FixedTimeSignalController(
        {"controller": {**controller_config, "offset": 15.0}}, network
    )
    assert offset_15.current_phase_idx == 0
    assert offset_15.current_phase.name == "ns_green"
    assert offset_15.time_in_current_state == 15.0
    assert offset_15.phase_time_remaining == 15.0

    # An offset landing inside the (shorter) EW phase.
    offset_35 = FixedTimeSignalController(
        {"controller": {**controller_config, "offset": 35.0}}, network
    )
    assert offset_35.current_phase_idx == 1
    assert offset_35.current_phase.name == "ew_green"
    assert offset_35.time_in_current_state == 5.0
    assert offset_35.phase_time_remaining == 15.0

    # Offset wraps modulo the (asymmetric) 50s cycle: 65 == 50 + 15 must
    # match offset_15 exactly.
    offset_65 = FixedTimeSignalController(
        {"controller": {**controller_config, "offset": 65.0}}, network
    )
    assert offset_65.current_phase_idx == offset_15.current_phase_idx
    assert offset_65.time_in_current_state == offset_15.time_in_current_state


def test_fixed_time_signal_ns_ew_duration_invalid_values_rejected_by_schema() -> None:
    """The controller itself performs no runtime bounds-checking on any
    duration field (matching existing behaviour for straightRightDuration
    etc.) -- validation for zero/negative values is enforced at the
    schema/Pydantic layer, exercised here directly against CONFIG_SCHEMA."""
    import jsonschema

    from src.main import CONFIG_SCHEMA

    base_config = {
        "simulation": {"duration": 60, "timeStep": 0.1},
        "geometry": {"intersectionType": "fixed_time_signal"},
    }

    for invalid_value in (0, -5.0):
        for field in ("nsGreenDuration", "ewGreenDuration"):
            bad_config = {
                **base_config,
                "controller": {field: invalid_value},
            }
            with pytest.raises(jsonschema.ValidationError):
                jsonschema.validate(instance=bad_config, schema=CONFIG_SCHEMA)


def test_roundabout_missing_approach_and_yielding_metrics() -> None:
    network = RoadNetwork()
    network.setup_default_intersection(
        approach_length=50.0, lane_width=3.5, lanes_per_approach=1
    )
    config = {
        "controller": {
            "innerRadius": 8.0,
            "outerRadius": 16.0,
            "criticalGap": 3.0,
        }
    }
    ctrl = RoundaboutController(config, network)
    ctrl.reset()

    # Add a stopped vehicle near end of north lane
    lane = network.get_incoming_approach(Direction.NORTH).get_lanes()[0]
    veh = Vehicle(
        "v_yield",
        length=4.0,
        width=2.0,
        desired_speed=10.0,
        route=[lane],
        start_position=46.0,
        initial_speed=0.0,
    )
    lane.add_vehicle(veh)

    state = ctrl.get_state()
    assert state["yieldingCount"] == 1

    # Empty network KeyError branch
    empty_net = RoadNetwork()
    ctrl_empty = RoundaboutController(config, empty_net)
    ctrl_empty.reset()
    ctrl_empty.update(0.1, [])
    state_empty = ctrl_empty.get_state()
    assert state_empty["yieldingCount"] == 0


def test_roundabout_circular_leader_detection() -> None:
    from src.core.enums import Direction, TurnIntent
    from src.vehicles.router import find_leader

    network = RoadNetwork()
    network.setup_default_intersection(
        approach_length=100.0, lane_width=3.5, lanes_per_approach=2, is_roundabout=True
    )
    # Vehicle A is circulating in the roundabout
    lane_a = network.generate_route(Direction.NORTH, 0, TurnIntent.STRAIGHT)[1]
    veh_a = Vehicle(
        "veh_a",
        length=4.5,
        width=2.0,
        desired_speed=8.0,
        route=[lane_a],
        start_position=5.0,
    )
    lane_a.add_vehicle(veh_a)

    # Vehicle B is behind Vehicle A on the roundabout
    lane_b = network.generate_route(Direction.EAST, 0, TurnIntent.STRAIGHT)[1]
    veh_b = Vehicle(
        "veh_b",
        length=4.5,
        width=2.0,
        desired_speed=8.0,
        route=[lane_b],
        start_position=0.0,
    )
    lane_b.add_vehicle(veh_b)

    leader, gap = find_leader(veh_b, network=network, active_vehicles=[veh_a, veh_b])
    # It should identify veh_a as the leader
    assert leader is veh_a


def _entry_controller(lanes: int = 1):
    network = RoadNetwork()
    network.setup_default_intersection(
        approach_length=200.0, lane_width=3.5, lanes_per_approach=lanes
    )
    config = {
        "controller": {
            "innerRadius": 10.0,
            "outerRadius": 20.0,
            "criticalGap": 4.0,
            "followUpTime": 0.0,
            "entrySpeed": 5.0,
            "circulatingSpeed": 8.0,
        }
    }
    controller = RoundaboutController(config, network)
    lane = network.get_incoming_approach(Direction.NORTH).get_lanes()[0]
    return network, controller, lane


def _vehicle(vid: str, lane, position: float, speed: float, desired: float = 25.0):
    veh = Vehicle(
        vid,
        length=4.0,
        width=2.0,
        desired_speed=desired,
        route=[lane],
        start_position=position,
        initial_speed=speed,
    )
    lane.add_vehicle(veh)
    return veh


def _build_stalled_queue(lane, count: int = 6):
    """Stopped chain from the give-way line back ~6 vehicles (~32 m)."""
    return [
        _vehicle(f"q{i}", lane, lane.length - 2.0 - i * 6.0, 0.0, 8.0)
        for i in range(count)
    ]


def _run_until_congested(controller, lane) -> None:
    from src.controllers.roundabout import _STALL_ON_TIME

    for _ in range(int(_STALL_ON_TIME / 0.1) + 5):
        controller.update(0.1, list(lane.get_vehicles()))


def test_roundabout_free_flow_entry_speed_cap() -> None:
    """Free-flowing approach: untouched far out, entrySpeed over the last 60 m.

    No traffic, so the congestion cap must stay out of it: the behaviour is
    exactly the fixed entry-zone cap.
    """
    from src.controllers.roundabout import _ENTRY_APPROACH_ZONE

    _, controller, lane = _entry_controller()

    veh = _vehicle("far", lane, 0.0, 20.0, desired=15.0)
    controller.update(0.1, [veh])
    assert veh.desired_speed == 15.0  # far from the line

    veh.position = lane.length - _ENTRY_APPROACH_ZONE - 1.0
    controller.update(0.1, [veh])
    assert veh.desired_speed == 15.0  # just outside the zone

    for dist in (_ENTRY_APPROACH_ZONE, 30.0, 2.0):
        veh.position = lane.length - dist
        controller.update(0.1, [veh])
        assert veh.desired_speed == 5.0
    assert controller._congested.get("north", False) is False

    # A slower vehicle's desired speed is left alone (cap, not a floor).
    slow = _vehicle("slow", lane, lane.length - 1.0, 3.0, desired=3.0)
    controller.update(0.1, [veh, slow])
    assert slow.desired_speed == 3.0


def test_roundabout_circulating_cap_and_exit_restore() -> None:
    """Circulating -> circulatingSpeed, exit -> the vehicle's own speed back."""
    from src.roads.lane import Lane

    network, controller, lane = _entry_controller()
    veh = _vehicle("v", lane, lane.length - 2.0, 10.0, desired=15.0)
    controller.update(0.1, [veh])
    assert veh.desired_speed < 15.0

    lane.remove_vehicle(veh)
    conn_lane = Lane("conn_north_0_straight", 0.0, 0.0, 10.0, 0.0)
    veh.lane = conn_lane
    controller.update(0.1, [veh])
    assert veh.desired_speed == 8.0

    slow = _vehicle("s", lane, 0.0, 3.0, desired=3.0)
    slow.lane = conn_lane
    controller.update(0.1, [veh, slow])
    assert slow.desired_speed == 3.0

    out_lane = network.get_outgoing_approach(Direction.SOUTH).get_lanes()[0]
    veh.lane = out_lane
    controller.update(0.1, [veh])
    assert veh.desired_speed == 15.0


def test_roundabout_short_or_discharging_queue_does_not_trigger_cap() -> None:
    """A short standing queue, or a long one that is discharging, is normal."""
    _, controller, lane = _entry_controller()
    _build_stalled_queue(lane, count=2)  # tail ~8 m: below the trigger distance
    approaching = _vehicle("app", lane, lane.length - 70.0, 20.0)
    for _ in range(200):  # 20 s
        controller.update(0.1, list(lane.get_vehicles()))
    assert approaching.desired_speed == 25.0
    assert controller._congested.get("north") is False

    # Long queue, but the ring keeps discharging it: never stalled.
    _, controller, lane = _entry_controller()
    _build_stalled_queue(lane, count=6)
    for _ in range(200):
        controller._last_entry_time[lane.lane_id] = controller.time_in_current_state
        controller.update(0.1, list(lane.get_vehicles()))
    assert controller._congested.get("north") is False


def test_roundabout_congestion_caps_approach_at_the_queue_tail() -> None:
    """Stalled ring + queue past the trigger distance -> entrySpeed at the tail."""
    from src.controllers.roundabout import _APPROACH_DECEL

    _, controller, lane = _entry_controller()
    queue = _build_stalled_queue(lane, count=6)
    tail_dist = lane.length - queue[-1].position
    assert tail_dist > 20.0
    approaching = _vehicle("app", lane, lane.length - 70.0, 20.0)

    # Before the stall time elapses nothing is congested.
    controller.update(0.1, list(lane.get_vehicles()))
    assert controller._congested["north"] is False

    _run_until_congested(controller, lane)
    assert controller._congested["north"] is True

    dist_to_line = lane.length - approaching.position
    expected = (5.0**2 + 2.0 * _APPROACH_DECEL * (dist_to_line - tail_dist)) ** 0.5
    assert approaching.desired_speed == pytest.approx(expected)
    assert approaching.desired_speed < 25.0  # free flow would leave it untouched

    # Vehicles inside the queue are held at entrySpeed or below.
    assert queue[-1].desired_speed <= 5.0


def test_roundabout_congestion_releases_with_hysteresis() -> None:
    """Held inside the hysteresis band; released once the queue is gone, and the
    vehicle's own desired speed is restored."""
    _, controller, lane = _entry_controller()
    queue = _build_stalled_queue(lane, count=6)
    approaching = _vehicle("app", lane, lane.length - 70.0, 20.0)
    _run_until_congested(controller, lane)
    assert controller._congested["north"] is True
    capped = approaching.desired_speed

    # Queue shrinks to between the release and trigger distances (tail ~14 m):
    # the state must NOT drop.
    for veh in queue[3:]:
        lane.remove_vehicle(veh)
    controller.update(0.1, list(lane.get_vehicles()))
    controller.update(3.5, list(lane.get_vehicles()))
    assert controller._congested["north"] is True

    # Queue clears entirely: released, cap lifts.
    for veh in list(queue[:3]):
        lane.remove_vehicle(veh)
    controller.update(0.1, list(lane.get_vehicles()))
    assert controller._congested["north"] is False
    assert approaching.desired_speed == 25.0  # own speed restored
    assert approaching.desired_speed > capped


def test_roundabout_congestion_state_does_not_chatter() -> None:
    """Queue length jittering across the trigger distance must not flip the
    state: once latched it stays latched while the tail is beyond the release
    distance."""
    _, controller, lane = _entry_controller()
    queue = _build_stalled_queue(lane, count=6)
    _run_until_congested(controller, lane)
    assert controller._congested["north"] is True

    transitions = 0
    prev = True
    for i in range(300):
        # Tail jitters between 14 m and 32 m: straddles the 20 m trigger but
        # stays above the 10 m release distance.
        queue[-1].position = lane.length - (14.0 if i % 2 else 32.0)
        controller.update(0.1, list(lane.get_vehicles()))
        now = controller._congested["north"]
        if now != prev:
            transitions += 1
        prev = now
    assert transitions == 0


def test_roundabout_reset_clears_congestion_state() -> None:
    _, controller, lane = _entry_controller()
    _build_stalled_queue(lane, count=6)
    _run_until_congested(controller, lane)
    assert controller._congested["north"] is True

    controller.reset()
    assert controller._congested == {}
    assert controller._congested_since == {}
    assert controller._queue_since == {}
    assert controller._approach_ctx == {}
    assert controller._pre_entry_desired_speed == {}


def test_roundabout_follow_up_time_gates_consecutive_entries() -> None:
    """followUpTime holds the next vehicle at a lane's entry for a spacing
    period after the previous vehicle from that lane completed its entry
    (actually left the lane), even with no conflicting circulating
    traffic."""
    network = RoadNetwork()
    network.setup_default_intersection(
        approach_length=100.0, lane_width=3.5, lanes_per_approach=1
    )
    config = {
        "controller": {
            "innerRadius": 10.0,
            "outerRadius": 20.0,
            "criticalGap": 4.0,
            "followUpTime": 2.0,
            "entrySpeed": 5.0,
            "circulatingSpeed": 8.0,
        }
    }
    controller = RoundaboutController(config, network)
    lane = network.get_incoming_approach(Direction.NORTH).get_lanes()[0]

    veh_a = Vehicle(
        "v_a",
        length=4.0,
        width=2.0,
        desired_speed=5.0,
        route=[lane],
        start_position=lane.length - 1.0,
        initial_speed=5.0,
    )
    lane.add_vehicle(veh_a)

    # No circulating traffic, so the gap-acceptance check alone clears
    # veh_a to enter.
    controller.update(0.1, [veh_a])
    assert lane.virtual_obstacle is None

    # veh_a actually crosses into the roundabout (leaves this lane), and
    # veh_b arrives right behind it at the entry.
    lane.remove_vehicle(veh_a)
    veh_b = Vehicle(
        "v_b",
        length=4.0,
        width=2.0,
        desired_speed=5.0,
        route=[lane],
        start_position=lane.length - 1.0,
        initial_speed=5.0,
    )
    lane.add_vehicle(veh_b)

    # veh_a's departure is only detected at the end of this tick (after
    # this tick's yield decision is made from the pre-departure state), so
    # veh_b is still cleared on this one tick.
    controller.update(0.1, [veh_b])
    assert lane.virtual_obstacle is None

    # From the next tick on, follow_up_time (measured from veh_a's
    # detected departure) gates veh_b even with no circulating conflict.
    controller.update(0.1, [veh_b])
    assert lane.virtual_obstacle is not None

    # After follow_up_time has elapsed, entry is clear again.
    controller.update(2.5, [veh_b])
    assert lane.virtual_obstacle is None
