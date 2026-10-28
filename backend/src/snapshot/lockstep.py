"""Several simulations of one scenario stepped in lockstep.

The live comparisons run every control on the same traffic: one engine per
control, all built from configurations derived from one scenario, sharing a
seed and a time step, and advanced one tick each per loop iteration so their
clocks never drift apart. This module owns that mechanism once; the
signal-vs-roundabout pair (``dual_orchestrator``) and the any-strategies
comparison (``strategy_comparison``) differ only in which configurations
they derive.
"""

import logging
import random
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from src.controllers.factory import create_controller
from src.core.clock import Clock
from src.core.enums import SimulationStatus
from src.engine.simulation_engine import SimulationEngine
from src.engine.tick_callback import build_tick_callback
from src.metrics.collector import MetricCollector
from src.snapshot.builder import SnapshotBuilder

logger = logging.getLogger(__name__)


def resolve_shared_seed(config: Dict[str, Any], what: str) -> int:
    """The seed every run of a comparison shares, drawing (and recording in
    ``config``) a fresh one when the scenario sets none."""
    seed = config.get("simulation", {}).get("randomSeed")
    if seed is None:
        # Never fall back to the shared global `random` module (see
        # vehicles/spawner.py for the same fix and rationale). Use a
        # private, independently OS-seeded instance instead, and log
        # the fallback so it is never silent.
        seed = random.Random().randint(1, 10_000_000)
        logger.warning(
            "No simulation.randomSeed configured for %s; generated seed=%d "
            "for this comparison run. Pass randomSeed explicitly for "
            "reproducible comparisons.",
            what,
            seed,
        )
        config.setdefault("simulation", {})["randomSeed"] = seed
    return seed


@dataclass
class LockstepRun:
    """One control's simulation within a lockstep comparison."""

    key: str
    config: Dict[str, Any]
    clock: Clock
    engine: SimulationEngine
    controller: Any
    collector: MetricCollector
    builder: SnapshotBuilder


def build_run(key: str, config: Dict[str, Any], builder_name: str) -> LockstepRun:
    """Builds one engine, its controller, collector and snapshot builder."""
    sim = config.get("simulation", {})
    # Every engine steps with the configured time step, so a study's Δt
    # choice is honoured and a reproduction can re-run at the recorded one.
    clock = Clock(time_step=float(sim.get("timeStep", 0.1)))
    engine = SimulationEngine(clock, duration=sim.get("duration", 300), config=config)
    controller = create_controller(config, engine.network)
    # CRITICAL: Assign controller to engine so engine.step() calls
    # controller.update() BEFORE vehicle physics (zero-latency response)
    engine.controller = controller
    collector = MetricCollector(config)
    builder = SnapshotBuilder(builder_name, "dual_cfg", engine, collector, controller)
    engine.register_tick_callback(
        build_tick_callback(controller, clock, engine, collector)
    )
    return LockstepRun(key, config, clock, engine, controller, collector, builder)


class LockstepOrchestrator:
    """Runs a fixed, ordered set of simulations one tick each per iteration.

    Lifecycle (start / pause / resume / stop / reset) applies to every run at
    once, and the first run's clock paces the loop: all runs share its time
    step and duration, so they finish on the same tick.
    """

    def __init__(self, runs: List[Tuple[str, Dict[str, Any], str]]) -> None:
        if not runs:
            raise ValueError("A lockstep comparison needs at least one run.")
        self.speed_multiplier = 1.0
        self.runs: List[LockstepRun] = [
            build_run(key, config, builder_name) for key, config, builder_name in runs
        ]
        self._thread: Optional[threading.Thread] = None
        self._stop_event: threading.Event = threading.Event()
        self._lock: threading.Lock = threading.Lock()

    @property
    def _lead(self) -> LockstepRun:
        return self.runs[0]

    def _transition_all(self, status: SimulationStatus) -> None:
        for run in self.runs:
            run.engine._transition_to(status)

    def start(self) -> None:
        with self._lock:
            if self._lead.engine.status == SimulationStatus.RUNNING:
                return
            if self._lead.engine.status == SimulationStatus.PAUSED:
                self.resume()
                return

            self._transition_all(SimulationStatus.RUNNING)
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            start_time = time.time()

            try:
                # Check and tick under one lock hold, as SimulationEngine's own
                # loop does: a stop() between the two used to make step() raise
                # on COMPLETED engines, which was then reported as ERROR.
                with self._lock:
                    if any(
                        run.engine.status != SimulationStatus.RUNNING
                        for run in self.runs
                    ):
                        break
                    self.step()
            except Exception:
                logger.exception("Error in lockstep simulation step")
                with self._lock:
                    self._transition_all(SimulationStatus.ERROR)
                break

            with self._lock:
                if all(
                    run.engine.status == SimulationStatus.COMPLETED
                    for run in self.runs
                ):
                    break

            elapsed = time.time() - start_time
            target_sleep = self._lead.clock.time_step / (
                self._lead.engine.config.get("simulation", {}).get("timeScale", 1.0)
                * self.speed_multiplier
            )
            time.sleep(max(0.0, target_sleep - elapsed))

    def resume(self) -> None:
        thread_to_join: Optional[threading.Thread] = None
        with self._lock:
            if self._lead.engine.status != SimulationStatus.PAUSED:
                return
            thread_to_join = self._thread

        if (
            thread_to_join is not None
            and thread_to_join is not threading.current_thread()
        ):
            thread_to_join.join()

        with self._lock:
            if self._lead.engine.status == SimulationStatus.PAUSED:
                self._transition_all(SimulationStatus.RUNNING)
                self._stop_event.clear()
                self._thread = threading.Thread(target=self._run_loop, daemon=True)
                self._thread.start()

    def pause(self) -> None:
        with self._lock:
            if self._lead.engine.status == SimulationStatus.RUNNING:
                self._stop_event.set()
                self._transition_all(SimulationStatus.PAUSED)

    def stop(self) -> None:
        thread_to_join: Optional[threading.Thread] = None
        with self._lock:
            self._stop_event.set()
            thread_to_join = self._thread
            self._transition_all(SimulationStatus.COMPLETED)

        if (
            thread_to_join is not None
            and thread_to_join is not threading.current_thread()
        ):
            thread_to_join.join()

    def reset(self) -> None:
        thread_to_join: Optional[threading.Thread] = None
        with self._lock:
            self._stop_event.set()
            thread_to_join = self._thread

        if (
            thread_to_join is not None
            and thread_to_join is not threading.current_thread()
        ):
            thread_to_join.join()

        with self._lock:
            for run in self.runs:
                run.engine.reset()

    def step(self) -> None:
        for run in self.runs:
            run.engine.step()

    def get_status(self) -> str:
        if any(run.engine.status == SimulationStatus.ERROR for run in self.runs):
            return "error"
        if all(run.engine.status == SimulationStatus.COMPLETED for run in self.runs):
            return "completed"
        return str(self._lead.engine.status.value).lower()
