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

from src.controllers.adaptive_signal import (
    ADAPTIVE_BOUNDS,
    SIGNAL_CONTROL_MODES,
    adaptive_plan_errors,
    resolve_adaptive_settings,
)
from src.core.lane_validation import lane_configuration_errors
from src.roads.lane_config import shortest_approach_length
from src.roads.network import lane_counts, resolve_lanes_per_approach
from src.vehicles.vehicle_types import vehicle_mix_errors

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

    errors.extend(vehicle_mix_errors(config))
    errors.extend(_lane_count_errors(config))
    errors.extend(lane_configuration_errors(config))
    errors.extend(_signal_control_errors(config))

    # NaN compares false against every bound, so it slips through each of the
    # schema's minimum/maximum checks; infinity passes any one-sided bound.
    errors.extend(
        f"{path} must be a finite number" for path in _non_finite_paths(config, "")
    )

    return errors


def _lane_count_errors(config: Dict[str, Any]) -> List[str]:
    """Opposite approaches must have the same number of lanes.

    Each road carries the same number of lanes in both directions, so through
    traffic from an approach with more lanes than the road opposite would
    have to merge inside the junction (a lane drop). The model has no merge
    behaviour there: the two through paths converge on one exit lane and the
    vehicles meeting at the merge wait on each other indefinitely (V1.0,
    north 1 / south 2 / east 1 / west 2: 14 of 171 vehicles got through in
    240 s). Different counts on the two crossing roads — a two-lane main road
    meeting a one-lane side street — are fully supported.
    """
    roads = _section(config, "roads")
    if not roads:
        return []
    if _section(config, "geometry").get("intersectionType") == "roundabout":
        # V1.4: a roundabout's traffic leaves from the ring, whose lanes are
        # mapped onto each exit (roads/lane_config.py); nothing goes straight
        # across from one approach into the opposite one, so unequal
        # opposite approaches are not a lane drop there.
        return []
    try:
        counts = lane_counts(resolve_lanes_per_approach(roads))
    except (TypeError, ValueError):
        return []  # shape errors are the schema's job
    errors: List[str] = []
    for a, b in (("north", "south"), ("east", "west")):
        if counts[a] != counts[b]:
            errors.append(
                f"{a} and {b} approaches must have the same number of lanes "
                f"(got {counts[a]} and {counts[b]}): through traffic cannot "
                "merge inside the junction in this model"
            )
    return errors


def _signal_control_errors(config: Dict[str, Any]) -> List[str]:
    """Adaptive signal control (V1.3): a known mode, a signalised junction,
    timings that can be met, and a phase plan it can end greens in safely.

    Shape and per-field bounds are the schema's job; they are re-checked here
    only where a value feeds a cross-field rule, so a hand-built config (the
    dashboard path) gets the same answer as the versioned API.
    """
    ctrl = _section(config, "controller")
    mode = ctrl.get("signalControl")
    adaptive_cfg = ctrl.get("adaptive")
    if mode is None and adaptive_cfg is None:
        return []
    errors: List[str] = []
    if mode is not None and mode not in SIGNAL_CONTROL_MODES:
        errors.append(
            f"controller.signalControl must be one of {list(SIGNAL_CONTROL_MODES)}; "
            f"got {mode!r}"
        )
        return errors
    if mode != "adaptive":
        return errors
    geom = _section(config, "geometry").get("intersectionType", "fixed_time_signal")
    if geom == "roundabout":
        errors.append(
            "controller.signalControl 'adaptive' applies to a signalised junction, "
            "not a roundabout"
        )
        return errors
    if adaptive_cfg is not None and not isinstance(adaptive_cfg, dict):
        errors.append("controller.adaptive must be an object")
        return errors
    raw = adaptive_cfg or {}
    unknown = sorted(set(raw) - set(ADAPTIVE_BOUNDS))
    if unknown:
        errors.append(f"controller.adaptive has unknown fields: {', '.join(unknown)}")
    settings = resolve_adaptive_settings(ctrl)
    for key, (low, high) in ADAPTIVE_BOUNDS.items():
        value = settings[key]
        if not _number(value):
            errors.append(f"controller.adaptive.{key} must be a number")
            return errors
        if key == "demandThreshold" and value != int(value):
            errors.append("controller.adaptive.demandThreshold must be a whole number")
        if not low <= value <= high:
            errors.append(
                f"controller.adaptive.{key} ({value:g}) must be between "
                f"{low:g} and {high:g}"
            )
    if errors:
        return errors
    if not settings["maxGreen"] > settings["minGreen"]:
        errors.append(
            f"controller.adaptive.maxGreen ({settings['maxGreen']:g}) must be "
            f"greater than minGreen ({settings['minGreen']:g})"
        )
    if not settings["extensionStep"] < settings["maxGreen"]:
        errors.append(
            f"controller.adaptive.extensionStep ({settings['extensionStep']:g}) "
            f"must be less than maxGreen ({settings['maxGreen']:g})"
        )
    approach = _section(config, "roads").get("approachLength", 200.0)
    if _number(approach) and not settings["detectionDistance"] < approach:
        errors.append(
            f"controller.adaptive.detectionDistance "
            f"({settings['detectionDistance']:g}) must be shorter than "
            f"roads.approachLength ({approach:g})"
        )
    else:
        # V1.4: an approach may be shorter than roads.approachLength.
        try:
            shortest = shortest_approach_length(_section(config, "roads"))
        except (TypeError, ValueError):
            shortest = None
        if shortest is not None and not settings["detectionDistance"] < shortest:
            errors.append(
                f"controller.adaptive.detectionDistance "
                f"({settings['detectionDistance']:g}) must be shorter than the "
                f"shortest approach ({shortest:g} m)"
            )
    offset = ctrl.get("offset")
    if _number(offset) and offset != 0:
        errors.append(
            "controller.offset (a fixed-time coordination offset) has no meaning "
            "for an adaptive signal; omit it or set it to 0"
        )
    sequence = ctrl.get("phaseSequence")
    if isinstance(sequence, list) and all(isinstance(x, str) for x in sequence):
        errors.extend(adaptive_plan_errors(sequence))
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
