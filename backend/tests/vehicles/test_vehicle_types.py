"""V1.1 vehicle classes: profiles, mix resolution, overrides and validation."""

from typing import Any, Dict

import pytest

from src.core.config_validation import semantic_config_errors
from src.vehicles.vehicle_types import (
    BUS,
    CAR,
    DEFAULT_PROFILES,
    MOTORCYCLE,
    REFERENCE_VEHICLE_LENGTH,
    SUV,
    TRUCK,
    VEHICLE_CLASSES,
    design_vehicle_allowance,
    long_vehicle_allowance,
    longest_vehicle_length,
    resolve_vehicle_population,
    vehicle_mix_errors,
)

MIX = {"car": 0.5, "suv": 0.2, "bus": 0.1, "truck": 0.1, "motorcycle": 0.1}


def _config(**veh_gen: Any) -> Dict[str, Any]:
    return {"roads": {"speedLimit": 13.89}, "vehicleGeneration": dict(veh_gen)}


def test_every_required_class_has_a_profile() -> None:
    assert set(VEHICLE_CLASSES) == {CAR, SUV, BUS, TRUCK, MOTORCYCLE}
    assert set(DEFAULT_PROFILES) == set(VEHICLE_CLASSES)


def test_classes_are_physically_differentiated() -> None:
    car, suv, bus, truck, moto = (DEFAULT_PROFILES[c] for c in VEHICLE_CLASSES)
    # Dimensions
    assert moto.length[1] < car.length[0]
    assert moto.width[1] < car.width[0]
    assert bus.length[0] > 2 * car.length[1]
    assert truck.length[0] > car.length[1]
    assert suv.length[0] > car.length[0]
    # Dynamics: heavy vehicles accelerate and brake more gently, keep longer
    # headways and corner more slowly; motorcycles are the opposite.
    for heavy in (bus, truck):
        assert heavy.max_acceleration < car.max_acceleration
        assert heavy.comfort_deceleration < car.comfort_deceleration
        assert heavy.desired_time_headway > car.desired_time_headway
        assert heavy.max_lateral_acceleration < car.max_lateral_acceleration
        assert heavy.desired_speed_factor[1] < car.desired_speed_factor[1]
        assert heavy.lane_change_duration > car.lane_change_duration
    assert moto.max_acceleration > car.max_acceleration
    assert moto.desired_time_headway < car.desired_time_headway
    assert moto.max_lateral_acceleration > car.max_lateral_acceleration


def test_no_mix_means_the_legacy_population() -> None:
    assert resolve_vehicle_population({}) is None
    assert resolve_vehicle_population(_config(maxAcceleration=2.5)) is None
    assert design_vehicle_allowance({}) == 0.0


def test_mix_resolves_in_canonical_order_and_skips_zero_shares() -> None:
    population = resolve_vehicle_population(
        _config(vehicleMix={"truck": 0.25, "car": 0.75, "bus": 0.0})
    )
    assert population is not None
    assert population.type_ids == ["car", "truck"]
    assert population.weights == [0.75, 0.25]


def test_car_in_a_mix_is_the_configured_reference_vehicle() -> None:
    population = resolve_vehicle_population(
        _config(
            vehicleMix={"car": 1.0},
            maxAcceleration=2.4,
            comfortDeceleration=3.3,
            desiredTimeHeadway=1.2,
            vehicleLength={"min": 4.2, "max": 4.4},
        )
    )
    assert population is not None
    car = population.params_by_type["car"].profile
    assert car.max_acceleration == 2.4
    assert car.comfort_deceleration == 3.3
    assert car.desired_time_headway == 1.2
    assert car.length == (4.2, 4.4)
    # One shared IDM per class, carrying the class's parameters.
    idm = population.params_by_type["car"].idm
    assert idm._max_acceleration == 2.4
    assert idm._desired_time_headway == 1.2


def test_desired_speed_follows_the_speed_limit_per_class() -> None:
    population = resolve_vehicle_population(_config(vehicleMix=MIX))
    assert population is not None
    limit = 13.89
    for type_id in VEHICLE_CLASSES:
        lo, hi = population.params_by_type[type_id].desired_speed_range
        f_lo, f_hi = DEFAULT_PROFILES[type_id].desired_speed_factor
        assert lo == pytest.approx(limit * f_lo)
        assert hi == pytest.approx(limit * f_hi)
    bus = population.params_by_type["bus"].desired_speed_range
    car = population.params_by_type["car"].desired_speed_range
    assert bus[1] < car[1]


def test_explicit_desired_speed_keeps_each_class_ratio_to_the_car() -> None:
    population = resolve_vehicle_population(
        _config(vehicleMix=MIX, desiredSpeed={"min": 10.0, "max": 12.0})
    )
    assert population is not None
    assert population.params_by_type["car"].desired_speed_range == pytest.approx(
        (10.0, 12.0)
    )
    lo, hi = population.params_by_type["bus"].desired_speed_range
    assert lo == pytest.approx(10.0 * 0.75 / 0.85)
    assert hi == pytest.approx(12.0 * 0.90 / 1.05)


def test_per_class_overrides_apply() -> None:
    population = resolve_vehicle_population(
        _config(
            vehicleMix={"bus": 1.0},
            vehicleTypes={
                "bus": {
                    "length": {"min": 11.5, "max": 11.8},
                    "maxAcceleration": 0.7,
                    "politeness": 0.9,
                }
            },
        )
    )
    assert population is not None
    bus = population.params_by_type["bus"].profile
    assert bus.length == (11.5, 11.8)
    assert bus.max_acceleration == 0.7
    assert bus.politeness == 0.9
    # Untouched parameters keep their defaults.
    assert bus.desired_time_headway == DEFAULT_PROFILES["bus"].desired_time_headway


def test_mix_validation() -> None:
    assert vehicle_mix_errors(_config(vehicleMix=MIX)) == []
    assert any(
        "sum to 1.0" in e for e in vehicle_mix_errors(_config(vehicleMix={"car": 0.5}))
    )
    assert any(
        "unknown vehicle classes" in e
        for e in vehicle_mix_errors(_config(vehicleMix={"car": 0.5, "bike": 0.5}))
    )
    assert any(
        "positive share" in e
        for e in vehicle_mix_errors(_config(vehicleMix={"car": 0.0}))
    )
    bad_range = _config(
        vehicleMix={"bus": 1.0},
        vehicleTypes={"bus": {"length": {"min": 12, "max": 10}}},
    )
    assert any("must be >= min" in e for e in vehicle_mix_errors(bad_range))
    # Wired into the contract's cross-field rules.
    assert semantic_config_errors(_config(vehicleMix={"car": 0.4}))


def test_longest_vehicle_and_design_allowance() -> None:
    assert longest_vehicle_length({}) == REFERENCE_VEHICLE_LENGTH
    assert long_vehicle_allowance(REFERENCE_VEHICLE_LENGTH) == 0.0
    assert long_vehicle_allowance(4.0) == 0.0
    cars = _config(vehicleMix={"car": 0.7, "motorcycle": 0.3})
    assert design_vehicle_allowance(cars) == 0.0
    heavy = _config(vehicleMix={"car": 0.9, "truck": 0.1})
    assert longest_vehicle_length(heavy) == DEFAULT_PROFILES["truck"].length[1]
    assert design_vehicle_allowance(heavy) == pytest.approx(
        DEFAULT_PROFILES["truck"].length[1] - REFERENCE_VEHICLE_LENGTH
    )
