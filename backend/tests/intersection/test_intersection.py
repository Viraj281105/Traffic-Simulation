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


def _signal_conflict_manager(lanes: int = 1) -> tuple:  # type: ignore[type-arg]
    network = RoadNetwork()
    network.setup_default_intersection(
        approach_length=200.0, lane_width=3.5, lanes_per_approach=lanes
    )
    cm = ConflictManager()
    for cl in network.get_all_connection_lanes():
        cm.register_connection_lane(cl)
    cm.compute_conflict_points()
    return cm, network


def test_refused_vehicle_is_held_at_the_stop_line_not_inside_the_box() -> None:
    """Regression: a vehicle refused admission was stopped ZONE_RADIUS short of
    the first blocked conflict point — which on a turning path can lie several
    metres INSIDE the junction — so it entered the box holding no reservations
    and parked on crossings others held (3-lane signal, 0.8 veh/s, seed 1:
    frozen from t = 95 s). Refused means held at the connection-lane start."""
    from src.intersection.conflict_manager import _shares_entry_lane

    cm, network = _signal_conflict_manager(lanes=3)
    left = network.generate_route(Direction.SOUTH, 0, TurnIntent.LEFT)[1]

    def dist_on_left(key: tuple) -> float:  # type: ignore[type-arg]
        cp = cm._conflict_points[key]
        return cp.dist_on_a if cp.lane_id_a == left.lane_id else cp.dist_on_b

    # Only the crossings well inside the box are held by someone else: the
    # old rule then stopped the refused vehicle past the stop line.
    far = [
        k
        for k in cm._lane_conflicts[left.lane_id]
        if not _shares_entry_lane(k[0], k[1])
        and dist_on_left(k) > ConflictManager.ZONE_RADIUS + 1.0
    ]
    assert far, "geometry no longer has a crossing deep inside the box"
    for key in far:
        other = key[0] if key[1] == left.lane_id else key[1]
        cm._acquire(key, "holder", other, current_time=0.0)

    for speed in (5.0, 0.0):  # still rolling, and already stopped
        block = cm.get_conflict_distance(
            vehicle_id="left_turner",
            vehicle_turn_intent=TurnIntent.LEFT,
            connection_lane_id=left.lane_id,
            vehicle_position_on_lane=0.0,
            current_time=0.0,
            all_vehicles_info=[],
            vehicle_speed=speed,
            on_connection_lane=False,
        )
        assert block == 0.0, (speed, block)
    # ...and it claimed nothing while refused.
    assert all(r.vehicle_id == "holder" for r in cm._reservations.values())


def test_admitted_vehicle_is_not_held() -> None:
    cm, network = _signal_conflict_manager()
    left = network.generate_route(Direction.SOUTH, 0, TurnIntent.LEFT)[1]
    block = cm.get_conflict_distance(
        vehicle_id="left_turner",
        vehicle_turn_intent=TurnIntent.LEFT,
        connection_lane_id=left.lane_id,
        vehicle_position_on_lane=0.0,
        current_time=0.0,
        all_vehicles_info=[],
        vehicle_speed=5.0,
        on_connection_lane=False,
    )
    assert block == float("inf")
