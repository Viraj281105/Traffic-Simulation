"""Strategy resolution contracts and parameter fingerprinting (V3.0 W3, ADR-014 §4).

Explicit contracts for resolving, inferring, and fingerprinting strategy configurations:
1. ``resolve_strategy``: Authoritative contract resolving a canonical ID, legacy alias,
   StrategyDescriptor, or configuration dictionary to its typed ``StrategyDescriptor``.
2. ``resolve_strategy_id``: Resolve source to canonical strategy identifier string.
3. ``infer_strategy_id_from_config``: Structural inference of canonical strategy ID from
   geometry and controller layers.
4. ``extract_explicit_strategy``: Extract explicit strategy identifier declared in configuration.
5. ``resolve_strategy_parameters``: Extract and validate strategy parameters against descriptor bounds.
6. ``compute_strategy_instance_fingerprint``: Deterministic 16-hex fingerprint of a resolved
   strategy instance incorporating descriptor ID, version, and resolved parameters (ADR-014 §4).
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, Optional, Tuple, Union

from src.strategies.models import StrategyDescriptor, canonical_json
from src.strategies.registry import StrategyRegistry, get_strategy_registry


def extract_explicit_strategy(config: Any) -> Optional[str]:
    """Extract explicit strategy name from root, controller, or scenario block if present.

    Ignores compound/paired strategies (e.g. 'fixed_time+roundabout' in live comparison).
    """
    if not isinstance(config, dict):
        return None

    # 1. Root level 'strategy'
    root_strat = config.get("strategy")
    if isinstance(root_strat, str) and root_strat.strip() and "+" not in root_strat:
        return root_strat.strip()

    # 2. Controller level 'strategy'
    ctrl = config.get("controller")
    if isinstance(ctrl, dict):
        ctrl_strat = ctrl.get("strategy")
        if isinstance(ctrl_strat, str) and ctrl_strat.strip() and "+" not in ctrl_strat:
            return ctrl_strat.strip()

    # 3. Scenario block 'strategy' (metadata from compiled scenario documents)
    scenario = config.get("scenario")
    if isinstance(scenario, dict):
        scen_strat = scenario.get("strategy")
        if isinstance(scen_strat, str) and scen_strat.strip() and "+" not in scen_strat:
            geom = config.get("geometry")
            geom_type = geom.get("intersectionType") if isinstance(geom, dict) else None
            # If geometry is explicitly overridden and contradicts scenario.strategy metadata
            # (e.g. DualSimulationOrchestrator constructing config_signal from a roundabout scenario),
            # let the structural geometry override govern.
            if geom_type is not None:
                is_rb_geom = geom_type == "roundabout"
                is_rb_strat = scen_strat in (
                    "roundabout",
                    "conventional_roundabout",
                    "signalised_roundabout",
                    "metered_entry_roundabout",
                )
                if is_rb_geom != is_rb_strat:
                    return None
            if scen_strat == "roundabout":
                ctrl_entry = config.get("controller")
                if (
                    isinstance(ctrl_entry, dict)
                    and ctrl_entry.get("entryControl") == "metered_entry"
                ):
                    return "metered_entry_roundabout"
            return scen_strat.strip()

    return None


def extract_geometry_type(config: Any) -> Optional[str]:
    """The junction type a configuration declares, or None if it declares none.

    ``geometry.intersectionType`` (engine configs) wins; scenario-document style
    ``junction.type`` is the fallback. Shared by strategy inference and
    compatibility validation so the two can never read different layouts.
    """
    if not isinstance(config, dict):
        return None
    geom = config.get("geometry")
    geom_type = geom.get("intersectionType") if isinstance(geom, dict) else None
    if geom_type is None:
        junc = config.get("junction")
        if isinstance(junc, dict):
            geom_type = junc.get("type")
    return geom_type if isinstance(geom_type, str) else None


def infer_strategy_id_from_config(config: Any) -> str:
    """Infer the canonical strategy ID from the structural configuration layers.

    Maps:
    - roundabout + metered_entry -> metered_entry_roundabout
    - roundabout (unmetered) -> conventional_roundabout
    - signal (or default) + adaptive -> adaptive_signal
    - signal (or default) -> fixed_time_signal
    """
    if not isinstance(config, dict):
        return "fixed_time_signal"

    geom_type = extract_geometry_type(config)

    ctrl = config.get("controller")
    ctrl_dict = ctrl if isinstance(ctrl, dict) else {}
    signal_control = ctrl_dict.get("signalControl")

    entry_control = ctrl_dict.get("entryControl")
    if entry_control is None and isinstance(config.get("roundabout"), dict):
        entry_control = config["roundabout"].get("entryControl")

    if geom_type == "roundabout":
        if entry_control == "metered_entry":
            return "metered_entry_roundabout"
        return "conventional_roundabout"

    if signal_control == "adaptive" or geom_type == "adaptive_signal":
        return "adaptive_signal"

    return "fixed_time_signal"


def resolve_strategy(
    source: Union[str, Dict[str, Any], StrategyDescriptor],
    registry: Optional[StrategyRegistry] = None,
) -> StrategyDescriptor:
    """Explicit contract for resolving a strategy to its authoritative StrategyDescriptor.

    Accepts:
    - StrategyDescriptor: validated and returned.
    - str: canonical ID or legacy alias resolved via the registry.
    - Dict[str, Any]: scenario document or engine configuration dict.

    Raises:
    - TypeError: if source is of an invalid type.
    - StrategyCompatibilityError: if source violates strategy compatibility contracts.
    - KeyError: if explicit strategy string cannot be resolved in registry.
    """
    from src.strategies.validator import check_scenario_strategy_compatibility

    reg = registry or get_strategy_registry()

    if isinstance(source, StrategyDescriptor):
        source.validate_self()
        return source

    if isinstance(source, str):
        canonical_id = reg.resolve_id(source)
        return reg.get(canonical_id)

    if isinstance(source, dict):
        check_scenario_strategy_compatibility(source)

        explicit = extract_explicit_strategy(source)
        if explicit is not None:
            canonical_explicit = reg.resolve_id(explicit)
            return reg.get(canonical_explicit)

        inferred = infer_strategy_id_from_config(source)
        return reg.get(inferred)

    raise TypeError(
        f"Cannot resolve strategy from source of type {type(source).__name__}. "
        "Expected str, Dict[str, Any], or StrategyDescriptor."
    )


def resolve_strategy_id(
    source: Union[str, Dict[str, Any], StrategyDescriptor],
    registry: Optional[StrategyRegistry] = None,
) -> str:
    """Resolve source to its canonical strategy identifier string."""
    return resolve_strategy(source, registry=registry).id


# Controller keys the engine accepts for a parameter, highest precedence first
# (FixedTimeSignalController: the *Duration names win over the *Time aliases, and
# straightRightDuration over greenTime over greenDuration).
PARAMETER_CONTROLLER_KEYS: Dict[str, Tuple[str, ...]] = {
    "green_time": ("straightRightDuration", "greenTime", "greenDuration"),
    "yellow_time": ("yellowDuration", "yellowTime"),
    "all_red_time": ("allRedDuration", "allRedTime"),
}

# Descriptor parameters whose config key is not the camelCase of their name:
# parameter -> (controller sub-object, key).
PARAMETER_CONFIG_ALIASES: Dict[str, Tuple[str, str]] = {
    "metering_yellow": ("entryMetering", "yellow"),
    "metering_all_red": ("entryMetering", "allRed"),
}


def _lookup_parameter(
    param_name: str,
    ctrl: Dict[str, Any],
    adapt: Dict[str, Any],
    config: Dict[str, Any],
) -> Any:
    """The configured value for a descriptor parameter, or None if unset."""
    alias = PARAMETER_CONFIG_ALIASES.get(param_name)
    if alias is not None:
        sub = ctrl.get(alias[0])
        return sub.get(alias[1]) if isinstance(sub, dict) else None

    for key in PARAMETER_CONTROLLER_KEYS.get(param_name, ()):
        if ctrl.get(key) is not None:
            return ctrl[key]

    camel_name = "".join(
        word.capitalize() if i > 0 else word
        for i, word in enumerate(param_name.split("_"))
    )
    for source in (ctrl, adapt, config):
        for key in (param_name, camel_name):
            if source.get(key) is not None:
                return source[key]
    return None


def resolve_strategy_parameters(
    descriptor: StrategyDescriptor,
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """Extract and validate strategy parameters against descriptor parameter bounds.

    Supports both canonical snake_case (e.g. 'green_time') and legacy/scenario camelCase
    (e.g. 'greenTime', controller.adaptive.minGreen).
    Returns a clean dictionary of parameter names to resolved values.
    """
    ctrl_raw = config.get("controller")
    ctrl: Dict[str, Any] = ctrl_raw if isinstance(ctrl_raw, dict) else {}
    adapt_raw = ctrl.get("adaptive")
    adapt: Dict[str, Any] = adapt_raw if isinstance(adapt_raw, dict) else {}
    resolved: Dict[str, Any] = {}

    for param_name, bound in descriptor.parameters.items():
        val = _lookup_parameter(param_name, ctrl, adapt, config)

        if val is not None:
            if isinstance(val, bool) or not isinstance(val, (int, float)):
                raise ValueError(
                    f"Strategy '{descriptor.id}': parameter '{param_name}' must be a "
                    f"number, got {type(val).__name__}"
                )
            num_val = float(val)
            if not (bound.min_value <= num_val <= bound.max_value):
                raise ValueError(
                    f"Strategy '{descriptor.id}': parameter '{param_name}' value {num_val} "
                    f"out of bounds [{bound.min_value}, {bound.max_value}] {bound.unit}"
                )
            resolved[param_name] = num_val
        elif bound.default_value is not None:
            resolved[param_name] = bound.default_value

    return resolved


def compute_strategy_instance_fingerprint(
    descriptor: StrategyDescriptor,
    resolved_parameters: Optional[Dict[str, Any]] = None,
) -> str:
    """Deterministic 16-hex SHA-256 fingerprint of a strategy instance (ADR-014 §4).

    Combines descriptor ID, version, descriptor fingerprint, and canonical resolved parameters.
    """
    payload = {
        # Recomputed, never read from the stored field: a modified copy of a
        # descriptor must not keep the identity of the one it was copied from.
        "descriptor_fingerprint": descriptor.compute_fingerprint(),
        "id": descriptor.id,
        "parameters": resolved_parameters or {},
        "version": descriptor.version,
    }
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()[:16]
