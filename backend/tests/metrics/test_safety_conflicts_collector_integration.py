"""Integration tests for TTC/PET as wired into MetricCollector.

Complements tests/metrics/test_safety_conflicts.py (which tests the pure
functions in isolation): these confirm MetricCollector.update()/get_metrics()
correctly accumulate, threshold, expose, and reset TTC/PET state, using real
Vehicle/Lane/ConflictManager objects rather than test doubles, since PET
specifically needs real conflict-point geometry.
"""

from src.core.enums import Direction
from src.intersection.conflict_manager import ConflictManager
from src.metrics.collector import MetricCollector
from src.roads.lane import Lane
from src.vehicles.vehicle import Vehicle

_SIGNALS = {
    Direction.NORTH: "green",
    Direction.SOUTH: "green",
    Direction.EAST: "green",
    Direction.WEST: "green",
}


def _config(**metrics_overrides: float) -> dict:
    return {
        "simulation": {"warmupTime": 0.0, "timeStep": 0.1},
        "metrics": metrics_overrides,
    }


def test_ttc_pet_fields_default_to_no_observations() -> None:
    collector = MetricCollector(_config())
    metrics = collector.get_metrics(10.0, [], [], total_spawned=0)

    assert metrics["minTTC"] is None
    assert metrics["ttcEventCount"] == 0
    assert metrics["ttcSampleCount"] == 0
    assert metrics["ttcThresholdSeconds"] == 1.5  # documented default

    assert metrics["minPET"] is None
    assert metrics["petEventCount"] == 0
    assert metrics["petSampleCount"] == 0
    assert metrics["petThresholdSeconds"] == 5.0  # documented default
    assert metrics["petApplicable"] is False


def test_ttc_observed_and_thresholded_via_collector_update() -> None:
    """Two vehicles closing on different lanes: update() must record a
    finite minTTC, and ttcEventCount must reflect the configured
    threshold, not an arbitrary hardcoded one."""
    collector = MetricCollector(_config(ttcThresholdSeconds=100.0))

    lane_north = Lane("lane_north", 0.0, 0.0, 0.0, 100.0)
    lane_south = Lane("lane_south", 0.0, 100.0, 0.0, 0.0)
    # 20 m apart (well within the default 50 m ttcSearchRadius).
    va = Vehicle(
        "va", 4.0, 2.0, 5.0, route=[lane_north], start_position=40.0, initial_speed=5.0
    )
    vb = Vehicle(
        "vb", 4.0, 2.0, 5.0, route=[lane_south], start_position=40.0, initial_speed=5.0
    )

    collector.update(1.0, [va, vb], [], _SIGNALS)
    metrics = collector.get_metrics(1.0, [va, vb], [], total_spawned=2)

    assert metrics["ttcSampleCount"] == 1
    assert metrics["minTTC"] is not None
    assert metrics["minTTC"] > 0.0
    # threshold=100s is far above any plausible TTC here, so it must count.
    assert metrics["ttcEventCount"] == 1


def test_ttc_event_not_counted_below_a_low_threshold() -> None:
    """Same closing pair, but with a threshold too tight to be crossed --
    the observation must still be recorded (sample/min), just not counted
    as an "event"."""
    collector = MetricCollector(_config(ttcThresholdSeconds=0.001))

    lane_north = Lane("lane_north", 0.0, 0.0, 0.0, 100.0)
    lane_south = Lane("lane_south", 0.0, 100.0, 0.0, 0.0)
    va = Vehicle(
        "va", 4.0, 2.0, 5.0, route=[lane_north], start_position=40.0, initial_speed=5.0
    )
    vb = Vehicle(
        "vb", 4.0, 2.0, 5.0, route=[lane_south], start_position=40.0, initial_speed=5.0
    )

    collector.update(1.0, [va, vb], [], _SIGNALS)
    metrics = collector.get_metrics(1.0, [va, vb], [], total_spawned=2)

    assert metrics["ttcSampleCount"] == 1
    assert metrics["minTTC"] is not None
    assert metrics["ttcEventCount"] == 0


def _crossing_conflict_manager() -> tuple[ConflictManager, Lane, Lane]:
    """A real ConflictManager with two lanes that genuinely cross at the
    origin -- north/south through (0, +-10), east/west through (+-10, 0)."""
    cm = ConflictManager()
    lane_ns = Lane("conn_n_0_straight", 0.0, -10.0, 0.0, 10.0)
    lane_ew = Lane("conn_e_0_straight", -10.0, 0.0, 10.0, 0.0)
    cm.register_connection_lane(lane_ns)
    cm.register_connection_lane(lane_ew)
    cm.compute_conflict_points()
    assert cm.get_all_conflict_points(), "test setup must produce a real crossing"
    return cm, lane_ns, lane_ew


def test_pet_measured_when_conflict_manager_supplied() -> None:
    cm, lane_ns, lane_ew = _crossing_conflict_manager()
    cp = cm.get_all_conflict_points()[0]
    collector = MetricCollector(_config(petThresholdSeconds=100.0))

    # Vehicle A occupies the crossing, then leaves.
    va = Vehicle(
        "va",
        4.0,
        2.0,
        5.0,
        route=[lane_ns],
        start_position=cp.dist_on_a,
        initial_speed=5.0,
    )
    collector.update(10.0, [va], [], _SIGNALS, conflict_manager=cm)
    va.position = cp.dist_on_a + 20.0  # well clear of ZONE_RADIUS
    collector.update(11.0, [va], [], _SIGNALS, conflict_manager=cm)

    # Vehicle B enters the same crossing afterwards.
    vb = Vehicle(
        "vb",
        4.0,
        2.0,
        5.0,
        route=[lane_ew],
        start_position=cp.dist_on_b,
        initial_speed=5.0,
    )
    collector.update(14.0, [vb], [], _SIGNALS, conflict_manager=cm)

    metrics = collector.get_metrics(14.0, [vb], [], total_spawned=2)
    assert metrics["petApplicable"] is True
    assert metrics["petSampleCount"] == 1
    assert metrics["minPET"] == 3.0  # 14.0 - 11.0
    assert metrics["petEventCount"] == 1  # 3.0 <= 100.0 threshold


def test_pet_not_applicable_without_conflict_manager() -> None:
    """Same scenario as above, but conflict_manager is never passed --
    PET must stay unmeasured (petApplicable False, minPET None), never
    silently report "no conflicts"."""
    cm, lane_ns, lane_ew = _crossing_conflict_manager()
    cp = cm.get_all_conflict_points()[0]
    collector = MetricCollector(_config())

    va = Vehicle(
        "va",
        4.0,
        2.0,
        5.0,
        route=[lane_ns],
        start_position=cp.dist_on_a,
        initial_speed=5.0,
    )
    collector.update(10.0, [va], [], _SIGNALS)  # no conflict_manager kwarg

    metrics = collector.get_metrics(10.0, [va], [], total_spawned=1)
    assert metrics["petApplicable"] is False
    assert metrics["minPET"] is None
    assert metrics["petSampleCount"] == 0


def test_reset_clears_ttc_and_pet_state_between_simulations() -> None:
    cm, lane_ns, lane_ew = _crossing_conflict_manager()
    cp = cm.get_all_conflict_points()[0]
    collector = MetricCollector(_config())

    va = Vehicle(
        "va",
        4.0,
        2.0,
        5.0,
        route=[lane_ns],
        start_position=cp.dist_on_a,
        initial_speed=5.0,
    )
    vb = Vehicle(
        "vb",
        4.0,
        2.0,
        5.0,
        route=[lane_ew],
        start_position=cp.dist_on_b + 30.0,  # far away, closing
        initial_speed=5.0,
    )
    collector.update(10.0, [va, vb], [], _SIGNALS, conflict_manager=cm)
    va.position = cp.dist_on_a + 20.0
    collector.update(11.0, [va, vb], [], _SIGNALS, conflict_manager=cm)

    pre_reset = collector.get_metrics(11.0, [va, vb], [], total_spawned=2)
    assert pre_reset["ttcSampleCount"] > 0 or pre_reset["petApplicable"] is True

    collector.reset()
    post_reset = collector.get_metrics(0.0, [], [], total_spawned=0)

    assert post_reset["minTTC"] is None
    assert post_reset["ttcEventCount"] == 0
    assert post_reset["ttcSampleCount"] == 0
    assert post_reset["minPET"] is None
    assert post_reset["petEventCount"] == 0
    assert post_reset["petSampleCount"] == 0
    assert post_reset["petApplicable"] is False


def test_ttc_pet_do_not_alter_unrelated_existing_metrics() -> None:
    """Adding TTC/PET must not change any pre-existing metric's value --
    spot-check a representative sample against a collector run without
    ever passing a conflict_manager (the common case for every existing
    caller before this change)."""
    lane_n = Lane("n_in_0", 0.0, 0.0, 0.0, 100.0)
    va = Vehicle(
        "va", 4.0, 2.0, 10.0, route=[lane_n], start_position=50.0, initial_speed=8.0
    )
    collector = MetricCollector(_config())
    collector.update(1.0, [va], [], _SIGNALS)
    metrics = collector.get_metrics(1.0, [va], [], total_spawned=1)

    assert metrics["activeVehicleCount"] == 1
    assert metrics["totalVehiclesSpawned"] == 1
    assert metrics["collisionCount"] == 0
    assert "masterEfficiencyScore" in metrics
    # New keys are additive, not a replacement for any existing key.
    assert "averageDelay" in metrics
    assert "throughput" in metrics
