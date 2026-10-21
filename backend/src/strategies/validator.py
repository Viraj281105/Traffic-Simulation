"""Strategy compatibility validator (``urbanflow-strategy`` v1) -- V3.0 W3 (ADR-014 §2).

Provides a pure, deterministic validation engine that evaluates compatibility
across the 6 architectural strategy layers before simulation initialization:
1. Geometry constraint
2. Movement topology
3. Right-of-way rule
4. Control policy
5. Adaptation logic
6. Priority overlay (reserved for Future Scope FS-1)

Security and Contract Properties:
- Pure and deterministic: no side effects, no randomness, no I/O.
- Rejection codes: every rule produces a stable, machine-readable code (e.g.
  ``compat.signal_requires_signal_geometry``) and explanatory message with suggestions.
- Pre-simulation guard: blocks contradictory or unsupported combinations before
  any engine or controller object is constructed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, FrozenSet, List, Optional, Sequence, Tuple

if TYPE_CHECKING:
    from src.strategies.models import StrategyDescriptor

# --- Machine-readable Diagnostic Codes ---
COMPATIBILITY_ERROR_CODES: FrozenSet[str] = frozenset(
    {
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
    }
)


@dataclass(frozen=True)
class CompatibilityIssue:
    """A typed diagnostic issue emitted by the strategy compatibility validator."""

    code: str
    message: str
    layers: Tuple[str, ...]
    suggestion: Optional[str] = None

    def formatted_message(self) -> str:
        """Format human-readable message with code and optional suggestion."""
        res = f"{self.message} ({self.code})"
        if self.suggestion:
            res += f" Suggestion: {self.suggestion}"
        return res

    def __str__(self) -> str:
        return self.formatted_message()


class StrategyCompatibilityError(ValueError):
    """Raised when a strategy descriptor or layer combination fails compatibility validation."""

    def __init__(
        self,
        issues: Sequence[CompatibilityIssue],
        strategy_id: Optional[str] = None,
    ) -> None:
        self.issues = list(issues)
        self.strategy_id = strategy_id
        self.code = self.issues[0].code if self.issues else "compat.unknown"
        prefix = f"Strategy '{strategy_id}': " if strategy_id else "Strategy compatibility violation: "
        detail = "; ".join(issue.formatted_message() for issue in self.issues)
        super().__init__(f"{prefix}{detail}")


def _get_val(obj: Any, key: str, default: Any = None) -> Any:
    """Extract an attribute or dictionary item cleanly."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def validate_layer_combination(
    geometry: Any,
    movement_topology: Any,
    right_of_way: Any,
    control_policy: Any,
    adaptation_logic: Any,
    priority_overlay: Any = None,
) -> List[CompatibilityIssue]:
    """Evaluate compatibility across raw layer components or dicts.

    Pure, deterministic validator checking all defined compatibility rules.
    Returns a list of CompatibilityIssue diagnostics (empty if valid).
    """
    issues: List[CompatibilityIssue] = []

    # Extract layer attributes
    geom_type = _get_val(geometry, "intersection_type")
    circulating_lanes = _get_val(geometry, "circulating_lanes")
    min_arms = _get_val(geometry, "min_arms")
    max_arms = _get_val(geometry, "max_arms")

    topo_type = _get_val(movement_topology, "topology_type")

    row_rule = _get_val(right_of_way, "rule")

    policy = _get_val(control_policy, "policy")
    cycle_aware = _get_val(control_policy, "cycle_aware", False)

    adapt_logic = _get_val(adaptation_logic, "logic", "none")

    overlay = _get_val(priority_overlay, "overlay", "none")

    # --- Rule: Geometry Arm Range Sanity ---
    if (
        isinstance(min_arms, int)
        and isinstance(max_arms, int)
        and min_arms > max_arms
    ):
        issues.append(
            CompatibilityIssue(
                code="compat.arms_range_invalid",
                message=f"min_arms ({min_arms}) cannot be greater than max_arms ({max_arms})",
                layers=("geometry",),
                suggestion=f"Set min_arms <= max_arms (currently {min_arms} > {max_arms}).",
            )
        )

    # --- Rule: Phased Priority Mode (ADR-014 §6, D-SR1) ---
    if row_rule == "phased_priority":
        issues.append(
            CompatibilityIssue(
                code="compat.phased_priority_unsupported",
                message=(
                    "Right-of-way rule 'phased_priority' is not implemented in V3.0 (ADR-014 §6, D-SR1)"
                ),
                layers=("right_of_way",),
                suggestion="Use 'signal_over_yield' (metered_entry) mode with entry metering instead.",
            )
        )

    # --- Rule: Signal vs Roundabout Right-of-Way and Geometry ---
    if row_rule == "signal":
        if geom_type != "fixed_time_signal":
            issues.append(
                CompatibilityIssue(
                    code="compat.signal_requires_signal_geometry",
                    message=(
                        f"Signal right-of-way ('signal') requires 'fixed_time_signal' geometry; "
                        f"roundabout geometry requires 'yield_to_ring' or 'signal_over_yield', got '{row_rule}'"
                    ),
                    layers=("geometry", "right_of_way"),
                    suggestion="Use 'fixed_time_signal' geometry, or change right-of-way to 'yield_to_ring' or 'signal_over_yield'.",
                )
            )
    elif row_rule in ("yield_to_ring", "signal_over_yield"):
        if geom_type != "roundabout":
            issues.append(
                CompatibilityIssue(
                    code="compat.roundabout_yield_requires_roundabout",
                    message=(
                        f"Right-of-way rule '{row_rule}' requires 'roundabout' geometry; "
                        f"fixed_time_signal geometry requires 'signal' right-of-way, got '{row_rule}'"
                    ),
                    layers=("geometry", "right_of_way"),
                    suggestion="Use 'roundabout' geometry, or change right-of-way rule to 'signal'.",
                )
            )

    # --- Rule: Geometry vs Movement Topology ---
    if geom_type == "fixed_time_signal":
        if topo_type != "point_based_conflicts":
            issues.append(
                CompatibilityIssue(
                    code="compat.signal_requires_point_topology",
                    message=(
                        f"fixed_time_signal requires 'point_based_conflicts' topology, got '{topo_type}'"
                    ),
                    layers=("geometry", "movement_topology"),
                    suggestion="Set movement_topology.topology_type to 'point_based_conflicts'.",
                )
            )
        if circulating_lanes is not None:
            issues.append(
                CompatibilityIssue(
                    code="compat.signal_forbids_circulating_lanes",
                    message="fixed_time_signal cannot have circulating_lanes specified",
                    layers=("geometry",),
                    suggestion="Set geometry.circulating_lanes to None.",
                )
            )
    elif geom_type == "roundabout":
        if topo_type != "zone_based_conflicts":
            issues.append(
                CompatibilityIssue(
                    code="compat.roundabout_requires_zone_topology",
                    message=(
                        f"roundabout requires 'zone_based_conflicts' topology, got '{topo_type}'"
                    ),
                    layers=("geometry", "movement_topology"),
                    suggestion="Set movement_topology.topology_type to 'zone_based_conflicts'.",
                )
            )
        if not circulating_lanes:
            issues.append(
                CompatibilityIssue(
                    code="compat.roundabout_requires_circulating_lanes",
                    message="roundabout geometry requires circulating_lanes definition",
                    layers=("geometry",),
                    suggestion="Specify circulating_lanes (e.g. [1] or [1, 2]).",
                )
            )

    # --- Rule: Right-of-Way vs Control Policy ---
    if row_rule == "signal":
        if policy != "fixed_time_phase_plan":
            issues.append(
                CompatibilityIssue(
                    code="compat.signal_row_requires_phase_plan",
                    message=(
                        f"'signal' rule requires 'fixed_time_phase_plan' policy, got '{policy}'"
                    ),
                    layers=("right_of_way", "control_policy"),
                    suggestion="Set control_policy.policy to 'fixed_time_phase_plan'.",
                )
            )
    elif row_rule == "yield_to_ring":
        if policy != "uncontrolled":
            issues.append(
                CompatibilityIssue(
                    code="compat.yield_to_ring_requires_uncontrolled",
                    message=(
                        f"'yield_to_ring' rule requires 'uncontrolled' policy, got '{policy}'"
                    ),
                    layers=("right_of_way", "control_policy"),
                    suggestion="Set control_policy.policy to 'uncontrolled', or use 'signal_over_yield' for metered roundabouts.",
                )
            )
    elif row_rule == "signal_over_yield":
        if policy != "metering":
            issues.append(
                CompatibilityIssue(
                    code="compat.signal_over_yield_requires_metering",
                    message=(
                        f"'signal_over_yield' rule requires 'metering' policy, got '{policy}'"
                    ),
                    layers=("right_of_way", "control_policy"),
                    suggestion="Set control_policy.policy to 'metering'.",
                )
            )

    # --- Rule: Adaptation Logic vs Control Policy ---
    if adapt_logic == "gap_out_extension":
        if policy not in ("fixed_time_phase_plan", "metering"):
            issues.append(
                CompatibilityIssue(
                    code="compat.adaptive_unsupported_policy",
                    message=(
                        f"'gap_out_extension' logic requires a phase plan or metering policy, got '{policy}'"
                    ),
                    layers=("control_policy", "adaptation_logic"),
                    suggestion="Set control_policy.policy to 'fixed_time_phase_plan' or 'metering', or set adaptation_logic.logic to 'none'.",
                )
            )

    # --- Rule: Uncontrolled Policy cannot be Cycle Aware ---
    if policy == "uncontrolled" and cycle_aware:
        issues.append(
            CompatibilityIssue(
                code="compat.uncontrolled_cannot_be_cycle_aware",
                message="Uncontrolled policy cannot be cycle-aware",
                layers=("control_policy",),
                suggestion="Set control_policy.cycle_aware to False.",
            )
        )

    # --- Rule: Priority Overlay Reserved / Unsupported in V3.0 (ADR-014 §1) ---
    if overlay != "none":
        issues.append(
            CompatibilityIssue(
                code="compat.priority_overlay_unsupported",
                message=(
                    f"Priority overlay '{overlay}' is reserved for future scope FS-1 and not implemented in V3.0"
                ),
                layers=("priority_overlay",),
                suggestion="Set priority_overlay.overlay to 'none'.",
            )
        )

    return issues


def validate_strategy_compatibility(
    descriptor: StrategyDescriptor,
) -> List[CompatibilityIssue]:
    """Pure, deterministic compatibility validator for a StrategyDescriptor."""
    return validate_layer_combination(
        geometry=descriptor.geometry,
        movement_topology=descriptor.movement_topology,
        right_of_way=descriptor.right_of_way,
        control_policy=descriptor.control_policy,
        adaptation_logic=descriptor.adaptation_logic,
        priority_overlay=descriptor.priority_overlay,
    )


def check_strategy_compatibility(descriptor: StrategyDescriptor) -> None:
    """Validate StrategyDescriptor compatibility; raise StrategyCompatibilityError if invalid."""
    issues = validate_strategy_compatibility(descriptor)
    if issues:
        raise StrategyCompatibilityError(issues, strategy_id=descriptor.id)


def validate_scenario_strategy_compatibility(
    config: Dict[str, Any],
) -> List[CompatibilityIssue]:
    """Check strategy compatibility for a scenario configuration before simulation construction.

    Translates scenario configuration fields (geometry.intersectionType, controller.signalControl,
    controller.entryControl) into effective strategy descriptor layers and evaluates them.
    Formally supersedes the legacy error 'adaptive applies to a signalised junction'.
    """
    geom = config.get("geometry")
    geom_type = geom.get("intersectionType", "fixed_time_signal") if isinstance(geom, dict) else "fixed_time_signal"

    ctrl = config.get("controller")
    ctrl_dict = ctrl if isinstance(ctrl, dict) else {}
    signal_control = ctrl_dict.get("signalControl", "fixed_time")
    entry_control = ctrl_dict.get("entryControl")

    # Map scenario configuration to architectural layers
    if geom_type == "roundabout":
        if entry_control == "metered_entry":
            row_rule = "signal_over_yield"
            policy = "metering"
        else:
            row_rule = "yield_to_ring"
            policy = "uncontrolled"

        topo_type = "zone_based_conflicts"
        circulating_lanes = [1, 2]  # Default / present in roundabout geometry
    else:
        row_rule = "signal"
        policy = "fixed_time_phase_plan"
        topo_type = "point_based_conflicts"
        circulating_lanes = None

    adapt_logic = "gap_out_extension" if signal_control == "adaptive" else "none"

    return validate_layer_combination(
        geometry={
            "intersection_type": geom_type,
            "min_arms": 3,
            "max_arms": 4,
            "circulating_lanes": circulating_lanes,
        },
        movement_topology={"topology_type": topo_type, "supports_uturns": True},
        right_of_way={"rule": row_rule},
        control_policy={"policy": policy, "cycle_aware": (policy == "fixed_time_phase_plan")},
        adaptation_logic={"logic": adapt_logic, "deterministic": True},
        priority_overlay={"overlay": "none"},
    )


def check_scenario_strategy_compatibility(config: Dict[str, Any]) -> None:
    """Validate scenario strategy compatibility; raise StrategyCompatibilityError if invalid."""
    issues = validate_scenario_strategy_compatibility(config)
    if issues:
        raise StrategyCompatibilityError(issues)
