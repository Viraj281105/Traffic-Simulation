"""Factor application (W1 WP3): the meaning of each factor kind, checked by hand against the mapping note
docs/engineering/v3-w1-factor-mapping.md, and the rule that an invalid result is rejected, never repaired."""

import copy

import pytest

from src.core.scenario import (
    ScenarioDocument,
    compile_scenario,
    scenario_fingerprint,
    validate_scenario,
)
from src.uncertainty import UncertaintySpec
from src.uncertainty.apply import FactorApplicationError, apply_factors, preflight
from src.vehicles.speed_profile import resolve_desired_speed_range
from src.vehicles.vehicle_types import resolve_vehicle_population

MIX = {"car": 0.7, "suv": 0.1, "bus": 0.05, "truck": 0.1, "motorcycle": 0.05}


def _doc(mix=None, vph=450.0, turning=None, **extra):
    body = {
        "format": "urbanflow-scenario",
        "version": 1,
        "name": "apply test",
        "junction": {"type": "fixed_time_signal"},
        "approaches": {
            d: {
                "lanes": 1,
                "vehiclesPerHour": vph,
                "turning": turning or {"left": 0.2, "straight": 0.6, "right": 0.2},
            }
            for d in ("north", "south", "east", "west")
        },
        "simulation": {"duration": 60, "warmup": 5, "seed": 3},
        **extra,
    }
    if mix is not None:
        body["vehicles"] = {"mix": mix}
    return ScenarioDocument.model_validate(body)


def _factors(*kinds):
    bounds = {
        "turning_shift": [-1.0, 1.0],
        "mix_shift": [-1.0, 1.0],
    }
    items = [
        {
            "id": k,
            "kind": k,
            "distribution": {"kind": "uniform"},
            "bounds": bounds.get(k, [0.1, 5.0]),
            "rationale": "test",
        }
        for k in kinds
    ]
    return UncertaintySpec.model_validate(
        {"conditions": 5, "seed": 1, "factors": items}
    ).factors


def _apply(doc, kind, s):
    return apply_factors(doc, _factors(kind), {kind: s})


def _config(doc):
    return compile_scenario(doc, "fixed_time")


# --- demand ---------------------------------------------------------------------------------------


def test_demand_scale_multiplies_every_arm():
    out = _apply(_doc(), "demand_scale", 1.2)
    assert all(a.vehiclesPerHour == 540.0 for a in out.approaches.present().values())


def test_demand_above_the_arm_limit_is_rejected_not_clipped():
    with pytest.raises(FactorApplicationError, match="vehiclesPerHour"):
        _apply(_doc(vph=3000.0), "demand_scale", 3.0)  # 9000 > 7200


# --- turning (hand-computed) ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "s, turning, expected",
    [
        # s > 0 moves the fraction s of straight to left/right in their proportion
        (0.5, (0.2, 0.6, 0.2), (0.35, 0.3, 0.35)),
        (1.0, (0.2, 0.6, 0.2), (0.5, 0.0, 0.5)),
        (0.5, (0.3, 0.6, 0.1), (0.525, 0.3, 0.175)),  # moved 0.3 split 3:1
        # s < 0 moves the fraction |s| of left+right into straight
        (-0.5, (0.2, 0.6, 0.2), (0.1, 0.8, 0.1)),
        (-1.0, (0.3, 0.5, 0.2), (0.0, 1.0, 0.0)),
        (-0.5, (0.3, 0.5, 0.2), (0.15, 0.75, 0.1)),  # moved 0.25 split 3:2
        # nothing to split evenly
        (0.5, (0.0, 1.0, 0.0), (0.25, 0.5, 0.25)),
        (0.0, (0.2, 0.6, 0.2), (0.2, 0.6, 0.2)),
    ],
)
def test_turning_shift_matches_hand_values(s, turning, expected):
    left, straight, right = turning
    doc = _doc(turning={"left": left, "straight": straight, "right": right})
    out = _apply(doc, "turning_shift", s)
    for arm in out.approaches.present().values():
        got = (arm.turning.left, arm.turning.straight, arm.turning.right)
        assert got == pytest.approx(expected, abs=1e-6)
        assert sum(got) == pytest.approx(1.0, abs=1e-6)


def test_turning_shift_leaves_uturns_alone():
    doc = _doc(turning={"left": 0.2, "straight": 0.5, "right": 0.2, "uturn": 0.1})
    out = _apply(doc, "turning_shift", 0.5)
    arm = out.approaches.north
    assert arm.turning.uturn == 0.1
    assert arm.turning.straight == pytest.approx(0.25)


# --- vehicle mix (hand-computed) -----------------------------------------------------------------


def test_mix_shift_towards_heavy_matches_hand_values():
    out = _apply(_doc(mix=MIX), "mix_shift", 0.5)
    mix = out.vehicles.mix.model_dump()
    # light = 0.85, moved = 0.425; light loses proportionally, heavy gains in proportion 1:2
    assert mix["car"] == pytest.approx(0.35, abs=1e-6)
    assert mix["suv"] == pytest.approx(0.05, abs=1e-6)
    assert mix["motorcycle"] == pytest.approx(0.025, abs=1e-6)
    assert mix["bus"] == pytest.approx(0.191667, abs=1e-6)
    assert mix["truck"] == pytest.approx(0.383333, abs=1e-6)
    assert sum(mix.values()) == pytest.approx(1.0, abs=1e-5)


def test_mix_shift_towards_light_matches_hand_values():
    out = _apply(_doc(mix=MIX), "mix_shift", -1.0)
    mix = out.vehicles.mix.model_dump()
    assert mix["bus"] == 0.0 and mix["truck"] == 0.0
    assert mix["car"] == pytest.approx(0.823529, abs=1e-6)
    assert mix["suv"] == pytest.approx(0.117647, abs=1e-6)
    assert mix["motorcycle"] == pytest.approx(0.058824, abs=1e-6)
    assert sum(mix.values()) == pytest.approx(1.0, abs=1e-5)


def test_mix_shift_with_no_heavy_share_splits_equally_between_bus_and_truck():
    out = _apply(_doc(mix={"car": 0.9, "suv": 0.1}), "mix_shift", 0.5)
    mix = out.vehicles.mix.model_dump()
    assert (mix["bus"], mix["truck"]) == (0.25, 0.25)
    assert mix["car"] == pytest.approx(0.45)


def test_mix_shift_also_shifts_an_arm_own_mix():
    body = _doc(mix=MIX).model_dump()
    body["approaches"]["north"]["vehicleMix"] = {"car": 1.0}
    out = _apply(ScenarioDocument.model_validate(body), "mix_shift", 0.5)
    assert out.approaches.north.vehicleMix.truck == 0.25
    assert out.approaches.south.vehicleMix is None


def test_mix_shift_without_a_declared_mix_is_rejected():
    with pytest.raises(FactorApplicationError, match="declared vehicle mix"):
        _apply(_doc(), "mix_shift", 0.5)
    assert any("mix_shift" in e for e in preflight(_doc(), _factors("mix_shift")))


# --- vehicle-generation factors -------------------------------------------------------------------


def test_headway_scale_legacy_population_changes_the_scalar_only():
    out = _apply(_doc(), "headway_scale", 1.5)
    generation = _config(out)["vehicleGeneration"]
    assert generation["desiredTimeHeadway"] == 2.25
    assert "vehicleTypes" not in generation


def test_headway_scale_scales_every_class_in_a_mixed_population():
    out = _apply(_doc(mix=MIX), "headway_scale", 1.5)
    config = _config(out)
    assert config["vehicleGeneration"]["desiredTimeHeadway"] == 2.25
    population = resolve_vehicle_population(config)
    headways = {
        t: p.profile.desired_time_headway for t, p in population.params_by_type.items()
    }
    # defaults 1.5 / 1.6 / 1.8 / 2.0 / 1.1 times 1.5
    assert headways == pytest.approx(
        {"car": 2.25, "suv": 2.4, "bus": 2.7, "truck": 3.0, "motorcycle": 1.65}
    )


def test_max_acceleration_scale_scales_every_class():
    out = _apply(_doc(mix=MIX), "max_acceleration_scale", 0.5)
    config = _config(out)
    population = resolve_vehicle_population(config)
    accel = {
        t: p.profile.max_acceleration for t, p in population.params_by_type.items()
    }
    assert accel == pytest.approx(
        {"car": 1.0, "suv": 0.9, "bus": 0.5, "truck": 0.4, "motorcycle": 1.5}
    )
    assert config["vehicleGeneration"]["maxAcceleration"] == 1.0
    assert (
        _config(_apply(_doc(), "max_acceleration_scale", 0.5))["vehicleGeneration"][
            "maxAcceleration"
        ]
        == 1.0
    )


def test_desired_speed_scale_scales_the_car_range_and_the_classes_follow():
    base = _doc(mix=MIX)
    low, high = resolve_desired_speed_range(_config(base))
    out = _apply(base, "desired_speed_scale", 0.8)
    config = _config(out)
    assert resolve_desired_speed_range(config) == pytest.approx((low * 0.8, high * 0.8))
    before = resolve_vehicle_population(_config(base)).params_by_type["truck"]
    after = resolve_vehicle_population(config).params_by_type["truck"]
    assert after.desired_speed_range == pytest.approx(
        tuple(v * 0.8 for v in before.desired_speed_range)
    )


def test_a_factor_scales_from_the_base_scenarios_own_override():
    doc = _doc(mix=MIX)
    body = doc.model_dump()
    body["vehicles"]["types"] = {"bus": {"desiredTimeHeadway": 2.4}}
    out = _apply(ScenarioDocument.model_validate(body), "headway_scale", 0.5)
    population = resolve_vehicle_population(_config(out))
    assert population.params_by_type[
        "bus"
    ].profile.desired_time_headway == pytest.approx(1.2)


def test_mix_shift_and_headway_together_cover_classes_the_shift_introduced():
    mix = {"car": 0.9, "suv": 0.1}
    factors = _factors("mix_shift", "headway_scale")
    out = apply_factors(
        _doc(mix=mix), factors, {"mix_shift": 0.5, "headway_scale": 2.0}
    )
    population = resolve_vehicle_population(_config(out))
    assert population.params_by_type[
        "bus"
    ].profile.desired_time_headway == pytest.approx(3.6)
    assert population.params_by_type[
        "truck"
    ].profile.desired_time_headway == pytest.approx(4.0)


# --- general properties ------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kind, s",
    [
        ("demand_scale", 1.3),
        ("turning_shift", 0.4),
        ("mix_shift", -0.3),
        ("headway_scale", 0.8),
        ("max_acceleration_scale", 1.2),
        ("desired_speed_scale", 1.1),
    ],
)
def test_every_perturbed_document_validates_for_all_three_strategies(kind, s):
    out = _apply(_doc(mix=MIX), kind, s)
    check = validate_scenario(
        out.model_dump(), ["fixed_time", "adaptive", "roundabout"]
    )
    assert check["valid"], check["errors"]


def test_application_is_pure_deterministic_and_changes_the_fingerprint():
    base = _doc(mix=MIX)
    snapshot = copy.deepcopy(base.model_dump())
    factors = _factors("demand_scale", "headway_scale")
    values = {"demand_scale": 1.1, "headway_scale": 0.9}
    one = apply_factors(base, factors, values)
    two = apply_factors(base, factors, values)
    assert base.model_dump() == snapshot  # the base is never edited
    assert scenario_fingerprint(one) == scenario_fingerprint(two)
    assert scenario_fingerprint(one) != scenario_fingerprint(base)
    assert one.advanced == two.advanced


def test_applied_values_are_rounded_to_six_decimals():
    out = _apply(_doc(mix=MIX), "headway_scale", 1.0 / 3.0 + 1.0)
    for entry in out.advanced["vehicleGeneration"]["vehicleTypes"].values():
        assert entry["desiredTimeHeadway"] == round(entry["desiredTimeHeadway"], 6)


def test_preflight_flags_advanced_sections_that_would_shadow_a_factor():
    clean = _doc(mix=MIX)
    assert (
        preflight(clean, _factors("demand_scale", "turning_shift", "mix_shift")) == []
    )
    shadow_demand = _doc(mix=MIX, advanced={"traffic": {"arrivalRate": 0.5}})
    assert any(
        "demand_scale" in e for e in preflight(shadow_demand, _factors("demand_scale"))
    )
    shadow_mix = _doc(
        mix=MIX, advanced={"vehicleGeneration": {"vehicleMix": {"car": 1.0}}}
    )
    assert any("mix_shift" in e for e in preflight(shadow_mix, _factors("mix_shift")))
    shadow_turn = _doc(mix=MIX, advanced={"traffic": {"approaches": []}})
    assert any(
        "turning_shift" in e for e in preflight(shadow_turn, _factors("turning_shift"))
    )
    # IDM-style factors read the effective values, so an advanced override is fine for them
    idm = _doc(mix=MIX, advanced={"vehicleGeneration": {"desiredTimeHeadway": 1.2}})
    assert preflight(idm, _factors("headway_scale")) == []
    out = _apply(idm, "headway_scale", 2.0)
    assert _config(out)["vehicleGeneration"]["desiredTimeHeadway"] == pytest.approx(2.4)
