"""Real-world junction geometry (V1.5): roads/junction_geometry.py and the
network it lays out."""

from __future__ import annotations

import math

import pytest

from src.core.enums import Direction, TurnIntent
from src.roads.junction_geometry import (
    MAX_SLOT_DEVIATION,
    ArmGeometry,
    JunctionGeometry,
    assign_slots,
    build_junction_geometry,
    geometry_errors,
    roundabout_geometry_errors,
    signal_stop_distances,
    slot_deviation,
    uturn_lanes_needed,
    uturn_radius,
)
from src.roads.network import RoadNetwork

N, E, S, W = Direction.NORTH, Direction.EAST, Direction.SOUTH, Direction.WEST


def _geometry(bearings=None, lanes=None, widths=None, arms=None, length=200.0):
    counts = {d: (lanes or {}).get(d, 1) for d in Direction}
    return build_junction_geometry(
        counts,
        {d: length for d in Direction},
        3.5,
        arms=arms,
        bearings=bearings,
        lane_widths=widths,
    )


# -- arm frame ----------------------------------------------------------------


@pytest.mark.parametrize(
    "direction, expected",
    [
        (N, (-1.75, 50.0)),
        (S, (1.75, -50.0)),
        (E, (50.0, 1.75)),
        (W, (-50.0, -1.75)),
    ],
)
def test_on_slot_arm_points_are_the_v10_coordinates(direction, expected) -> None:
    arm = ArmGeometry(direction, {N: 0, E: 90, S: 180, W: 270}[direction], 1, 3.5, 200)
    assert arm.on_slot
    # Incoming lane 0 centre, 50 m out: exactly what V1.0 laid out.
    assert arm.point(50.0, -1.75) == expected


def test_a_rotated_arm_is_the_slot_layout_turned_by_its_deviation() -> None:
    arm = ArmGeometry(N, 20.0, 1, 3.5, 200)
    x, y = arm.point(50.0, 0.0)
    assert math.isclose(math.degrees(math.atan2(x, y)), 20.0)
    # The exit side stays to the left of a driver arriving on the arm.
    ex, ey = arm.point(0.0, 1.0)
    assert math.isclose(ex, math.cos(math.radians(20)))
    assert math.isclose(ey, -math.sin(math.radians(20)))


def test_slot_deviation_is_signed_and_wraps() -> None:
    assert slot_deviation(N, 350) == -10
    assert slot_deviation(N, 10) == 10
    assert slot_deviation(W, 300) == 30


# -- stop lines -------------------------------------------------------------------


def test_square_junction_keeps_the_v10_box() -> None:
    geometry = _geometry(lanes={N: 2, S: 2, E: 1, W: 1})
    stops = signal_stop_distances(geometry, 3.5)
    assert set(stops.values()) == {2 * 3.5 + 3.5}


def test_skewed_arms_set_their_stop_lines_back_until_clear() -> None:
    geometry = _geometry(bearings={N: 30.0})
    stops = signal_stop_distances(geometry, 3.5)
    # North at 30 deg meets east at 60 deg and west at 120 deg (the tighter
    # angle governs): (w_E + w_N cos 60) / sin 60 = (3.5 + 1.75) / 0.866.
    expected = (3.5 + 3.5 * math.cos(math.radians(60))) / math.sin(math.radians(60))
    assert stops[N] == pytest.approx(expected + 3.5)
    assert stops[N] > 3.5 + 3.5
    # The opposite slot is the same road continuing, not a crossing.
    assert stops[S] >= 3.5 + 3.5


def test_a_three_arm_junction_sizes_its_box_from_the_arms_it_has() -> None:
    geometry = _geometry(arms=(E, S, W), lanes={N: 4, E: 1, S: 1, W: 1})
    assert set(geometry.arms) == {E, S, W}
    assert set(signal_stop_distances(geometry, 3.5).values()) == {7.0}


# -- U-turn radius ------------------------------------------------------------------


def test_uturn_radius_is_half_the_lane1_to_kerb_lane_distance() -> None:
    arm = ArmGeometry(N, 0, 3, 4.0, 200)
    # Lane 1 centre 2 m left of the centre line, kerb exit lane 10 m right.
    assert uturn_radius(arm, 0) == pytest.approx(6.0)
    assert uturn_lanes_needed(6.4, 3.5) == 4
    assert uturn_lanes_needed(6.4, 4.5) == 3


# -- validation ---------------------------------------------------------------------


def test_an_arm_out_of_its_slot_is_rejected_with_the_valid_range() -> None:
    errors = geometry_errors(_geometry(bearings={E: 135.0}), False, 3.5)
    assert len(errors) == 1
    assert "east" in errors[0] and "45°" in errors[0]
    assert "60° to 120°" in errors[0]


def test_bunched_arms_are_rejected() -> None:
    errors = geometry_errors(_geometry(bearings={N: 25.0, E: 65.0}), False, 3.5)
    assert any("only 40° apart" in e for e in errors)


def test_two_arms_are_not_a_junction() -> None:
    errors = geometry_errors(_geometry(arms=(N, S)), False, 3.5)
    assert errors and "3 or 4 arms" in errors[0]


def test_a_skewed_signal_needs_approach_storage() -> None:
    geometry = _geometry(
        bearings={N: 30.0, E: 75.0}, lanes={d: 4 for d in Direction}, length=55.0
    )
    errors = geometry_errors(geometry, False, 3.5)
    assert any("too short for this junction's angles" in e for e in errors)


def test_roundabout_mouths_must_not_overlap() -> None:
    wide = _geometry(bearings={N: 25.0, E: 72.0}, lanes={d: 3 for d in Direction})
    assert geometry_errors(wide, True, 0.0) == []
    errors = roundabout_geometry_errors(wide, 15.0)
    assert errors and "overlap where they meet the ring" in errors[0]
    assert "outerRadius" in errors[0]
    assert roundabout_geometry_errors(_geometry(), 20.0) == []


# -- import foundation ----------------------------------------------------------------


def test_measured_bearings_are_placed_on_slots_in_order() -> None:
    assignment, errors = assign_slots([182.0, 5.0, 268.0, 93.0])
    assert errors == []
    assert assignment == {N: 5.0, E: 93.0, S: 182.0, W: 268.0}


def test_a_t_junction_keeps_its_arms_order() -> None:
    assignment, errors = assign_slots([95.0, 185.0, 275.0])
    assert errors == []
    assert assignment == {E: 95.0, S: 185.0, W: 275.0}


@pytest.mark.parametrize(
    "bearings, needle",
    [
        ([0, 72, 144, 216, 288], "Five or more arms"),
        ([0, 180], "bend in one road"),
        ([0, 20, 180, 270], "cannot be placed on compass slots"),
        ([25, 65, 180, 270], "only 40° apart"),
    ],
)
def test_junctions_the_slot_model_cannot_hold_are_explained(bearings, needle) -> None:
    assignment, errors = assign_slots(bearings)
    assert assignment is None
    assert any(needle in e for e in errors)


def test_assignment_never_exceeds_the_slot_tolerance() -> None:
    for start in range(0, 360, 7):
        bearings = [(start + k * 120) % 360 for k in range(3)]
        assignment, _ = assign_slots(bearings)
        if assignment is not None:
            assert all(
                abs(slot_deviation(d, b)) <= MAX_SLOT_DEVIATION
                for d, b in assignment.items()
            )


# -- network --------------------------------------------------------------------------


def _network(**kwargs) -> RoadNetwork:
    network = RoadNetwork()
    network.setup_default_intersection(approach_length=200.0, **kwargs)
    return network


def test_explicit_slot_bearings_reproduce_the_default_network_exactly() -> None:
    plain = _network(lanes_per_approach=2)
    explicit = _network(
        lanes_per_approach=2,
        arms=tuple(Direction),
        bearings={N: 0.0, E: 90.0, S: 180.0, W: 270.0},
        lane_widths={d: 3.5 for d in Direction},
    )
    a = {ln.lane_id: ln.waypoints for ln in plain.get_all_connection_lanes()}
    b = {ln.lane_id: ln.waypoints for ln in explicit.get_all_connection_lanes()}
    assert a == b


def test_a_three_arm_network_has_no_lanes_or_paths_into_the_missing_arm() -> None:
    network = _network(lanes_per_approach=1, arms=(E, S, W))
    assert network.lane_count(N) == 0
    with pytest.raises(KeyError):
        network.get_incoming_approach(N)
    for lane in network.get_all_connection_lanes():
        assert lane.lane_id.split("_")[1] != "north"
        assert lane.exit_direction is None or lane.exit_direction != N
    # Default lane use leaves out the movements into the missing arm.
    assert network.permitted_turns(S, 0) == frozenset(
        {TurnIntent.LEFT, TurnIntent.RIGHT}
    )


def test_rotated_arms_carry_their_lanes_on_their_bearing() -> None:
    network = _network(lanes_per_approach=1, bearings={E: 70.0})
    lane = network.get_incoming_approach(E).get_lanes()[0]
    # Incoming traffic heads towards the centre: bearing + 180.
    assert lane.heading == pytest.approx(250.0)


def test_per_arm_lane_width_sets_lane_offsets() -> None:
    network = _network(lanes_per_approach=2, lane_widths={N: 4.5})
    lanes = network.get_incoming_approach(N).get_lanes()
    assert lanes[0].start_coords[0] == pytest.approx(-2.25)
    assert lanes[1].start_coords[0] == pytest.approx(-6.75)


def test_uturn_paths_exist_only_where_lane_use_allows_them() -> None:
    plain = _network(lanes_per_approach=4)
    assert not any("uturn" in ln.lane_id for ln in plain.get_all_connection_lanes())
    use = {
        N: [
            frozenset({TurnIntent.UTURN, TurnIntent.LEFT}),
            frozenset({TurnIntent.STRAIGHT}),
            frozenset({TurnIntent.STRAIGHT}),
            frozenset({TurnIntent.STRAIGHT, TurnIntent.RIGHT}),
        ]
    }
    network = _network(lanes_per_approach=4, lane_use=use)
    paths = [ln for ln in network.get_all_connection_lanes() if "uturn" in ln.lane_id]
    assert [p.lane_id for p in paths] == ["conn_north_0_uturn"]
    path = paths[0]
    incoming = network.get_incoming_approach(N).get_lanes()[0]
    kerb_exit = network.get_outgoing_approach(N).get_lanes()[3]
    assert path.start_coords == incoming.end_coords
    assert path.end_coords == kerb_exit.start_coords
    # A half circle of radius uturn_radius (4 lanes x 3.5 m / 2 = 7 m).
    assert path.length == pytest.approx(math.pi * 7.0, rel=0.01)


def test_geometry_is_built_once_not_per_tick() -> None:
    network = _network(lanes_per_approach=2, bearings={N: 15.0})
    first = network.get_all_connection_lanes()
    route = network.generate_route(N, 0, TurnIntent.LEFT)
    assert route[1] is next(ln for ln in first if ln.lane_id == "conn_north_0_left")
    assert isinstance(network.geometry, JunctionGeometry)
