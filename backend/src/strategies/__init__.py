"""Strategy descriptor models, built-in strategies, and registry (V3.0 W3, ADR-014)."""

from src.strategies.builtins import (
    ADAPTIVE_SIGNAL,
    BUILTIN_STRATEGIES,
    BUILTIN_STRATEGY_MAP,
    CONVENTIONAL_ROUNDABOUT,
    FIXED_TIME_SIGNAL,
    METERED_ENTRY_ROUNDABOUT,
)
from src.strategies.models import (
    STRATEGY_FORMAT,
    STRATEGY_VERSION,
    AdaptationLogic,
    ControlPolicy,
    GeometryConstraint,
    MovementTopology,
    ParameterBound,
    PriorityOverlay,
    RightOfWay,
    StrategyDescriptor,
    canonical_json,
)
from src.strategies.registry import (
    LEGACY_STRATEGY_ALIASES,
    StrategyRegistry,
    get_strategy_registry,
    reset_strategy_registry,
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

__all__ = [
    "STRATEGY_FORMAT",
    "STRATEGY_VERSION",
    "AdaptationLogic",
    "ControlPolicy",
    "GeometryConstraint",
    "MovementTopology",
    "ParameterBound",
    "PriorityOverlay",
    "RightOfWay",
    "StrategyDescriptor",
    "canonical_json",
    "FIXED_TIME_SIGNAL",
    "ADAPTIVE_SIGNAL",
    "CONVENTIONAL_ROUNDABOUT",
    "METERED_ENTRY_ROUNDABOUT",
    "BUILTIN_STRATEGIES",
    "BUILTIN_STRATEGY_MAP",
    "LEGACY_STRATEGY_ALIASES",
    "StrategyRegistry",
    "get_strategy_registry",
    "reset_strategy_registry",
    "COMPATIBILITY_ERROR_CODES",
    "CompatibilityIssue",
    "StrategyCompatibilityError",
    "validate_strategy_compatibility",
    "check_strategy_compatibility",
    "validate_layer_combination",
    "validate_scenario_strategy_compatibility",
    "check_scenario_strategy_compatibility",
]

