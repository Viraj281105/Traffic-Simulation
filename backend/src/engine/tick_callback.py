"""The per-tick callback that feeds an engine's state to its metric collector
(and, for the versioned API, to a snapshot buffer)."""

from typing import Any, Optional

from src.controllers.base import BaseController
from src.controllers.factory import derive_signals_state
from src.controllers.fixed_time_signal import FixedTimeSignalController
from src.core.clock import Clock
from src.engine.simulation_engine import SimulationEngine
from src.metrics.collector import MetricCollector


def build_tick_callback(
    controller: BaseController,
    clock: Clock,
    engine: SimulationEngine,
    collector: MetricCollector,
    buffer: Optional[Any] = None,
    builder: Optional[Any] = None,
) -> Any:
    """Builds a standardized tick callback to sync the controller and collector."""
    # Let the engine reach this collector directly, so SimulationEngine.reset()
    # can clear its accumulated run state instead of leaving the previous run's
    # queue history and tick counts in place.
    engine.register_collector(collector)

    def tick_callback() -> None:
        # PET (see metrics/definitions/safety_conflicts.py) is only
        # geometrically valid for fixed_time_signal -- a roundabout's
        # curved connection lanes make ConflictManager's straight-chord
        # crossing points wrong, the same reason VehiclePool.update itself
        # never uses conflict_manager for roundabout geometry. Mirror that
        # gate here rather than passing it through unconditionally.
        signal_conflict_manager = (
            engine.conflict_manager
            if isinstance(controller, FixedTimeSignalController)
            else None
        )
        collector.update(
            clock.get_elapsed_time(),
            engine.pool.active_vehicles,
            engine.pool.exited_vehicles,
            derive_signals_state(controller),
            conflict_manager=signal_conflict_manager,
            signal_controller=(
                controller
                if isinstance(controller, FixedTimeSignalController)
                else None
            ),
        )

        if buffer is not None and builder is not None:
            buffer.append(builder.build())

    return tick_callback
