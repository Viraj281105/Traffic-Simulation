"""Apply sampled factor values to a scenario document (W1 WP3).

The meaning of every factor kind is fixed in ``docs/engineering/v3-w1-factor-mapping.md``. In short, a
condition's values produce a **new** :class:`ScenarioDocument` from the base one, through existing scenario
inputs only (document fields and the ``advanced`` merge). No engine or physics code is touched. A document
that fails validation is *rejected* with :class:`FactorApplicationError`, never repaired: a mix is never
rescaled, a demand above the arm limit is never clipped.

Every factor is global: it acts on all arms and on every vehicle class identically.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Mapping, Sequence, Set, Tuple

from pydantic import ValidationError

from src.scenario.documents import ScenarioDocument, compile_scenario
from src.vehicles.speed_profile import resolve_desired_speed_range
from src.vehicles.vehicle_types import (
    VEHICLE_CLASSES,
    VehicleTypeProfile,
    resolve_vehicle_population,
)

from .spec import Factor

VALUE_DECIMALS = 6
LIGHT_CLASSES: Tuple[str, ...] = ("car", "suv", "motorcycle")
HEAVY_CLASSES: Tuple[str, ...] = ("bus", "truck")

_STRUCTURAL = ("demand_scale", "turning_shift", "mix_shift")
_VEHICLE_GENERATION = (
    "headway_scale",
    "max_acceleration_scale",
    "desired_speed_scale",
)


class FactorApplicationError(ValueError):
    """The perturbed scenario is invalid. The runner counts it as ``validation_failed``."""


def _r(value: float) -> float:
    return round(value, VALUE_DECIMALS)


# --- structural factors ---------------------------------------------------------------------------


def _shift_turning(turning: Mapping[str, Any], s: float) -> Dict[str, Any]:
    """Move share between *straight* and *turning* (left + right), conserving the total.

    s > 0 moves the fraction s of the straight share to left/right in their existing proportion (evenly
    when both are zero); s < 0 moves the fraction |s| of left + right into straight. U-turns are untouched.
    """
    left, straight, right = (
        float(turning["left"]),
        float(turning["straight"]),
        float(turning["right"]),
    )
    turning_total = left + right
    left_weight = left / turning_total if turning_total > 0 else 0.5
    if s >= 0:
        moved = s * straight
        new_left = left + moved * left_weight
        new_straight = straight - moved
        new_right = right + moved * (1.0 - left_weight)
    else:
        moved = -s * turning_total
        new_left = left - moved * left_weight
        new_straight = straight + moved
        new_right = right - moved * (1.0 - left_weight)
    return {
        **turning,
        "left": max(0.0, _r(new_left)),
        "straight": max(0.0, _r(new_straight)),
        "right": max(0.0, _r(new_right)),
    }


def _shift_mix(mix: Mapping[str, Any], s: float) -> Dict[str, float]:
    """Move share between *light* (car, suv, motorcycle) and *heavy* (bus, truck), conserving the total.

    s > 0 moves the fraction s of the light share into the heavy classes in proportion to their existing
    shares (equally when both are zero); s < 0 does the reverse.
    """
    shares = {c: float(mix.get(c) or 0.0) for c in VEHICLE_CLASSES}
    heavy = sum(shares[c] for c in HEAVY_CLASSES)
    light = sum(shares[c] for c in LIGHT_CLASSES)
    if s >= 0:
        source, sink, source_total, sink_total = (
            LIGHT_CLASSES,
            HEAVY_CLASSES,
            light,
            heavy,
        )
        moved = s * light
    else:
        source, sink, source_total, sink_total = (
            HEAVY_CLASSES,
            LIGHT_CLASSES,
            heavy,
            light,
        )
        moved = -s * heavy
    for c in source:
        shares[c] -= moved * (shares[c] / source_total if source_total > 0 else 0.0)
    for c in sink:
        shares[c] += moved * (
            shares[c] / sink_total if sink_total > 0 else 1.0 / len(sink)
        )
    return {c: max(0.0, _r(v)) for c, v in shares.items()}


# --- vehicle-generation factors (read the effective base, write absolute values) ------------------


def _classes_in_use(body: Mapping[str, Any]) -> Set[str]:
    used: Set[str] = set()
    mix = (body.get("vehicles") or {}).get("mix")
    if mix:
        used |= {c for c, share in mix.items() if share and share > 0}
    for arm in body["approaches"].values():
        if arm and arm.get("vehicleMix"):
            used |= {c for c, share in arm["vehicleMix"].items() if share and share > 0}
    return used


def _effective(body: Dict[str, Any]) -> Dict[str, Any]:
    """The compiled engine config of the document as it stands (the engine's own resolution)."""
    try:
        return compile_scenario(ScenarioDocument.model_validate(body), "fixed_time")
    except (ValidationError, ValueError) as exc:
        raise FactorApplicationError(_first_message(exc)) from exc


def _class_profiles(config: Mapping[str, Any]) -> Dict[str, VehicleTypeProfile]:
    population = resolve_vehicle_population(
        dict(config),
        mix_override={c: 1.0 / len(VEHICLE_CLASSES) for c in VEHICLE_CLASSES},
    )
    assert population is not None  # an explicit mix override always gives a population
    return {t: p.profile for t, p in population.params_by_type.items()}


def _vehicle_generation(body: Dict[str, Any]) -> Dict[str, Any]:
    advanced = body.get("advanced")
    if advanced is None:
        advanced = body["advanced"] = {}
    generation: Dict[str, Any] = advanced.setdefault("vehicleGeneration", {})
    return generation


def _scale_idm(body: Dict[str, Any], kind: str, s: float) -> None:
    """Scale the desired time headway or the maximum acceleration of every class by ``s``."""
    config = _effective(body)
    generation = config.get("vehicleGeneration") or {}
    profiles = _class_profiles(config)
    if kind == "headway_scale":
        key, attr, fallback = "desiredTimeHeadway", "desired_time_headway", 1.5
    else:
        key, attr, fallback = "maxAcceleration", "max_acceleration", 2.0
    target = _vehicle_generation(body)
    target[key] = _r(
        float(generation.get(key, fallback)) * s
    )  # legacy cars, reference car
    used = _classes_in_use(body)
    if used:
        types = target.setdefault("vehicleTypes", {})
        for c in sorted(used):
            types.setdefault(c, {})[key] = _r(getattr(profiles[c], attr) * s)


def _scale_desired_speed(body: Dict[str, Any], s: float) -> None:
    """Scale the car's desired-speed range; every class derives its range from the car's by a fixed ratio."""
    low, high = resolve_desired_speed_range(_effective(body))
    _vehicle_generation(body)["desiredSpeed"] = {
        "min": _r(low * s),
        "max": _r(high * s),
    }


# --- entry points ---------------------------------------------------------------------------------


def _first_message(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        first = exc.errors()[0]
        where = ".".join(str(part) for part in first["loc"])
        return f"{where}: {first['msg']}" if where else str(first["msg"])
    return str(exc)


def preflight(base: ScenarioDocument, factors: Sequence[Factor]) -> List[str]:
    """Problems that would make a factor meaningless for this base scenario, found before any run.

    An experiment with any of these is refused at submission, once, rather than excluded condition by
    condition: ``mix_shift`` on a scenario with no declared mix would silently switch the engine from its
    legacy single-car population to the mixed one, and an ``advanced`` section that sets the same inputs a
    document-level factor writes would shadow it through the deep merge.
    """
    errors: List[str] = []
    kinds = {f.kind for f in factors}
    advanced = base.advanced or {}
    traffic = advanced.get("traffic") if isinstance(advanced, dict) else None
    generation = (
        advanced.get("vehicleGeneration") if isinstance(advanced, dict) else None
    )
    traffic_keys = set(traffic) if isinstance(traffic, dict) else set()
    if "mix_shift" in kinds:
        has_mix = base.vehicles.mix is not None or any(
            arm.vehicleMix is not None for arm in base.approaches.present().values()
        )
        if not has_mix:
            errors.append(
                "mix_shift needs the base scenario to declare a vehicle mix (vehicles.mix or an "
                "approach vehicleMix); without one the engine uses its legacy single-car population"
            )
        if isinstance(generation, dict) and "vehicleMix" in generation:
            errors.append(
                "mix_shift would be overridden by advanced.vehicleGeneration.vehicleMix in the base "
                "scenario; remove it from advanced"
            )
    if "demand_scale" in kinds and traffic_keys & {
        "arrivalRate",
        "directionalSplit",
        "totalVehicles",
        "approaches",
    }:
        errors.append(
            "demand_scale would be overridden by advanced.traffic in the base scenario; remove its "
            "demand keys from advanced"
        )
    if {"turning_shift", "mix_shift"} & kinds and "approaches" in traffic_keys:
        errors.append(
            "turning_shift/mix_shift would be overridden by advanced.traffic.approaches in the base "
            "scenario; remove it from advanced"
        )
    return errors


def apply_factors(
    base: ScenarioDocument,
    factors: Sequence[Factor],
    values: Mapping[str, float],
) -> ScenarioDocument:
    """The scenario for one sampled condition. Raises :class:`FactorApplicationError` if it is invalid."""
    by_kind = {f.kind: float(values[f.id]) for f in factors}
    body: Dict[str, Any] = copy.deepcopy(base.model_dump())
    arms = [arm for arm in body["approaches"].values() if arm]

    if "demand_scale" in by_kind:
        for arm in arms:
            arm["vehiclesPerHour"] = _r(
                arm["vehiclesPerHour"] * by_kind["demand_scale"]
            )
    if "turning_shift" in by_kind:
        for arm in arms:
            arm["turning"] = _shift_turning(arm["turning"], by_kind["turning_shift"])
    if "mix_shift" in by_kind:
        shifted = False
        scenario_mix = (body.get("vehicles") or {}).get("mix")
        if scenario_mix:
            body["vehicles"]["mix"] = _shift_mix(scenario_mix, by_kind["mix_shift"])
            shifted = True
        for arm in arms:
            if arm.get("vehicleMix"):
                arm["vehicleMix"] = _shift_mix(arm["vehicleMix"], by_kind["mix_shift"])
                shifted = True
        if not shifted:
            raise FactorApplicationError("mix_shift needs a declared vehicle mix")

    # Validate the structural changes before the generation factors read the effective base.
    try:
        ScenarioDocument.model_validate(body)
    except ValidationError as exc:
        raise FactorApplicationError(_first_message(exc)) from exc

    for kind in _VEHICLE_GENERATION:
        if kind not in by_kind:
            continue
        if kind == "desired_speed_scale":
            _scale_desired_speed(body, by_kind[kind])
        else:
            _scale_idm(body, kind, by_kind[kind])

    try:
        return ScenarioDocument.model_validate(body)
    except ValidationError as exc:
        raise FactorApplicationError(_first_message(exc)) from exc
