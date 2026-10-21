"""Built-in strategy descriptors (``urbanflow-strategy`` v1) -- V3.0 W3 (ADR-014).

Defines the four core built-in strategies:
1. ``fixed_time_signal``: Classic cyclic fixed-duration signalized intersection.
2. ``adaptive_signal``: Traffic-actuated gap-out signalized intersection.
3. ``conventional_roundabout``: Offside-priority yield-at-entry circular intersection.
4. ``metered_entry_roundabout``: Hybrid roundabout with entry metering signals.

Each descriptor is frozen with its computed 16-hex deterministic fingerprint.
"""

from __future__ import annotations

from typing import Dict, List

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

FIXED_TIME_SIGNAL = StrategyDescriptor(
    id="fixed_time_signal",
    name="Fixed-Time Signal",
    status="stable",
    description=(
        "Cyclic fixed-duration signal control across orthogonal or multi-leg approaches "
        "with conflict points managed by dedicated green phases."
    ),
    not_modelled=[
        "Actuated / demand-responsive extensions",
        "Coordination with upstream junctions",
        "Pedestrian call buttons",
    ],
    geometry=GeometryConstraint(
        intersection_type="fixed_time_signal",
        min_arms=3,
        max_arms=4,
        circulating_lanes=None,
    ),
    movement_topology=MovementTopology(
        topology_type="point_based_conflicts",
        supports_uturns=True,
    ),
    right_of_way=RightOfWay(rule="signal"),
    control_policy=ControlPolicy(
        policy="fixed_time_phase_plan",
        cycle_aware=True,
    ),
    adaptation_logic=AdaptationLogic(
        logic="none",
        deterministic=True,
    ),
    priority_overlay=PriorityOverlay(overlay="none"),
    parameters={
        "cycle_time": ParameterBound(
            min_value=30.0,
            max_value=180.0,
            default_value=60.0,
            unit="s",
            description="Total signal cycle duration across all phases.",
        ),
        "green_time": ParameterBound(
            min_value=5.0,
            max_value=120.0,
            default_value=25.0,
            unit="s",
            description="Green interval duration for vehicular phase.",
        ),
        "yellow_time": ParameterBound(
            min_value=3.0,
            max_value=6.0,
            default_value=3.0,
            unit="s",
            description="Yellow change interval duration.",
        ),
        "all_red_time": ParameterBound(
            min_value=1.0,
            max_value=5.0,
            default_value=2.0,
            unit="s",
            description="All-red intersection clearance interval.",
        ),
    },
    invariants=[
        "sum(green + yellow + all_red) == cycle_length",
        "green_time >= min_green",
    ],
).with_computed_fingerprint()


ADAPTIVE_SIGNAL = StrategyDescriptor(
    id="adaptive_signal",
    name="Adaptive (Actuated) Signal",
    status="stable",
    description=(
        "Traffic-actuated signal control extending green phases based on vehicle detection "
        "and gap-out thresholds within bounded cycle limits."
    ),
    not_modelled=[
        "Queue spillback detection across junctions",
        "Dynamic phase reordering",
        "Emergency preemption",
    ],
    geometry=GeometryConstraint(
        intersection_type="fixed_time_signal",
        min_arms=3,
        max_arms=4,
        circulating_lanes=None,
    ),
    movement_topology=MovementTopology(
        topology_type="point_based_conflicts",
        supports_uturns=True,
    ),
    right_of_way=RightOfWay(rule="signal"),
    control_policy=ControlPolicy(
        policy="fixed_time_phase_plan",
        cycle_aware=True,
    ),
    adaptation_logic=AdaptationLogic(
        logic="gap_out_extension",
        deterministic=True,
    ),
    priority_overlay=PriorityOverlay(overlay="none"),
    parameters={
        "min_green": ParameterBound(
            min_value=5.0,
            max_value=30.0,
            default_value=10.0,
            unit="s",
            description="Minimum green interval duration before gap-out allowed.",
        ),
        "max_green": ParameterBound(
            min_value=20.0,
            max_value=120.0,
            default_value=60.0,
            unit="s",
            description="Maximum green interval duration before forced termination.",
        ),
        "passage_gap": ParameterBound(
            min_value=1.5,
            max_value=5.0,
            default_value=3.0,
            unit="s",
            description="Vehicle headway threshold terminating phase extension.",
        ),
        "extension_step": ParameterBound(
            min_value=0.5,
            max_value=3.0,
            default_value=1.0,
            unit="s",
            description="Incremental green extension time per detected vehicle arrival.",
        ),
        "yellow_time": ParameterBound(
            min_value=3.0,
            max_value=6.0,
            default_value=3.0,
            unit="s",
            description="Yellow change interval duration.",
        ),
        "all_red_time": ParameterBound(
            min_value=1.0,
            max_value=5.0,
            default_value=2.0,
            unit="s",
            description="All-red intersection clearance interval.",
        ),
    },
    invariants=[
        "min_green <= current_green <= max_green",
        "green extensions stop on gap_out or max_green reach",
    ],
).with_computed_fingerprint()


CONVENTIONAL_ROUNDABOUT = StrategyDescriptor(
    id="conventional_roundabout",
    name="Conventional Roundabout",
    status="stable",
    description=(
        "Self-governing circular junction operating on yield-at-entry (offside priority) "
        "without signal control, with continuous circulating flow."
    ),
    not_modelled=[
        "Lane changes within circulating ring",
        "Pedestrian crosswalks on splitter islands",
        "Spiral lane markings",
    ],
    geometry=GeometryConstraint(
        intersection_type="roundabout",
        min_arms=3,
        max_arms=4,
        circulating_lanes=[1, 2],
    ),
    movement_topology=MovementTopology(
        topology_type="zone_based_conflicts",
        supports_uturns=True,
    ),
    right_of_way=RightOfWay(rule="yield_to_ring"),
    control_policy=ControlPolicy(
        policy="uncontrolled",
        cycle_aware=False,
    ),
    adaptation_logic=AdaptationLogic(
        logic="none",
        deterministic=True,
    ),
    priority_overlay=PriorityOverlay(overlay="none"),
    parameters={
        "critical_headway": ParameterBound(
            min_value=2.5,
            max_value=6.0,
            default_value=4.1,
            unit="s",
            description="Minimum accepted time gap in circulating flow for entry.",
        ),
        "follow_up_headway": ParameterBound(
            min_value=1.5,
            max_value=4.0,
            default_value=2.6,
            unit="s",
            description="Time headway between queued vehicles entering into same gap.",
        ),
        "circulating_radius": ParameterBound(
            min_value=10.0,
            max_value=50.0,
            default_value=20.0,
            unit="m",
            description="Inner circulating carriageway radius.",
        ),
    },
    invariants=[
        "circulating vehicles maintain absolute priority over entry vehicles",
        "keep-clear zones prevent gridlock inside circulating quadrants",
    ],
).with_computed_fingerprint()


METERED_ENTRY_ROUNDABOUT = StrategyDescriptor(
    id="metered_entry_roundabout",
    name="Metered-Entry Signalised Roundabout",
    status="stable",
    description=(
        "Hybrid roundabout where signals meter entry onto the circulating carriageway on "
        "designated approaches while circulating traffic retains offside priority."
    ),
    not_modelled=[
        "Phased priority / signal-controlled circulation inside the ring",
        "Dynamic metering based on ring occupancy queues",
        "Queue detector setbacks > 150m",
    ],
    geometry=GeometryConstraint(
        intersection_type="roundabout",
        min_arms=3,
        max_arms=4,
        circulating_lanes=[1, 2],
    ),
    movement_topology=MovementTopology(
        topology_type="zone_based_conflicts",
        supports_uturns=True,
    ),
    right_of_way=RightOfWay(rule="signal_over_yield"),
    control_policy=ControlPolicy(
        policy="metering",
        cycle_aware=True,
    ),
    adaptation_logic=AdaptationLogic(
        logic="none",
        deterministic=True,
    ),
    priority_overlay=PriorityOverlay(overlay="none"),
    parameters={
        "metering_cycle": ParameterBound(
            min_value=15.0,
            max_value=90.0,
            default_value=30.0,
            unit="s",
            description="Entry signal metering cycle duration.",
        ),
        "metering_green": ParameterBound(
            min_value=4.0,
            max_value=60.0,
            default_value=12.0,
            unit="s",
            description="Green interval permitting entry to the yield line.",
        ),
        "metering_yellow": ParameterBound(
            min_value=2.0,
            max_value=5.0,
            default_value=3.0,
            unit="s",
            description="Yellow change interval on metered entry approach.",
        ),
        "metering_red": ParameterBound(
            min_value=4.0,
            max_value=60.0,
            default_value=15.0,
            unit="s",
            description="Red interval holding entry vehicles upstream of yield line.",
        ),
        "setback_distance": ParameterBound(
            min_value=15.0,
            max_value=100.0,
            default_value=30.0,
            unit="m",
            description="Distance from entry stopline to circulatory yield line.",
        ),
    },
    invariants=[
        "metering signal only restricts entry opportunity, never overrides circulating yield",
        "AlwaysOpen default gate reproduces conventional roundabout bit-identically",
    ],
).with_computed_fingerprint()


BUILTIN_STRATEGIES: List[StrategyDescriptor] = [
    FIXED_TIME_SIGNAL,
    ADAPTIVE_SIGNAL,
    CONVENTIONAL_ROUNDABOUT,
    METERED_ENTRY_ROUNDABOUT,
]

BUILTIN_STRATEGY_MAP: Dict[str, StrategyDescriptor] = {
    s.id: s for s in BUILTIN_STRATEGIES
}
