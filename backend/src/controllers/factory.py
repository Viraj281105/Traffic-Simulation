"""Factory functions for creating simulation controllers and metric callbacks."""

from typing import Any, Dict, Optional

from src.controllers.base import BaseController
from src.controllers.fixed_time_signal import FixedTimeSignalController
from src.controllers.roundabout import RoundaboutController
from src.core.clock import Clock
from src.core.engine import SimulationEngine
from src.core.enums import Direction
from src.metrics.collector import MetricCollector
from src.roads.network import RoadNetwork


def create_controller(config: Dict[str, Any], network: RoadNetwork) -> BaseController:
    """Creates a controller based on configuration geometry type."""
    geom_type = config.get("geometry", {}).get("intersectionType", "fixed_time_signal")
    if geom_type == "roundabout":
        return RoundaboutController(config, network)
    else:
        return FixedTimeSignalController(config, network)


def build_tick_callback(
    controller: BaseController,
    clock: Clock,
    engine: SimulationEngine,
    collector: MetricCollector,
    buffer: Optional[Any] = None,
    builder: Optional[Any] = None,
) -> Any:
    """Builds a standardized tick callback to sync the controller and collector."""

    def tick_callback() -> None:
        signals_state = {}
        if isinstance(controller, FixedTimeSignalController):
            state = controller.get_state()
            for sig in state.get("signals", []):
                direction_str = sig["direction"].upper()
                dir_enum = getattr(Direction, direction_str)
                signals_state[dir_enum] = sig["color"]
        else:
            # Roundabout or other: all directions are green
            for d in Direction:
                signals_state[d] = "green"

        collector.update(
            clock.get_elapsed_time(),
            engine.pool.active_vehicles,
            engine.pool.exited_vehicles,
            signals_state,
        )

        if buffer is not None and builder is not None:
            buffer.append(builder.build())

    return tick_callback
