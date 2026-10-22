"""Driver aggression profiles (V3.0 ADR-016).

A profile is a set of multipliers/offsets applied on top of each vehicle
class's base values: IDM car-following (time headway T, standstill gap s0),
launch acceleration a, desired-speed factor, and the MOBIL lane-change
incentive (politeness, acceleration threshold).

Profiles:
- standard: Today's behaviour bit for bit (multipliers 1.0, offsets 0.0).
- moderate: Headway x0.85, gap x0.875, accel x1.075, speed factor +0.025, politeness x0.75, threshold x0.75.
- high: Headway x0.70, gap x0.75, accel x1.15, speed factor +0.05, politeness x0.50, threshold x0.50.

The desired-speed factor of every profile is capped at SPEED_FACTOR_CEILING
(1.10 x the speed limit); a class already at the cap stays there.

Strict Invariants:
- Safe deceleration b_safe is unchanged at 4.0 m/s^2.
- Comfort deceleration b (3.0 m/s^2) and IDM exponent delta (4.0) are strictly unchanged.
- Roundabout gap acceptance and internal safety margins (_EXIT_SAFETY_HEADWAY = 1.0 s) are unmodified.
- high does NOT imply aggressiveTwoWheelers.
- Scientific disclaimer: "driver aggression — a simulation assumption, not a measurement of real-world driver behaviour".

This module is the single owner of profile resolution: every engine
component reads the profile through ``aggression_multipliers_for``. An absent
or null profile is ``standard``; any other value that is not a profile name
raises ValueError, so a config that bypassed validation fails loudly instead
of silently running as ``standard``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from typing import Any, Dict, Literal, Mapping, Tuple

from src.vehicles.speed_profile import DESIRED_SPEED_LIMIT_FACTORS
from src.vehicles.vehicle_types import VehicleTypeProfile

DriverAggression = Literal["standard", "moderate", "high"]
DRIVER_AGGRESSION_PROFILES: Tuple[DriverAggression, ...] = (
    "standard",
    "moderate",
    "high",
)

DRIVER_AGGRESSION_DISCLAIMER: str = "driver aggression — a simulation assumption, not a measurement of real-world driver behaviour"

# Upper bound of any class's desired-speed factor under any profile.
SPEED_FACTOR_CEILING: float = 1.10
# MOBIL safe deceleration (m/s^2); no profile changes it.
SAFE_DECELERATION: float = 4.0

# Validated ADR-016 multipliers
AGGRESSION_MULTIPLIERS: Dict[str, Dict[str, float]] = {
    "standard": {
        "headway_mult": 1.0,
        "gap_mult": 1.0,
        "accel_mult": 1.0,
        "speed_factor_offset": 0.0,
        "politeness_mult": 1.0,
        "threshold_mult": 1.0,
    },
    "moderate": {
        "headway_mult": 0.85,
        "gap_mult": 0.875,
        "accel_mult": 1.075,
        "speed_factor_offset": 0.025,
        "politeness_mult": 0.75,
        "threshold_mult": 0.75,
    },
    "high": {
        "headway_mult": 0.70,
        "gap_mult": 0.75,
        "accel_mult": 1.15,
        "speed_factor_offset": 0.05,
        "politeness_mult": 0.50,
        "threshold_mult": 0.50,
    },
}


def _profile_name(value: Any) -> str:
    """A profile name, 'standard' when absent; ValueError for anything else."""
    if value is None:
        return "standard"
    if isinstance(value, str) and value in AGGRESSION_MULTIPLIERS:
        return value
    raise ValueError(
        f"traffic.driverAggression {value!r} is invalid; "
        "expected 'standard', 'moderate', or 'high'"
    )


def resolve_aggression_name(config: Mapping[str, Any]) -> str:
    """The driverAggression profile of an engine configuration, 'standard' when absent."""
    traffic = config.get("traffic")
    if not isinstance(traffic, Mapping):
        return "standard"
    return _profile_name(traffic.get("driverAggression"))


def resolve_aggression_multipliers(profile_name: str | None) -> Dict[str, float]:
    """A copy of the multiplier mapping of a profile; None means 'standard'."""
    return dict(AGGRESSION_MULTIPLIERS[_profile_name(profile_name)])


def aggression_multipliers_for(config: Mapping[str, Any]) -> Dict[str, float]:
    """The multipliers of an engine configuration's profile."""
    return resolve_aggression_multipliers(resolve_aggression_name(config))


def stop_line_margin(minimum_gap: float, multipliers: Mapping[str, float]) -> float:
    """Extra distance a vehicle keeps from a stop line under a profile (ADR-019).

    ``minimum_gap`` is the vehicle's standstill gap *under the profile*. The
    profile shortens the gap to the vehicle ahead, not where a driver stops at
    a line, so against a line the vehicle keeps its unscaled gap: the margin
    is the difference. 0.0 for ``standard``. The stop lines and junction
    clearances were laid out for the unscaled gap; without this a head
    vehicle under ``high`` waited 0.5 m closer to the box, inside the swept
    corridor of turning traffic, which then stopped for it mid-junction.
    """
    gap_mult = multipliers["gap_mult"]
    if gap_mult == 1.0:
        return 0.0
    return minimum_gap / gap_mult - minimum_gap


def _speed_factors(factors: Tuple[float, float], offset: float) -> Tuple[float, float]:
    f_lo, f_hi = factors
    new_f_hi = min(SPEED_FACTOR_CEILING, f_hi + offset)
    new_f_lo = min(new_f_hi, f_lo + offset)
    return new_f_lo, new_f_hi


def apply_aggression_to_profile(
    profile: VehicleTypeProfile, profile_name: str | None
) -> VehicleTypeProfile:
    """Apply aggression multipliers on top of a base vehicle type profile."""
    m = resolve_aggression_multipliers(profile_name)
    if (
        m["headway_mult"] == 1.0
        and m["gap_mult"] == 1.0
        and m["accel_mult"] == 1.0
        and m["speed_factor_offset"] == 0.0
        and m["politeness_mult"] == 1.0
    ):
        return profile

    return replace(
        profile,
        desired_time_headway=profile.desired_time_headway * m["headway_mult"],
        minimum_gap=profile.minimum_gap * m["gap_mult"],
        max_acceleration=profile.max_acceleration * m["accel_mult"],
        desired_speed_factor=_speed_factors(
            profile.desired_speed_factor, m["speed_factor_offset"]
        ),
        politeness=profile.politeness * m["politeness_mult"],
    )


def apply_aggression_to_speed_range(
    speed_range: Tuple[float, float], profile_name: str | None
) -> Tuple[float, float]:
    """The legacy cars-only desired-speed range under a profile.

    Scaled exactly as resolve_vehicle_population scales the car class, so a
    scenario without a vehicle mix and one with ``{car: 1.0}`` get the same
    speeds under every profile. ``standard`` returns the range untouched.
    """
    m = resolve_aggression_multipliers(profile_name)
    if m["speed_factor_offset"] == 0.0:
        return speed_range
    car_lo, car_hi = DESIRED_SPEED_LIMIT_FACTORS
    f_lo, f_hi = _speed_factors(DESIRED_SPEED_LIMIT_FACTORS, m["speed_factor_offset"])
    base_lo, base_hi = speed_range
    lo = base_lo * f_lo / car_lo
    hi = base_hi * f_hi / car_hi
    return min(lo, hi), max(lo, hi)


def compute_aggression_parameter_hash(profile_name_or_config: Any = None) -> str:
    """Canonical 16-hex SHA-256 hash of the resolved profile: its multipliers and the bounds applied with them."""
    if isinstance(profile_name_or_config, Mapping):
        name = resolve_aggression_name(profile_name_or_config)
    else:
        name = _profile_name(profile_name_or_config)
    payload = {
        "profile": name,
        "multipliers": AGGRESSION_MULTIPLIERS[name],
        "safe_deceleration": SAFE_DECELERATION,
        "speed_factor_ceiling": SPEED_FACTOR_CEILING,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
