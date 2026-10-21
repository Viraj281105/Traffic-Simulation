"""Unit tests for Strategy Compatibility Validator (V3.0 W3, ADR-014 §2).

Verifies:
1. Pure pre-simulation validation engine evaluating the 6 strategy descriptor layers.
2. 100% test coverage for all defined compatibility rules with dedicated rejection tests.
3. Stable machine-readable diagnostic error codes (compat.*).
4. Valid combination tests for all 4 built-ins and custom valid compositions.
5. Formal replacement of legacy error "adaptive applies to a signalised junction"
   with coded, explanatory diagnostics (ADR-014 §2, Sprint Plan §3.4).
6. Pre-simulation initialization protection preventing construction of invalid simulation objects.
"""

from typing import Any, Dict, List

import pytest

from src.scenario.config_validation import semantic_config_errors
from src.simulations.registry import InvalidSimulationConfigError, register_simulation
from src.strategies.builtins import (
    ADAPTIVE_SIGNAL,
    BUILTIN_STRATEGIES,
    CONVENTIONAL_ROUNDABOUT,
    FIXED_TIME_SIGNAL,
    METERED_ENTRY_ROUNDABOUT,
)
from src.strategies.models import (
    AdaptationLogic,
    ControlPolicy,
    GeometryConstraint,
    MovementTopology,
    PriorityOverlay,
    RightOfWay,
    StrategyDescriptor,
)
from src.strategies.validator import (
    COMPATIBILITY_ERROR_CODES,
    CompatibilityIssue,
    StrategyCompatibilityError,
    check_scenario_strategy_compatibility,
    check_strategy_compatibility,
    validate_layer_combination,
    validate_scenario_strategy_compatibility,
    validate_strategy_compatibility,
)


def _codes(issues: List[CompatibilityIssue]) -> List[str]:
    return [issue.code for issue in issues]


class TestCompatibilityRuleRejections:
    """Dedicated rejecting unit test for 100% of defined compatibility rules."""

    def test_rule_signal_requires_signal_geometry(self) -> None:
        """Right-of-way 'signal' cannot be used with roundabout geometry."""
        issues = validate_layer_combination(
            geometry=GeometryConstraint(
                intersection_type="roundabout", circulating_lanes=[1]
            ),
            movement_topology=MovementTopology(topology_type="zone_based_conflicts"),
            right_of_way=RightOfWay(rule="signal"),
            control_policy=ControlPolicy(policy="fixed_time_phase_plan"),
            adaptation_logic=AdaptationLogic(logic="none"),
        )
        assert "compat.signal_requires_signal_geometry" in _codes(issues)
        issue = next(
            i for i in issues if i.code == "compat.signal_requires_signal_geometry"
        )
        assert (
            "Signal right-of-way ('signal') requires 'fixed_time_signal' geometry"
            in issue.message
        )
        assert issue.suggestion is not None
        assert "Use 'fixed_time_signal' geometry" in issue.suggestion
        assert issue.layers == ("geometry", "right_of_way")

    def test_rule_roundabout_yield_requires_roundabout_geom(self) -> None:
        """'yield_to_ring' or 'signal_over_yield' cannot be used with signal geometry."""
        # Case A: yield_to_ring on fixed_time_signal
        issues_a = validate_layer_combination(
            geometry=GeometryConstraint(intersection_type="fixed_time_signal"),
            movement_topology=MovementTopology(topology_type="point_based_conflicts"),
            right_of_way=RightOfWay(rule="yield_to_ring"),
            control_policy=ControlPolicy(policy="uncontrolled"),
            adaptation_logic=AdaptationLogic(logic="none"),
        )
        assert "compat.roundabout_yield_requires_roundabout" in _codes(issues_a)

        # Case B: signal_over_yield on fixed_time_signal
        issues_b = validate_layer_combination(
            geometry=GeometryConstraint(intersection_type="fixed_time_signal"),
            movement_topology=MovementTopology(topology_type="point_based_conflicts"),
            right_of_way=RightOfWay(rule="signal_over_yield"),
            control_policy=ControlPolicy(policy="metering"),
            adaptation_logic=AdaptationLogic(logic="none"),
        )
        assert "compat.roundabout_yield_requires_roundabout" in _codes(issues_b)
        issue = issues_b[0]
        assert "requires 'roundabout' geometry" in issue.message
        assert issue.suggestion is not None
        assert "Use 'roundabout' geometry" in issue.suggestion

    def test_rule_phased_priority_unsupported(self) -> None:
        """Right-of-way 'phased_priority' is rejected (ADR-014 §6, D-SR1)."""
        issues = validate_layer_combination(
            geometry={"intersection_type": "roundabout", "circulating_lanes": [1]},
            movement_topology={"topology_type": "zone_based_conflicts"},
            right_of_way={"rule": "phased_priority"},
            control_policy={"policy": "fixed_time_phase_plan"},
            adaptation_logic={"logic": "none"},
        )
        assert "compat.phased_priority_unsupported" in _codes(issues)
        issue = next(
            i for i in issues if i.code == "compat.phased_priority_unsupported"
        )
        assert "not implemented in V3.0" in issue.message
        assert issue.suggestion is not None
        assert "metered_entry" in issue.suggestion

    def test_rule_signal_requires_point_topology(self) -> None:
        """Signal geometry requires point-based conflict topology."""
        issues = validate_layer_combination(
            geometry=GeometryConstraint(intersection_type="fixed_time_signal"),
            movement_topology=MovementTopology(topology_type="zone_based_conflicts"),
            right_of_way=RightOfWay(rule="signal"),
            control_policy=ControlPolicy(policy="fixed_time_phase_plan"),
            adaptation_logic=AdaptationLogic(logic="none"),
        )
        assert "compat.signal_requires_point_topology" in _codes(issues)
        issue = next(
            i for i in issues if i.code == "compat.signal_requires_point_topology"
        )
        assert (
            "fixed_time_signal requires 'point_based_conflicts' topology"
            in issue.message
        )

    def test_rule_roundabout_requires_zone_topology(self) -> None:
        """Roundabout geometry requires zone-based conflict topology."""
        issues = validate_layer_combination(
            geometry=GeometryConstraint(
                intersection_type="roundabout", circulating_lanes=[1]
            ),
            movement_topology=MovementTopology(topology_type="point_based_conflicts"),
            right_of_way=RightOfWay(rule="yield_to_ring"),
            control_policy=ControlPolicy(policy="uncontrolled"),
            adaptation_logic=AdaptationLogic(logic="none"),
        )
        assert "compat.roundabout_requires_zone_topology" in _codes(issues)
        issue = next(
            i for i in issues if i.code == "compat.roundabout_requires_zone_topology"
        )
        assert "roundabout requires 'zone_based_conflicts' topology" in issue.message

    def test_rule_roundabout_requires_circulating_lanes(self) -> None:
        """Roundabout geometry cannot omit circulating lanes."""
        issues = validate_layer_combination(
            geometry={"intersection_type": "roundabout", "circulating_lanes": None},
            movement_topology={"topology_type": "zone_based_conflicts"},
            right_of_way={"rule": "yield_to_ring"},
            control_policy={"policy": "uncontrolled"},
            adaptation_logic={"logic": "none"},
        )
        assert "compat.roundabout_requires_circulating_lanes" in _codes(issues)

        # Empty circulating lanes also rejected
        issues_empty = validate_layer_combination(
            geometry={"intersection_type": "roundabout", "circulating_lanes": []},
            movement_topology={"topology_type": "zone_based_conflicts"},
            right_of_way={"rule": "yield_to_ring"},
            control_policy={"policy": "uncontrolled"},
            adaptation_logic={"logic": "none"},
        )
        assert "compat.roundabout_requires_circulating_lanes" in _codes(issues_empty)

    def test_rule_signal_forbids_circulating_lanes(self) -> None:
        """Signal geometry cannot define circulating lanes."""
        issues = validate_layer_combination(
            geometry={
                "intersection_type": "fixed_time_signal",
                "circulating_lanes": [1, 2],
            },
            movement_topology={"topology_type": "point_based_conflicts"},
            right_of_way={"rule": "signal"},
            control_policy={"policy": "fixed_time_phase_plan"},
            adaptation_logic={"logic": "none"},
        )
        assert "compat.signal_forbids_circulating_lanes" in _codes(issues)

    def test_rule_arms_range_invalid(self) -> None:
        """min_arms cannot exceed max_arms."""
        issues = validate_layer_combination(
            geometry={
                "intersection_type": "fixed_time_signal",
                "min_arms": 4,
                "max_arms": 3,
            },
            movement_topology={"topology_type": "point_based_conflicts"},
            right_of_way={"rule": "signal"},
            control_policy={"policy": "fixed_time_phase_plan"},
            adaptation_logic={"logic": "none"},
        )
        assert "compat.arms_range_invalid" in _codes(issues)

    def test_rule_signal_row_requires_phase_plan(self) -> None:
        """'signal' right-of-way cannot run uncontrolled or with metering."""
        issues = validate_layer_combination(
            geometry=GeometryConstraint(intersection_type="fixed_time_signal"),
            movement_topology=MovementTopology(topology_type="point_based_conflicts"),
            right_of_way=RightOfWay(rule="signal"),
            control_policy=ControlPolicy(policy="uncontrolled"),
            adaptation_logic=AdaptationLogic(logic="none"),
        )
        assert "compat.signal_row_requires_phase_plan" in _codes(issues)

    def test_rule_yield_to_ring_requires_uncontrolled(self) -> None:
        """'yield_to_ring' right-of-way cannot run with a phase plan or metering."""
        issues = validate_layer_combination(
            geometry=GeometryConstraint(
                intersection_type="roundabout", circulating_lanes=[1]
            ),
            movement_topology=MovementTopology(topology_type="zone_based_conflicts"),
            right_of_way=RightOfWay(rule="yield_to_ring"),
            control_policy=ControlPolicy(policy="fixed_time_phase_plan"),
            adaptation_logic=AdaptationLogic(logic="none"),
        )
        assert "compat.yield_to_ring_requires_uncontrolled" in _codes(issues)

    def test_rule_signal_over_yield_requires_metering(self) -> None:
        """'signal_over_yield' right-of-way requires 'metering' control policy."""
        issues = validate_layer_combination(
            geometry=GeometryConstraint(
                intersection_type="roundabout", circulating_lanes=[1]
            ),
            movement_topology=MovementTopology(topology_type="zone_based_conflicts"),
            right_of_way=RightOfWay(rule="signal_over_yield"),
            control_policy=ControlPolicy(policy="uncontrolled"),
            adaptation_logic=AdaptationLogic(logic="none"),
        )
        assert "compat.signal_over_yield_requires_metering" in _codes(issues)

    def test_rule_adaptive_unsupported_policy(self) -> None:
        """'gap_out_extension' logic is rejected when control policy is uncontrolled."""
        issues = validate_layer_combination(
            geometry=GeometryConstraint(
                intersection_type="roundabout", circulating_lanes=[1]
            ),
            movement_topology=MovementTopology(topology_type="zone_based_conflicts"),
            right_of_way=RightOfWay(rule="yield_to_ring"),
            control_policy=ControlPolicy(policy="uncontrolled"),
            adaptation_logic=AdaptationLogic(logic="gap_out_extension"),
        )
        assert "compat.adaptive_unsupported_policy" in _codes(issues)
        issue = next(
            i for i in issues if i.code == "compat.adaptive_unsupported_policy"
        )
        assert "requires a phase plan or metering policy" in issue.message
        assert issue.suggestion is not None

    def test_rule_uncontrolled_cannot_be_cycle_aware(self) -> None:
        """Uncontrolled policy cannot declare cycle_aware=True."""
        issues = validate_layer_combination(
            geometry=GeometryConstraint(
                intersection_type="roundabout", circulating_lanes=[1]
            ),
            movement_topology=MovementTopology(topology_type="zone_based_conflicts"),
            right_of_way=RightOfWay(rule="yield_to_ring"),
            control_policy=ControlPolicy(policy="uncontrolled", cycle_aware=True),
            adaptation_logic=AdaptationLogic(logic="none"),
        )
        assert "compat.uncontrolled_cannot_be_cycle_aware" in _codes(issues)

    def test_rule_priority_overlay_unsupported(self) -> None:
        """Priority overlay 'emergency_preemption' is rejected as reserved for FS-1."""
        issues = validate_layer_combination(
            geometry=GeometryConstraint(intersection_type="fixed_time_signal"),
            movement_topology=MovementTopology(topology_type="point_based_conflicts"),
            right_of_way=RightOfWay(rule="signal"),
            control_policy=ControlPolicy(policy="fixed_time_phase_plan"),
            adaptation_logic=AdaptationLogic(logic="none"),
            priority_overlay=PriorityOverlay(overlay="emergency_preemption"),
        )
        assert "compat.priority_overlay_unsupported" in _codes(issues)
        issue = next(
            i for i in issues if i.code == "compat.priority_overlay_unsupported"
        )
        assert "reserved for future scope FS-1" in issue.message


class TestValidCombinations:
    """Validate all 4 built-in strategy descriptors and valid layer combinations."""

    def test_all_builtin_strategies_are_valid(self) -> None:
        """All 4 standard built-ins must have zero compatibility issues."""
        for builtin in BUILTIN_STRATEGIES:
            issues = validate_strategy_compatibility(builtin)
            assert issues == [], (
                f"Built-in '{builtin.id}' had compatibility issues: {issues}"
            )
            # check_strategy_compatibility does not raise
            check_strategy_compatibility(builtin)

    def test_fixed_time_signal_combination(self) -> None:
        assert validate_strategy_compatibility(FIXED_TIME_SIGNAL) == []

    def test_adaptive_signal_combination(self) -> None:
        assert validate_strategy_compatibility(ADAPTIVE_SIGNAL) == []

    def test_conventional_roundabout_combination(self) -> None:
        assert validate_strategy_compatibility(CONVENTIONAL_ROUNDABOUT) == []

    def test_metered_entry_roundabout_combination(self) -> None:
        assert validate_strategy_compatibility(METERED_ENTRY_ROUNDABOUT) == []

    def test_custom_valid_signal_combination(self) -> None:
        """Custom valid 3-arm fixed-time signal descriptor."""
        desc = StrategyDescriptor(
            id="custom_t_junction",
            name="Custom 3-arm Signal",
            status="experimental",
            description="A valid 3-arm fixed time signal junction.",
            geometry=GeometryConstraint(
                intersection_type="fixed_time_signal", min_arms=3, max_arms=3
            ),
            movement_topology=MovementTopology(
                topology_type="point_based_conflicts", supports_uturns=False
            ),
            right_of_way=RightOfWay(rule="signal"),
            control_policy=ControlPolicy(
                policy="fixed_time_phase_plan", cycle_aware=True
            ),
            adaptation_logic=AdaptationLogic(logic="none"),
        )
        assert validate_strategy_compatibility(desc) == []
        check_strategy_compatibility(desc)


class TestStrategyCompatibilityErrorHandling:
    """Verifies typed exception structure, error codes, and formatting."""

    def test_strategy_compatibility_error_is_value_error(self) -> None:
        """StrategyCompatibilityError must inherit from ValueError for backward compatibility."""
        assert issubclass(StrategyCompatibilityError, ValueError)

    def test_exception_properties_and_string_representation(self) -> None:
        issue = CompatibilityIssue(
            code="compat.signal_requires_signal_geometry",
            message="Test message",
            layers=("geometry", "right_of_way"),
            suggestion="Test suggestion",
        )
        err = StrategyCompatibilityError([issue], strategy_id="test_strat")
        assert err.strategy_id == "test_strat"
        assert err.code == "compat.signal_requires_signal_geometry"
        assert len(err.issues) == 1
        err_str = str(err)
        assert (
            "Strategy 'test_strat': Test message (compat.signal_requires_signal_geometry)"
            in err_str
        )
        assert "Suggestion: Test suggestion" in err_str

    def test_check_strategy_compatibility_raises(self) -> None:
        desc = StrategyDescriptor(
            id="broken_strat",
            name="Broken Strategy",
            status="experimental",
            description="Contradictory layers for testing.",
            geometry=GeometryConstraint(
                intersection_type="roundabout", circulating_lanes=[1]
            ),
            movement_topology=MovementTopology(topology_type="zone_based_conflicts"),
            right_of_way=RightOfWay(rule="signal"),
            control_policy=ControlPolicy(policy="fixed_time_phase_plan"),
            adaptation_logic=AdaptationLogic(logic="none"),
        )
        with pytest.raises(StrategyCompatibilityError) as exc_info:
            check_strategy_compatibility(desc)
        assert exc_info.value.code == "compat.signal_requires_signal_geometry"
        assert "compat.signal_requires_signal_geometry" in str(exc_info.value)

    def test_all_declared_error_codes_are_registered(self) -> None:
        """All emitted codes must be present in COMPATIBILITY_ERROR_CODES."""
        assert "compat.signal_requires_signal_geometry" in COMPATIBILITY_ERROR_CODES
        assert (
            "compat.roundabout_yield_requires_roundabout" in COMPATIBILITY_ERROR_CODES
        )
        assert "compat.phased_priority_unsupported" in COMPATIBILITY_ERROR_CODES
        assert "compat.adaptive_unsupported_policy" in COMPATIBILITY_ERROR_CODES
        assert len(COMPATIBILITY_ERROR_CODES) >= 14


class TestLegacyAdaptiveReplacementAndPreSimulationGuard:
    """Verifies replacement of legacy error and pre-simulation initialization protection."""

    def test_scenario_validation_replaces_legacy_adaptive_error(self) -> None:
        """Scenario config with roundabout + adaptive emits compat.adaptive_unsupported_policy."""
        bad_config: Dict[str, Any] = {
            "geometry": {"intersectionType": "roundabout"},
            "controller": {"signalControl": "adaptive"},
        }
        issues = validate_scenario_strategy_compatibility(bad_config)
        assert "compat.adaptive_unsupported_policy" in _codes(issues)

        # semantic_config_errors should now contain the machine-readable compat code
        errors = semantic_config_errors(bad_config)
        assert any("compat.adaptive_unsupported_policy" in err for err in errors)
        assert any("requires a signalised junction" in err for err in errors)

    def test_scenario_validation_accepts_valid_scenarios(self) -> None:
        """Valid scenario configurations have no compatibility issues."""
        valid_fts: Dict[str, Any] = {
            "geometry": {"intersectionType": "fixed_time_signal"},
            "controller": {"signalControl": "fixed_time"},
        }
        assert validate_scenario_strategy_compatibility(valid_fts) == []
        check_scenario_strategy_compatibility(valid_fts)

        valid_adaptive: Dict[str, Any] = {
            "geometry": {"intersectionType": "fixed_time_signal"},
            "controller": {"signalControl": "adaptive"},
        }
        assert validate_scenario_strategy_compatibility(valid_adaptive) == []
        check_scenario_strategy_compatibility(valid_adaptive)

        valid_rb: Dict[str, Any] = {
            "geometry": {"intersectionType": "roundabout"},
            "controller": {},
        }
        assert validate_scenario_strategy_compatibility(valid_rb) == []
        check_scenario_strategy_compatibility(valid_rb)

        valid_metered_rb: Dict[str, Any] = {
            "geometry": {"intersectionType": "roundabout"},
            "controller": {"entryControl": "metered_entry"},
        }
        assert validate_scenario_strategy_compatibility(valid_metered_rb) == []
        check_scenario_strategy_compatibility(valid_metered_rb)

    def test_register_simulation_rejects_incompatible_strategy_before_initialization(
        self,
    ) -> None:
        """register_simulation aborts before engine initialization on incompatible strategy combinations."""
        incompatible_config: Dict[str, Any] = {
            "simulation": {"duration": 60, "timeStep": 0.1},
            "geometry": {"intersectionType": "roundabout"},
            "controller": {"signalControl": "adaptive"},
        }
        with pytest.raises(InvalidSimulationConfigError) as exc_info:
            register_simulation(incompatible_config)

        assert "compat.adaptive_unsupported_policy" in str(exc_info.value)
