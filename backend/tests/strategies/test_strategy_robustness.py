"""Strategy Robustness, Edge-Case & Regression Tests -- V3.0 W3-T5 (ADR-014).

Verifies the robustness and stability of the composable control strategy system:
1. Malformed descriptors, extra fields, invalid layer combinations, and parameter bound invariants.
2. Registry isolation, untrusted object rejection, re-registration guards, alias cycles, and custom compositions.
3. Diagnostic code stability, formatting, backward-compatible error messages, and suggestions.
4. Simulation initialization failure guards, parameter bounds enforcement, and simulations_db isolation.
5. Golden fingerprint parity, cross-invocation determinism, and configuration equivalence.
6. Scenario validation contracts for both canonical strategy IDs and legacy aliases.
"""

from __future__ import annotations

from typing import Any, Dict

import pytest
from pydantic import ValidationError

from src.scenario.config_validation import semantic_config_errors
from src.scenario.documents import (
    validate_scenario,
)
from src.simulations.registry import (
    InvalidSimulationConfigError,
    register_simulation,
    simulations_db,
)
from src.strategies.builtins import BUILTIN_STRATEGIES
from src.strategies.models import (
    AdaptationLogic,
    ControlPolicy,
    GeometryConstraint,
    MovementTopology,
    ParameterBound,
    PriorityOverlay,
    RightOfWay,
    StrategyDescriptor,
)
from src.strategies.registry import (
    StrategyRegistry,
    get_strategy_registry,
    reset_strategy_registry,
)
from src.strategies.resolution import (
    compute_strategy_instance_fingerprint,
)
from src.strategies.validator import (
    COMPATIBILITY_ERROR_CODES,
    CompatibilityIssue,
    StrategyCompatibilityError,
)

# ============================================================================
# 1. Descriptor Edge Cases & Model Boundary Validation
# ============================================================================


class TestDescriptorBoundaryValidation:
    """Test boundary validation and error handling for strategy descriptor models."""

    def test_descriptor_forbids_extra_fields(self) -> None:
        """Extra fields at root or layer levels must be strictly rejected (extra='forbid')."""
        sample = BUILTIN_STRATEGIES[0].model_dump()
        sample["unauthorized_plugin"] = "exploit.py"
        with pytest.raises(ValidationError) as exc:
            StrategyDescriptor.model_validate(sample)
        assert "unauthorized_plugin" in str(exc.value)

    def test_descriptor_id_pattern_and_bounds(self) -> None:
        """Strategy ID must be lowercase alphanumeric with underscores only."""
        sample = BUILTIN_STRATEGIES[0].model_dump()
        for invalid_id in ("FixedTime", "fixed-time", "fixed time", "fixed@time", ""):
            sample["id"] = invalid_id
            with pytest.raises(ValidationError):
                StrategyDescriptor.model_validate(sample)

    def test_parameter_bounds_inversion_rejected(self) -> None:
        """ParameterBound min_value cannot exceed max_value."""
        with pytest.raises(ValueError, match="cannot exceed max_value"):
            ParameterBound(
                min_value=30.0,
                max_value=10.0,
                unit="s",
                description="Invalid inverted bounds",
            )

    def test_parameter_bound_default_out_of_range_rejected(self) -> None:
        """ParameterBound default_value must fall within [min_value, max_value]."""
        with pytest.raises(ValueError, match="must be within"):
            ParameterBound(
                min_value=5.0,
                max_value=60.0,
                default_value=70.0,
                unit="s",
                description="Default too high",
            )
        with pytest.raises(ValueError, match="must be within"):
            ParameterBound(
                min_value=5.0,
                max_value=60.0,
                default_value=2.0,
                unit="s",
                description="Default too low",
            )

    def test_parameter_bound_valid_exact_boundaries(self) -> None:
        """ParameterBound handles exact min and max bounds."""
        bound = ParameterBound(
            min_value=5.0,
            max_value=5.0,
            default_value=5.0,
            unit="s",
            description="Exact single point bound",
        )
        assert bound.min_value == 5.0
        assert bound.max_value == 5.0
        assert bound.default_value == 5.0

    def test_geometry_constraint_arms_range_validation(self) -> None:
        """GeometryConstraint rejects min_arms > max_arms."""
        with pytest.raises(ValueError, match="cannot be greater than max_arms"):
            GeometryConstraint(
                intersection_type="fixed_time_signal",
                min_arms=4,
                max_arms=3,
            )

    def test_geometry_constraint_out_of_bounds_arms(self) -> None:
        """GeometryConstraint enforces 3 <= arms <= 4."""
        with pytest.raises(ValidationError):
            GeometryConstraint(
                intersection_type="fixed_time_signal", min_arms=2, max_arms=4
            )
        with pytest.raises(ValidationError):
            GeometryConstraint(
                intersection_type="fixed_time_signal", min_arms=3, max_arms=5
            )


# ============================================================================
# 2. Registry Security, Isolation & Custom Composition
# ============================================================================


class TestRegistrySecurityAndIsolation:
    """Test registry isolation, security rules (ADR-014 §3), and custom composition."""

    def test_registry_rejects_untrusted_raw_payloads(self) -> None:
        """Registry accepts StrategyDescriptor instances only; dicts or strings are rejected."""
        reg = StrategyRegistry(load_builtins=False)
        for bad_payload in (
            {"id": "hacked", "name": "Fake"},
            "import os; os.system('echo hacked')",
            12345,
            [BUILTIN_STRATEGIES[0]],
        ):
            with pytest.raises(TypeError, match="expected StrategyDescriptor instance"):
                reg.register(bad_payload)  # type: ignore[arg-type]

    def test_registry_forbids_duplicate_registration(self) -> None:
        """Re-registering an existing strategy ID is strictly forbidden."""
        reg = StrategyRegistry(load_builtins=True)
        builtin = BUILTIN_STRATEGIES[0]
        with pytest.raises(ValueError, match="is already registered"):
            reg.register(builtin)

    def test_registry_rejects_invalid_layer_composition(self) -> None:
        """Attempting to register a descriptor with contradictory layers must fail at self-validation."""
        bad_desc = StrategyDescriptor(
            id="contradictory_strat",
            name="Contradictory Strategy",
            description="Attempts signal right of way on a roundabout geometry.",
            geometry=GeometryConstraint(
                intersection_type="roundabout",
                circulating_lanes=[1, 2],
            ),
            movement_topology=MovementTopology(topology_type="zone_based_conflicts"),
            right_of_way=RightOfWay(
                rule="signal"
            ),  # Incompatible with roundabout geometry
            control_policy=ControlPolicy(
                policy="fixed_time_phase_plan", cycle_aware=True
            ),
            adaptation_logic=AdaptationLogic(logic="none"),
            priority_overlay=PriorityOverlay(overlay="none"),
        )
        reg = StrategyRegistry(load_builtins=False)
        with pytest.raises(StrategyCompatibilityError) as exc:
            reg.register(bad_desc)
        assert "compat.signal_requires_signal_geometry" in str(exc.value)

    def test_registry_detects_cyclic_aliases(self) -> None:
        """Cyclic alias definitions are detected and rejected upon registration and resolution."""
        reg = StrategyRegistry(load_builtins=True)
        reg.register_alias("alias_a", "fixed_time_signal")
        reg.register_alias("alias_b", "alias_a")
        # Attempting to map alias_a back to alias_b creates a cycle
        with pytest.raises(ValueError, match="Cyclic alias detected"):
            reg.register_alias("alias_a", "alias_b")

        # Also test runtime resolution defense-in-depth if _aliases was mutated
        reg._aliases["alias_a"] = "alias_b"
        with pytest.raises(ValueError, match="Cyclic alias detected"):
            reg.resolve_id("alias_a")

    def test_registry_alias_to_unknown_strategy_rejected(self) -> None:
        """Registering an alias pointing to a non-existent strategy is rejected."""
        reg = StrategyRegistry(load_builtins=True)
        with pytest.raises(KeyError, match="unknown strategy 'ghost_strategy'"):
            reg.register_alias("ghost_alias", "ghost_strategy")

    def test_custom_strategy_composition_isolation(self) -> None:
        """A valid custom strategy can be registered in an isolated registry without leaking."""
        custom_desc = StrategyDescriptor(
            id="custom_actuated_t_junction",
            name="Custom Actuated T-Junction",
            status="experimental",
            description="Actuated 3-arm T-junction with gap-out detector extensions.",
            geometry=GeometryConstraint(
                intersection_type="fixed_time_signal",
                min_arms=3,
                max_arms=3,
            ),
            movement_topology=MovementTopology(topology_type="point_based_conflicts"),
            right_of_way=RightOfWay(rule="signal"),
            control_policy=ControlPolicy(
                policy="fixed_time_phase_plan", cycle_aware=True
            ),
            adaptation_logic=AdaptationLogic(
                logic="gap_out_extension", deterministic=True
            ),
            priority_overlay=PriorityOverlay(overlay="none"),
            parameters={
                "min_green": ParameterBound(
                    min_value=5.0,
                    max_value=20.0,
                    default_value=8.0,
                    unit="s",
                    description="Min green",
                ),
            },
        ).with_computed_fingerprint()

        isolated_reg = StrategyRegistry(load_builtins=True)
        isolated_reg.register(custom_desc)
        isolated_reg.self_check()

        assert isolated_reg.has("custom_actuated_t_junction")
        retrieved = isolated_reg.get("custom_actuated_t_junction")
        assert retrieved.id == "custom_actuated_t_junction"
        assert retrieved.fingerprint is not None

        # Verify global registry was NOT mutated or polluted
        global_reg = get_strategy_registry()
        assert not global_reg.has("custom_actuated_t_junction")

        # Verify reset leaves global registry intact
        reset_reg = reset_strategy_registry()
        assert not reset_reg.has("custom_actuated_t_junction")
        assert len(reset_reg.list_ids()) == 4


# ============================================================================
# 3. Diagnostic Codes, Error Formatting & Suggestion Verification
# ============================================================================


class TestDiagnosticCodesAndErrorFormatting:
    """Verify all 16 diagnostic codes, error formatting, and actionable suggestions."""

    def test_all_16_diagnostic_codes_registered(self) -> None:
        """Ensure all 16 defined diagnostic codes are recognized in COMPATIBILITY_ERROR_CODES."""
        expected_codes = {
            "compat.signal_requires_signal_geometry",
            "compat.roundabout_yield_requires_roundabout",
            "compat.phased_priority_unsupported",
            "compat.signal_requires_point_topology",
            "compat.roundabout_requires_zone_topology",
            "compat.roundabout_requires_circulating_lanes",
            "compat.signal_forbids_circulating_lanes",
            "compat.arms_range_invalid",
            "compat.signal_row_requires_phase_plan",
            "compat.yield_to_ring_requires_uncontrolled",
            "compat.signal_over_yield_requires_metering",
            "compat.adaptive_unsupported_policy",
            "compat.uncontrolled_cannot_be_cycle_aware",
            "compat.priority_overlay_unsupported",
            "compat.unknown_strategy",
            "compat.strategy_config_mismatch",
        }
        assert expected_codes == COMPATIBILITY_ERROR_CODES

    def test_diagnostic_issue_formatting(self) -> None:
        """CompatibilityIssue formats code, message, and suggestion cleanly."""
        issue = CompatibilityIssue(
            code="compat.signal_requires_signal_geometry",
            message="Signal right-of-way requires signal geometry",
            layers=("geometry", "right_of_way"),
            suggestion="Set geometry.intersection_type to 'fixed_time_signal'.",
        )
        formatted = issue.formatted_message()
        assert "(compat.signal_requires_signal_geometry)" in formatted
        assert "Suggestion: Set geometry.intersection_type" in formatted
        assert str(issue) == formatted

    def test_multi_issue_exception_formatting(self) -> None:
        """StrategyCompatibilityError aggregates multiple issues with semicolon separation."""
        issue1 = CompatibilityIssue(
            code="compat.roundabout_requires_zone_topology",
            message="Roundabout requires zone topology",
            layers=("geometry", "movement_topology"),
        )
        issue2 = CompatibilityIssue(
            code="compat.roundabout_requires_circulating_lanes",
            message="Roundabout requires circulating lanes",
            layers=("geometry",),
            suggestion="Specify circulating lanes.",
        )
        err = StrategyCompatibilityError([issue1, issue2], strategy_id="test_combo")
        msg = str(err)
        assert msg.startswith("Strategy 'test_combo':")
        assert "compat.roundabout_requires_zone_topology" in msg
        assert "compat.roundabout_requires_circulating_lanes" in msg
        assert "; " in msg


# ============================================================================
# 4. Simulation Initialization Guards & Failure Tests
# ============================================================================


class TestSimulationInitializationGuards:
    """Test that invalid configurations cannot start simulations and leave registry clean."""

    def _base_valid_config(self) -> Dict[str, Any]:
        return {
            "simulation": {"duration": 10, "timeStep": 0.1},
            "geometry": {"intersectionType": "fixed_time_signal"},
            "roads": {
                "approachLength": 100.0,
                "lanesPerApproach": 1,
                "laneWidth": 3.5,
                "speedLimit": 13.9,
                "approaches": [
                    {
                        "direction": d,
                        "length": 100.0,
                        "lanes": 1,
                        "turnProbabilities": {
                            "left": 0.2,
                            "straight": 0.6,
                            "right": 0.2,
                        },
                    }
                    for d in ("north", "south", "east", "west")
                ],
            },
            "traffic": {
                "arrivalRate": 0.2,
                "arrivalDistribution": "poisson",
                "totalVehicles": 5,
                "directionalSplit": {
                    "north": 0.25,
                    "south": 0.25,
                    "east": 0.25,
                    "west": 0.25,
                },
                "turnProbabilities": {"left": 0.2, "straight": 0.6, "right": 0.2},
            },
            "controller": {
                "greenTime": 25.0,
                "yellowTime": 3.0,
                "allRedTime": 2.0,
            },
        }

    def test_init_fails_on_unknown_strategy(self) -> None:
        """Calling register_simulation with an unknown strategy raises InvalidSimulationConfigError."""
        cfg = self._base_valid_config()
        cfg["strategy"] = "non_existent_policy"
        initial_count = len(simulations_db)

        with pytest.raises(InvalidSimulationConfigError) as exc:
            register_simulation(cfg)
        assert "compat.unknown_strategy" in str(exc.value)
        # Verify no simulation was added
        assert len(simulations_db) == initial_count

    def test_init_fails_on_strategy_geometry_mismatch(self) -> None:
        """Strategy fixed_time_signal with roundabout geometry fails initialization."""
        cfg = self._base_valid_config()
        cfg["strategy"] = "fixed_time_signal"
        cfg["geometry"]["intersectionType"] = "roundabout"
        initial_count = len(simulations_db)

        with pytest.raises(InvalidSimulationConfigError) as exc:
            register_simulation(cfg)
        assert "compat.strategy_config_mismatch" in str(exc.value)
        assert len(simulations_db) == initial_count

    def test_init_fails_on_adaptive_roundabout_conflict(self) -> None:
        """Adaptive control on unmetered roundabout fails before simulation construction."""
        cfg = self._base_valid_config()
        cfg["geometry"]["intersectionType"] = "roundabout"
        cfg["controller"]["signalControl"] = "adaptive"
        initial_count = len(simulations_db)

        with pytest.raises(InvalidSimulationConfigError) as exc:
            register_simulation(cfg)
        assert "compat.adaptive_unsupported_policy" in str(exc.value)
        assert len(simulations_db) == initial_count

    def test_init_fails_on_out_of_bounds_parameter(self) -> None:
        """Green duration below descriptor min_value (5.0s) fails initialization."""
        cfg = self._base_valid_config()
        cfg["strategy"] = "fixed_time_signal"
        cfg["controller"]["greenTime"] = 2.0  # min is 5.0
        initial_count = len(simulations_db)

        with pytest.raises(InvalidSimulationConfigError) as exc:
            register_simulation(cfg)
        assert "out of bounds [5.0, 120.0]" in str(exc.value)
        assert len(simulations_db) == initial_count


# ============================================================================
# 5. Golden Fingerprint Parity & Determinism Invariants
# ============================================================================


class TestDeterminismAndGoldenParity:
    """Verify bit-identical determinism and golden fingerprint invariants."""

    def test_instance_fingerprint_deterministic_repeatability(self) -> None:
        """Same descriptor and parameters always yield bit-identical instance fingerprints."""
        desc = BUILTIN_STRATEGIES[0]
        params = {"green_time": 30.0, "yellow_time": 3.0, "all_red_time": 2.0}
        fp1 = compute_strategy_instance_fingerprint(desc, params)
        fp2 = compute_strategy_instance_fingerprint(desc, params)
        assert fp1 == fp2
        assert len(fp1) == 16

    def test_instance_fingerprint_changes_on_parameter_change(self) -> None:
        """Changing a parameter changes the strategy instance fingerprint."""
        desc = BUILTIN_STRATEGIES[0]
        fp_baseline = compute_strategy_instance_fingerprint(
            desc, {"green_time": 25.0, "yellow_time": 3.0}
        )
        fp_custom = compute_strategy_instance_fingerprint(
            desc, {"green_time": 35.0, "yellow_time": 3.0}
        )
        assert fp_baseline != fp_custom

    def test_legacy_and_canonical_produce_identical_fingerprints(self) -> None:
        """Canonical strategy and its legacy alias produce bit-identical instance fingerprints."""
        reg = get_strategy_registry()
        desc_canonical = reg.get("conventional_roundabout")
        desc_alias = reg.get("roundabout")
        params = {"critical_gap": 4.1, "follow_up_time": 2.6}

        fp_canonical = compute_strategy_instance_fingerprint(desc_canonical, params)
        fp_alias = compute_strategy_instance_fingerprint(desc_alias, params)
        assert fp_canonical == fp_alias


# ============================================================================
# 6. Scenario Validation & Compilation Compatibility
# ============================================================================


class TestScenarioValidationCompatibility:
    """Verify scenario document validation and compilation with canonical IDs and aliases."""

    def _sample_scenario_dict(self) -> Dict[str, Any]:
        return {
            "format": "urbanflow-scenario",
            "version": 1,
            "name": "Robustness Test Scenario",
            "junction": {"type": "fixed_time_signal"},
            "simulation": {
                "duration": 60,
                "timeStep": 0.1,
                "warmup": 10,
                "seed": 42,
                "arrivalPattern": "poisson",
            },
            "roads": {
                "laneWidth": 3.5,
                "speedLimit": 13.9,
                "laneChanging": False,
            },
            "approaches": {
                "north": {"lanes": 1, "length": 100.0, "vehiclesPerHour": 200},
                "south": {"lanes": 1, "length": 100.0, "vehiclesPerHour": 200},
                "east": {"lanes": 1, "length": 100.0, "vehiclesPerHour": 200},
                "west": {"lanes": 1, "length": 100.0, "vehiclesPerHour": 200},
            },
            "signal": {
                "greenTime": 25.0,
                "yellowTime": 3.0,
                "allRedTime": 2.0,
            },
            "vehicles": {"mix": {"car": 1.0}},
        }

    def test_validate_scenario_accepts_canonical_strategy_ids(self) -> None:
        """validate_scenario accepts canonical strategy IDs as well as legacy aliases."""
        scen = self._sample_scenario_dict()
        res = validate_scenario(
            scen,
            strategies=["fixed_time_signal", "fixed_time"],
        )
        assert res["valid"] is True, res["errors"]

    def test_validate_scenario_rejects_unknown_strategy(self) -> None:
        """validate_scenario rejects unknown strategy strings with an informative message."""
        scen = self._sample_scenario_dict()
        res = validate_scenario(scen, strategies=["unknown_teleport_strategy"])
        assert res["valid"] is False
        assert any(
            "Unknown strategies ['unknown_teleport_strategy']" in e
            for e in res["errors"]
        )

    def test_semantic_config_errors_surfaces_strategy_compatibility_codes(self) -> None:
        """semantic_config_errors detects explicit strategy mismatch and includes diagnostic code."""
        cfg = {
            "strategy": "fixed_time_signal",
            "geometry": {"intersectionType": "roundabout"},
            "controller": {},
        }
        errors = semantic_config_errors(cfg)
        assert any("compat.strategy_config_mismatch" in e for e in errors)
