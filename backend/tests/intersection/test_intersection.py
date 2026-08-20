from src.intersection.conflict_zones import ConflictZoneDetector
from src.intersection.geometry import IntersectionGeometry


def test_intersection_geometry() -> None:
    geom = IntersectionGeometry(center_x=0.0, center_y=0.0, bounding_radius=15.0)
    assert geom.is_within_intersection(0.0, 0.0) is True
    assert geom.is_within_intersection(10.0, 10.0) is True  # dist^2 = 200 <= 225
    assert geom.is_within_intersection(12.0, 12.0) is False  # dist^2 = 288 > 225

    geom.register_entry_node("n_in_0", (0.0, 15.0))
    assert geom.entry_nodes["n_in_0"] == (0.0, 15.0)


def test_conflict_zone_detector() -> None:
    detector = ConflictZoneDetector()
    detector.register_conflict(
        "conn_north_0_straight", "conn_east_0_straight", 0.0, 0.0
    )

    # Let's verify sorted keys storing works
    assert detector._get_intersection_point(
        "conn_north_0_straight", "conn_east_0_straight"
    ) == (0.0, 0.0)
    assert detector._get_intersection_point(
        "conn_east_0_straight", "conn_north_0_straight"
    ) == (0.0, 0.0)


def test_360_degree_conflict_yielding() -> None:
    from src.roads.lane import Lane
    from src.vehicles.router import find_leader
    from src.vehicles.vehicle import Vehicle

    # Create two crossing lanes
    lane_1 = Lane("lane_1", start_x=0.0, start_y=0.0, end_x=10.0, end_y=0.0)
    lane_2 = Lane("lane_2", start_x=5.0, start_y=-5.0, end_x=5.0, end_y=5.0)

    # Vehicle 1 is on Lane 1 at position 2.0 (distance to crossing point (5.0, 0.0) is 3.0)
    v1 = Vehicle("v1", length=2.0, width=1.8, desired_speed=10.0, route=[lane_1], start_position=2.0)
    
    # Vehicle 2 is on Lane 2 at position 4.0 (distance to crossing point (5.0, 0.0) is 1.0)
    # Vehicle 2 is closer to the crossing point (1.0 vs 3.0), so v1 should yield to v2
    v2 = Vehicle("v2", length=2.0, width=1.8, desired_speed=10.0, route=[lane_2], start_position=4.0)

    leader, gap = find_leader(v1, active_vehicles=[v1, v2])

    assert leader == v2
    # Expected gap: dist_to_pt_self - v1.length / 2 = 3.0 - 1.0 = 2.0
    assert abs(gap - 2.0) < 1e-3

