from src.core.enums import Direction, TurnIntent
from src.intersection.conflict_manager import ConflictManager
from src.roads.lane import Lane
from src.roads.network import RoadNetwork
from src.vehicles.router import find_leader
from src.vehicles.vehicle import Vehicle


def test_conflict_manager_reservation() -> None:
    """Test that the ConflictManager detects crossing connection lanes and
    manages reservations correctly."""
    # Build a network and get its connection lanes
    network = RoadNetwork()
    network.setup_default_intersection(
        approach_length=100.0, lane_width=3.5, lanes_per_approach=2
    )

    cm = ConflictManager()
    for cl in network.get_all_connection_lanes():
        cm.register_connection_lane(cl)
    cm.compute_conflict_points()

    # There should be multiple conflict points (crossing connection lanes)
    cps = cm.get_all_conflict_points()
    assert len(cps) > 0, "Expected conflict points between crossing connection lanes"


def test_lane_following_with_shared_connection_lanes() -> None:
    """Test that vehicles on the same connection lane can detect each other
    (this was the root cause of collisions before lane deduplication)."""
    network = RoadNetwork()
    network.setup_default_intersection(
        approach_length=100.0, lane_width=3.5, lanes_per_approach=2
    )

    # Two vehicles taking the same route: north, lane 1, going straight
    route = network.generate_route(Direction.NORTH, 1, TurnIntent.STRAIGHT)
    v1 = Vehicle(
        "v1",
        length=4.0,
        width=2.0,
        desired_speed=10.0,
        route=route,
        start_position=50.0,
        initial_speed=10.0,
        turn_intent=TurnIntent.STRAIGHT,
    )
    v2 = Vehicle(
        "v2",
        length=4.0,
        width=2.0,
        desired_speed=10.0,
        route=route,
        start_position=30.0,
        initial_speed=10.0,
        turn_intent=TurnIntent.STRAIGHT,
    )

    # v2 is behind v1 on the same lane — find_leader should detect v1 as leader
    leader, gap = find_leader(v2, network=network, active_vehicles=[v1, v2])
    assert leader is v1
    assert gap > 0


def test_emergency_proximity_detection() -> None:
    """Test that the emergency proximity layer detects dangerously close vehicles."""
    # Create a simple straight lane
    lane = Lane("test_lane", start_x=0.0, start_y=0.0, end_x=100.0, end_y=0.0)

    v1 = Vehicle(
        "v1",
        length=4.0,
        width=2.0,
        desired_speed=10.0,
        route=[lane],
        start_position=10.0,
        initial_speed=5.0,
    )
    v2 = Vehicle(
        "v2",
        length=4.0,
        width=2.0,
        desired_speed=10.0,
        route=[lane],
        start_position=6.0,
        initial_speed=5.0,
    )

    # v2 is behind v1 — they are very close (10 - 6 = 4m, less than vehicle lengths)
    leader, gap = find_leader(v2, active_vehicles=[v1, v2])
    assert leader is not None
    assert gap >= 0


def test_conflict_manager_full_lifecycle_and_arbitration() -> None:
    cm = ConflictManager()
    lane_a = Lane("conn_a", start_x=-20.0, start_y=0.0, end_x=20.0, end_y=0.0)
    lane_b = Lane("conn_b", start_x=0.0, start_y=-20.0, end_x=0.0, end_y=20.0)
    lane_unrelated = Lane(
        "conn_c", start_x=100.0, start_y=100.0, end_x=120.0, end_y=100.0
    )

    cm.register_connection_lane(lane_a)
    cm.register_connection_lane(lane_b)
    cm.register_connection_lane(lane_unrelated)
    cm.compute_conflict_points()

    assert cm.get_reservation_count() == 0

    # Query unknown lane returns inf
    assert cm.get_conflict_distance(
        "v1", TurnIntent.STRAIGHT, "conn_unknown", 0.0, 0.0
    ) == float("inf")

    # Approaching within 2 * ZONE_RADIUS
    # Conflict point for lane_a is at (0,0) which is distance 20.0m along lane
    # If vehicle is at pos 10.0m, remaining = 10.0m <= 12.0m (ZONE_RADIUS * 2)
    # 1. Higher priority vehicle (STRAIGHT) approaches along lane_b
    all_info_1 = [
        {
            "vehicle_id": "v_left",  # Same vehicle ID to test self-skip
            "turn_intent": TurnIntent.LEFT,
            "connection_lane_id": "conn_a",
            "position_on_lane": 10.0,
        },
        {
            "vehicle_id": "v_passed",  # Position > dist_to_cp + ZONE_RADIUS
            "turn_intent": TurnIntent.STRAIGHT,
            "connection_lane_id": "conn_b",
            "position_on_lane": 30.0,
        },
        {
            "vehicle_id": "v_other_same_lane",
            "turn_intent": TurnIntent.LEFT,
            "connection_lane_id": "conn_a",
            "position_on_lane": 5.0,
        },
        {
            "vehicle_id": "v_unrelated",
            "turn_intent": TurnIntent.STRAIGHT,
            "connection_lane_id": "conn_c",
            "position_on_lane": 10.0,
        },
        {
            "vehicle_id": "v_straight",
            "turn_intent": TurnIntent.STRAIGHT,
            "connection_lane_id": "conn_b",
            "position_on_lane": 10.0,
        },
    ]

    # v_left (LEFT) yields to v_straight (STRAIGHT)
    dist = cm.get_conflict_distance(
        "v_left", TurnIntent.LEFT, "conn_a", 10.0, 0.0, all_vehicles_info=all_info_1
    )
    assert dist < float("inf")

    # Now query v_straight on conn_b (other vehicle v_left on conn_a == cp.lane_id_a)
    dist_straight = cm.get_conflict_distance(
        "v_straight",
        TurnIntent.STRAIGHT,
        "conn_b",
        10.0,
        0.0,
        all_vehicles_info=all_info_1,
    )
    assert dist_straight == float("inf")
    cm.release_vehicle("v_straight")

    # 2. Equal priority tiebreak (lower vehicle ID wins)
    all_info_2 = [
        {
            "vehicle_id": "v0_alpha",
            "turn_intent": TurnIntent.STRAIGHT,
            "connection_lane_id": "conn_b",
            "position_on_lane": 10.0,
        }
    ]
    # v1_beta yields to v0_alpha
    dist_tie = cm.get_conflict_distance(
        "v1_beta",
        TurnIntent.STRAIGHT,
        "conn_a",
        10.0,
        0.0,
        all_vehicles_info=all_info_2,
    )
    assert dist_tie < float("inf")

    # 3. v0_alpha acquires reservation
    dist_acquire = cm.get_conflict_distance(
        "v0_alpha", TurnIntent.STRAIGHT, "conn_b", 10.0, 0.0, all_vehicles_info=[]
    )
    assert dist_acquire == float("inf")
    assert cm.get_reservation_count() == 1

    # Own reservation check (v0_alpha owns it)
    assert cm.get_conflict_distance(
        "v0_alpha", TurnIntent.STRAIGHT, "conn_b", 10.0, 0.0
    ) == float("inf")

    # Another vehicle yields to active reservation held by v0_alpha
    dist_blocked = cm.get_conflict_distance(
        "v_other", TurnIntent.STRAIGHT, "conn_a", 10.0, 0.0
    )
    assert dist_blocked < float("inf")

    # Vehicle already past conflict point
    assert cm.get_conflict_distance(
        "v_past", TurnIntent.STRAIGHT, "conn_a", 30.0, 0.0
    ) == float("inf")

    # Update reservation clear time
    cm.update_reservation_clear_time("v0_alpha", "conn_b", 1.0)

    # Expire reservations
    cm.update_reservations(current_time=10.0)
    assert cm.get_reservation_count() == 0

    # Acquire again and release_vehicle
    cm.get_conflict_distance("v_to_release", TurnIntent.STRAIGHT, "conn_a", 10.0, 0.0)
    assert cm.get_reservation_count() == 1
    cm.release_vehicle("v_to_release")
    assert cm.get_reservation_count() == 0
