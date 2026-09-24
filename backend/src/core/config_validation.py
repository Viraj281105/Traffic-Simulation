"""Cross-field rules of the scenario-configuration contract.

``shared/schemas/config.schema.json`` can only express per-field shape and
bounds. The contract's validation summary
(docs/architecture/06-scenario-configuration-contract.md §5) also lists rules
that relate one field to another. Those were documented but enforced nowhere,
so a roundabout whose outer radius was smaller than its inner one, or a
directional split that sums to 4 (silently quadrupling demand), was accepted
with a 201 and simulated. This module is the single place those rules live, so
the validate endpoint and every creation path apply the same ones.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, TypeGuard, Union

# §5: "Must sum to 1.0 (±0.01 tolerance)".
SUM_TO_ONE_TOLERANCE: float = 0.01

# Accepted by the schema's enum (it is part of the published contract) but
# VehicleSpawner has no implementation for it, and a run requesting it used to
# fail with an unhandled NotImplementedError -> HTTP 500.
UNIMPLEMENTED_ARRIVAL_DISTRIBUTIONS = frozenset({"burst"})


def _section(config: Dict[str, Any], key: str) -> Dict[str, Any]:
    value = config.get(key)
    return value if isinstance(value, dict) else {}


def _number(value: Any) -> TypeGuard[Union[int, float]]:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _check_sum_to_one(
    errors: List[str], section: Dict[str, Any], key: str, fields: List[str]
) -> None:
    values = section.get(key)
    if not isinstance(values, dict):
        return
    parts = [values.get(f) for f in fields]
    numbers = [p for p in parts if _number(p)]
    if len(numbers) != len(parts):
        return  # shape errors are the schema's job
    total = float(sum(numbers))
    if abs(total - 1.0) > SUM_TO_ONE_TOLERANCE:
        errors.append(
            f"{key} values must sum to 1.0 (±{SUM_TO_ONE_TOLERANCE}); got {total:g}"
        )


def semantic_config_errors(config: Dict[str, Any]) -> List[str]:
    """Return every contract cross-field rule *config* violates (empty if none).

    Only fields actually present are checked, so a rule is never applied to a
    value the caller did not supply. In particular ``warmupTime < duration`` is
    enforced only for an explicit ``warmupTime``: short runs that rely on the
    30 s default are an existing, documented usage (metrics simply stay in
    warm-up), and rejecting them would break callers that never set it.
    """
    errors: List[str] = []

    sim = _section(config, "simulation")
    duration = sim.get("duration")
    warmup = sim.get("warmupTime")
    if _number(duration) and _number(warmup) and not warmup < duration:
        errors.append(
            f"simulation.warmupTime ({warmup:g}) must be less than "
            f"simulation.duration ({duration:g})"
        )

    traffic = _section(config, "traffic")
    _check_sum_to_one(
        errors, traffic, "directionalSplit", ["north", "south", "east", "west"]
    )
    _check_sum_to_one(
        errors, traffic, "turnProbabilities", ["left", "straight", "right"]
    )
    distribution = traffic.get("arrivalDistribution")
    if distribution in UNIMPLEMENTED_ARRIVAL_DISTRIBUTIONS:
        errors.append(
            f"traffic.arrivalDistribution {distribution!r} is not implemented yet; "
            "use 'poisson' or 'uniform'"
        )

    ctrl = _section(config, "controller")
    inner = ctrl.get("innerRadius")
    outer = ctrl.get("outerRadius")
    # Both radii have defaults (10 / 20), so a single explicit value can still
    # invert the ring against the other's default.
    inner_v = float(inner) if _number(inner) else 10.0
    outer_v = float(outer) if _number(outer) else 20.0
    if (_number(inner) or _number(outer)) and not outer_v > inner_v:
        errors.append(
            f"controller.outerRadius ({outer_v:g}) must be greater than "
            f"controller.innerRadius ({inner_v:g})"
        )

    veh = _section(config, "vehicleGeneration")
    for key in ("vehicleLength", "vehicleWidth", "desiredSpeed"):
        rng = veh.get(key)
        if (
            isinstance(rng, dict)
            and _number(rng.get("min"))
            and _number(rng.get("max"))
        ):
            if rng["max"] < rng["min"]:
                errors.append(
                    f"vehicleGeneration.{key}.max ({rng['max']:g}) must be >= "
                    f"min ({rng['min']:g})"
                )

    # NaN compares false against every bound, so it slips through each of the
    # schema's minimum/maximum checks; infinity passes any one-sided bound.
    errors.extend(
        f"{path} must be a finite number" for path in _non_finite_paths(config, "")
    )

    return errors


def _non_finite_paths(value: Any, path: str) -> List[str]:
    if isinstance(value, float) and not math.isfinite(value):
        return [path]
    found: List[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            found.extend(_non_finite_paths(child, f"{path}.{key}" if path else key))
    elif isinstance(value, list):
        for i, child in enumerate(value):
            found.extend(_non_finite_paths(child, f"{path}[{i}]"))
    return found
