import time

import pytest

from src.core.clock import Clock
from src.core.engine import SimulationEngine
from src.core.enums import SimulationStatus


def test_engine_initialization() -> None:
    clock = Clock(0.1)
    engine = SimulationEngine(clock, duration=1.0)
    assert engine.status == SimulationStatus.INITIALIZED
    assert engine.duration == 1.0


def test_engine_invalid_initialization() -> None:
    clock = Clock(0.1)
    with pytest.raises(ValueError, match="duration must be greater than zero"):
        SimulationEngine(clock, duration=0.0)
    with pytest.raises(ValueError, match="duration must be greater than zero"):
        SimulationEngine(clock, duration=-1.0)


def test_engine_state_transitions() -> None:
    clock = Clock(0.1)
    engine = SimulationEngine(clock, duration=1.0)

    # Initialized -> Running
    engine.start()
    assert engine.status == SimulationStatus.RUNNING

    # Can't start again
    with pytest.raises(RuntimeError, match="Cannot start simulation"):
        engine.start()

    # Running -> Paused
    engine.pause()
    assert engine.status == SimulationStatus.PAUSED

    # Paused -> Running
    engine.resume()
    assert engine.status == SimulationStatus.RUNNING

    # Running -> Completed
    engine.stop()
    assert engine.status == SimulationStatus.COMPLETED

    # Reset
    engine.reset()
    assert engine.status == SimulationStatus.INITIALIZED
    assert clock.get_tick_count() == 0


def test_engine_manual_step() -> None:
    clock = Clock(0.1)
    engine = SimulationEngine(clock, duration=0.5)

    # Tick 1
    engine.step()
    assert clock.get_tick_count() == 1
    assert engine.status == SimulationStatus.INITIALIZED

    # Advance to end
    engine.step()
    engine.step()
    engine.step()
    engine.step()
    assert clock.get_tick_count() == 5
    assert engine.status == SimulationStatus.COMPLETED

    # Cannot step when completed
    msg = "Cannot step simulation in 'completed' status"
    with pytest.raises(RuntimeError, match=msg):
        engine.step()


def test_engine_callbacks() -> None:
    clock = Clock(0.1)
    engine = SimulationEngine(clock, duration=0.3)

    tick_count = 0

    def tick_cb() -> None:
        nonlocal tick_count
        tick_count += 1

    status_changes: list[SimulationStatus] = []

    def status_cb(status: SimulationStatus) -> None:
        status_changes.append(status)

    engine.register_tick_callback(tick_cb)
    engine.register_status_callback(status_cb)

    engine.start()
    time.sleep(0.4)  # Wait for background thread to run 3 ticks

    assert tick_count == 3
    assert engine.status == SimulationStatus.COMPLETED
    assert status_changes[0] == SimulationStatus.RUNNING
    assert status_changes[-1] == SimulationStatus.COMPLETED
