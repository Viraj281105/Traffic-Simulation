"""Vehicle classes (V1.1): what makes a bus behave differently from a car.

Every vehicle class is described by one :class:`VehicleTypeProfile` — its
dimensions, its Intelligent Driver Model parameters, how hard it may corner
and how it changes lanes. The engine never branches on a class name: the
spawner draws a class from the configured mix, builds the vehicle from that
class's profile, and every behaviour downstream (car-following, curve speed,
yellow-light decisions, lane changing, conflict-zone occupancy) reads the
numbers carried by the vehicle itself.

Two populations exist:

* **Legacy** — no ``vehicleGeneration.vehicleMix`` configured. Every vehicle
  is the V1.0 passenger car, drawn exactly as before (same random-number
  stream, same shared IDM), so existing scenarios reproduce bit for bit.
  :func:`resolve_vehicle_population` returns ``None`` for it.
* **Mixed** — ``vehicleMix`` gives each class a share of arrivals. The
  ``car`` class is the configured reference vehicle (``vehicleGeneration``'s
  own ranges and IDM values); every other class has its own defaults below,
  each overridable through ``vehicleGeneration.vehicleTypes.<class>``.

The default parameters are model inputs, not findings. They follow the
relative ordering in the IDM literature (Treiber & Kesting, *Traffic Flow
Dynamics*, 2013, ch. 11: heavy vehicles accelerate and brake more gently and
keep longer headways than cars) scaled to this model's urban car (a = 2.0,
b = 3.0 m/s^2, T = 1.5 s, s0 = 2 m), and typical urban dimensions (12 m
single-deck bus, 8-12 m rigid truck, 2 m motorcycle).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Any, Dict, List, Mapping, Optional, Tuple

from src.vehicles.idm import IntelligentDriverModel
from src.vehicles.speed_profile import (
    DESIRED_SPEED_LIMIT_FACTORS,
    resolve_desired_speed_range,
    resolve_max_lateral_acceleration,
)

CAR = "car"
SUV = "suv"
BUS = "bus"
TRUCK = "truck"
MOTORCYCLE = "motorcycle"

#: Every vehicle class, in the canonical order used for drawing from a mix
#: (the order is part of the seeded random stream, so it must never change).
VEHICLE_CLASSES: Tuple[str, ...] = (CAR, SUV, BUS, TRUCK, MOTORCYCLE)

# Same tolerance as the other sum-to-one rules (core/config_validation.py).
MIX_SUM_TOLERANCE: float = 0.01

# The longest vehicle the V1.0 geometry constants were sized for (the legacy
# passenger car's vehicleLength maximum). Allowances for longer vehicles are
# measured from it, so a legacy car never receives any.
REFERENCE_VEHICLE_LENGTH: float = 5.0


@dataclass(frozen=True)
class VehicleTypeProfile:
    """The complete, explicit parameter set of one vehicle class."""

    type_id: str
    label: str
    length: Tuple[float, float]
    width: Tuple[float, float]
    # Desired speed as a fraction of the road's speed limit (min, max).
    desired_speed_factor: Tuple[float, float]
    max_acceleration: float
    comfort_deceleration: float
    desired_time_headway: float
    minimum_gap: float
    idm_delta: float
    # Lateral-acceleration limit on curved paths (m/s^2): heavier, taller
    # vehicles corner more slowly (see speed_profile.curve_speed_ceiling).
    max_lateral_acceleration: float
    # Lane changing (V1.2): nominal manoeuvre time, the shortest distance
    # the lateral move may be compressed into at low speed, and the MOBIL
    # politeness factor (weight given to the gain/loss of other drivers).
    lane_change_duration: float
    lane_change_min_distance: float
    politeness: float

    @property
    def max_length(self) -> float:
        return self.length[1]


DEFAULT_PROFILES: Dict[str, VehicleTypeProfile] = {
    # The V1.0 passenger car. Overridden from vehicleGeneration at resolve
    # time, so in a mixed population "car" is always the configured
    # reference vehicle.
    CAR: VehicleTypeProfile(
        type_id=CAR,
        label="Car",
        length=(4.0, 5.0),
        width=(1.8, 2.2),
        desired_speed_factor=DESIRED_SPEED_LIMIT_FACTORS,
        max_acceleration=2.0,
        comfort_deceleration=3.0,
        desired_time_headway=1.5,
        minimum_gap=2.0,
        idm_delta=4.0,
        max_lateral_acceleration=3.0,
        lane_change_duration=3.0,
        lane_change_min_distance=12.0,
        politeness=0.3,
    ),
    SUV: VehicleTypeProfile(
        type_id=SUV,
        label="SUV",
        length=(4.6, 5.2),
        width=(1.9, 2.1),
        desired_speed_factor=(0.85, 1.05),
        max_acceleration=1.8,
        comfort_deceleration=2.8,
        desired_time_headway=1.6,
        minimum_gap=2.0,
        idm_delta=4.0,
        max_lateral_acceleration=2.7,
        lane_change_duration=3.2,
        lane_change_min_distance=14.0,
        politeness=0.3,
    ),
    BUS: VehicleTypeProfile(
        type_id=BUS,
        label="Bus",
        length=(10.5, 12.0),
        width=(2.50, 2.55),
        desired_speed_factor=(0.75, 0.90),
        max_acceleration=1.0,
        comfort_deceleration=2.0,
        desired_time_headway=1.8,
        minimum_gap=2.5,
        idm_delta=4.0,
        max_lateral_acceleration=1.8,
        lane_change_duration=4.5,
        lane_change_min_distance=22.0,
        politeness=0.5,
    ),
    TRUCK: VehicleTypeProfile(
        type_id=TRUCK,
        label="Truck",
        length=(8.0, 12.0),
        width=(2.40, 2.55),
        desired_speed_factor=(0.70, 0.90),
        max_acceleration=0.8,
        comfort_deceleration=2.0,
        desired_time_headway=2.0,
        minimum_gap=3.0,
        idm_delta=4.0,
        max_lateral_acceleration=1.6,
        lane_change_duration=5.0,
        lane_change_min_distance=24.0,
        politeness=0.5,
    ),
    MOTORCYCLE: VehicleTypeProfile(
        type_id=MOTORCYCLE,
        label="Motorcycle / bike",
        length=(1.9, 2.3),
        width=(0.7, 0.9),
        desired_speed_factor=(0.90, 1.10),
        max_acceleration=3.0,
        comfort_deceleration=3.5,
        desired_time_headway=1.1,
        minimum_gap=1.5,
        idm_delta=4.0,
        max_lateral_acceleration=4.0,
        lane_change_duration=2.0,
        lane_change_min_distance=8.0,
        politeness=0.1,
    ),
}

# Lane-change behaviour of a legacy vehicle (no profile attached): the car's.
DEFAULT_LANE_CHANGE_DURATION: float = DEFAULT_PROFILES[CAR].lane_change_duration
DEFAULT_LANE_CHANGE_MIN_DISTANCE: float = DEFAULT_PROFILES[CAR].lane_change_min_distance
DEFAULT_POLITENESS: float = DEFAULT_PROFILES[CAR].politeness


class VehicleParams:
    """Per-class behaviour shared by every vehicle of that class.

    One instance per class per simulation: vehicles hold a reference, so the
    IDM object is built once, not once per vehicle.
    """

    __slots__ = ("profile", "idm", "desired_speed_range")

    def __init__(
        self, profile: VehicleTypeProfile, desired_speed_range: Tuple[float, float]
    ) -> None:
        self.profile = profile
        self.desired_speed_range = desired_speed_range
        self.idm = IntelligentDriverModel(
            max_acceleration=profile.max_acceleration,
            comfort_deceleration=profile.comfort_deceleration,
            desired_time_headway=profile.desired_time_headway,
            minimum_gap=profile.minimum_gap,
            idm_delta=profile.idm_delta,
        )

    @property
    def type_id(self) -> str:
        return self.profile.type_id

    @property
    def comfort_deceleration(self) -> float:
        return self.profile.comfort_deceleration

    @property
    def max_lateral_acceleration(self) -> float:
        return self.profile.max_lateral_acceleration

    @property
    def minimum_gap(self) -> float:
        return self.profile.minimum_gap


class VehiclePopulation:
    """The configured mix of vehicle classes and their resolved parameters."""

    def __init__(self, entries: List[Tuple[VehicleParams, float]]) -> None:
        if not entries:
            raise ValueError("A vehicle population needs at least one class")
        self.entries = entries
        self.params_by_type: Dict[str, VehicleParams] = {
            params.type_id: params for params, _ in entries
        }

    @property
    def type_ids(self) -> List[str]:
        return [params.type_id for params, _ in self.entries]

    @property
    def weights(self) -> List[float]:
        return [weight for _, weight in self.entries]

    @property
    def max_length(self) -> float:
        return max(params.profile.max_length for params, _ in self.entries)


def _range(value: Any) -> Optional[Tuple[float, float]]:
    if isinstance(value, Mapping) and "min" in value and "max" in value:
        return float(value["min"]), float(value["max"])
    return None


_SCALAR_OVERRIDES: Dict[str, str] = {
    "maxAcceleration": "max_acceleration",
    "comfortDeceleration": "comfort_deceleration",
    "desiredTimeHeadway": "desired_time_headway",
    "minimumGap": "minimum_gap",
    "idmDelta": "idm_delta",
    "maxLateralAcceleration": "max_lateral_acceleration",
    "laneChangeDuration": "lane_change_duration",
    "laneChangeMinDistance": "lane_change_min_distance",
    "politeness": "politeness",
}
_RANGE_OVERRIDES: Dict[str, str] = {
    "length": "length",
    "width": "width",
    "desiredSpeedFactor": "desired_speed_factor",
}


def _apply_overrides(
    profile: VehicleTypeProfile, overrides: Mapping[str, Any]
) -> VehicleTypeProfile:
    changes: Dict[str, Any] = {}
    for key, attr in _SCALAR_OVERRIDES.items():
        if overrides.get(key) is not None:
            changes[attr] = float(overrides[key])
    for key, attr in _RANGE_OVERRIDES.items():
        rng = _range(overrides.get(key))
        if rng is not None:
            changes[attr] = rng
    return replace(profile, **changes) if changes else profile


def _reference_car(veh_gen: Mapping[str, Any], config: Mapping[str, Any]) -> Any:
    """The car profile as the scenario's vehicleGeneration section defines it."""
    base = DEFAULT_PROFILES[CAR]
    changes: Dict[str, Any] = {
        "max_acceleration": float(veh_gen.get("maxAcceleration", 2.0)),
        "comfort_deceleration": float(veh_gen.get("comfortDeceleration", 3.0)),
        "desired_time_headway": float(veh_gen.get("desiredTimeHeadway", 1.5)),
        "minimum_gap": float(veh_gen.get("minimumGap", 2.0)),
        "idm_delta": float(veh_gen.get("idmDelta", 4.0)),
        "max_lateral_acceleration": resolve_max_lateral_acceleration(dict(config)),
    }
    length = _range(veh_gen.get("vehicleLength"))
    if length is not None:
        changes["length"] = length
    width = _range(veh_gen.get("vehicleWidth"))
    if width is not None:
        changes["width"] = width
    return replace(base, **changes)


def configured_mix(config: Mapping[str, Any]) -> Optional[Dict[str, float]]:
    """``vehicleGeneration.vehicleMix`` as {class: share}, or None if unset."""
    veh_gen = config.get("vehicleGeneration") or {}
    mix = veh_gen.get("vehicleMix") if isinstance(veh_gen, Mapping) else None
    if not isinstance(mix, Mapping):
        return None
    return {
        key: float(mix[key])
        for key in VEHICLE_CLASSES
        if isinstance(mix.get(key), (int, float)) and not isinstance(mix[key], bool)
    }


def resolve_vehicle_population(
    config: Mapping[str, Any],
) -> Optional[VehiclePopulation]:
    """The scenario's mixed vehicle population, or None for the legacy one.

    Classes with a zero share are left out entirely, so they consume no
    random draws.
    """
    mix = configured_mix(config)
    if mix is None:
        return None
    veh_gen = config.get("vehicleGeneration") or {}
    overrides_by_type = veh_gen.get("vehicleTypes") or {}

    base_lo, base_hi = resolve_desired_speed_range(dict(config))
    car_lo, car_hi = DESIRED_SPEED_LIMIT_FACTORS

    entries: List[Tuple[VehicleParams, float]] = []
    for type_id in VEHICLE_CLASSES:
        share = mix.get(type_id, 0.0)
        if not share > 0.0:
            continue
        profile = (
            _reference_car(veh_gen, config)
            if type_id == CAR
            else DEFAULT_PROFILES[type_id]
        )
        overrides = overrides_by_type.get(type_id)
        if isinstance(overrides, Mapping):
            profile = _apply_overrides(profile, overrides)

        # Desired speed relative to the scenario's car range: with no
        # explicit desiredSpeed that is exactly factor x speed limit; with an
        # explicit one, every class keeps its speed ratio to the car.
        f_lo, f_hi = profile.desired_speed_factor
        lo = base_lo * f_lo / car_lo
        hi = base_hi * f_hi / car_hi
        entries.append((VehicleParams(profile, (min(lo, hi), max(lo, hi))), share))

    if not entries:
        return None
    return VehiclePopulation(entries)


def vehicle_mix_errors(config: Mapping[str, Any]) -> List[str]:
    """Cross-field rules for vehicleMix / vehicleTypes (see config_validation)."""
    errors: List[str] = []
    veh_gen = config.get("vehicleGeneration") or {}
    if not isinstance(veh_gen, Mapping):
        return errors
    raw_mix = veh_gen.get("vehicleMix")
    if isinstance(raw_mix, Mapping):
        unknown = sorted(set(raw_mix) - set(VEHICLE_CLASSES))
        if unknown:
            errors.append(
                f"vehicleGeneration.vehicleMix has unknown vehicle classes "
                f"{unknown}; expected some of {list(VEHICLE_CLASSES)}"
            )
        mix = configured_mix(config) or {}
        if any(share < 0 for share in mix.values()):
            errors.append("vehicleGeneration.vehicleMix shares must be >= 0")
        total = sum(mix.values())
        if not total > 0:
            errors.append(
                "vehicleGeneration.vehicleMix must give at least one class "
                "a positive share"
            )
        elif abs(total - 1.0) > MIX_SUM_TOLERANCE:
            errors.append(
                f"vehicleGeneration.vehicleMix values must sum to 1.0 "
                f"(±{MIX_SUM_TOLERANCE}); got {total:g}"
            )
    types = veh_gen.get("vehicleTypes")
    if isinstance(types, Mapping):
        unknown = sorted(set(types) - set(VEHICLE_CLASSES))
        if unknown:
            errors.append(
                f"vehicleGeneration.vehicleTypes has unknown vehicle classes "
                f"{unknown}; expected some of {list(VEHICLE_CLASSES)}"
            )
        for type_id, overrides in types.items():
            if not isinstance(overrides, Mapping):
                continue
            for key in _RANGE_OVERRIDES:
                rng = _range(overrides.get(key))
                if rng is not None and rng[1] < rng[0]:
                    errors.append(
                        f"vehicleGeneration.vehicleTypes.{type_id}.{key}.max "
                        f"({rng[1]:g}) must be >= min ({rng[0]:g})"
                    )
            politeness = overrides.get("politeness")
            if isinstance(politeness, (int, float)) and not (
                0.0 <= float(politeness) <= 1.0
            ):
                errors.append(
                    f"vehicleGeneration.vehicleTypes.{type_id}.politeness must "
                    "be between 0 and 1"
                )
    return errors


def longest_vehicle_length(config: Mapping[str, Any]) -> float:
    """Longest vehicle the scenario can generate (m).

    The legacy population's longest car is vehicleLength.max (5.0 m by
    default); a mixed population's is the longest class in the mix.
    """
    population = resolve_vehicle_population(config)
    if population is not None:
        return population.max_length
    veh_gen = config.get("vehicleGeneration") or {}
    length = _range(veh_gen.get("vehicleLength"))
    return length[1] if length is not None else REFERENCE_VEHICLE_LENGTH


def long_vehicle_allowance(length: float) -> float:
    """Extra length (m) beyond the reference car — 0 for every legacy car."""
    if not math.isfinite(length):
        return 0.0
    return max(0.0, length - REFERENCE_VEHICLE_LENGTH)


def design_vehicle_allowance(config: Mapping[str, Any]) -> float:
    """How much longer than the 5 m reference car the longest vehicle of a
    *mixed* population is (0 for the legacy population, whose geometry is
    left exactly as in V1.0). See RoadNetwork.setup_default_intersection."""
    population = resolve_vehicle_population(config)
    if population is None:
        return 0.0
    return long_vehicle_allowance(population.max_length)
