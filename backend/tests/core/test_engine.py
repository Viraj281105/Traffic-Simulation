import time

import pytest

try:
    from src.core.clock import Clock
    from src.core.engine import SimulationEngine
    from src.core.enums import SimulationStatus
except ImportError:
    pytest.skip("Engine module is not implemented yet", allow_module_level=True)


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


def test_engine_resume_when_not_paused() -> None:
    clock = Clock(0.1)
    engine = SimulationEngine(clock, duration=1.0)
    # Should do nothing when initialized
    engine.resume()
    assert engine.status == SimulationStatus.INITIALIZED


def test_engine_loop_exception_handling() -> None:
    clock = Clock(0.01)
    engine = SimulationEngine(clock, duration=1.0)

    # Monkeypatch step to raise an exception
    def bad_step() -> None:
        raise RuntimeError("Simulated crash")

    engine.step = bad_step  # type: ignore[assignment]
    engine.start()
    if engine._thread:
        engine._thread.join(timeout=1.0)
    assert engine.status == SimulationStatus.ERROR


def test_engine_reset_with_spawner() -> None:
    clock = Clock(0.1)
    engine = SimulationEngine(clock, duration=1.0)

    class DummySpawner:
        def __init__(self) -> None:
            self.reset_called = False

        def reset(self) -> None:
            self.reset_called = True

    dummy_spawner = DummySpawner()
    engine.spawner = dummy_spawner  # type: ignore[assignment]
    engine.reset()
    assert dummy_spawner.reset_called is True


def test_engine_with_config_and_step() -> None:
    config = {
        "roads": {
            "approachLength": 100.0,
            "laneWidth": 3.5,
            "lanesPerApproach": 2,
        },
        "vehicleGeneration": {
            "maxAcceleration": 2.5,
            "comfortDeceleration": 3.0,
            "desiredTimeHeadway": 1.5,
            "minimumGap": 2.0,
            "idmDelta": 4.0,
        },
        "traffic": {
            "arrivalRate": 10.0,
            "totalVehicles": 100,
        },
        "controller": {
            "type": "fixed_time_signal",
        },
    }
    clock = Clock(0.1)
    engine = SimulationEngine(clock, duration=0.5, config=config)
    assert engine.spawner is not None
    assert engine.idm is not None

    # Step simulation with spawner active
    for _ in range(5):
        engine.step()
    assert engine.status == SimulationStatus.COMPLETED
