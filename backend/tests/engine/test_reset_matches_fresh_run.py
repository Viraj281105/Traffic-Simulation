"""A reset engine reruns exactly like a fresh one, for every control strategy.

``SimulationEngine.reset`` is what the live comparison's "Reset" calls (a
fresh run of the same strategies). A rerun after reset must be the run a new
engine would produce with the same seed: same vehicles, same states, same
metrics, same signal states. Each component that keeps run state (spawner,
pool, controller and its entry gate, conflict manager, metric collector,
deadlock detector) has to clear all of it; one that does not shows up here.
Checkpoint 3 found two that did not (F-35, F-36).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

import pytest

from src.controllers.factory import create_controller, derive_signals_state
from src.core.clock import Clock
from src.engine.simulation_engine import SimulationEngine
from src.engine.tick_callback import build_tick_callback
from src.metrics.collector import MetricCollector
from src.scenario.documents import compile_scenario, parse_scenario

TICKS = 600  # 60 s: queues form and the signals change phase


def _document(
    junction: str, roundabout: Dict[str, Any] | None = None
) -> Dict[str, Any]:
    doc: Dict[str, Any] = {
        "format": "urbanflow-scenario",
        "version": 1,
        "name": "reset",
        "junction": {"type": junction},
        "approaches": {
            d: {
                "lanes": 2,
                "length": 150.0,
                "vehiclesPerHour": 500,
                "turning": {"left": 0.25, "straight": 0.5, "right": 0.25},
                "vehicleMix": {"car": 0.7, "bus": 0.1, "truck": 0.1, "motorcycle": 0.1},
            }
            for d in ("north", "south", "east", "west")
        },
        "simulation": {"duration": 200.0, "warmup": 10.0, "seed": 21},
    }
    if roundabout is not None:
        doc["roundabout"] = roundabout
    return doc


def _cars_only(doc: Dict[str, Any]) -> Dict[str, Any]:
    for approach in doc["approaches"].values():
        approach.pop("vehicleMix", None)
    return doc


_METERED = {
    "circulatingLanes": 2,
    "entryControl": "metered_entry",
    "entryMetering": {
        "phases": [
            {"entries": ["north", "south"], "green": 20.0},
            {"entries": ["east", "west"], "green": 20.0},
        ],
        "yellow": 3.0,
        "allRed": 2.0,
        "spillbackGuard": {"enabled": True, "stoppedThreshold": 2, "maxHold": 10.0},
        "queueCap": {"enabled": True, "vehicles": 8},
    },
}

# (id, document, strategy, unstructured traffic)
CASES: List[Tuple[str, Dict[str, Any], str, bool]] = [
    ("fixed-time", _document("fixed_time_signal"), "fixed_time", False),
    ("adaptive", _document("adaptive_signal"), "adaptive", False),
    (
        "roundabout",
        _document("roundabout", {"circulatingLanes": 2}),
        "roundabout",
        False,
    ),
    ("metered-roundabout", _document("roundabout", _METERED), "roundabout", False),
    # A vehicle mix under unstructuredTraffic: every class drives the
    # stochastic model on the spawner's stream (F-38).
    (
        "roundabout-stochastic-mixed",
        _document("roundabout", {"circulatingLanes": 2}),
        "roundabout",
        True,
    ),
    # Cars only: the engine-wide stochastic model and the shared stream (F-35).
    (
        "fixed-time-stochastic",
        _cars_only(_document("fixed_time_signal")),
        "fixed_time",
        True,
    ),
]


def _build(
    document: Dict[str, Any], strategy: str, unstructured: bool
) -> Tuple[SimulationEngine, Any, MetricCollector]:
    parsed, errors = parse_scenario(document)
    assert not errors, errors
    config = compile_scenario(parsed, strategy)
    if unstructured:
        config["traffic"]["unstructuredTraffic"] = True
    clock = Clock(time_step=0.1)
    engine = SimulationEngine(clock, duration=200.0, config=config)
    controller = create_controller(config, engine.network)
    engine.controller = controller
    collector = MetricCollector(config)
    engine.register_tick_callback(
        build_tick_callback(controller, clock, engine, collector)
    )
    return engine, controller, collector


def _observe(
    engine: SimulationEngine, controller: Any, collector: MetricCollector
) -> Dict[str, Any]:
    for _ in range(TICKS):
        engine.step()
    vehicles = [
        (
            v.vehicle_id,
            v.lane.lane_id if v.lane is not None else None,
            v.position,
            v.speed,
            v.state.value,
            v.wait_time,
            v.stop_count,
        )
        for v in engine.pool.active_vehicles
    ]
    metrics = collector.get_metrics(
        engine.clock.get_elapsed_time(),
        engine.pool.active_vehicles,
        engine.pool.exited_vehicles,
        engine.spawner.spawned_count if engine.spawner else 0,
        engine.pool.collision_count,
        engine.spawner.demand_accounting() if engine.spawner else None,
    )
    detector = engine.deadlock_detector
    return {
        "vehicles": vehicles,
        "exited": [v.vehicle_id for v in engine.pool.exited_vehicles],
        "metrics": metrics,
        "signals": derive_signals_state(controller),
        "deadlock": detector.get_insight() if detector is not None else None,
    }


@pytest.mark.parametrize(
    "case_id, document, strategy, unstructured", CASES, ids=[c[0] for c in CASES]
)
def test_rerun_after_reset_equals_a_fresh_run(
    case_id: str, document: Dict[str, Any], strategy: str, unstructured: bool
) -> None:
    logging.disable(logging.WARNING)  # deadlock and collision log lines
    try:
        fresh = _observe(*_build(document, strategy, unstructured))
        engine, controller, collector = _build(document, strategy, unstructured)
        _observe(engine, controller, collector)
        engine.reset()
        rerun = _observe(engine, controller, collector)
    finally:
        logging.disable(logging.NOTSET)
    assert rerun["vehicles"], f"{case_id}: no vehicles after {TICKS} ticks"
    for key in ("vehicles", "exited", "signals", "deadlock", "metrics"):
        assert rerun[key] == fresh[key], f"{case_id}: {key} differ after reset"
