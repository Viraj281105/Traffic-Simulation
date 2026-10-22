"""Focused validation and parity tests for W4-T2 Driver Aggression profile (ADR-016)."""

from typing import Any, Dict

import pytest

from src.controllers.roundabout import _EXIT_COMMIT_MARGIN, _EXIT_SAFETY_HEADWAY
from src.core.config_models import TrafficSection
from src.experiments.manifest import (
    build_experiment_manifest,
    build_manifest_assumptions,
)
from src.scenario.config_validation import semantic_config_errors
from src.scenario.documents import (
    DRIVER_AGGRESSION_DISCLAIMER,
    compile_scenario,
    create_scenario,
    parse_scenario,
    scenario_fingerprint,
)
from src.vehicles.driver_aggression import (
    compute_aggression_parameter_hash,
    resolve_aggression_multipliers,
)
from src.vehicles.lane_change import resolve_lane_change_settings
from src.vehicles.vehicle_types import (
    CAR,
    DEFAULT_PROFILES,
    resolve_vehicle_population,
)


def _valid_scenario_dict(driver_aggression: Any = None) -> Dict[str, Any]:
    base: Dict[str, Any] = {
        "format": "urbanflow-scenario",
        "version": 1,
        "name": "Test Scenario",
        "junction": {"type": "fixed_time_signal"},
        "approaches": {
            d: {
                "lanes": 1,
                "length": 200,
                "vehiclesPerHour": 300,
                "turning": {"left": 0.2, "straight": 0.6, "right": 0.2},
            }
            for d in ("north", "south", "east", "west")
        },
        "roads": {"laneWidth": 3.5, "speedLimit": 13.89, "laneChanging": False},
        "vehicles": {"mix": None},
        "signal": {"greenTime": 30, "yellowTime": 4, "allRedTime": 2},
        "simulation": {"duration": 60, "seed": 42},
    }
    if driver_aggression is not None:
        base["traffic"] = {"driverAggression": driver_aggression}
    return base


def test_scientific_disclaimer_constant() -> None:
    """ADR-016 §7 wording constraint."""
    assert (
        DRIVER_AGGRESSION_DISCLAIMER
        == "driver aggression \u2014 a simulation assumption, not a measurement of real-world driver behaviour"
    )


def test_legacy_default_is_standard_in_config_models() -> None:
    """Legacy and stored configurations default to standard."""
    raw: Dict[str, Any] = {}
    parsed = TrafficSection.model_validate(raw)
    assert parsed.driverAggression == "standard"

    raw_mod: Dict[str, Any] = {"driverAggression": "moderate"}
    parsed_mod = TrafficSection.model_validate(raw_mod)
    assert parsed_mod.driverAggression == "moderate"


def test_config_validation_accepts_valid_profiles_and_rejects_invalid() -> None:
    """Validation accepts standard, moderate, high and rejects any other value."""
    for p in ("standard", "moderate", "high"):
        errs = semantic_config_errors({"traffic": {"driverAggression": p}})
        assert not any("driverAggression" in e for e in errs)

    bad_errs = semantic_config_errors({"traffic": {"driverAggression": "extreme"}})
    assert any("driverAggression" in e for e in bad_errs)

    numeric_errs = semantic_config_errors({"traffic": {"driverAggression": 123}})
    assert any("driverAggression" in e for e in numeric_errs)


def test_authoring_boundary_defaults_to_high_and_preserves_overrides() -> None:
    """create_scenario defaults to high at the authoring boundary, and preserves explicit selections."""
    doc_default = create_scenario(name="Default Scenario")
    assert doc_default.traffic is not None
    assert doc_default.traffic.driverAggression == "high"

    doc_std = create_scenario(name="Std Scenario", driver_aggression="standard")
    assert doc_std.traffic is not None
    assert doc_std.traffic.driverAggression == "standard"

    doc_mod = create_scenario(name="Mod Scenario", driver_aggression="moderate")
    assert doc_mod.traffic is not None
    assert doc_mod.traffic.driverAggression == "moderate"

    doc_high = create_scenario(name="High Scenario", driver_aggression="high")
    assert doc_high.traffic is not None
    assert doc_high.traffic.driverAggression == "high"


def test_stored_document_without_traffic_has_no_traffic_spec() -> None:
    """Legacy stored scenario document without traffic field parses with traffic=None."""
    raw_stored = _valid_scenario_dict()
    doc, errs = parse_scenario(raw_stored)
    assert errs == []
    assert doc is not None
    assert doc.traffic is None

    # Compilation omits driverAggression when unset in document,
    # which lets config_models default it to "standard" in engine
    compiled = compile_scenario(doc, "fixed_time")
    assert "driverAggression" not in compiled.get("traffic", {})


def test_fingerprint_parity_and_differentiation() -> None:
    """Bit-identical fingerprint when traffic is absent or standard; distinct when aggression is moderate or high."""
    base_raw = _valid_scenario_dict()
    doc_none, _ = parse_scenario(base_raw)
    assert doc_none is not None
    fp_none = scenario_fingerprint(doc_none)

    # With explicit standard aggression: must be bit-identical to absent/none
    raw_std = _valid_scenario_dict(driver_aggression="standard")
    doc_std, errs = parse_scenario(raw_std)
    assert errs == []
    assert doc_std is not None
    assert scenario_fingerprint(doc_std) == fp_none

    # With explicit moderate aggression: distinct from standard/none
    raw_mod = _valid_scenario_dict(driver_aggression="moderate")
    doc_mod, errs = parse_scenario(raw_mod)
    assert errs == []
    assert doc_mod is not None
    fp_mod = scenario_fingerprint(doc_mod)
    assert fp_mod != fp_none

    # With explicit high aggression: distinct from standard/none and moderate
    raw_high = _valid_scenario_dict(driver_aggression="high")
    doc_high, errs = parse_scenario(raw_high)
    assert errs == []
    assert doc_high is not None
    fp_high = scenario_fingerprint(doc_high)

    assert fp_high != fp_none
    assert fp_high != fp_mod

    # Determinism: same scenario produces exact same fingerprint
    doc_high_2, _ = parse_scenario(raw_high)
    assert doc_high_2 is not None
    assert scenario_fingerprint(doc_high_2) == fp_high


def test_aggression_multipliers_and_profiles() -> None:
    """Verify multiplier values approved in ADR-016 §2."""
    std = resolve_aggression_multipliers("standard")
    assert std["headway_mult"] == 1.0
    assert std["gap_mult"] == 1.0
    assert std["accel_mult"] == 1.0
    assert std["speed_factor_offset"] == 0.0
    assert std["politeness_mult"] == 1.0
    assert std["threshold_mult"] == 1.0

    mod = resolve_aggression_multipliers("moderate")
    assert mod["headway_mult"] == 0.85
    assert mod["gap_mult"] == 0.875
    assert mod["accel_mult"] == 1.075
    assert mod["speed_factor_offset"] == 0.025
    assert mod["politeness_mult"] == 0.75
    assert mod["threshold_mult"] == 0.75

    high = resolve_aggression_multipliers("high")
    assert high["headway_mult"] == 0.70
    assert high["gap_mult"] == 0.75
    assert high["accel_mult"] == 1.15
    assert high["speed_factor_offset"] == 0.05
    assert high["politeness_mult"] == 0.50
    assert high["threshold_mult"] == 0.50

    # Absent is standard; an unknown name is an error, never a silent standard
    assert resolve_aggression_multipliers(None) == std
    with pytest.raises(ValueError):
        resolve_aggression_multipliers("unknown")


def test_vehicle_population_scaling_per_profile() -> None:
    """Population resolution scales headway, gap, and acceleration while preserving comfort decel and delta."""
    car_base = DEFAULT_PROFILES[CAR]

    cfg_std = {
        "vehicleGeneration": {"vehicleMix": {"car": 1.0}},
        "traffic": {"driverAggression": "standard"},
    }
    pop_std = resolve_vehicle_population(cfg_std)
    assert pop_std is not None
    car_std = pop_std.params_by_type[CAR].profile
    assert car_std.desired_time_headway == pytest.approx(car_base.desired_time_headway)
    assert car_std.minimum_gap == pytest.approx(car_base.minimum_gap)
    assert car_std.max_acceleration == pytest.approx(car_base.max_acceleration)
    assert car_std.comfort_deceleration == pytest.approx(car_base.comfort_deceleration)
    assert car_std.idm_delta == pytest.approx(car_base.idm_delta)

    cfg_high = {
        "vehicleGeneration": {"vehicleMix": {"car": 1.0}},
        "traffic": {"driverAggression": "high"},
    }
    pop_high = resolve_vehicle_population(cfg_high)
    assert pop_high is not None
    car_high = pop_high.params_by_type[CAR].profile
    assert car_high.desired_time_headway == pytest.approx(
        car_base.desired_time_headway * 0.70
    )
    assert car_high.minimum_gap == pytest.approx(car_base.minimum_gap * 0.75)
    assert car_high.max_acceleration == pytest.approx(car_base.max_acceleration * 1.15)
    # Comfort decel and delta exponent strictly unchanged
    assert car_high.comfort_deceleration == pytest.approx(car_base.comfort_deceleration)
    assert car_high.idm_delta == pytest.approx(car_base.idm_delta)


def test_safe_deceleration_invariant_and_dag2_independence() -> None:
    """Safe deceleration is 4.0 m/s^2 across all profiles, and high aggression does not imply aggressiveTwoWheelers."""
    for profile in ("standard", "moderate", "high"):
        lc_settings = resolve_lane_change_settings(
            {"traffic": {"driverAggression": profile}}
        )
        # Safe deceleration is strictly immutable
        assert lc_settings.safe_deceleration == 4.0

    # D-AG2 check: aggressive_two_wheelers remains False even under high aggression
    lc_high = resolve_lane_change_settings(
        {
            "traffic": {
                "driverAggression": "high",
                "aggressiveTwoWheelers": False,
                "unstructuredTraffic": False,
            }
        }
    )
    # Under high aggression, threshold is 0.50 * base = 0.10 m/s^2
    assert lc_high.acceleration_threshold == pytest.approx(0.10)
    assert lc_high.aggressive_two_wheelers is False


def test_roundabout_safety_constants_unchanged() -> None:
    """ADR-016 §3: Roundabout safety margins are strictly fixed at 1.0s."""
    assert _EXIT_SAFETY_HEADWAY == 1.0
    assert _EXIT_COMMIT_MARGIN == 1.0


def test_experiment_preparation_with_aggression_profile() -> None:
    """Experiments accept scenarios with explicit driverAggression."""
    from src.experiments.preparation import prepare

    valid_request: Dict[str, Any] = {
        "format": "urbanflow-experiment",
        "version": 1,
        "name": "Aggression Experiment",
        "scenario": _valid_scenario_dict(driver_aggression="high"),
        "uncertainty": {
            "factors": [
                {
                    "id": "demand",
                    "kind": "demand_scale",
                    "distribution": {"kind": "uniform"},
                    "bounds": [0.9, 1.1],
                    "rationale": "Peak traffic fluctuation",
                }
            ],
            "conditions": 4,
            "seed": 10,
        },
    }

    prepared = prepare(valid_request)
    assert prepared.errors == []
    assert prepared.base is not None
    assert prepared.base.traffic is not None
    assert prepared.base.traffic.driverAggression == "high"

    # Invalid aggression in experiment scenario rejected with error
    invalid_scenario = dict(_valid_scenario_dict())
    invalid_scenario["traffic"] = {"driverAggression": "invalid_mode"}
    invalid_request: Dict[str, Any] = {
        "format": "urbanflow-experiment",
        "version": 1,
        "name": "Invalid Aggression Experiment",
        "scenario": invalid_scenario,
        "uncertainty": {
            "factors": [
                {
                    "id": "demand",
                    "kind": "demand_scale",
                    "distribution": {"kind": "uniform"},
                    "bounds": [0.9, 1.1],
                    "rationale": "Peak traffic fluctuation",
                }
            ],
            "conditions": 4,
            "seed": 10,
        },
    }

    bad_prepared = prepare(invalid_request)
    assert any("driverAggression" in e for e in bad_prepared.errors)


def test_compute_aggression_parameter_hash() -> None:
    """Verify aggression parameter hash calculation, fallbacks, and distinction."""
    # Determinism
    h_std1 = compute_aggression_parameter_hash("standard")
    h_std2 = compute_aggression_parameter_hash("standard")
    assert h_std1 == h_std2
    assert len(h_std1) == 16

    # Unset/None is standard; an unknown name is an error, never standard
    assert compute_aggression_parameter_hash(None) == h_std1
    with pytest.raises(ValueError):
        compute_aggression_parameter_hash("unknown_mode")
    assert compute_aggression_parameter_hash({}) == h_std1
    assert (
        compute_aggression_parameter_hash({"traffic": {"driverAggression": "standard"}})
        == h_std1
    )

    # Distinct hashes for moderate and high
    h_mod = compute_aggression_parameter_hash("moderate")
    h_high = compute_aggression_parameter_hash("high")
    assert len(h_mod) == 16
    assert len(h_high) == 16
    assert h_mod != h_std1
    assert h_high != h_std1
    assert h_mod != h_high


def test_experiment_manifest_assumptions() -> None:
    """Verify manifest assumptions block records profile, hash, and scientific disclaimer."""
    # Scenario with standard aggression (or absent)
    base_raw = _valid_scenario_dict()
    doc_std, _ = parse_scenario(base_raw)
    assert doc_std is not None

    assumptions_std = build_manifest_assumptions(doc_std)
    assert assumptions_std["driverAggression"] == "standard"
    assert assumptions_std["driverAggressionHash"] == compute_aggression_parameter_hash(
        "standard"
    )
    assert assumptions_std["disclaimer"] == DRIVER_AGGRESSION_DISCLAIMER

    manifest_std = build_experiment_manifest(
        scenario=doc_std,
        spec_fingerprint="abcd1234efgh5678",
        result_fingerprint="12345678abcdef00",
    )
    assert manifest_std["format"] == "urbanflow-experiment-manifest"
    assert manifest_std["version"] == 1
    assert manifest_std["scenarioFingerprint"] == scenario_fingerprint(doc_std)
    assert manifest_std["assumptions"]["driverAggression"] == "standard"

    # Scenario with explicit high aggression
    raw_high = _valid_scenario_dict(driver_aggression="high")
    doc_high, _ = parse_scenario(raw_high)
    assert doc_high is not None

    manifest_high = build_experiment_manifest(
        scenario=doc_high,
        spec_fingerprint="abcd1234efgh5678",
        result_fingerprint="12345678abcdef00",
    )
    assert manifest_high["assumptions"]["driverAggression"] == "high"
    assert manifest_high["assumptions"][
        "driverAggressionHash"
    ] == compute_aggression_parameter_hash("high")
    assert (
        manifest_high["assumptions"]["driverAggressionHash"]
        != assumptions_std["driverAggressionHash"]
    )


# --- W4-T6: Bounds, Malformed Inputs, and Validation Edge Cases --------------------------------


class TestAggressionBoundsAndEdgeCases:
    @pytest.mark.parametrize(
        "malformed_val",
        [
            "extreme",
            "low",
            "aggressive",
            "STANDARD",
            "High",
            "moderate ",
            "",
            "   ",
            123,
            0,
            True,
            False,
            [],
            ["high"],
            {"name": "high"},
        ],
    )
    def test_semantic_errors_rejects_malformed_aggression(
        self, malformed_val: Any
    ) -> None:
        """semantic_config_errors must reject non-standard strings, bad cases, and wrong types."""
        errs = semantic_config_errors({"traffic": {"driverAggression": malformed_val}})
        assert any("driverAggression" in e for e in errs), (
            f"Expected error for {malformed_val!r}"
        )

    def test_semantic_errors_handles_non_dict_traffic(self) -> None:
        """semantic_config_errors must not crash when traffic is not a dict."""
        errs = semantic_config_errors({"traffic": "not_a_dict"})
        assert isinstance(errs, list)
        errs_int = semantic_config_errors({"traffic": 42})
        assert isinstance(errs_int, list)

    @pytest.mark.parametrize(
        "bad_val",
        ["extreme", "aggressive", 999, False, ["high"]],
    )
    def test_parse_scenario_rejects_malformed_aggression(self, bad_val: Any) -> None:
        """parse_scenario returns descriptive errors for malformed driverAggression values."""
        raw = _valid_scenario_dict(driver_aggression=bad_val)
        doc, errs = parse_scenario(raw)
        assert len(errs) > 0
        assert any("driverAggression" in e for e in errs)

    def test_traffic_spec_rejects_unknown_fields(self) -> None:
        """Strict validation rejects unknown fields inside traffic."""
        raw = _valid_scenario_dict()
        raw["traffic"] = {"driverAggression": "high", "unknownField": "unsupported"}
        doc, errs = parse_scenario(raw)
        assert len(errs) > 0
        assert any("extra" in e.lower() or "unknownfield" in e.lower() for e in errs)

    def test_create_scenario_rejects_invalid_aggression_at_boundary(self) -> None:
        """create_scenario rejects invalid profile name via Pydantic ValidationError."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            create_scenario(driver_aggression="extreme")  # type: ignore[arg-type]

    def test_absent_profile_is_standard(self) -> None:
        """None (absent) resolves to standard everywhere, untouched."""
        from src.vehicles.driver_aggression import apply_aggression_to_profile

        base_car = DEFAULT_PROFILES[CAR]
        assert resolve_aggression_multipliers(None) == resolve_aggression_multipliers(
            "standard"
        )
        assert compute_aggression_parameter_hash(
            None
        ) == compute_aggression_parameter_hash("standard")
        assert apply_aggression_to_profile(base_car, None) is base_car

    @pytest.mark.parametrize(
        "bad", ["", "invalid", "High", "high_speed", 123, True, ["high"], ("high",)]
    )
    def test_invalid_profile_fails_loudly_instead_of_running_standard(
        self, bad: Any
    ) -> None:
        """A value that bypassed validation must not silently run as standard."""
        from src.vehicles.driver_aggression import (
            aggression_multipliers_for,
            apply_aggression_to_profile,
        )

        with pytest.raises(ValueError, match="driverAggression"):
            resolve_aggression_multipliers(bad)
        with pytest.raises(ValueError, match="driverAggression"):
            compute_aggression_parameter_hash(bad)
        with pytest.raises(ValueError, match="driverAggression"):
            apply_aggression_to_profile(DEFAULT_PROFILES[CAR], bad)
        with pytest.raises(ValueError, match="driverAggression"):
            aggression_multipliers_for({"traffic": {"driverAggression": bad}})

    @pytest.mark.parametrize("profile_name", ("standard", "moderate", "high"))
    def test_physical_bounds_across_all_vehicle_classes(
        self, profile_name: str
    ) -> None:
        """All vehicle classes must respect physical safety and realism bounds under every profile."""
        from src.vehicles.driver_aggression import apply_aggression_to_profile
        from src.vehicles.vehicle_types import VEHICLE_CLASSES

        for class_name in VEHICLE_CLASSES:
            base = DEFAULT_PROFILES[class_name]
            p = apply_aggression_to_profile(base, profile_name)

            # Desired time headway T > 0 and within realistic physical bounds
            assert 0.5 <= p.desired_time_headway <= 3.5, (
                f"T out of bounds for {class_name} ({profile_name})"
            )
            # Minimum standstill gap s0 > 0 and within bounds
            assert 0.5 <= p.minimum_gap <= 4.0, (
                f"s0 out of bounds for {class_name} ({profile_name})"
            )
            # Max launch acceleration a within bounds
            assert 0.8 <= p.max_acceleration <= 4.0, (
                f"a out of bounds for {class_name} ({profile_name})"
            )
            # Desired speed factor upper bound NEVER exceeds 1.10
            f_lo, f_hi = p.desired_speed_factor
            assert f_lo <= f_hi
            assert f_hi <= 1.10 + 1e-9, (
                f"Speed factor ceiling exceeded 1.10 for {class_name} ({profile_name})"
            )
            # Politeness within [0, 1]
            assert 0.0 <= p.politeness <= 1.0, (
                f"Politeness out of range for {class_name} ({profile_name})"
            )

    def test_physical_class_ordering_preserved_under_high_aggression(self) -> None:
        """Physical relative ordering between light and heavy classes must hold under high aggression."""
        from src.vehicles.driver_aggression import apply_aggression_to_profile
        from src.vehicles.vehicle_types import BUS, CAR, TRUCK

        car_p = apply_aggression_to_profile(DEFAULT_PROFILES[CAR], "high")
        truck_p = apply_aggression_to_profile(DEFAULT_PROFILES[TRUCK], "high")
        bus_p = apply_aggression_to_profile(DEFAULT_PROFILES[BUS], "high")

        # Heavy vehicles must maintain larger headways and larger gaps than cars
        assert truck_p.desired_time_headway > car_p.desired_time_headway
        assert bus_p.desired_time_headway > car_p.desired_time_headway
        assert truck_p.minimum_gap > car_p.minimum_gap
        assert bus_p.minimum_gap > car_p.minimum_gap

        # Cars must have higher launch acceleration than heavy vehicles
        assert car_p.max_acceleration > truck_p.max_acceleration
        assert car_p.max_acceleration > bus_p.max_acceleration

    def test_speed_factor_ceiling_clamped_at_1_10(self) -> None:
        """Adding offset to already high speed factor must clamp at exactly 1.10."""
        from dataclasses import replace

        from src.vehicles.driver_aggression import apply_aggression_to_profile

        base_car = DEFAULT_PROFILES[CAR]
        fast_car = replace(base_car, desired_speed_factor=(1.05, 1.08))

        high_fast = apply_aggression_to_profile(fast_car, "high")
        f_lo, f_hi = high_fast.desired_speed_factor
        assert f_hi == pytest.approx(1.10)
        assert f_lo <= 1.10
