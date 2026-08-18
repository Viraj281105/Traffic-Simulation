import json
from typing import Any, Dict

from src.controllers.fixed_time_signal import FixedTimeSignalController
from src.controllers.roundabout import RoundaboutController
from src.core.clock import Clock
from src.core.engine import SimulationEngine
from src.core.enums import Direction
from src.metrics.collector import MetricCollector
from src.snapshot.builder import SnapshotBuilder


class DualSimulationOrchestrator:
    """Orchestrates two parallel simulations (Fixed-Time Signal and Roundabout) in lockstep with matching random seeds."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config

        # Make deep copies of the configuration for both instances
        self.config_signal = json.loads(json.dumps(config))
        self.config_signal["geometry"] = self.config_signal.get("geometry", {})
        self.config_signal["geometry"]["intersectionType"] = "fixed_time_signal"

        self.config_roundabout = json.loads(json.dumps(config))
        self.config_roundabout["geometry"] = self.config_roundabout.get("geometry", {})
        self.config_roundabout["geometry"]["intersectionType"] = "roundabout"

        # Propagate random seed to align spawn sequences
        seed = config.get("simulation", {}).get("randomSeed", 42)
        if "simulation" not in self.config_signal:
            self.config_signal["simulation"] = {}
        if "simulation" not in self.config_roundabout:
            self.config_roundabout["simulation"] = {}
        self.config_signal["simulation"]["randomSeed"] = seed
        self.config_roundabout["simulation"]["randomSeed"] = seed

        # Build Signal Simulation
        self.clock_signal = Clock(time_step=0.1)
        self.engine_signal = SimulationEngine(self.clock_signal, duration=300, config=self.config_signal)
        self.controller_signal = FixedTimeSignalController(self.config_signal, self.engine_signal.network)
        self.collector_signal = MetricCollector(self.config_signal)
        self.builder_signal = SnapshotBuilder("dual_signal", "dual_cfg", self.engine_signal, self.collector_signal, self.controller_signal)

        def tick_callback_sig() -> None:
            self.controller_signal.update(0.1, self.engine_signal.pool.active_vehicles)
            signals_state = {}
            state = self.controller_signal.get_state()
            for sig in state.get("signals", []):
                dir_enum = getattr(Direction, sig["direction"].upper())
                signals_state[dir_enum] = sig["color"]
            self.collector_signal.update(
                self.clock_signal.get_elapsed_time(),
                self.engine_signal.pool.active_vehicles,
                self.engine_signal.pool.exited_vehicles,
                signals_state,
            )
        self.engine_signal.register_tick_callback(tick_callback_sig)

        # Build Roundabout Simulation
        self.clock_roundabout = Clock(time_step=0.1)
        self.engine_roundabout = SimulationEngine(self.clock_roundabout, duration=300, config=self.config_roundabout)
        self.controller_roundabout = RoundaboutController(self.config_roundabout, self.engine_roundabout.network)
        self.collector_roundabout = MetricCollector(self.config_roundabout)
        self.builder_roundabout = SnapshotBuilder("dual_roundabout", "dual_cfg", self.engine_roundabout, self.collector_roundabout, self.controller_roundabout)

        def tick_callback_round() -> None:
            self.controller_roundabout.update(0.1, self.engine_roundabout.pool.active_vehicles)
            self.collector_roundabout.update(
                self.clock_roundabout.get_elapsed_time(),
                self.engine_roundabout.pool.active_vehicles,
                self.engine_roundabout.pool.exited_vehicles,
                {},
            )
        self.engine_roundabout.register_tick_callback(tick_callback_round)

    def start(self) -> None:
        self.engine_signal.start()
        self.engine_roundabout.start()

    def pause(self) -> None:
        self.engine_signal.pause()
        self.engine_roundabout.pause()

    def stop(self) -> None:
        self.engine_signal.stop()
        self.engine_roundabout.stop()

    def get_status(self) -> str:
        return self.engine_signal.status.value.lower()

    def get_dual_snapshot(self) -> Dict[str, Any]:
        return {
            "tick": self.clock_signal.get_tick_count(),
            "elapsed": round(self.clock_signal.get_elapsed_time(), 2),
            "signal": self.builder_signal.build(),
            "roundabout": self.builder_roundabout.build(),
        }
