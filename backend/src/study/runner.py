"""Bounded parallel execution of study simulations, with live progress.

A volume sweep or a Monte Carlo study is a list of independent simulations:
one per (arrival-rate tier or seed) x geometry. Each geometry's engine has its
own clock, network, controller and privately seeded ``random.Random`` (see
vehicles/spawner.py), so the signal and roundabout sides of a
DualSimulationOrchestrator share no state. Running one geometry on its own,
in its own process, therefore gives exactly the result the lockstep loop gave
(tests/study/test_runner.py checks this bit for bit). Results are returned in
task order, so aggregation downstream is unchanged and deterministic whatever
order the workers finish in.

The work runs in a ``ProcessPoolExecutor``, not threads: simulation is pure
Python and holds the GIL, so running it inside the API process (as the study
endpoints used to) made every other request and live stream wait on it.

Worker count (``STUDY_WORKERS``):
  * unset -- one per CPU, at most ``MAX_AUTO_WORKERS`` (a t3.micro gets 2);
  * ``N`` -- exactly N worker processes (clamped to 1..32);
  * ``0`` -- run inline in the calling thread, no pool (the test suite uses
    this so monkeypatched engines keep working; see tests/conftest.py).
"""

from __future__ import annotations

import json
import logging
import multiprocessing
import os
import threading
import time
import uuid
from concurrent.futures import Future, ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from dataclasses import dataclass
from functools import partial
from typing import Any, Callable, Dict, List, Optional

from src.snapshot.dual_orchestrator import DualSimulationOrchestrator

logger = logging.getLogger(__name__)

GEOMETRY_TITLES = {"signal": "Signal", "roundabout": "Roundabout"}

# One process per core costs ~40 MB each; eight keeps a large dev machine
# responsive and bounds memory, and small hosts get one per core.
MAX_AUTO_WORKERS = 8
MAX_WORKERS = 32

# Progress messages per simulation (every 2 % of its ticks).
_REPORTS_PER_TASK = 50


@dataclass(frozen=True)
class SimTask:
    """One geometry of one dual-simulation configuration."""

    config: Dict[str, Any]
    geometry: str  # "signal" | "roundabout"
    duration: float
    label: str
    # Relative expected cost; heavier tasks are started first so the slowest
    # simulation is not the last one to begin. Affects scheduling only.
    cost: float = 0.0


def study_workers() -> int:
    raw = os.environ.get("STUDY_WORKERS", "").strip()
    if raw:
        try:
            return max(0, min(MAX_WORKERS, int(raw)))
        except ValueError:
            logger.warning("Ignoring invalid STUDY_WORKERS=%r", raw)
    return max(1, min(MAX_AUTO_WORKERS, os.cpu_count() or 1))


def simulate_geometry(
    config: Dict[str, Any],
    geometry: str,
    duration: float,
    report: Optional[Callable[[float], None]] = None,
) -> Dict[str, Any]:
    """Run one geometry of ``config`` for ``duration`` simulated seconds.

    Returns its final metrics plus what a stored run records about it: the
    engine's own config (with the controller settings the orchestrator
    injects), elapsed time, tick count, time step, duration and warm-up.
    """
    orch = DualSimulationOrchestrator(config)
    engine = getattr(orch, f"engine_{geometry}")
    clock = getattr(orch, f"clock_{geometry}")
    collector = getattr(orch, f"collector_{geometry}")

    # Counted on the engine's own clock, so a configured timeStep runs the
    # same simulated time.
    steps = clock.ticks_for_duration(duration)
    every = max(1, steps // _REPORTS_PER_TASK)
    if report:
        report(0.0)
    for tick in range(1, steps + 1):
        engine.step()
        if report and tick % every == 0:
            report(tick / steps)

    elapsed = clock.get_elapsed_time()
    metrics = collector.get_metrics(
        elapsed,
        engine.pool.active_vehicles,
        engine.pool.exited_vehicles,
        engine.spawner.spawned_count if engine.spawner else 0,
        engine.pool.collision_count,
    )
    return {
        "metrics": metrics,
        "elapsed": elapsed,
        "steps": steps,
        "config": json.loads(json.dumps(getattr(orch, f"config_{geometry}"))),
        "timeStep": clock.time_step,
        "engineDuration": engine.duration,
        "warmupTime": collector.warmup_time,
    }


class Progress:
    """Live, thread-safe progress of a list of simulations.

    Every number comes from the simulations themselves: a task counts as
    running once its worker has started it, and its fraction is ticks done /
    ticks total. ``etaSeconds`` is only given once enough work is done for
    the extrapolation to mean something.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._labels: List[str] = []
        self._fractions: List[float] = []
        self._started: List[bool] = []
        self._done: List[bool] = []
        self._t0 = time.monotonic()
        self.phase = "queued"

    def begin(self, labels: List[str]) -> None:
        with self._lock:
            self._labels = list(labels)
            self._fractions = [0.0] * len(labels)
            self._started = [False] * len(labels)
            self._done = [False] * len(labels)
            self.phase = "simulating"

    def advance(self, index: int, fraction: float) -> None:
        with self._lock:
            self._started[index] = True
            self._fractions[index] = max(self._fractions[index], min(1.0, fraction))

    def finish(self, index: int) -> None:
        with self._lock:
            self._started[index] = self._done[index] = True
            self._fractions[index] = 1.0

    def set_phase(self, phase: str) -> None:
        with self._lock:
            self.phase = phase

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._labels)
            fraction = sum(self._fractions) / total if total else 0.0
            elapsed = time.monotonic() - self._t0
            eta = None
            if self.phase == "simulating" and fraction >= 0.2 and elapsed >= 3.0:
                eta = round(elapsed * (1.0 - fraction) / fraction, 1)
            return {
                "phase": self.phase,
                "total": total,
                "completed": sum(self._done),
                "fraction": round(fraction, 4),
                "running": [
                    label
                    for label, started, done in zip(
                        self._labels, self._started, self._done
                    )
                    if started and not done
                ],
                "elapsedSeconds": round(elapsed, 1),
                "etaSeconds": eta,
            }


# ── Worker pool ──────────────────────────────────────────────────────────

_progress_queue: Any = None  # set in each worker by _init_worker


def _init_worker(queue: Any) -> None:
    global _progress_queue
    _progress_queue = queue


def _run_in_worker(
    token: str, index: int, config: Dict[str, Any], geometry: str, duration: float
) -> Dict[str, Any]:
    def report(fraction: float) -> None:
        _progress_queue.put((token, index, fraction))

    return simulate_geometry(config, geometry, duration, report)


class _WorkerPool:
    """The process pool plus one thread routing worker progress messages to
    the run that sent them."""

    def __init__(self, workers: int) -> None:
        # "spawn" everywhere: forking a process that runs uvicorn's threads is
        # unsafe, and it keeps Linux/Docker behaviour the same as Windows.
        ctx = multiprocessing.get_context("spawn")
        self.workers = workers
        self.queue = ctx.Queue()
        self.executor = ProcessPoolExecutor(
            max_workers=workers,
            mp_context=ctx,
            initializer=_init_worker,
            initargs=(self.queue,),
        )
        self._routes: Dict[str, Callable[[int, float], None]] = {}
        self._routes_lock = threading.Lock()
        self._listener = threading.Thread(
            target=self._listen, name="study-progress", daemon=True
        )
        self._listener.start()

    def _listen(self) -> None:
        while True:
            message = self.queue.get()
            if message is None:
                return
            token, index, fraction = message
            with self._routes_lock:
                route = self._routes.get(token)
            if route is not None:
                route(index, fraction)

    def route(self, token: str, callback: Callable[[int, float], None]) -> None:
        with self._routes_lock:
            self._routes[token] = callback

    def unroute(self, token: str) -> None:
        with self._routes_lock:
            self._routes.pop(token, None)

    def shutdown(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.queue.put(None)


_pool: Optional[_WorkerPool] = None
_pool_lock = threading.Lock()


def _get_pool(workers: int) -> _WorkerPool:
    global _pool
    with _pool_lock:
        if _pool is None or _pool.workers != workers:
            if _pool is not None:
                _pool.shutdown()
            _pool = _WorkerPool(workers)
        return _pool


def _discard_pool(broken: _WorkerPool) -> None:
    global _pool
    with _pool_lock:
        if _pool is broken:
            _pool = None
    broken.shutdown()


def shutdown_pool() -> None:
    """Stop the worker processes (application shutdown)."""
    global _pool
    with _pool_lock:
        pool, _pool = _pool, None
    if pool is not None:
        pool.shutdown()


def _finished(progress: Progress, index: int, _future: Future[Any]) -> None:
    progress.finish(index)


def run_simulation_tasks(
    tasks: List[SimTask], progress: Optional[Progress] = None
) -> List[Dict[str, Any]]:
    """Run every task and return their results in task order."""
    progress = progress or Progress()
    progress.begin([t.label for t in tasks])
    workers = study_workers()

    if workers == 0:
        results = []
        for i, t in enumerate(tasks):
            results.append(
                simulate_geometry(
                    t.config,
                    t.geometry,
                    t.duration,
                    partial(progress.advance, i),
                )
            )
            progress.finish(i)
        return results

    pool = _get_pool(workers)
    token = uuid.uuid4().hex
    pool.route(token, progress.advance)
    try:
        futures: Dict[int, Future[Dict[str, Any]]] = {}
        # Heaviest first (stable, so equal costs keep their order).
        for i in sorted(range(len(tasks)), key=lambda i: -tasks[i].cost):
            t = tasks[i]
            future = pool.executor.submit(
                _run_in_worker, token, i, t.config, t.geometry, t.duration
            )
            future.add_done_callback(partial(_finished, progress, i))
            futures[i] = future
        try:
            return [futures[i].result() for i in range(len(tasks))]
        except BrokenProcessPool:
            # A worker died (e.g. killed for memory). Start a fresh pool for
            # the next run rather than failing every run after this one.
            _discard_pool(pool)
            raise
        except BaseException:
            for future in futures.values():
                future.cancel()
            raise
    finally:
        pool.unroute(token)
