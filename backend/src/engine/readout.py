"""Reading a running engine's metrics from outside its tick loop."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.engine.simulation_engine import SimulationEngine
    from src.metrics.collector import MetricCollector


def engine_metrics(engine: SimulationEngine, collector: MetricCollector) -> Any:
    """The collector's metrics for the engine's current state -- the same
    call that produces every snapshot's "metrics" -- read under the engine
    lock so a concurrent tick cannot interleave."""
    with engine.lock:
        return collector.get_metrics(
            engine.clock.get_elapsed_time(),
            engine.pool.active_vehicles,
            engine.pool.exited_vehicles,
            engine.spawner.spawned_count if engine.spawner else 0,
            engine.pool.collision_count,
        )
