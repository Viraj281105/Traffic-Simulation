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
