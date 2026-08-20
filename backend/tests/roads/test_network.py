import pytest

try:
    from src.core.enums import Direction, TurnIntent
    from src.roads.approach import Approach
    from src.roads.lane import Lane
    from src.roads.network import RoadNetwork
except ImportError:
    pytest.skip("Network modules not implemented yet", allow_module_level=True)


def test_network_empty_validation() -> None:
    network = RoadNetwork()
    with pytest.raises(ValueError, match="Missing incoming approach"):
        network.validate_connectivity()


def test_network_validation_missing_lanes() -> None:
    network = RoadNetwork()
    for d in Direction:
        network.add_incoming_approach(Approach(d))
        network.add_outgoing_approach(Approach(d))

    # Missing lanes
    with pytest.raises(ValueError, match="has zero lanes"):
        network.validate_connectivity()


def test_network_default_builder() -> None:
    network = RoadNetwork()
    network.setup_default_intersection(
        approach_length=100.0, lane_width=3.5, lanes_per_approach=2
    )
    network.validate_connectivity()

    # Verify lane parameters
    n_in = network.get_incoming_approach(Direction.NORTH)
    assert len(n_in.get_lanes()) == 2

    # Innermost North incoming lane (index 0)
    # x = -0.5 * 3.5 = -1.75
    # start_y = 100.0, end_y = 2 * 3.5 = 7.0
    lane_0 = n_in.get_lanes()[0]
    assert lane_0.lane_id == "n_in_0"
    assert lane_0.start_coords == (-1.75, 100.0)
    assert lane_0.end_coords == (-1.75, 7.0)
    assert lane_0.length == 93.0


def test_network_route_generation() -> None:
    network = RoadNetwork()
    network.setup_default_intersection(
        approach_length=100.0, lane_width=3.5, lanes_per_approach=2
    )

    # Route: North (incoming) -> East (exit) via LEFT turn
    # Innermost lane: index 0
    route = network.generate_route(
        Direction.NORTH, lane_index=0, turn_intent=TurnIntent.LEFT
    )

    assert len(route) == 3
    incoming, connection, exit_lane = route

    # Incoming
    assert incoming.lane_id == "n_in_0"
    assert incoming.end_coords == (-1.75, 7.0)

    # Exit: East outgoing lane 0 is innermost (closest to y=0 divider)
    # y = -0.5 * 3.5 = -1.75
    # start_x = 2 * 3.5 = 7.0, end_x = 100.0
    assert exit_lane.lane_id == "e_out_0"
    assert exit_lane.start_coords == (7.0, -1.75)

    # Connection: goes from (-1.75, 7.0) to (7.0, -1.75)
    assert connection.lane_id == "conn_north_0_left"
    assert connection.start_coords == (-1.75, 7.0)
    assert connection.end_coords == (7.0, -1.75)

    # Straight route: North (incoming) -> South (exit)
    route_straight = network.generate_route(
        Direction.NORTH, lane_index=0, turn_intent=TurnIntent.STRAIGHT
    )
    incoming, connection, exit_lane = route_straight

    assert exit_lane.lane_id == "s_out_0"
    # South outgoing moves North -> South on West side (x < 0)
    # start_y = -ns_boundary = -7.0, end_y = -L = -100.0
    assert exit_lane.start_coords == (-1.75, -7.0)
    assert connection.start_coords == (-1.75, 7.0)
    assert connection.end_coords == (-1.75, -7.0)


def test_network_edge_cases_and_missing_approaches() -> None:
    network = RoadNetwork()

    # KeyError on missing approaches
    with pytest.raises(KeyError):
        network.get_incoming_approach(Direction.NORTH)
    with pytest.raises(KeyError):
        network.get_outgoing_approach(Direction.NORTH)

    # Missing outgoing approach in validation
    for d in Direction:
        in_app = Approach(d)
        in_app.add_lane(Lane(f"in_{d.value}", 0, 0, 10, 10))
        network.add_incoming_approach(in_app)

    with pytest.raises(ValueError, match="Missing outgoing approach"):
        network.validate_connectivity()

    # Outgoing approach with zero lanes in validation
    for d in Direction:
        network.add_outgoing_approach(Approach(d))

    with pytest.raises(ValueError, match="Outgoing approach .* has zero lanes"):
        network.validate_connectivity()


def test_network_setup_with_dict_lanes_and_all_turns() -> None:
    network = RoadNetwork()
    dict_lanes = {"north": 2, "south": 3, "east": 1, "west": 2}
    network.setup_default_intersection(approach_length=100.0, lane_width=3.5, lanes_per_approach=dict_lanes)
    network.validate_connectivity()

    # Test right turns from each direction
    for d in Direction:
        route_right = network.generate_route(d, lane_index=0, turn_intent=TurnIntent.RIGHT)
        assert len(route_right) == 3

    # Test cache hit on connection lane
    cached_conn = network._get_or_create_connection_lane(Direction.NORTH, 0, TurnIntent.STRAIGHT)
    assert cached_conn in network.get_all_connection_lanes()

    # Test precompute on incomplete network
    empty_net = RoadNetwork()
    empty_net._precompute_connection_lanes()

    # Precompute when incoming has lanes but outgoing is missing
    partial_net = RoadNetwork()
    in_app = Approach(Direction.NORTH)
    in_app.add_lane(Lane("n_in_0", 0, 10, 0, 0))
    partial_net.add_incoming_approach(in_app)
    partial_net._precompute_connection_lanes()


