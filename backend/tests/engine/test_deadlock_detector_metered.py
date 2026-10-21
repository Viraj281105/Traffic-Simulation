"""Unit and integration tests for the extended deadlock detector (D-W2-9a).

The deadlock detector is extended for metered roundabouts:
1. In metered mode (ring_only=True), it counts only circulating ring vehicles
   on connection lanes (ids starting with 'conn_'). Approach queues at red signals
   or give-way lines are never classified as deadlock.
2. In unstructured traffic (legacy mode, ring_only=False), all active vehicles
   are counted as before.
3. For conventional roundabouts and standard signals, the engine attaches no detector.
"""

from types import SimpleNamespace
from typing import Any, Dict, List

from src.core.clock import Clock
from src.engine.deadlock_detector import DeadlockDetector
from src.engine.simulation_engine import SimulationEngine


class _FakePool:
    def __init__(self, vehicles: List[Any]) -> None:
        self._vehicles = vehicles

    def get_active_vehicles(self) -> List[Any]:
        return self._vehicles


def test_metered_detector_ignores_stopped_vehicles_on_approach_lanes() -> None:
    """Vehicles stopped in approach queues (red metering or yield) must not trigger deadlock."""
    clock = Clock(1.0)
    # 6 vehicles stopped on approach lanes for 10 seconds
    vehicles = [
        SimpleNamespace(
            vehicle_id=f"v{i}",
            speed=0.0,
            lane=SimpleNamespace(lane_id=f"north_in_{i % 2}"),
        )
        for i in range(6)
    ]
    detector = DeadlockDetector(clock, _FakePool(vehicles), ring_only=True)  # type: ignore[arg-type]

    for _ in range(10):
        clock.tick()
        detector.tick(1.0)

    assert not detector.has_occurred
    assert detector.get_insight() is None
    assert len(detector.stopped_durations) == 0


def test_metered_detector_flags_blocked_ring_connection_lanes() -> None:
    """Circulating vehicles stopped on connection lanes for > 5s trigger ring deadlock."""
    clock = Clock(1.0)
    vehicles = [
        SimpleNamespace(
            vehicle_id=f"v{i}",
            speed=0.0,
            lane=SimpleNamespace(lane_id=f"conn_arm_{i}_turn"),
        )
        for i in range(5)
    ]
    detector = DeadlockDetector(clock, _FakePool(vehicles), ring_only=True)  # type: ignore[arg-type]

    for _ in range(6):
        clock.tick()
        detector.tick(1.0)

    assert detector.has_occurred
    insight = detector.get_insight()
    assert insight is not None
    assert "Ring deadlock emerged" in insight
    assert "deadlock emerged" in insight
    assert "5 circulating vehicles" in insight


def test_metered_detector_clears_when_ring_vehicles_move() -> None:
    """Ring deadlock resolves when circulating vehicles start moving."""
    clock = Clock(1.0)
    vehicles = [
        SimpleNamespace(
            vehicle_id=f"v{i}",
            speed=0.0,
            lane=SimpleNamespace(lane_id=f"conn_arm_{i}_turn"),
        )
        for i in range(5)
    ]
    detector = DeadlockDetector(clock, _FakePool(vehicles), ring_only=True)  # type: ignore[arg-type]

    for _ in range(6):
        clock.tick()
        detector.tick(1.0)
    assert detector.has_occurred

    # Vehicles move
    for v in vehicles:
        v.speed = 4.0
    clock.tick()
    detector.tick(1.0)

    assert not detector.has_occurred
    insight = detector.get_insight()
    assert insight is not None
    assert "Ring deadlock resolved" in insight
    assert "resolved" in insight


def test_metered_detector_purges_vehicles_leaving_ring() -> None:
    """Vehicles exiting connection lanes are purged from stopped durations."""
    clock = Clock(1.0)
    v1 = SimpleNamespace(
        vehicle_id="v1",
        speed=0.0,
        lane=SimpleNamespace(lane_id="conn_north_0_straight"),
    )
    v2 = SimpleNamespace(
        vehicle_id="v2",
        speed=0.0,
        lane=SimpleNamespace(lane_id="conn_east_0_straight"),
    )
    pool = _FakePool([v1, v2])
    detector = DeadlockDetector(clock, pool, ring_only=True)  # type: ignore[arg-type]

    clock.tick()
    detector.tick(1.0)
    assert "v1" in detector.stopped_durations
    assert "v2" in detector.stopped_durations

    # v1 exits to an outgoing lane
    v1.lane = SimpleNamespace(lane_id="south_out_0")
    clock.tick()
    detector.tick(1.0)
    assert "v1" not in detector.stopped_durations
    assert "v2" in detector.stopped_durations


def test_unstructured_legacy_detector_counts_all_active_vehicles() -> None:
    """Legacy unstructured mode (ring_only=False) counts all vehicles regardless of lane."""
    clock = Clock(1.0)
    vehicles = [
        SimpleNamespace(
            vehicle_id=f"v{i}",
            speed=0.0,
            lane=SimpleNamespace(lane_id="approach_lane"),
        )
        for i in range(5)
    ]
    detector = DeadlockDetector(clock, _FakePool(vehicles), ring_only=False)  # type: ignore[arg-type]

    for _ in range(6):
        clock.tick()
        detector.tick(1.0)

    assert detector.has_occurred
    insight = detector.get_insight()
    assert insight is not None
    assert "Natural deadlock emerged" in insight


def _metered_config() -> Dict[str, Any]:
    return {
        "simulation": {"warmupTime": 0.0, "timeStep": 0.1},
        "geometry": {"intersectionType": "roundabout"},
        "roads": {"approachLength": 100.0, "laneWidth": 3.5, "lanesPerApproach": 2},
        "controller": {
            "entryControl": "metered_entry",
            "entryMetering": {
                "phases": [
                    {"entries": ["north", "south"], "green": 20},
                    {"entries": ["east", "west"], "green": 20},
                ],
                "yellow": 3.0,
                "allRed": 2.0,
            },
        },
    }


def _conventional_config() -> Dict[str, Any]:
    return {
        "simulation": {"warmupTime": 0.0, "timeStep": 0.1},
        "geometry": {"intersectionType": "roundabout"},
        "roads": {"approachLength": 100.0, "laneWidth": 3.5, "lanesPerApproach": 2},
        "controller": {},
    }


def test_simulation_engine_initializes_metered_roundabout_deadlock_detector() -> None:
    """A metered roundabout run automatically gets an attached ring-only deadlock detector."""
    engine = SimulationEngine(Clock(0.1), duration=10.0, config=_metered_config())
    assert engine.deadlock_detector is not None
    assert isinstance(engine.deadlock_detector, DeadlockDetector)
    assert engine.deadlock_detector.ring_only is True


def test_simulation_engine_leaves_deadlock_detector_none_for_conventional_roundabout() -> (
    None
):
    """A conventional roundabout does not attach a deadlock detector (preserving bit-identity)."""
    engine = SimulationEngine(Clock(0.1), duration=10.0, config=_conventional_config())
    assert engine.deadlock_detector is None
