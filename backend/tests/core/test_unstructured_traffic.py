"""Regression tests for the opt-in unstructured-traffic mode.

The mode swaps in a stochastic IDM and attaches a deadlock detector to the
engine tick. Both are off by default, so the deterministic path is covered by
the existing suites; these tests pin the opt-in path and the default.
"""

from types import SimpleNamespace
from typing import Any, Dict, List

from src.core.clock import Clock
from src.core.engine import SimulationEngine
from src.metrics.deadlock_detector import DeadlockDetector
from src.vehicles.idm import IntelligentDriverModel
from src.vehicles.stochastic_idm import StochasticIDM


def _config(unstructured: bool) -> Dict[str, Any]:
    return {
        "simulation": {"warmupTime": 0.0, "timeStep": 0.1},
        "geometry": {"intersectionType": "fixed_time_signal"},
        "roads": {"approachLength": 100.0, "laneWidth": 3.5, "lanesPerApproach": 2},
        "traffic": {"unstructuredTraffic": unstructured},
    }


def test_default_engine_has_no_detector_and_plain_idm() -> None:
    engine = SimulationEngine(Clock(0.1), duration=10.0, config=_config(False))
    assert engine.deadlock_detector is None
    assert type(engine.idm) is IntelligentDriverModel


def test_unstructured_engine_ticks_without_error() -> None:
    """The detector runs on every tick; a bad Clock attribute used to make
    each step raise AttributeError."""
    engine = SimulationEngine(Clock(0.1), duration=10.0, config=_config(True))
    assert isinstance(engine.idm, StochasticIDM)
    assert isinstance(engine.deadlock_detector, DeadlockDetector)
    for _ in range(20):
        engine.step()
    assert engine.clock.get_tick_count() == 20


class _FakePool:
    def __init__(self, vehicles: List[Any]) -> None:
        self._vehicles = vehicles

    def get_active_vehicles(self) -> List[Any]:
        return self._vehicles


def test_deadlock_detector_flags_and_resolves() -> None:
    clock = Clock(1.0)
    vehicles = [SimpleNamespace(vehicle_id=f"v{i}", speed=0.0) for i in range(6)]
    detector = DeadlockDetector(clock, _FakePool(vehicles))  # type: ignore[arg-type]

    for _ in range(7):
        clock.tick()
        detector.tick(1.0)
    assert detector.has_occurred
    insight = detector.get_insight()
    assert insight is not None and "deadlock emerged" in insight

    for v in vehicles:
        v.speed = 5.0
    clock.tick()
    detector.tick(1.0)
    assert not detector.has_occurred
    resolved = detector.get_insight()
    assert resolved is not None and "resolved" in resolved


def test_stochastic_idm_returns_finite_acceleration() -> None:
    idm = StochasticIDM()
    for speed in (0.0, 0.05, 1.0, 10.0):
        acc = idm.calculate_acceleration(speed, 13.9, lead_speed=0.0, gap=3.0)
        assert acc == acc and abs(acc) < 100.0
