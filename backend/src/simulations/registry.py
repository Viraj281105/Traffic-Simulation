"""The in-memory registry of versioned simulations and how one is assembled.

``simulations_db`` maps a simulation id to its engine, collector, controller,
config id, snapshot buffer and creation time. It is bounded: completed or
errored simulations are evicted, oldest first, to make room, and a RUNNING or
PAUSED one never is. A simulation is written to run history
(``simulation_runs``) the moment it completes, is stopped or errors.
"""

import logging
import threading
import time
import uuid
from typing import Any, Dict

from src.controllers.factory import create_controller
from src.core.clock import Clock
from src.core.enums import SimulationStatus
from src.core.provenance import build_run_provenance
from src.database.dao import SimulationRunDAO
from src.database.db import get_db_connection
from src.engine.simulation_engine import SimulationEngine
from src.engine.tick_callback import build_tick_callback
from src.metrics.collector import MetricCollector
from src.snapshot.buffer import SnapshotBuffer
from src.snapshot.builder import SnapshotBuilder
from src.strategies.validator import check_scenario_strategy_compatibility

logger = logging.getLogger(__name__)

simulations_db: Dict[str, Dict[str, Any]] = {}
simulations_lock: threading.RLock = threading.RLock()

# Bound the in-memory simulation registry so it cannot grow without limit.
MAX_CONCURRENT_SIMULATIONS = 50


class InvalidSimulationConfigError(Exception):
    """The configuration cannot be built into an engine; the message says why."""


class SimulationLimitReachedError(RuntimeError):
    """Every slot holds a simulation that is still running or paused."""


def persist_completed_run(
    sim_id: str,
    config: Dict[str, Any],
    engine: SimulationEngine,
    collector: MetricCollector,
    status: str = "completed",
) -> None:
    """Records a completed, stopped, or errored simulation into simulation_runs.

    Reads the random seed straight from the spawner — the single
    authoritative place a seed is resolved (see VehicleSpawner.__init__) —
    so the persisted seed is always the exact one actually used, whether it
    was user-supplied or auto-generated. Any failure here is logged and
    swallowed rather than propagated, so a database hiccup can never flip an
    otherwise-successful simulation into an error state or mask a simulation failure.
    """
    try:
        itype = config.get("geometry", {}).get("intersectionType", "unknown")
        seed = (
            engine.spawner.random_seed
            if engine.spawner is not None
            else config.get("simulation", {}).get("randomSeed", 0)
        )
        arrival_rate = config.get("traffic", {}).get("arrivalRate", 0.5)
        elapsed = engine.clock.get_elapsed_time()
        try:
            final_metrics = collector.get_metrics(
                elapsed,
                engine.pool.active_vehicles,
                engine.pool.exited_vehicles,
                engine.spawner.spawned_count if engine.spawner else 0,
                engine.pool.collision_count,
            )
        except Exception:
            logger.exception(
                "Failed to calculate metrics for simulation %s with status %s",
                sim_id,
                status,
            )
            final_metrics = {}
        with get_db_connection() as conn:
            SimulationRunDAO.save(
                conn,
                sim_id,
                status,
                elapsed,
                intersection_type=itype,
                random_seed=seed,
                arrival_rate=arrival_rate,
                duration=elapsed,
                config=config,
                summary_metrics=final_metrics,
                provenance=build_run_provenance(
                    config_source="engine",
                    run_mode="single",
                    time_step=engine.clock.time_step,
                    duration=engine.duration,
                    warmup_time=collector.warmup_time,
                ),
            )
    except Exception:
        logger.exception("Failed to persist simulation run %s to history", sim_id)


def evict_completed_simulations() -> None:
    """Evicts the oldest completed/errored simulations to make room.

    Never evicts a RUNNING or PAUSED simulation.
    """
    with simulations_lock:
        if len(simulations_db) < MAX_CONCURRENT_SIMULATIONS:
            return

        evictable = [
            (sid, entry)
            for sid, entry in simulations_db.items()
            if entry["engine"].status
            in (SimulationStatus.COMPLETED, SimulationStatus.ERROR)
        ]
        evictable.sort(key=lambda item: item[1].get("created_at", 0.0))

        slots_needed = len(simulations_db) - MAX_CONCURRENT_SIMULATIONS + 1
        for sid, _ in evictable[:slots_needed]:
            del simulations_db[sid]


def register_simulation(config: Dict[str, Any]) -> Dict[str, Any]:
    """Builds a simulation for an already-validated configuration and adds it
    to the registry; returns its registry entry plus ``sim_id``.

    A config that passed schema validation but is semantically invalid (e.g.
    duration <= 0, an unsupported phaseSequence entry) makes the engine,
    controller or collector raise ValueError/KeyError/TypeError, reported as
    InvalidSimulationConfigError; a full registry raises SimulationLimitReachedError.
    Nothing is registered in either case.
    """
    sim_id = str(uuid.uuid4())
    config_id = str(uuid.uuid4())

    try:
        check_scenario_strategy_compatibility(config)
        clock = Clock(time_step=config.get("simulation", {}).get("timeStep", 0.1))
        duration = config.get("simulation", {}).get("duration", 300)
        engine = SimulationEngine(clock, duration=duration, config=config)

        controller = create_controller(config, engine.network)
        engine.controller = controller

        collector = MetricCollector(config)
    except (ValueError, KeyError, TypeError) as exc:
        raise InvalidSimulationConfigError(str(exc)) from exc

    builder = SnapshotBuilder(sim_id, config_id, engine, collector, controller)
    buffer = SnapshotBuffer(max_frames=1000)

    # Register tick callback on engine to update collector and controller
    engine.register_tick_callback(
        build_tick_callback(controller, clock, engine, collector, buffer, builder)
    )
    # Persist to run history the moment the simulation completes (naturally
    # or via an explicit stop) or terminates in an error state — the single
    # existing "run-save flow" this extends to cover ordinary /api/v1/simulations
    # runs, not just sweeps and manually-saved replays.
    has_persisted = False
    persist_lock = threading.Lock()

    def _on_status_change(new_status: SimulationStatus) -> None:
        nonlocal has_persisted
        if new_status in (SimulationStatus.COMPLETED, SimulationStatus.ERROR):
            with persist_lock:
                if has_persisted:
                    return
                has_persisted = True
            try:
                persist_completed_run(
                    sim_id,
                    config,
                    engine,
                    collector,
                    status=new_status.value.lower(),
                )
            except Exception:
                logger.exception(
                    "Failed to persist simulation run %s on status transition %s",
                    sim_id,
                    new_status,
                )

    engine.register_status_callback(_on_status_change)

    created_at = time.time()
    entry: Dict[str, Any] = {
        "engine": engine,
        "collector": collector,
        "controller": controller,
        "config_id": config_id,
        "buffer": buffer,
        "created_at": created_at,
    }
    with simulations_lock:
        evict_completed_simulations()
        if len(simulations_db) >= MAX_CONCURRENT_SIMULATIONS:
            raise SimulationLimitReachedError("Maximum concurrent simulations reached")
        simulations_db[sim_id] = entry

    return {**entry, "sim_id": sim_id}
