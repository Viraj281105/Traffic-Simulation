"""Unit tests for StrategyDescriptor model and 6-layer architecture (ADR-014)."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.strategies.builtins import (
    BUILTIN_STRATEGIES,
    FIXED_TIME_SIGNAL,
)
from src.strategies.models import (
    STRATEGY_FORMAT,
    STRATEGY_VERSION,
    AdaptationLogic,
    ControlPolicy,
    GeometryConstraint,
    MovementTopology,
    RightOfWay,
    StrategyDescriptor,
)


class TestStrategyDescriptorModel:
    def test_builtins_are_valid_and_self_consistent(self) -> None:
        """All 4 built-in strategies must validate without error."""
        for desc in BUILTIN_STRATEGIES:
            assert desc.format == STRATEGY_FORMAT
            assert desc.version == STRATEGY_VERSION
            assert desc.fingerprint is not None
            assert len(desc.fingerprint) == 16
            assert desc.fingerprint == desc.compute_fingerprint()
            desc.validate_self()

    def test_extra_fields_forbidden_on_descriptor(self) -> None:
        """Unknown root fields must be strictly rejected (extra='forbid')."""
        valid_dump = FIXED_TIME_SIGNAL.model_dump(mode="json")
        valid_dump["unauthorized_field"] = "malicious_payload"
        with pytest.raises(ValidationError):
            StrategyDescriptor.model_validate(valid_dump)

    def test_extra_fields_forbidden_on_layers(self) -> None:
        """Unknown fields inside layer models must be rejected."""
        with pytest.raises(ValidationError):
            GeometryConstraint(
                intersection_type="fixed_time_signal",
                min_arms=3,
                max_arms=4,
                unknown_layer_prop=123,  # type: ignore[call-arg]
            )

    def test_deterministic_fingerprint(self) -> None:
        """Fingerprint must be stable, 16 hex chars, and sensitive to edits."""
        fp1 = FIXED_TIME_SIGNAL.compute_fingerprint()
        fp2 = FIXED_TIME_SIGNAL.compute_fingerprint()
        assert fp1 == fp2
        assert len(fp1) == 16
        assert all(c in "0123456789abcdef" for c in fp1)

        # Mutating a parameter bound changes the fingerprint
        modified = FIXED_TIME_SIGNAL.model_copy(deep=True)
        modified.parameters["cycle_time"].max_value = 240.0
        assert modified.compute_fingerprint() != fp1

    def test_fingerprint_mismatch_validation(self) -> None:
        """validate_self must raise ValueError if declared fingerprint does not match computed."""
        tampered = FIXED_TIME_SIGNAL.model_copy(
            update={"fingerprint": "0123456789abcdef"}
        )
        with pytest.raises(ValueError, match="fingerprint mismatch"):
            tampered.validate_self()

    def test_reject_fixed_time_with_invalid_right_of_way(self) -> None:
        """fixed_time_signal with yield_to_ring rule must be rejected."""
        desc = StrategyDescriptor(
            id="invalid_fts",
            name="Invalid FTS",
            status="stable",
            description="Testing invalid right of way rule.",
            geometry=GeometryConstraint(intersection_type="fixed_time_signal"),
            movement_topology=MovementTopology(topology_type="point_based_conflicts"),
            right_of_way=RightOfWay(rule="yield_to_ring"),
            control_policy=ControlPolicy(policy="fixed_time_phase_plan"),
            adaptation_logic=AdaptationLogic(logic="none"),
        )
        with pytest.raises(ValueError, match="requires 'signal' right-of-way"):
            desc.validate_self()

    def test_reject_fixed_time_with_circulating_lanes(self) -> None:
        """fixed_time_signal cannot have circulating lanes specified."""
        desc = StrategyDescriptor(
            id="invalid_fts_lanes",
            name="Invalid FTS Lanes",
            status="stable",
            description="Testing invalid circulating lanes on signal.",
            geometry=GeometryConstraint(
                intersection_type="fixed_time_signal", circulating_lanes=[1, 2]
            ),
            movement_topology=MovementTopology(topology_type="point_based_conflicts"),
            right_of_way=RightOfWay(rule="signal"),
            control_policy=ControlPolicy(policy="fixed_time_phase_plan"),
            adaptation_logic=AdaptationLogic(logic="none"),
        )
        with pytest.raises(ValueError, match="cannot have circulating_lanes specified"):
            desc.validate_self()

    def test_reject_roundabout_with_signal_right_of_way(self) -> None:
        """roundabout geometry cannot have pure 'signal' right of way."""
        desc = StrategyDescriptor(
            id="invalid_rb_signal",
            name="Invalid Roundabout Signal",
            status="stable",
            description="Testing invalid right of way for roundabout.",
            geometry=GeometryConstraint(
                intersection_type="roundabout", circulating_lanes=[1]
            ),
            movement_topology=MovementTopology(topology_type="zone_based_conflicts"),
            right_of_way=RightOfWay(rule="signal"),
            control_policy=ControlPolicy(policy="fixed_time_phase_plan"),
            adaptation_logic=AdaptationLogic(logic="none"),
        )
        with pytest.raises(
            ValueError,
            match="roundabout geometry requires 'yield_to_ring' or 'signal_over_yield'",
        ):
            desc.validate_self()

    def test_reject_roundabout_without_circulating_lanes(self) -> None:
        """roundabout requires circulating_lanes definition."""
        desc = StrategyDescriptor(
            id="invalid_rb_no_lanes",
            name="Invalid Roundabout No Lanes",
            status="stable",
            description="Testing missing circulating lanes.",
            geometry=GeometryConstraint(
                intersection_type="roundabout", circulating_lanes=None
            ),
            movement_topology=MovementTopology(topology_type="zone_based_conflicts"),
            right_of_way=RightOfWay(rule="yield_to_ring"),
            control_policy=ControlPolicy(policy="uncontrolled"),
            adaptation_logic=AdaptationLogic(logic="none"),
        )
        with pytest.raises(
            ValueError,
            match="roundabout geometry requires circulating_lanes definition",
        ):
            desc.validate_self()

    def test_reject_signal_over_yield_without_metering_policy(self) -> None:
        """signal_over_yield rule requires metering policy."""
        desc = StrategyDescriptor(
            id="invalid_metering",
            name="Invalid Metering",
            status="stable",
            description="Testing signal over yield without metering.",
            geometry=GeometryConstraint(
                intersection_type="roundabout", circulating_lanes=[1, 2]
            ),
            movement_topology=MovementTopology(topology_type="zone_based_conflicts"),
            right_of_way=RightOfWay(rule="signal_over_yield"),
            control_policy=ControlPolicy(policy="uncontrolled"),
            adaptation_logic=AdaptationLogic(logic="none"),
        )
        with pytest.raises(
            ValueError, match="'signal_over_yield' rule requires 'metering' policy"
        ):
            desc.validate_self()

    def test_reject_gap_out_on_uncontrolled(self) -> None:
        """gap_out_extension cannot apply to uncontrolled policy."""
        desc = StrategyDescriptor(
            id="invalid_adaptation",
            name="Invalid Adaptation",
            status="stable",
            description="Testing gap out on uncontrolled policy.",
            geometry=GeometryConstraint(
                intersection_type="roundabout", circulating_lanes=[1, 2]
            ),
            movement_topology=MovementTopology(topology_type="zone_based_conflicts"),
            right_of_way=RightOfWay(rule="yield_to_ring"),
            control_policy=ControlPolicy(policy="uncontrolled"),
            adaptation_logic=AdaptationLogic(logic="gap_out_extension"),
        )
        with pytest.raises(
            ValueError,
            match="'gap_out_extension' logic requires a phase plan or metering policy",
        ):
            desc.validate_self()

    def test_schema_file_matches_model(self) -> None:
        """shared/schemas/v3/strategy-descriptor.schema.json must match model schema."""
        schema_path = (
            Path(__file__).resolve().parents[3]
            / "shared"
            / "schemas"
            / "v3"
            / "strategy-descriptor.schema.json"
        )
        assert schema_path.is_file(), f"Schema file not found at {schema_path}"
        saved_schema = json.loads(schema_path.read_text(encoding="utf-8"))

        generated = StrategyDescriptor.model_json_schema()
        generated["$schema"] = "http://json-schema.org/draft-07/schema#"
        generated["title"] = "StrategyDescriptor"
        generated["description"] = (
            "Layered strategy descriptor (urbanflow-strategy v1) -- V3.0 W3 (ADR-014)"
        )

        assert saved_schema == generated
