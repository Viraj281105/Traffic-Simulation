"""Layered strategy descriptor (``urbanflow-strategy`` v1) -- V3.0 W3 (ADR-014).

A strategy is a declarative composition of six layers:
1. Geometry constraint (arms, circulating lanes, approach lanes)
2. Movement topology (conflict points, zone-based conflicts, turn support)
3. Right-of-way rule (signal, yield_to_ring, signal_over_yield)
4. Control policy (fixed_time_phase_plan, metering, uncontrolled)
5. Adaptation logic (none, gap_out_extension)
6. Priority overlay (none; reserved for Future Scope FS-1 emergency/bus)

All models are strict Pydantic models (``extra="forbid"``). Each descriptor records
its format, integer version, unique id, display name, release status ('stable' | 'experimental'),
user-facing description, unmodelled limitations, parameter bounds, invariants, and a 16-hex fingerprint.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

STRATEGY_FORMAT: Literal["urbanflow-strategy"] = "urbanflow-strategy"
STRATEGY_VERSION: Literal[1] = 1

# Most ring lanes the engine models (roads/lane_config.py MAX_CIRCULATING_LANES;
# strategies/ is a leaf package, so the value is mirrored and a test pins it).
MAX_CIRCULATING_LANES: int = 2


def canonical_json(value: Any) -> str:
    """Return compact, sorted JSON string for stable fingerprinting."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- Layer 1: Geometry Constraint ---
class GeometryConstraint(_Strict):
    intersection_type: Literal["fixed_time_signal", "roundabout"]
    min_arms: int = Field(default=3, ge=3, le=4)
    max_arms: int = Field(default=4, ge=3, le=4)
    circulating_lanes: Optional[List[int]] = None

    @field_validator("circulating_lanes")
    @classmethod
    def _validate_circulating_lanes(
        cls, lanes: Optional[List[int]]
    ) -> Optional[List[int]]:
        """Supported ring lane counts: unique integers in 1..MAX_CIRCULATING_LANES.

        An empty list is left to the ``compat.roundabout_requires_circulating_lanes``
        rule so it surfaces as a coded diagnostic.
        """
        if lanes is None:
            return lanes
        for count in lanes:
            if not 1 <= count <= MAX_CIRCULATING_LANES:
                raise ValueError(
                    f"circulating_lanes entry {count} must be between 1 and "
                    f"{MAX_CIRCULATING_LANES}"
                )
        if len(set(lanes)) != len(lanes):
            raise ValueError(f"circulating_lanes {lanes} contains duplicates")
        return lanes

    @model_validator(mode="after")
    def _validate_arms_range(self) -> GeometryConstraint:
        if self.min_arms > self.max_arms:
            raise ValueError(
                f"min_arms ({self.min_arms}) cannot be greater than max_arms ({self.max_arms})"
            )
        return self


# --- Layer 2: Movement Topology ---
class MovementTopology(_Strict):
    topology_type: Literal["point_based_conflicts", "zone_based_conflicts"]
    supports_uturns: bool = True


# --- Layer 3: Right-of-Way Rule ---
class RightOfWay(_Strict):
    rule: Literal["signal", "yield_to_ring", "signal_over_yield"]


# --- Layer 4: Control Policy ---
class ControlPolicy(_Strict):
    policy: Literal["fixed_time_phase_plan", "metering", "uncontrolled"]
    cycle_aware: bool = False


# --- Layer 5: Adaptation Logic ---
class AdaptationLogic(_Strict):
    logic: Literal["none", "gap_out_extension"] = "none"
    deterministic: bool = True


# --- Layer 6: Priority Overlay (Reserved for FS-1) ---
class PriorityOverlay(_Strict):
    overlay: Literal["none", "emergency_preemption"] = "none"


# --- Parameter Bounds Specification ---
class ParameterBound(_Strict):
    min_value: float
    max_value: float
    default_value: Optional[float] = None
    unit: str
    description: str

    @model_validator(mode="after")
    def _validate_bounds(self) -> ParameterBound:
        if self.min_value > self.max_value:
            raise ValueError(
                f"min_value ({self.min_value}) cannot exceed max_value ({self.max_value})"
            )
        if self.default_value is not None:
            if not (self.min_value <= self.default_value <= self.max_value):
                raise ValueError(
                    f"default_value ({self.default_value}) must be within [{self.min_value}, {self.max_value}]"
                )
        return self


# --- Complete Strategy Descriptor ---
class StrategyDescriptor(_Strict):
    format: Literal["urbanflow-strategy"] = STRATEGY_FORMAT
    version: int = STRATEGY_VERSION
    id: str = Field(min_length=1, pattern=r"^[a-z0-9_]+$")
    name: str = Field(min_length=1)
    status: Literal["stable", "experimental"] = "stable"
    description: str = Field(min_length=10)
    not_modelled: List[str] = Field(default_factory=list)

    # The 6 architectural layers (ADR-014)
    geometry: GeometryConstraint
    movement_topology: MovementTopology
    right_of_way: RightOfWay
    control_policy: ControlPolicy
    adaptation_logic: AdaptationLogic
    priority_overlay: PriorityOverlay = Field(default_factory=PriorityOverlay)

    parameters: Dict[str, ParameterBound] = Field(default_factory=dict)
    invariants: List[str] = Field(default_factory=list)
    fingerprint: Optional[str] = None

    def compute_fingerprint(self) -> str:
        """Calculate deterministic 16-hex SHA-256 fingerprint of the descriptor."""
        payload = self.model_dump(mode="json", exclude={"fingerprint"})
        return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()[:16]

    def with_computed_fingerprint(self) -> StrategyDescriptor:
        """Return a copy with computed fingerprint populated if absent or mismatched."""
        expected = self.compute_fingerprint()
        if self.fingerprint == expected:
            return self
        dump = self.model_dump(mode="json", exclude={"fingerprint"})
        dump["fingerprint"] = expected
        return StrategyDescriptor.model_validate(dump)

    def validate_self(self) -> None:
        """Assert internal layer consistency and validity via compatibility validator."""
        from src.strategies.validator import check_strategy_compatibility

        # 1. Compatibility rules across the 6 layers (ADR-014 §2)
        check_strategy_compatibility(self)

        # 2. Fingerprint consistency if set
        if self.fingerprint is not None:
            expected = self.compute_fingerprint()
            if self.fingerprint != expected:
                raise ValueError(
                    f"Strategy '{self.id}': fingerprint mismatch (declared '{self.fingerprint}' != computed '{expected}')."
                )
