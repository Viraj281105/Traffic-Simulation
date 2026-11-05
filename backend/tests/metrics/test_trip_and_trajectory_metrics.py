"""Delay / travel-time, fuel / CO2 and TTC pure functions (W33/W34, F9)."""

import math

import pytest

from src.metrics.definitions.environmental_estimates import (
    estimate_co2_kg,
    estimate_fuel_liters_per_vehicle_per_tick,
)
from src.metrics.trajectory_metrics import (
    summarize_emissions,
    summarize_ttc,
    time_to_collision,
    trajectory_emissions,
)
from src.metrics.trip_metrics import (
    free_flow_time,
    percentile,
    summarize_trips,
    trip_delay,
)


def test_free_flow_and_delay() -> None:
    assert free_flow_time(100.0, 10.0) == 10.0
    assert free_flow_time(100.0, 0.0) is None
    assert trip_delay(15.0, 10.0) == 5.0
    assert trip_delay(8.0, 10.0) == 0.0


def test_percentile_interpolates() -> None:
    assert percentile([1, 2, 3, 4], 50) == 2.5
    assert percentile([], 50) is None


def test_trip_summary_values() -> None:
    trips = [
        {"travelTimeS": 20.0, "freeFlowTimeS": 10.0},
        {"travelTimeS": 30.0, "distanceM": 100.0, "desiredSpeedMps": 10.0},
        {"travelTimeS": 10.0, "freeFlowTimeS": 10.0},
    ]
    s = summarize_trips(trips)
    assert s["n"] == 3 and s["skipped"] == 0 and s["lowSample"] is True
    assert s["meanTravelTimeS"] == pytest.approx(20.0)
    assert s["meanDelayS"] == pytest.approx(10.0)
    assert s["maxDelayS"] == 20.0
    assert s["totalDelayVehicleHours"] == pytest.approx(30.0 / 3600.0)
    assert s["delayRatio"] == pytest.approx(0.5)


def test_trip_summary_skips_bad_records_and_handles_empty() -> None:
    s = summarize_trips(
        [
            {"travelTimeS": float("nan"), "freeFlowTimeS": 1.0},
            {"travelTimeS": 5.0},
            {"travelTimeS": 5.0, "freeFlowTimeS": 4.0},
        ]
    )
    assert (s["n"], s["skipped"]) == (1, 2)
    empty = summarize_trips([])
    assert empty["n"] == 0 and empty["meanDelayS"] is None


def test_trip_summary_low_sample_flag_clears() -> None:
    trips = [{"travelTimeS": 10.0 + i, "freeFlowTimeS": 10.0} for i in range(25)]
    s = summarize_trips(trips)
    assert s["lowSample"] is False
    assert s["planningTimeIndex"] > 1.0


def test_emissions_match_per_tick_model() -> None:
    speeds = [0.0, 5.0, 10.0, 10.0]
    dt = 0.5
    expected = 0.0
    prev = None
    for v in speeds:
        a = 0.0 if prev is None else (v - prev) / dt
        expected += estimate_fuel_liters_per_vehicle_per_tick(v, a, dt)
        prev = v
    out = trajectory_emissions(speeds, dt)
    assert out["fuelLiters"] == pytest.approx(expected)
    assert out["co2Kg"] == pytest.approx(estimate_co2_kg(expected))
    assert out["distanceM"] == pytest.approx((0 + 5 + 10 + 10) * dt)


def test_idling_burns_fuel_but_has_no_intensity() -> None:
    out = trajectory_emissions([0.0] * 10, 1.0)
    assert out["fuelLiters"] > 0.0
    assert out["idleTimeS"] == 10.0
    assert out["fuelLPer100Km"] is None


def test_stop_and_go_costs_more_than_steady_for_same_distance() -> None:
    steady = trajectory_emissions([10.0] * 20, 1.0)
    stop_go = trajectory_emissions([0.0, 20.0] * 10, 1.0)
    assert stop_go["distanceM"] == pytest.approx(steady["distanceM"])
    assert stop_go["fuelLiters"] > steady["fuelLiters"]


def test_summarize_emissions_is_labelled_estimate() -> None:
    s = summarize_emissions([[0.0, 10.0], [5.0, 5.0]], 1.0)
    assert s["isEstimate"] is True and "estimate" in s["label"].lower()
    assert s["vehicles"] == 2 and 0.0 < s["idleShare"] < 1.0
    with pytest.raises(ValueError):
        summarize_emissions([[1.0]], 0.0)


def test_ttc_basic_cases() -> None:
    assert time_to_collision(20.0, 15.0, 5.0) == pytest.approx(2.0)
    assert time_to_collision(20.0, 5.0, 15.0) is None
    assert time_to_collision(20.0, 10.0, 10.0) is None
    assert time_to_collision(0.0, 1.0, 5.0) == 0.0


def _s(gap: float, vf: float, vl: float) -> dict:
    return {"gapM": gap, "followerSpeedMps": vf, "leaderSpeedMps": vl}


def test_ttc_summary_counts_episodes_not_samples() -> None:
    # TTC: 2.0 (ok), 1.0, 0.5 (one event), none, 1.0 (second event)
    series = [_s(20, 15, 5), _s(10, 15, 5), _s(5, 15, 5), _s(5, 5, 15), _s(10, 15, 5)]
    out = summarize_ttc([series], dt=0.1, threshold_s=1.5)
    assert out["minTtcS"] == pytest.approx(0.5)
    assert out["conflictEvents"] == 2
    assert out["timeExposedTtcS"] == pytest.approx(0.3)
    assert out["timeIntegratedTtcS"] == pytest.approx(((1.5 - 1.0) * 2 + 1.0) * 0.1)
    assert out["observations"] == 4 and out["samples"] == 5
    assert out["isProxy"] is True


def test_ttc_summary_no_conflicts() -> None:
    out = summarize_ttc([[_s(10, 5, 15)]], dt=1.0)
    assert out["minTtcS"] is None and out["conflictEvents"] == 0
    assert out["thresholdS"] == 1.5
    with pytest.raises(ValueError):
        summarize_ttc([], dt=1.0, threshold_s=0.0)
    assert math.isfinite(out["timeIntegratedTtcS"])
