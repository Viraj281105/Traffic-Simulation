"""Property-based invariants of the engines (V3.2 W32): vehicles are conserved, queues are never negative.

Hypothesis draws a seed and a demand level; the signal and roundabout engines are stepped for a short
run and checked at several points along it, not only at the end.
"""

from typing import Any, Dict

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from src.metrics.definitions.queue_length import get_current_queue_lengths
from src.snapshot.dual_orchestrator import DualSimulationOrchestrator
from src.study.multiseed import default_study_config, seeded_run_config

DURATION = 40.0
STEPS = 300  # 30 simulated seconds at the default 0.1 s step
CHECK_EVERY = 50

pytestmark = pytest.mark.integration


def _config(seed: int, arrival_rate: float) -> Dict[str, Any]:
    base = default_study_config(DURATION)
    base["traffic"]["arrivalRate"] = arrival_rate
    return seeded_run_config(base, seed, DURATION)


def _check_invariants(engine: Any) -> None:
    pool = engine.pool
    active = len(pool.active_vehicles)
    exited = len(pool.exited_vehicles)
    spawner = engine.spawner
    # Every vehicle ever spawned is either still in the network or has left it.
    assert spawner.spawned_count == active + exited
    # No vehicle is counted twice.
    ids = [id(v) for v in pool.active_vehicles] + [id(v) for v in pool.exited_vehicles]
    assert len(ids) == len(set(ids))
    # Every arrival is admitted, waiting at the entry, or rejected.
    demand = spawner.demand_accounting()
    assert demand["arrivals"] == (
        demand["admitted"] + demand["waitingAtEntry"] + demand["rejected"]
    )
    for count in (demand["admitted"], demand["waitingAtEntry"], demand["rejected"]):
        assert count >= 0
    # No queue is negative.
    queues = get_current_queue_lengths(pool.active_vehicles)
    assert all(length >= 0 for length in queues.values())
    assert sum(queues.values()) <= active


@pytest.mark.parametrize("geometry", ["signal", "roundabout"])
@settings(
    max_examples=6,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(seed=st.integers(0, 2**31 - 1), arrival_rate=st.floats(0.05, 1.2))
def test_vehicles_conserved_and_queues_non_negative(
    geometry: str, seed: int, arrival_rate: float
) -> None:
    orchestrator = DualSimulationOrchestrator(_config(seed, arrival_rate))
    engine = getattr(orchestrator, f"engine_{geometry}")
    for step in range(1, STEPS + 1):
        engine.step()
        if step % CHECK_EVERY == 0:
            _check_invariants(engine)
    final_queues = get_current_queue_lengths(engine.pool.active_vehicles)
    assert all(length >= 0 for length in final_queues.values())


@settings(max_examples=4, deadline=None)
@given(seed=st.integers(0, 2**31 - 1))
def test_reported_queue_metrics_never_negative(seed: int) -> None:
    orchestrator = DualSimulationOrchestrator(_config(seed, 0.9))
    engine = orchestrator.engine_signal
    for _ in range(STEPS):
        engine.step()
    metrics = orchestrator.collector_signal.get_metrics(
        orchestrator.clock_signal.get_elapsed_time(),
        engine.pool.active_vehicles,
        engine.pool.exited_vehicles,
        engine.spawner.spawned_count,
        engine.pool.collision_count,
        engine.spawner.demand_accounting(),
    )
    assert metrics["averageQueueLength"] >= 0
    assert metrics["maxQueueLength"] >= 0
    assert all(v >= 0 for v in metrics["currentQueueLengths"].values())
    assert metrics["totalVehiclesSpawned"] == (
        metrics["activeVehicleCount"] + len(engine.pool.exited_vehicles)
    )
