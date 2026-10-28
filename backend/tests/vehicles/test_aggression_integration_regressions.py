"""Regressions found in the W4 integration audit of the driver-aggression profile (ADR-016).

1. The cars-only population without a vehicle mix (stored scenarios, presets without a mix) took
   the IDM levers of a profile but not its desired-speed offset or politeness, so ``high`` meant
   something different with and without ``vehicles.mix = {car: 1.0}``.
2. The dashboard's flat payload (quick setup) dropped ``driverAggression`` silently.
3. The manifest read the profile from the document's ``traffic`` block, while the engine runs the
   compiled config, where ``advanced.traffic`` wins.
4. The scenario fingerprint named a non-standard profile but not its parameters, so re-tuning a
   profile's multipliers left every document that uses it with its old identity.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, Tuple

import pytest
from fastapi import HTTPException

from src.controllers.factory import create_controller
from src.core.clock import Clock
from src.engine.simulation_engine import SimulationEngine
from src.engine.tick_callback import build_tick_callback
from src.experiments.manifest import build_manifest_assumptions
from src.live.dashboard_config import DEFAULT_CONFIG, compile_dashboard_config
from src.metrics.collector import MetricCollector
from src.scenario.documents import (
    compile_scenario,
    parse_scenario,
    scenario_driver_aggression,
    scenario_fingerprint,
)
from src.vehicles import driver_aggression
from src.vehicles.lane_change import LaneChangeModel, resolve_lane_change_settings
from src.vehicles.spawner import VehicleSpawner
from src.vehicles.speed_profile import resolve_desired_speed_range
from src.vehicles.vehicle_types import CAR, resolve_vehicle_population


def _legacy_config(profile: str | None) -> Dict[str, Any]:
    config = copy.deepcopy(DEFAULT_CONFIG)
    config.setdefault("simulation", {})["randomSeed"] = 7
    if profile is not None:
        config.setdefault("traffic", {})["driverAggression"] = profile
    return config


def _document(**extra: Any) -> Any:
    raw: Dict[str, Any] = {
        "format": "urbanflow-scenario",
        "version": 1,
        "name": "audit",
        "junction": {"type": "fixed_time_signal"},
        "approaches": {
            d: {"lanes": 1, "length": 200.0, "vehiclesPerHour": 300.0}
            for d in ("north", "south", "east", "west")
        },
        **extra,
    }
    doc, errs = parse_scenario(raw)
    assert not errs, errs
    return doc


# --- 1. Legacy cars-only population -------------------------------------------------------------


@pytest.mark.parametrize("profile", ["standard", "moderate", "high"])
def test_legacy_cars_only_matches_car_mix_under_every_profile(profile: str) -> None:
    legacy = _legacy_config(profile)
    with_mix = copy.deepcopy(legacy)
    with_mix.setdefault("vehicleGeneration", {})["vehicleMix"] = {CAR: 1.0}

    engine = SimulationEngine(Clock(time_step=0.1), duration=10, config=legacy)
    car = resolve_vehicle_population(with_mix).params_by_type[CAR]  # type: ignore[union-attr]

    assert (
        engine.spawner.speed_min,
        engine.spawner.speed_max,
    ) == car.desired_speed_range
    model = LaneChangeModel(resolve_lane_change_settings(legacy), engine.idm)
    assert model.settings.default_politeness == car.profile.politeness
    # The shared IDM of legacy vehicles carries the same levers as the car class.
    assert engine.idm._desired_time_headway == car.idm._desired_time_headway
    assert engine.idm._minimum_gap == car.idm._minimum_gap
    assert engine.idm._max_acceleration == car.idm._max_acceleration


@pytest.mark.parametrize("profile", [None, "standard"])
def test_legacy_cars_only_standard_is_untouched(profile: str | None) -> None:
    config = _legacy_config(profile)
    spawner = VehicleSpawner(
        config,
        SimulationEngine(Clock(time_step=0.1), duration=10, config=config).network,
    )
    assert (spawner.speed_min, spawner.speed_max) == resolve_desired_speed_range(config)
    settings = resolve_lane_change_settings(config)
    assert settings.default_politeness == 0.3
    assert settings.acceleration_threshold == 0.2
    assert settings.safe_deceleration == 4.0


def test_high_raises_legacy_speeds_and_lowers_politeness() -> None:
    std = SimulationEngine(
        Clock(time_step=0.1), duration=10, config=_legacy_config("standard")
    )
    high = SimulationEngine(
        Clock(time_step=0.1), duration=10, config=_legacy_config("high")
    )
    assert high.spawner.speed_min > std.spawner.speed_min
    assert high.spawner.speed_max > std.spawner.speed_max
    assert resolve_lane_change_settings(
        _legacy_config("high")
    ).default_politeness == pytest.approx(0.15)


def test_explicit_lane_change_settings_win_over_the_profile() -> None:
    config = _legacy_config("high")
    config.setdefault("roads", {})["laneChange"] = {
        "accelerationThreshold": 0.3,
        "politeness": 0.4,
    }
    settings = resolve_lane_change_settings(config)
    assert settings.acceleration_threshold == 0.3
    assert settings.politeness == 0.4
    assert settings.safe_deceleration == 4.0


# --- 2. Dashboard flat payload ------------------------------------------------------------------


def test_flat_dashboard_payload_carries_the_profile() -> None:
    config = compile_dashboard_config({"duration": 60, "driverAggression": "high"}, 1)
    assert config["traffic"]["driverAggression"] == "high"


def test_flat_dashboard_payload_without_profile_is_unchanged() -> None:
    config = compile_dashboard_config({"duration": 60}, 1)
    assert "driverAggression" not in config["traffic"]


@pytest.mark.parametrize("bad", ["extreme", "HIGH", 3, True, ["high"]])
def test_flat_dashboard_payload_rejects_a_bad_profile(bad: Any) -> None:
    with pytest.raises(HTTPException) as err:
        compile_dashboard_config({"duration": 60, "driverAggression": bad}, 1)
    assert err.value.status_code == 400
    assert "driverAggression" in str(err.value.detail)


@pytest.mark.parametrize("flag", ["unstructuredTraffic", "aggressiveTwoWheelers"])
def test_flat_dashboard_payload_carries_the_behaviour_toggles(flag: str) -> None:
    on = compile_dashboard_config({"duration": 60, flag: True}, 1)
    assert on["traffic"][flag] is True
    off = compile_dashboard_config({"duration": 60, flag: False}, 1)
    assert off == compile_dashboard_config({"duration": 60}, 1)


@pytest.mark.parametrize("bad", ["yes", 1, "true"])
def test_flat_dashboard_payload_rejects_a_non_boolean_toggle(bad: Any) -> None:
    with pytest.raises(HTTPException) as err:
        compile_dashboard_config({"duration": 60, "unstructuredTraffic": bad}, 1)
    assert err.value.status_code == 400


def test_toggles_reach_the_engine() -> None:
    config = compile_dashboard_config(
        {"duration": 60, "unstructuredTraffic": True, "aggressiveTwoWheelers": True},
        1,
    )
    engine = SimulationEngine(Clock(time_step=0.1), duration=60, config=config)
    assert type(engine.idm).__name__ == "StochasticIDM"
    assert resolve_lane_change_settings(config).aggressive_two_wheelers is True


# --- 3. Manifest records the profile the engine runs ----------------------------------------------


def test_manifest_follows_an_advanced_override() -> None:
    doc = _document(advanced={"traffic": {"driverAggression": "high"}})
    assert scenario_driver_aggression(doc) == "high"
    assumptions = build_manifest_assumptions(doc)
    assert assumptions["driverAggression"] == "high"
    assert assumptions[
        "driverAggressionHash"
    ] == driver_aggression.compute_aggression_parameter_hash("high")


def test_manifest_follows_an_advanced_override_back_to_standard() -> None:
    doc = _document(
        traffic={"driverAggression": "high"},
        advanced={"traffic": {"driverAggression": "standard"}},
    )
    assert build_manifest_assumptions(doc)["driverAggression"] == "standard"


@pytest.mark.parametrize("profile", ["standard", "moderate", "high"])
def test_manifest_records_the_document_profile(profile: str) -> None:
    doc = _document(traffic={"driverAggression": profile})
    assert build_manifest_assumptions(doc)["driverAggression"] == profile


# --- 4. Fingerprint identifies a profile by its parameters ----------------------------------------


def test_fingerprint_follows_the_profile_parameters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    legacy = _document()
    standard = _document(traffic={"driverAggression": "standard"})
    high = _document(traffic={"driverAggression": "high"})
    before = {
        "legacy": scenario_fingerprint(legacy),
        "standard": scenario_fingerprint(standard),
        "high": scenario_fingerprint(high),
    }
    assert before["legacy"] == before["standard"] != before["high"]

    retuned = dict(driver_aggression.AGGRESSION_MULTIPLIERS["high"], headway_mult=0.65)
    monkeypatch.setitem(driver_aggression.AGGRESSION_MULTIPLIERS, "high", retuned)

    assert scenario_fingerprint(high) != before["high"]
    assert scenario_fingerprint(legacy) == before["legacy"]
    assert scenario_fingerprint(standard) == before["standard"]


# --- 5. Aggression gridlocked a saturated single-lane signal (ADR-019) ---------------------------
#
# A head vehicle waited s0 short of its stop line. Under high that was 0.5 m nearer the box than
# the junction clearances were laid out for, inside the swept corridor of a right turn crossing in
# front of it: the turner stopped for it mid-junction, a follower entered behind the turner, the
# opposite right-turner stopped for that follower, and the head waited on the zone the first
# turner was stalled in. Nothing exited for the rest of the run. A stop line is now kept at the
# unscaled gap under every profile.


def _single_lane_signal(profile: str, seed: int, car_mix: bool) -> Dict[str, Any]:
    raw: Dict[str, Any] = {
        "format": "urbanflow-scenario",
        "version": 1,
        "name": "single-lane saturated signal",
        "junction": {"type": "fixed_time_signal"},
        "approaches": {
            d: {"lanes": 1, "length": 200.0, "vehiclesPerHour": 1000.0}
            for d in ("north", "south", "east", "west")
        },
        "traffic": {"driverAggression": profile},
        "simulation": {"duration": 300, "warmup": 60, "seed": seed},
    }
    if car_mix:
        raw["vehicles"] = {"mix": {"car": 1.0}}
    doc, errs = parse_scenario(raw)
    assert not errs, errs
    return compile_scenario(doc, "fixed_time")


def _longest_stall(config: Dict[str, Any]) -> Tuple[float, int]:
    clock = Clock(time_step=0.1)
    engine = SimulationEngine(clock, duration=300, config=config)
    ctrl = create_controller(config, engine.network)
    engine.controller = ctrl
    engine.register_tick_callback(
        build_tick_callback(ctrl, clock, engine, MetricCollector(config))
    )
    seen = last = tick = 0
    stall = 0.0
    while engine.status.value.lower() != "completed":
        engine.step()
        exited = len(engine.pool.exited_vehicles)
        if exited > seen:
            seen, last = exited, tick
        elif engine.pool.active_vehicles:
            stall = max(stall, (tick - last) * 0.1)
        tick += 1
    return stall, engine.pool.collision_count


@pytest.mark.slow
@pytest.mark.parametrize(
    "profile, seed, car_mix",
    [
        # Each of these locked up for 115-169 s before the fix.
        ("high", 1, False),
        ("moderate", 3, True),
        ("high", 4, True),
        ("standard", 1, False),
    ],
)
def test_aggression_does_not_gridlock_a_saturated_single_lane_signal(
    profile: str, seed: int, car_mix: bool
) -> None:
    stall, collisions = _longest_stall(_single_lane_signal(profile, seed, car_mix))
    assert collisions == 0
    assert stall <= 70.0


def test_a_head_vehicle_stops_at_the_line_where_standard_would() -> None:
    """The profile shortens the gap to the vehicle ahead, never the stop position at a line."""
    from src.vehicles.driver_aggression import stop_line_margin

    for profile, s0 in (("high", 1.5), ("moderate", 1.75), ("standard", 2.0)):
        m = driver_aggression.resolve_aggression_multipliers(profile)
        assert s0 + stop_line_margin(s0, m) == pytest.approx(2.0)
    assert (
        stop_line_margin(2.0, driver_aggression.resolve_aggression_multipliers(None))
        == 0.0
    )


@pytest.mark.parametrize("profile", ["standard", "high"])
def test_stopped_head_vehicle_position_is_profile_independent(profile: str) -> None:
    """Measured in the engine: the first car stopped at a red signal waits at the same place."""
    config = _single_lane_signal(profile, seed=3, car_mix=False)
    config["simulation"]["duration"] = 40
    clock = Clock(time_step=0.1)
    engine = SimulationEngine(clock, duration=40, config=config)
    ctrl = create_controller(config, engine.network)
    engine.controller = ctrl
    engine.register_tick_callback(
        build_tick_callback(ctrl, clock, engine, MetricCollector(config))
    )
    heads: Dict[str, float] = {}
    while engine.status.value.lower() != "completed":
        engine.step()
        for v in engine.pool.active_vehicles:
            lane = v.lane
            if "_in_" in lane.lane_id and v.speed < 0.01 and lane.virtual_obstacle:
                front_gap = lane.length - (v.position + v.length / 2.0)
                if front_gap < 5.0:
                    heads[lane.lane_id] = round(front_gap, 2)
    assert heads, "no vehicle stopped at a red line in 40 s"
    for gap in heads.values():
        assert gap == pytest.approx(2.0, abs=0.05)
