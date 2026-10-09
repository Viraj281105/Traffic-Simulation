"""Tests for environmental_estimates.py (Phase 2 -- V1.6).

Verifies:
  - Idling vehicles produce positive fuel and CO2.
  - Moving vehicles produce more than idling vehicles.
  - Accelerating vehicles produce more than cruising vehicles.
  - Decelerating vehicles are treated the same as idling (only idle term).
  - CO2 is proportional to fuel with the documented factor.
  - The environmentalMetricsAreEstimates key is always True in get_metrics().
  - Fuel/CO2 accumulate correctly in MetricCollector after warmup.
"""

from src.metrics.definitions.environmental_estimates import (
    _CO2_KG_PER_LITRE_PETROL,
    estimate_co2_kg,
    estimate_fuel_liters_per_vehicle_per_tick,
)

# ---------------------------------------------------------------------------
# estimate_fuel_liters_per_vehicle_per_tick
# ---------------------------------------------------------------------------


def test_idling_vehicle_produces_positive_fuel() -> None:
    """A vehicle at rest (speed=0, accel=0) still consumes idle fuel."""
    fuel = estimate_fuel_liters_per_vehicle_per_tick(
        speed=0.0, acceleration=0.0, time_step=0.1
    )
    assert fuel > 0.0


def test_moving_vehicle_produces_more_than_idling() -> None:
    """A cruising vehicle at 10 m/s uses more fuel per tick than one idling."""
    idle = estimate_fuel_liters_per_vehicle_per_tick(0.0, 0.0, 0.1)
    cruise = estimate_fuel_liters_per_vehicle_per_tick(10.0, 0.0, 0.1)
    assert cruise > idle


def test_accelerating_vehicle_produces_more_than_cruising() -> None:
    """Positive acceleration adds an extra fuel penalty above the cruise rate."""
    cruise = estimate_fuel_liters_per_vehicle_per_tick(10.0, 0.0, 0.1)
    accel = estimate_fuel_liters_per_vehicle_per_tick(10.0, 2.0, 0.1)
    assert accel > cruise


def test_decelerating_vehicle_same_as_idling_for_accel_term() -> None:
    """Negative acceleration should not reduce fuel below idle (a2 term clamped)."""
    idle_only = estimate_fuel_liters_per_vehicle_per_tick(0.0, 0.0, 0.1)
    braking = estimate_fuel_liters_per_vehicle_per_tick(0.0, -3.0, 0.1)
    assert abs(idle_only - braking) < 1e-12


def test_negative_speed_clamped_to_zero() -> None:
    """A negative speed (guard against invalid input) is treated as zero."""
    normal_idle = estimate_fuel_liters_per_vehicle_per_tick(0.0, 0.0, 0.1)
    neg_speed = estimate_fuel_liters_per_vehicle_per_tick(-5.0, 0.0, 0.1)
    assert abs(normal_idle - neg_speed) < 1e-12


def test_zero_time_step_yields_zero_fuel() -> None:
    """Zero (or negative) time_step produces 0 fuel consumed."""
    assert estimate_fuel_liters_per_vehicle_per_tick(10.0, 1.0, 0.0) == 0.0
    assert estimate_fuel_liters_per_vehicle_per_tick(10.0, 1.0, -1.0) == 0.0


def test_fuel_scales_linearly_with_time_step() -> None:
    """Fuel consumed is proportional to time step."""
    f1 = estimate_fuel_liters_per_vehicle_per_tick(10.0, 0.0, 0.1)
    f2 = estimate_fuel_liters_per_vehicle_per_tick(10.0, 0.0, 0.2)
    assert abs(f2 - 2 * f1) < 1e-12


# ---------------------------------------------------------------------------
# estimate_co2_kg
# ---------------------------------------------------------------------------


def test_co2_proportional_to_fuel() -> None:
    """CO2 = fuel * CO2_KG_PER_LITRE_PETROL."""
    fuel = 1.5
    expected = fuel * _CO2_KG_PER_LITRE_PETROL
    assert abs(estimate_co2_kg(fuel) - expected) < 1e-12


def test_co2_zero_for_zero_fuel() -> None:
    assert estimate_co2_kg(0.0) == 0.0


def test_co2_clamped_for_negative_fuel() -> None:
    """Negative fuel (guard input) should yield 0, not negative CO2."""
    assert estimate_co2_kg(-1.0) == 0.0


# ---------------------------------------------------------------------------
# Integration: MetricCollector accumulates fuel/CO2 and always sets the flag
# ---------------------------------------------------------------------------


def _run_collector_ticks(
    n_vehicles: int,
    speed: float = 5.0,
    acceleration: float = 0.0,
    warmup: float = 0.0,
    time_step: float = 0.1,
    n_ticks: int = 10,
):
    """Run MetricCollector for n_ticks post-warmup ticks with n_vehicles that
    have real numeric .speed and .acceleration but are otherwise minimal stubs
    built from the existing test helpers in the safety-conflicts test suite.
    """
    from src.core.enums import Direction
    from src.metrics.collector import MetricCollector
    from src.roads.lane import Lane
    from src.vehicles.vehicle import Vehicle

    config = {
        "simulation": {"warmupTime": warmup, "timeStep": time_step},
        "geometry": {"intersectionType": "fixed_time_signal"},
    }
    collector = MetricCollector(config)

    # Lane placed so vehicles are stationary and far apart (no TTC events).
    lane = Lane("env_lane", 0.0, 0.0, 0.0, 1000.0)
    vehicles = []
    for i in range(n_vehicles):
        v = Vehicle(
            f"env_v{i}",
            length=4.0,
            width=2.0,
            desired_speed=max(speed, 1.0),
            route=[lane],
            start_position=float(i * 100),  # 100 m apart -- no TTC proximity
            initial_speed=speed,
        )
        v.acceleration = acceleration
        vehicles.append(v)

    signals = {d: "green" for d in Direction}
    for tick in range(n_ticks):
        t = warmup + (tick + 1) * time_step
        collector.update(t, vehicles, [], signals)

    return collector, vehicles


def test_environmental_metrics_are_estimates_flag_always_true() -> None:
    """The environmentalMetricsAreEstimates key must always be True."""
    collector, vehicles = _run_collector_ticks(1)
    metrics = collector.get_metrics(1.0, vehicles, [], 1)
    assert metrics["environmentalMetricsAreEstimates"] is True


def test_fuel_accumulates_post_warmup() -> None:
    """Total fuel estimate > 0 after 10 ticks with active vehicles."""
    collector, vehicles = _run_collector_ticks(2, speed=10.0)
    metrics = collector.get_metrics(1.0, vehicles, [], 2)
    assert metrics["estimatedFuelLitersTotal"] > 0.0


def test_co2_accumulates_post_warmup() -> None:
    """Total CO2 estimate > 0 after 10 ticks with active vehicles."""
    collector, vehicles = _run_collector_ticks(2, speed=10.0)
    metrics = collector.get_metrics(1.0, vehicles, [], 2)
    assert metrics["estimatedCO2KgTotal"] > 0.0


def test_co2_proportional_to_fuel_in_metrics() -> None:
    """CO2 = fuel * CO2_KG_PER_LITRE_PETROL within rounding tolerance."""
    collector, vehicles = _run_collector_ticks(1, speed=5.0)
    metrics = collector.get_metrics(1.0, vehicles, [], 1)
    fuel = metrics["estimatedFuelLitersTotal"]
    co2 = metrics["estimatedCO2KgTotal"]
    assert abs(co2 - round(fuel * _CO2_KG_PER_LITRE_PETROL, 3)) < 0.001


def test_no_fuel_accumulated_before_warmup() -> None:
    """Fuel stays 0 when only pre-warmup ticks are run (warmup=30s)."""
    from src.core.enums import Direction
    from src.metrics.collector import MetricCollector
    from src.roads.lane import Lane
    from src.vehicles.vehicle import Vehicle

    config = {
        "simulation": {"warmupTime": 30.0, "timeStep": 0.1},
        "geometry": {"intersectionType": "fixed_time_signal"},
    }
    collector = MetricCollector(config)
    lane = Lane("env_pre_warmup", 0.0, 0.0, 0.0, 500.0)
    v = Vehicle(
        "v_warmup", 4.0, 2.0, 10.0, [lane], start_position=0.0, initial_speed=5.0
    )
    v.acceleration = 0.0
    signals = {d: "green" for d in Direction}

    # Run only during warmup
    collector.update(10.0, [v], [], signals)

    # get_metrics needs spawn_time on v; Vehicle sets spawn_time=0.0 by default
    metrics = collector.get_metrics(10.0, [v], [], 1)
    assert metrics["estimatedFuelLitersTotal"] == 0.0
    assert metrics["estimatedCO2KgTotal"] == 0.0
