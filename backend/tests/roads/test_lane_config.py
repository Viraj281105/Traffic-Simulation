"""V1.4 lane configuration and roundabout lane designation (roads/lane_config.py)."""

import pytest

from src.core.enums import Direction, TurnIntent
from src.roads.lane_config import (
    MAX_CIRCULATING_LANES,
    configured_approach_lengths,
    configured_lane_use,
    default_policy_turns,
    default_roundabout_lane_use,
    designated_ring_lanes,
    entry_home_ring_lane,
    exit_merges,
    lane_use_order_errors,
    merging_entry_groups,
    ring_exit_lane,
    ring_lane_for,
    ring_lane_radius,
    signal_exit_lane,
    target_direction,
)
from src.roads.network import RoadNetwork

L, S, R = TurnIntent.LEFT, TurnIntent.STRAIGHT, TurnIntent.RIGHT


def test_one_lane_ring_takes_every_movement_on_its_only_lane() -> None:
    for turn in TurnIntent:
        assert ring_lane_for(0, 1, 1, 1, turn) == 0
        assert ring_exit_lane(0, 1, 1) == 0


def test_two_lane_ring_designation() -> None:
    # Right turns outer, left turns inner, straight on either.
    assert designated_ring_lanes(2, R) == frozenset({1})
    assert designated_ring_lanes(2, L) == frozenset({0})
    assert designated_ring_lanes(2, S) == frozenset({0, 1})
    # Two-lane entry: each lane its own ring lane — the V1.0-V1.3 paths.
    assert ring_lane_for(0, 2, 2, 2, L) == 0
    assert ring_lane_for(0, 2, 2, 2, S) == 0
    assert ring_lane_for(0, 2, 2, 2, R) is None
    assert ring_lane_for(1, 2, 2, 2, R) == 1
    assert ring_lane_for(1, 2, 2, 2, S) == 1
    assert ring_lane_for(1, 2, 2, 2, L) is None


def test_one_lane_approach_feeds_both_ring_lanes() -> None:
    assert entry_home_ring_lane(0, 1, 2) == 1
    assert ring_lane_for(0, 1, 2, 1, R) == 1
    assert ring_lane_for(0, 1, 2, 1, S) == 1
    assert ring_lane_for(0, 1, 2, 1, L) == 0


def test_three_lane_approach_merges_its_two_left_lanes_onto_the_inner_ring() -> None:
    assert [entry_home_ring_lane(j, 3, 2) for j in range(3)] == [0, 0, 1]
    assert merging_entry_groups(3, 2) == [[0, 1]]
    assert merging_entry_groups(2, 2) == []
    assert ring_lane_for(1, 3, 2, 2, S) == 0
    assert ring_lane_for(2, 3, 2, 2, S) == 1
    assert ring_lane_for(2, 3, 2, 2, R) == 1


def test_exit_lanes_are_right_aligned_and_one_lane_exits_merge() -> None:
    assert ring_exit_lane(1, 2, 2) == 1
    assert ring_exit_lane(0, 2, 2) == 0
    assert ring_exit_lane(0, 2, 3) == 1
    assert ring_exit_lane(0, 2, 1) == 0
    assert ring_exit_lane(1, 2, 1) == 0
    assert exit_merges(2, 1) and not exit_merges(2, 2)


def test_ring_radius_matches_the_v1_expression_bit_for_bit() -> None:
    for lanes in (1, 2, 3):
        for k in range(lanes):
            legacy = 10.0 + (k + 0.5) * ((20.0 - 10.0) / lanes)
            assert ring_lane_radius(10.0, 20.0, lanes, k) == legacy


def test_more_than_two_circulating_lanes_is_not_supported() -> None:
    assert MAX_CIRCULATING_LANES == 2


def test_default_roundabout_lane_use_moves_movements_to_lanes_that_reach_them() -> None:
    counts = {
        Direction.NORTH: 2,
        Direction.SOUTH: 2,
        Direction.EAST: 1,
        Direction.WEST: 1,
    }
    north = default_roundabout_lane_use(Direction.NORTH, counts, 2)
    # With as many entry lanes as ring lanes: the default policy itself.
    assert north == [frozenset({L, S}), frozenset({S, R})]
    east = default_roundabout_lane_use(Direction.EAST, counts, 2)
    assert east == [frozenset({L, S, R})]
    # A two-lane approach onto a one-lane ring: both lanes merge, and every
    # movement the policy gives them stays available.
    one_ring = default_roundabout_lane_use(Direction.NORTH, counts, 1)
    assert one_ring == [frozenset({L, S}), frozenset({S, R})]


def test_default_lane_use_matches_v12_policy() -> None:
    assert default_policy_turns(0, 1) == frozenset(TurnIntent)
    assert default_policy_turns(0, 3) == frozenset({L, S})
    assert default_policy_turns(1, 3) == frozenset({S})
    assert default_policy_turns(2, 3) == frozenset({S, R})


def test_signal_exit_mapping_pairs_dual_turn_lanes_with_receiving_lanes() -> None:
    dual_left = [frozenset({L}), frozenset({L, S}), frozenset({S, R})]
    assert signal_exit_lane(0, L, dual_left, 3) == 0
    assert signal_exit_lane(1, L, dual_left, 3) == 1
    assert signal_exit_lane(2, R, dual_left, 3) == 2
    # Default policy: the V1.0 mapping.
    default = [default_policy_turns(i, 2) for i in range(2)]
    assert signal_exit_lane(0, L, default, 2) == 0
    assert signal_exit_lane(1, R, default, 2) == 1
    assert signal_exit_lane(1, S, default, 2) == 1


def test_lane_arrows_must_not_cross() -> None:
    assert (
        lane_use_order_errors("x", [frozenset({L}), frozenset({S}), frozenset({S, R})])
        == []
    )
    errors = lane_use_order_errors("North", [frozenset({S}), frozenset({L})])
    assert len(errors) == 1 and "cross" in errors[0]


def test_configured_lane_use_and_lengths_are_read_per_approach() -> None:
    roads = {
        "approaches": [
            {
                "direction": "north",
                "lanes": 2,
                "laneUse": [["left"], ["straight", "right"]],
                "length": 300,
            },
            {"direction": "east", "laneUse": [["sideways"]]},
        ]
    }
    use = configured_lane_use(roads)
    assert use == {Direction.NORTH: [frozenset({L}), frozenset({S, R})]}
    assert configured_approach_lengths(roads) == {Direction.NORTH: 300.0}


def test_targets_follow_right_hand_traffic() -> None:
    assert target_direction(Direction.NORTH, L) == Direction.EAST
    assert target_direction(Direction.NORTH, S) == Direction.SOUTH
    assert target_direction(Direction.NORTH, R) == Direction.WEST


@pytest.mark.parametrize("rings", [1, 2])
def test_network_paths_carry_their_ring_lane_and_spiral_point(rings: int) -> None:
    net = RoadNetwork()
    net.setup_default_intersection(
        200,
        3.5,
        {"north": 2, "south": 2, "east": 1, "west": 1},
        True,
        10,
        20,
        circulating_lanes=rings,
    )
    assert net.circulating_lanes == rings
    for conn in net.get_all_connection_lanes():
        assert conn.ring_lane is not None and 0 <= conn.ring_lane < rings
        assert 0 < conn.exit_transition_start < conn.length
        assert conn.exit_direction is not None


def test_unequal_roundabout_approaches_build_one_ring_of_consistent_radii() -> None:
    net = RoadNetwork()
    net.setup_default_intersection(
        200,
        3.5,
        {"north": 2, "south": 2, "east": 1, "west": 1},
        True,
        10,
        20,
    )
    assert net.circulating_lanes == 2
    radii = {round(c.circulating_radius, 6) for c in net.get_all_connection_lanes()}
    assert radii == {12.5, 17.5}


def test_inner_exit_spiral_keeps_clear_of_the_outer_lane_path_to_the_same_exit() -> (
    None
):
    """Pins the separation study behind ROUNDABOUT_INNER_EXIT_TRANSITION_ARC."""
    import math

    net = RoadNetwork()
    net.setup_default_intersection(200, 3.5, 2, True, 10, 20, circulating_lanes=2)
    conns = net.get_all_connection_lanes()

    def pts(lane: object, start: float = 0.0) -> list:
        n = int((lane.length - start) / 0.25)  # type: ignore[attr-defined]
        return [lane.get_point_at_distance(start + i * 0.25) for i in range(n + 1)]  # type: ignore[attr-defined]

    worst = math.inf
    for a in (c for c in conns if c.ring_lane == 0):
        pa = pts(a, a.exit_transition_start)
        for b in (
            c
            for c in conns
            if c.ring_lane == 1
            and c.approach != a.approach
            and c.exit_direction == a.exit_direction
        ):
            pb = pts(b)
            worst = min(worst, min(math.dist(p, q) for p in pa for q in pb[::2]))
    assert worst >= 2.9, worst


def test_every_crossing_of_the_outer_lane_lies_inside_an_exit_zone() -> None:
    """Wherever an inner-lane exit curve comes within two metres of an
    outer-lane path, both vehicles are inside the convergence zone of that
    exit (controllers/roundabout.py), so the crossing is arbitrated."""
    import math

    from src.controllers.roundabout import RoundaboutController

    net = RoadNetwork()
    net.setup_default_intersection(200, 3.5, 2, True, 10, 20, circulating_lanes=2)
    ctl = RoundaboutController({"controller": {}}, net)
    conns = net.get_all_connection_lanes()
    checked = 0
    for a in (c for c in conns if c.ring_lane == 0):
        (exit_a, a_start, a_end), *_ = ctl._zones_of(a)
        for b in (c for c in conns if c.ring_lane == 1 and c.approach != a.approach):
            zones_b = {z[0]: z for z in ctl._zones_of(b)}
            s = a.exit_transition_start
            while s <= a.length:
                p = a.get_point_at_distance(s)
                t = 0.0
                while t <= b.length:
                    q = b.get_point_at_distance(t)
                    if math.dist(p, q) < 2.0 and t > 1.0:
                        checked += 1
                        assert exit_a in zones_b, (a.lane_id, b.lane_id)
                        _, b_start, b_end = zones_b[exit_a]
                        assert a_start - 1e-6 <= s <= a_end + 4.5, (a.lane_id, s)
                        assert b_start - 2.5 <= t <= b_end + 4.5, (b.lane_id, t)
                    t += 0.5
                s += 0.5
    assert checked > 0
