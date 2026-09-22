"""Tests for src/metrics/definitions/safety_conflicts.py (TTC/PET).

Lane headings: 0=North(+Y), 90=East(+X), 180=South(-Y), 270=West(-X) (see
Lane.heading), matching compute_ttc's velocity-vector convention
(h_x=sin(heading), h_y=cos(heading), the same one Vehicle.get_bounding_box
uses).
"""

from src.intersection.conflict_manager import ConflictPoint
from src.metrics.definitions.safety_conflicts import (
    ConflictZoneOccupancyTracker,
    compute_ttc,
    find_ttc_events,
)
from src.roads.lane import Lane
from src.vehicles.vehicle import Vehicle


def _vehicle(
    vehicle_id: str,
    lane: Lane,
    position: float,
    speed: float,
    length: float = 4.0,
    width: float = 2.0,
) -> Vehicle:
    return Vehicle(
        vehicle_id,
        length=length,
        width=width,
        desired_speed=max(speed, 1.0),
        route=[lane],
        start_position=position,
        initial_speed=speed,
    )


# ── TTC: pairwise compute_ttc ────────────────────────────────────────────


def test_ttc_none_when_no_conflict_between_stationary_far_vehicles() -> None:
    lane_a = Lane("lane_a", 0.0, 0.0, 0.0, 100.0)
    lane_b = Lane("lane_b", 200.0, 0.0, 200.0, 100.0)
    va = _vehicle("va", lane_a, 0.0, 0.0)
    vb = _vehicle("vb", lane_b, 0.0, 0.0)
    assert compute_ttc(va, vb) is None


def test_ttc_decreases_as_approaching_vehicles_get_closer() -> None:
    """Two vehicles closing head-on at a fixed relative speed: TTC must be
    smaller when the starting gap is smaller (same closing speed, less
    distance to cover)."""
    lane_north = Lane("lane_north", 0.0, 0.0, 0.0, 100.0)  # heading 0 (+Y)
    lane_south = Lane("lane_south", 0.0, 100.0, 0.0, 0.0)  # heading 180 (-Y)

    # Far apart (80 m gap).
    va_far = _vehicle("va", lane_north, 10.0, 5.0)
    vb_far = _vehicle("vb", lane_south, 10.0, 5.0)  # at y=90
    ttc_far = compute_ttc(va_far, vb_far)

    # Closer (40 m gap), same speeds.
    va_near = _vehicle("va", lane_north, 30.0, 5.0)
    vb_near = _vehicle("vb", lane_south, 30.0, 5.0)  # at y=70
    ttc_near = compute_ttc(va_near, vb_near)

    assert ttc_far is not None
    assert ttc_near is not None
    assert ttc_near < ttc_far


def test_ttc_none_when_vehicles_moving_apart() -> None:
    """va (behind, slower) and vb (ahead, faster), both heading the same
    direction on offset parallel lanes: the gap between them widens."""
    lane_a = Lane("lane_a", 0.0, 0.0, 0.0, 100.0)  # heading 0 (+Y)
    lane_b = Lane("lane_b", 5.0, 0.0, 5.0, 100.0)  # heading 0 (+Y), offset in X
    va = _vehicle("va", lane_a, 20.0, 3.0)
    vb = _vehicle("vb", lane_b, 60.0, 8.0)
    assert compute_ttc(va, vb) is None


def test_ttc_none_at_zero_relative_speed() -> None:
    """Same direction, same speed, laterally offset (different lanes):
    the gap between them never changes."""
    lane_a = Lane("lane_a", 0.0, 0.0, 0.0, 100.0)
    lane_b = Lane("lane_b", 3.5, 0.0, 3.5, 100.0)
    va = _vehicle("va", lane_a, 20.0, 8.0)
    vb = _vehicle("vb", lane_b, 20.0, 8.0)
    assert compute_ttc(va, vb) is None


def test_ttc_none_when_closest_approach_exceeds_combined_radius() -> None:
    """Opposing lanes offset far enough apart laterally that the vehicles
    are closing (in projection) but their paths never actually come close
    enough to be a real conflict."""
    lane_north = Lane("lane_north", 0.0, 0.0, 0.0, 100.0)
    lane_south = Lane("lane_south", 50.0, 100.0, 50.0, 0.0)  # 50 m away in X
    va = _vehicle("va", lane_north, 10.0, 5.0)
    vb = _vehicle("vb", lane_south, 10.0, 5.0)
    assert compute_ttc(va, vb) is None


def test_ttc_zero_when_already_overlapping() -> None:
    lane_a = Lane("lane_a", 0.0, 0.0, 0.0, 100.0)
    lane_b = Lane("lane_b", 0.0, 100.0, 0.0, 0.0)
    va = _vehicle("va", lane_a, 50.0, 5.0)  # at y=50
    vb = _vehicle("vb", lane_b, 50.0, 5.0)  # at y=50, same point, closing
    assert compute_ttc(va, vb) == 0.0


# ── find_ttc_events: candidate-pair selection ────────────────────────────


def test_find_ttc_events_empty_for_single_vehicle() -> None:
    lane = Lane("lane_a", 0.0, 0.0, 0.0, 100.0)
    va = _vehicle("va", lane, 10.0, 5.0)
    assert find_ttc_events([va], search_radius=50.0) == []


def test_find_ttc_events_excludes_same_lane_pairs() -> None:
    """Same-lane following is not a crossing conflict and must never
    produce a TTC event, however fast the follower is closing."""
    lane = Lane("lane_a", 0.0, 0.0, 0.0, 100.0)
    leader = _vehicle("leader", lane, 40.0, 2.0)
    follower = _vehicle("follower", lane, 10.0, 10.0)  # closing fast
    assert find_ttc_events([leader, follower], search_radius=50.0) == []


def test_find_ttc_events_excludes_pairs_beyond_search_radius() -> None:
    lane_a = Lane("lane_a", 0.0, 0.0, 0.0, 1000.0)
    lane_b = Lane("lane_b", 0.0, 1000.0, 0.0, 0.0)
    va = _vehicle("va", lane_a, 10.0, 5.0)
    vb = _vehicle("vb", lane_b, 10.0, 5.0)  # at y=990, 980 m away
    assert find_ttc_events([va, vb], search_radius=50.0) == []
    assert find_ttc_events([va, vb], search_radius=2000.0) != []


def test_find_ttc_events_reports_multiple_independent_pairs() -> None:
    """Two unrelated closing pairs, far apart from each other, must both
    be reported -- and no spurious cross-pair events between them."""
    # Cluster 1 near the origin.
    lane_n1 = Lane("n1", 0.0, 0.0, 0.0, 100.0)
    lane_s1 = Lane("s1", 0.0, 100.0, 0.0, 0.0)
    a1 = _vehicle("a1", lane_n1, 40.0, 5.0)
    b1 = _vehicle("b1", lane_s1, 40.0, 5.0)

    # Cluster 2, far away (well beyond the search radius from cluster 1).
    lane_n2 = Lane("n2", 5000.0, 0.0, 5000.0, 100.0)
    lane_s2 = Lane("s2", 5000.0, 100.0, 5000.0, 0.0)
    a2 = _vehicle("a2", lane_n2, 40.0, 5.0)
    b2 = _vehicle("b2", lane_s2, 40.0, 5.0)

    events = find_ttc_events([a1, b1, a2, b2], search_radius=50.0)
    pairs = {frozenset((e[0], e[1])) for e in events}
    assert pairs == {frozenset(("a1", "b1")), frozenset(("a2", "b2"))}


# ── PET: ConflictZoneOccupancyTracker ────────────────────────────────────


def _conflict_point(
    lane_a: str, lane_b: str, dist_a: float, dist_b: float
) -> ConflictPoint:
    return ConflictPoint(
        lane_id_a=lane_a,
        lane_id_b=lane_b,
        x=0.0,
        y=0.0,
        dist_on_a=dist_a,
        dist_on_b=dist_b,
    )


def test_pet_no_event_when_zone_never_occupied() -> None:
    lane_a = Lane("conn_a", 0.0, 0.0, 0.0, 30.0)
    cp = _conflict_point("conn_a", "conn_b", 15.0, 15.0)
    tracker = ConflictZoneOccupancyTracker()

    va = _vehicle("va", lane_a, 0.0, 5.0)  # far from the zone (pos 0 vs 15)
    events = tracker.update(1.0, [va], [cp], zone_radius=3.0)
    assert events == []


def test_pet_ordering_when_two_vehicles_cleanly_traverse_a_conflict_area() -> None:
    lane_a = Lane("conn_a", 0.0, 0.0, 0.0, 30.0)
    lane_b = Lane("conn_b", 0.0, 0.0, 0.0, 30.0)
    cp = _conflict_point("conn_a", "conn_b", 15.0, 15.0)
    tracker = ConflictZoneOccupancyTracker()

    # Vehicle A enters and occupies the zone at t=10.
    va = _vehicle("va", lane_a, 15.0, 5.0)
    assert tracker.update(10.0, [va], [cp], zone_radius=3.0) == []

    # A leaves the zone at t=11 (zone empties).
    va.position = 25.0
    assert tracker.update(11.0, [va], [cp], zone_radius=3.0) == []

    # B enters the (now-empty) zone at t=14 -- a clean, non-overlapping
    # PET of 14 - 11 = 3.0 s.
    vb = _vehicle("vb", lane_b, 15.0, 5.0)
    events = tracker.update(14.0, [vb], [cp], zone_radius=3.0)
    assert events == [3.0]

    # No further event while B just sits there.
    assert tracker.update(14.1, [vb], [cp], zone_radius=3.0) == []


def test_pet_not_reported_when_occupancy_overlaps() -> None:
    """If a second vehicle reaches the zone before the first leaves, that
    is an overlapping encroachment, not a clean PET -- no event."""
    lane_a = Lane("conn_a", 0.0, 0.0, 0.0, 30.0)
    lane_b = Lane("conn_b", 0.0, 0.0, 0.0, 30.0)
    cp = _conflict_point("conn_a", "conn_b", 15.0, 15.0)
    tracker = ConflictZoneOccupancyTracker()

    va = _vehicle("va", lane_a, 15.0, 5.0)
    vb = _vehicle("vb", lane_b, 15.0, 5.0)

    assert tracker.update(10.0, [va], [cp], zone_radius=3.0) == []
    # Both present this tick -- overlap.
    assert tracker.update(10.5, [va, vb], [cp], zone_radius=3.0) == []
    # A leaves while B is still there -- direct handover, no clean gap.
    va.position = 25.0
    assert tracker.update(11.0, [vb], [cp], zone_radius=3.0) == []


def test_pet_reset_clears_occupancy_state() -> None:
    lane_a = Lane("conn_a", 0.0, 0.0, 0.0, 30.0)
    lane_b = Lane("conn_b", 0.0, 0.0, 0.0, 30.0)
    cp = _conflict_point("conn_a", "conn_b", 15.0, 15.0)
    tracker = ConflictZoneOccupancyTracker()

    va = _vehicle("va", lane_a, 15.0, 5.0)
    tracker.update(10.0, [va], [cp], zone_radius=3.0)
    va.position = 25.0
    tracker.update(11.0, [va], [cp], zone_radius=3.0)

    tracker.reset()

    # After reset, a new occupant must not be compared against the
    # pre-reset exit -- no stale PET should appear.
    vb = _vehicle("vb", lane_b, 15.0, 5.0)
    events = tracker.update(50.0, [vb], [cp], zone_radius=3.0)
    assert events == []
