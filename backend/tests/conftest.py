"""Shared test fixtures.

The autouse fixture here stops real-time engine threads that a test leaves
running. See its docstring for why that is not merely tidiness.
"""

from typing import Any, Iterator, List

import pytest

from src.core.enums import SimulationStatus


def _running_engines() -> List[Any]:
    """Every engine currently held by the app that is still stepping."""
    from src.main import (
        _live_sessions,
        _live_sessions_lock,
        simulations_db,
        simulations_lock,
    )

    engines: List[Any] = []

    with simulations_lock:
        for entry in list(simulations_db.values()):
            engine = entry.get("engine") if isinstance(entry, dict) else None
            if engine is not None:
                engines.append(engine)

    with _live_sessions_lock:
        for session in list(_live_sessions.values()):
            live = getattr(session, "live_sim_data", None)
            if isinstance(live, dict) and live.get("engine") is not None:
                engines.append(live["engine"])
            orchestrator = getattr(session, "dual_sim_orchestrator", None)
            if orchestrator is not None:
                engines.append(orchestrator)

    return engines


@pytest.fixture(autouse=True)
def stop_engines_left_running() -> Iterator[None]:
    """Stop any engine thread the test leaves running, once it finishes.

    ``SimulationEngine.start()`` spawns a daemon thread that paces itself
    against the wall clock: it steps, then sleeps out the remainder of
    ``timeStep``. Nothing joins that thread, so a test that starts a
    simulation and does not stop it leaves it stepping for the rest of the
    session — and the API tests routinely configure ``duration: 300``, which
    is 3000 ticks.

    On a developer machine this is invisible: a step costs far less than the
    0.1 s tick, so the thread spends its life asleep on a spare core. On a
    two-vCPU CI runner it is not. There a step costs more than the tick, the
    ``sleep`` is always zero, and each leaked thread runs flat out, competing
    for the same two cores as the tests that follow. Four such threads were
    alive at the end of the API/database group, and the CPU-bound simulation
    tests that run after them were taking 100x their normal time as a
    result — ``test_roundabout_runs_stay_deterministic_for_a_fixed_seed``
    measured 895 s on the runner against 9 s in an unconstrained Linux
    container running the same code, interpreter and dependencies. That was
    the whole of a 45-minute backend job.

    Stopping only flips engines that are RUNNING or PAUSED; registries are
    left alone, so tests that assert on simulation history still see it.
    """
    yield

    for engine in _running_engines():
        try:
            status = getattr(engine, "status", None)
            if status in (SimulationStatus.RUNNING, SimulationStatus.PAUSED):
                engine.stop()
        except Exception:
            # Teardown must never turn a passing test red, and a stray engine
            # that cannot be stopped is reported by the test that leaked it,
            # not by this fixture.
            pass
