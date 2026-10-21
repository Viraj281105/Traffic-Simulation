"""Choosing a controller for a configuration, and reading its signal state."""

from typing import Any, Dict, cast

from src.controllers.adaptive_signal import AdaptiveSignalController, is_adaptive
from src.controllers.base import BaseController
from src.controllers.fixed_time_signal import FixedTimeSignalController
from src.controllers.roundabout import RoundaboutController
from src.core.enums import Direction
from src.roads.network import RoadNetwork


def create_controller(config: Dict[str, Any], network: RoadNetwork) -> BaseController:
    """Creates a controller based on configuration geometry type.

    A signalised junction runs the fixed-time plan unless
    ``controller.signalControl`` is ``"adaptive"`` (V1.3), which times the
    same plan's greens from detected demand.
    """
    geom_type = config.get("geometry", {}).get("intersectionType", "fixed_time_signal")
    if geom_type == "roundabout":
        ctrl_cfg = config.get("controller") or {}
        if (
            isinstance(ctrl_cfg, dict)
            and ctrl_cfg.get("entryControl") == "metered_entry"
        ):
            from src.controllers.signalised_roundabout import (
                SignalisedRoundaboutController,
            )

            return SignalisedRoundaboutController(config, network)
        return RoundaboutController(config, network)
    if is_adaptive(config):
        return AdaptiveSignalController(config, network)
    return FixedTimeSignalController(config, network)


def derive_signals_state(controller: BaseController) -> Dict[Direction, str]:
    """Reads the current per-direction signal colors from a controller.

    Shared by engine/tick_callback.py and run reproduction
    (src/history/reproduce.py) so both derive collector.update()'s signals_state the
    same way, from the controller's own current state after it has already
    been advanced for this tick — never by re-invoking controller.update().
    """
    if hasattr(controller, "signals_state"):
        return cast(Dict[Direction, str], controller.signals_state())
    if isinstance(controller, FixedTimeSignalController):
        signals_state: Dict[Direction, str] = {}
        state = controller.get_state()
        for sig in state.get("signals", []):
            direction_str = sig["direction"].upper()
            dir_enum = getattr(Direction, direction_str)
            signals_state[dir_enum] = sig["color"]
        return signals_state
    # Roundabout or other: all directions are green
    return {d: "green" for d in Direction}
