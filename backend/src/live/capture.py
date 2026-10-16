"""An exact, reproducible record of the run a live session is showing."""

import copy
from typing import Any, Dict, Optional

from src.core.engine import SimulationEngine
from src.live.sessions import LiveSession
from src.metrics.collector import MetricCollector
from src.metrics.readout import engine_metrics


def capture_engine_run(
    session: Optional[LiveSession], mode: str, claimed_seed: Any
) -> Optional[Dict[str, Any]]:
    """Reads the exact config, seed, elapsed time, timing and metrics of the
    run the caller is saving from its live engine (or dual orchestrator).

    The metrics are computed here, at the recorded elapsed time, rather than
    taken from the client: the last snapshot a client received can trail the
    engine by a tick or more, and stored metrics must describe the same
    instant as the stored elapsed time for the run to be reproducible.

    Returns None -- the caller then falls back to the client-supplied
    config -- when no engine has actually run, or when the engine's seed is
    not the seed the client says it is saving, so a stale or different
    engine's configuration is never attributed to this run.
    """
    if session is None:
        return None
    engine: Optional[SimulationEngine]
    collector: Optional[MetricCollector]
    if mode == "dual":
        orch = session.dual_sim_orchestrator
        if orch is None:
            return None
        engine = orch.engine_signal
        clock = orch.clock_signal
        collector = orch.collector_signal
        # The orchestrator derives both engines' configs from this one.
        config = orch.config

        def read_metrics() -> Dict[str, Any]:
            return {
                "signal": engine_metrics(orch.engine_signal, orch.collector_signal),
                "roundabout": engine_metrics(
                    orch.engine_roundabout, orch.collector_roundabout
                ),
            }
    else:
        engine = session.live_sim_data.get("engine")
        collector = session.live_sim_data.get("collector")
        if engine is None or collector is None:
            return None
        clock = engine.clock
        config = engine.config
        live_engine, live_collector = engine, collector

        def read_metrics() -> Dict[str, Any]:
            return dict(engine_metrics(live_engine, live_collector))

    elapsed = clock.get_elapsed_time()
    seed = engine.spawner.random_seed if engine.spawner is not None else None
    if elapsed <= 0 or seed is None:
        return None
    if claimed_seed is not None and claimed_seed != seed:
        return None
    exact_config = copy.deepcopy(config)
    exact_config.setdefault("simulation", {})["randomSeed"] = seed
    return {
        "config": exact_config,
        "seed": seed,
        "elapsed": elapsed,
        "timeStep": clock.time_step,
        "duration": engine.duration,
        "warmupTime": collector.warmup_time,
        "metrics": read_metrics(),
    }
