import pytest

try:
    from src.core.clock import Clock
except ImportError:
    pytest.skip("Clock module is not implemented yet", allow_module_level=True)


def test_clock_initialization() -> None:
    clock = Clock(0.1)
    assert clock.time_step == 0.1
    assert clock.get_tick_count() == 0
    assert clock.get_elapsed_time() == 0.0


def test_clock_invalid_initialization() -> None:
    with pytest.raises(ValueError, match="Time step must be positive and non-zero"):
        Clock(0.0)
    with pytest.raises(ValueError, match="Time step must be positive and non-zero"):
        Clock(-0.5)


def test_clock_tick() -> None:
    clock = Clock(0.1)
    clock.tick()
    assert clock.get_tick_count() == 1
    assert pytest.approx(clock.get_elapsed_time()) == 0.1
    clock.tick()
    assert clock.get_tick_count() == 2
    assert pytest.approx(clock.get_elapsed_time()) == 0.2


def test_clock_reset() -> None:
    clock = Clock(0.2)
    clock.tick()
    clock.tick()
    assert clock.get_tick_count() == 2
    clock.reset()
    assert clock.get_tick_count() == 0
    assert clock.get_elapsed_time() == 0.0


def test_clock_seconds_to_ticks() -> None:
    clock = Clock(0.1)
    assert clock.seconds_to_ticks(0.0) == 0
    assert clock.seconds_to_ticks(0.1) == 1
    assert clock.seconds_to_ticks(0.25) == 3
    assert clock.seconds_to_ticks(1.0) == 10

    with pytest.raises(ValueError, match="Seconds cannot be negative"):
        clock.seconds_to_ticks(-0.1)


def test_clock_ticks_to_seconds() -> None:
    clock = Clock(0.1)
    assert pytest.approx(clock.ticks_to_seconds(0)) == 0.0
    assert pytest.approx(clock.ticks_to_seconds(1)) == 0.1
    assert pytest.approx(clock.ticks_to_seconds(10)) == 1.0

    with pytest.raises(ValueError, match="Ticks cannot be negative"):
        clock.ticks_to_seconds(-1)


def test_ticks_for_duration_matches_the_engine_stop_rule() -> None:
    """Regression: study runners stepped int(duration / dt) ticks, which for
    many fractional durations is one short (2.3 / 0.1 = 22.999...)."""
    clock = Clock(0.1)
    assert clock.ticks_for_duration(2.3) == 23
    assert clock.ticks_for_duration(60.0) == 600
    assert clock.ticks_for_duration(2.35) == 24
    for tenths in range(10, 3000):
        duration = tenths / 10
        ticks = clock.ticks_for_duration(duration)
        # the engine completes on the first tick with ticks * dt >= duration
        assert ticks * 0.1 >= duration - 1e-9
        assert (ticks - 1) * 0.1 < duration - 1e-9
