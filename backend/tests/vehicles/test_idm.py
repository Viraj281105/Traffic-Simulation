import pytest

try:
    from src.vehicles.idm import IntelligentDriverModel
except ImportError:
    pytest.skip("IDM module not implemented yet", allow_module_level=True)


def test_idm_initialization() -> None:
    idm = IntelligentDriverModel(max_acceleration=2.5, comfort_deceleration=3.5)
    # Validates parameters run cleanly
    assert idm._max_acceleration == 2.5
    assert idm._comfort_deceleration == 3.5


def test_idm_invalid_initialization() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        IntelligentDriverModel(max_acceleration=0.0)
    with pytest.raises(ValueError, match="must be positive"):
        IntelligentDriverModel(comfort_deceleration=-1.0)


def test_idm_free_flow() -> None:
    idm = IntelligentDriverModel(
        max_acceleration=2.0, desired_time_headway=1.5, minimum_gap=2.0
    )

    # Standstill (v=0) -> should accelerate at max comfortable rate (a0)
    assert idm.calculate_acceleration(speed=0.0, desired_speed=10.0) == 2.0

    # At desired speed (v=v0) -> acceleration should be 0
    acc_zero = idm.calculate_acceleration(speed=10.0, desired_speed=10.0)
    assert pytest.approx(acc_zero) == 0.0

    # Overspeed (v > v0) -> acceleration should be negative
    assert idm.calculate_acceleration(speed=12.0, desired_speed=10.0) < 0.0


def test_idm_following() -> None:
    idm = IntelligentDriverModel(
        max_acceleration=2.0,
        comfort_deceleration=3.0,
        minimum_gap=2.0,
        desired_time_headway=1.5,
    )

    # Standstill equilibrium: both vehicles stopped at minimum standstill gap
    # Target gap s* = s0. gap = s0. Term (s*/gap)^2 = 1.
    # acc = a0 * (1 - 0 - 1) = 0
    acc = idm.calculate_acceleration(
        speed=0.0, desired_speed=10.0, lead_speed=0.0, gap=2.0
    )
    assert pytest.approx(acc) == 0.0

    # Closing fast on stationary vehicle (high closing speed, small gap)
    # Deceleration should trigger and be strongly negative (braking)
    acc_braking = idm.calculate_acceleration(
        speed=10.0, desired_speed=15.0, lead_speed=0.0, gap=5.0
    )
    assert acc_braking < 0.0

    # Check max deceleration capping
    acc_extreme = idm.calculate_acceleration(
        speed=30.0, desired_speed=15.0, lead_speed=0.0, gap=1.0
    )
    assert acc_extreme == -9.0  # Capped at max_deceleration


def test_idm_collision_gap() -> None:
    idm = IntelligentDriverModel(max_deceleration=9.0)
    # Zero or negative gap should return absolute decel limit
    acc_zero = idm.calculate_acceleration(
        speed=5.0, desired_speed=10.0, lead_speed=5.0, gap=0.0
    )
    acc_neg = idm.calculate_acceleration(
        speed=5.0, desired_speed=10.0, lead_speed=5.0, gap=-1.0
    )
    assert acc_zero == -9.0
    assert acc_neg == -9.0


def test_idm_invalid_arguments() -> None:
    idm = IntelligentDriverModel()
    with pytest.raises(ValueError, match="speed cannot be negative"):
        idm.calculate_acceleration(speed=-1.0, desired_speed=10.0)
    with pytest.raises(ValueError, match="must be greater than zero"):
        idm.calculate_acceleration(speed=5.0, desired_speed=0.0)
