"""V1.2 lane model: explicit lane identity, lane-use policy, per-approach lanes."""

from typing import Any, Dict

import pytest

from src.core.config_validation import semantic_config_errors
from src.core.enums import Direction, TurnIntent
from src.roads.network import (
    SIGNAL_STOP_LINE_SETBACK,
    RoadNetwork,
    lane_counts,
    lane_permitted_turns,
    resolve_lanes_per_approach,
)

L, S, R = TurnIntent.LEFT, TurnIntent.STRAIGHT, TurnIntent.RIGHT


def test_lane_use_policy() -> None:
    assert lane_permitted_turns(0, 1) == {L, S, R}
    assert lane_permitted_turns(0, 2) == {L, S}
    assert lane_permitted_turns(1, 2) == {S, R}
    assert lane_permitted_turns(0, 3) == {L, S}
    assert lane_permitted_turns(1, 3) == {S}
    assert lane_permitted_turns(2, 3) == {S, R}
    # Every lane carries something; turns only from the kerb-side lanes.
    for n in (1, 2, 3, 4):
        for i in range(n):
            assert S in lane_permitted_turns(i, n)
        assert sum(L in lane_permitted_turns(i, n) for i in range(n)) == 1
        assert sum(R in lane_permitted_turns(i, n) for i in range(n)) == 1


def test_lanes_carry_explicit_identity() -> None:
    network = RoadNetwork()
    network.setup_default_intersection(lanes_per_approach=3)
    for d in Direction:
        for i, lane in enumerate(network.get_incoming_approach(d).get_lanes()):
            assert (lane.approach, lane.index, lane.role) == (d, i, "incoming")
        for i, lane in enumerate(network.get_outgoing_approach(d).get_lanes()):
            assert (lane.approach, lane.index, lane.role) == (d, i, "outgoing")
    conn = network.generate_route(Direction.NORTH, 2, R)[1]
    assert (conn.approach, conn.index, conn.role) == (Direction.NORTH, 2, "connection")
    assert network.lane_count(Direction.EAST) == 3


def test_controller_lane_use_override() -> None:
    network = RoadNetwork()
    network.setup_default_intersection(lanes_per_approach=2)
    assert network.permitted_turns(Direction.NORTH, 0) == {L, S}
    network.set_lane_use(Direction.NORTH, 0, frozenset({L}))
    assert network.permitted_turns(Direction.NORTH, 0) == {L}
    assert network.permitted_turns(Direction.SOUTH, 0) == {L, S}
    with pytest.raises(ValueError):
        network.set_lane_use(Direction.NORTH, 1, frozenset())
    # Rebuilding the network clears controller markings.
    network.setup_default_intersection(lanes_per_approach=2)
    assert network.permitted_turns(Direction.NORTH, 0) == {L, S}


def test_protected_left_signal_plan_marks_lane_zero_as_a_turn_pocket() -> None:
    from src.controllers.fixed_time_signal import FixedTimeSignalController

    network = RoadNetwork()
    network.setup_default_intersection(lanes_per_approach=2)
    FixedTimeSignalController({"controller": {}}, network)
    assert network.permitted_turns(Direction.NORTH, 0) == {L}
    assert network.permitted_turns(Direction.NORTH, 1) == {S, R}

    paired = RoadNetwork()
    paired.setup_default_intersection(lanes_per_approach=2)
    FixedTimeSignalController(
        {"controller": {"phaseSequence": ["ns_green", "ew_green"]}}, paired
    )
    # A grouped plan releases every movement of an approach at once.
    assert paired.permitted_turns(Direction.NORTH, 0) == {L, S}


def test_resolve_lanes_per_approach() -> None:
    assert resolve_lanes_per_approach({}) == 2
    assert resolve_lanes_per_approach({"lanesPerApproach": 3}) == 3
    per = {"north": 2, "south": 2, "east": 1, "west": 1}
    assert resolve_lanes_per_approach({"lanesPerApproach": per}) == per
    merged = resolve_lanes_per_approach(
        {
            "lanesPerApproach": 2,
            "approaches": [
                {"direction": "east", "lanes": 1},
                {"direction": "west", "lanes": 1},
                {"direction": "north"},  # no lanes: keeps the default
            ],
        }
    )
    assert merged == per
    assert lane_counts(3) == {d.value: 3 for d in Direction}


def _signal_boundary(network: RoadNetwork, d: Direction) -> float:
    lane = network.get_incoming_approach(d).get_lanes()[0]
    return float(max(abs(lane.end_coords[0]), abs(lane.end_coords[1])))


def test_junction_box_is_sized_to_the_widest_road() -> None:
    network = RoadNetwork()
    network.setup_default_intersection(
        lane_width=3.5,
        lanes_per_approach={"north": 2, "south": 2, "east": 1, "west": 1},
    )
    expected = 2 * 3.5 + SIGNAL_STOP_LINE_SETBACK
    for d in Direction:
        assert _signal_boundary(network, d) == pytest.approx(expected)

    # Equal counts: exactly the V1.0 boundary.
    symmetric = RoadNetwork()
    symmetric.setup_default_intersection(lane_width=3.5, lanes_per_approach=1)
    assert _signal_boundary(symmetric, Direction.NORTH) == pytest.approx(
        3.5 + SIGNAL_STOP_LINE_SETBACK
    )


def test_design_vehicle_allowance_moves_stop_lines_back() -> None:
    plain = RoadNetwork()
    plain.setup_default_intersection(lanes_per_approach=1)
    heavy = RoadNetwork()
    heavy.setup_default_intersection(lanes_per_approach=1, design_vehicle_allowance=7)
    assert heavy.stop_line_setback == pytest.approx(SIGNAL_STOP_LINE_SETBACK + 7)
    assert _signal_boundary(heavy, Direction.NORTH) == pytest.approx(
        _signal_boundary(plain, Direction.NORTH) + 7
    )
    # Turning paths run stop line to stop line, so they get longer (wider).
    plain_turn = plain.generate_route(Direction.WEST, 0, R)[1].length
    heavy_turn = heavy.generate_route(Direction.WEST, 0, R)[1].length
    assert heavy_turn > plain_turn

    # The roundabout's geometry is set by its radii and is not changed.
    ring = RoadNetwork()
    ring.setup_default_intersection(is_roundabout=True, design_vehicle_allowance=7)
    plain_ring = RoadNetwork()
    plain_ring.setup_default_intersection(is_roundabout=True)
    assert (
        ring.get_incoming_approach(Direction.NORTH).get_lanes()[0].end_coords
        == plain_ring.get_incoming_approach(Direction.NORTH).get_lanes()[0].end_coords
    )


def _roads(lanes: Any) -> Dict[str, Any]:
    return {"roads": {"lanesPerApproach": lanes}}


def test_opposite_approaches_must_match() -> None:
    assert semantic_config_errors(_roads(2)) == []
    assert (
        semantic_config_errors(_roads({"north": 2, "south": 2, "east": 1, "west": 1}))
        == []
    )
    errors = semantic_config_errors(
        _roads({"north": 1, "south": 2, "east": 1, "west": 1})
    )
    assert len(errors) == 1 and "north and south" in errors[0]
    via_approaches = semantic_config_errors(
        {
            "roads": {
                "lanesPerApproach": 2,
                "approaches": [{"direction": "west", "lanes": 3}],
            }
        }
    )
    assert len(via_approaches) == 1 and "east and west" in via_approaches[0]
