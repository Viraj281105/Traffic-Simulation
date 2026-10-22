"""Driver aggression profiles (V3.0 ADR-016).

Simulation driver aggression profiles apply calibrated multipliers/offsets
on top of base vehicle class parameters across IDM car-following, vehicle launch/acceleration,
MOBIL lane changing, and gap acceptance.

Profiles:
- standard: Today's behavior bit for bit (multipliers 1.0, offsets 0.0).
- moderate: Headway x0.85, gap x0.875, accel x1.075, speed factor +0.025, politeness x0.75, threshold x0.75.
- high: Headway x0.70, gap x0.75, accel x1.15, speed factor +0.05, politeness x0.50, threshold x0.50.

Strict Invariants:
- Safe deceleration b_safe is unchanged at 4.0 m/s^2.
- Comfort deceleration b (3.0 m/s^2) and IDM exponent delta (4.0) are strictly unchanged.
- Roundabout internal safety margins (_EXIT_SAFETY_HEADWAY = 1.0s) are unmodified.
- high does NOT imply aggressiveTwoWheelers.
- Scientific disclaimer: "driver aggression — a simulation assumption, not a measurement of real-world driver behaviour".
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from typing import Any, Dict, Literal, Mapping, Tuple

from src.vehicles.vehicle_types import VehicleTypeProfile

DriverAggression = Literal["standard", "moderate", "high"]
DRIVER_AGGRESSION_PROFILES: Tuple[DriverAggression, ...] = (
    "standard",
    "moderate",
    "high",
)

DRIVER_AGGRESSION_DISCLAIMER: str = "driver aggression — a simulation assumption, not a measurement of real-world driver behaviour"

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


def resolve_aggression_name(config: Mapping[str, Any]) -> str:
    """Extract driverAggression profile name from scenario configuration, defaulting to 'standard'."""
    traffic = config.get("traffic")
    if isinstance(traffic, Mapping):
        val = traffic.get("driverAggression")
        if val in DRIVER_AGGRESSION_PROFILES:
            return str(val)
    return "standard"


def resolve_aggression_multipliers(profile_name: str | None) -> Dict[str, float]:
    """Return the multiplier mapping for a profile name. Unknown/None defaults to 'standard'."""
    if not profile_name or profile_name not in AGGRESSION_MULTIPLIERS:
        return AGGRESSION_MULTIPLIERS["standard"]
    return AGGRESSION_MULTIPLIERS[profile_name]


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

    speed_offset = m["speed_factor_offset"]
    f_lo, f_hi = profile.desired_speed_factor
    new_f_hi = min(1.10, f_hi + speed_offset)
    new_f_lo = min(new_f_hi, f_lo + speed_offset)

    return replace(
        profile,
        desired_time_headway=profile.desired_time_headway * m["headway_mult"],
        minimum_gap=profile.minimum_gap * m["gap_mult"],
        max_acceleration=profile.max_acceleration * m["accel_mult"],
        desired_speed_factor=(new_f_lo, new_f_hi),
        politeness=profile.politeness * m["politeness_mult"],
    )


def compute_aggression_parameter_hash(profile_name_or_config: Any = None) -> str:
    """Compute a canonical 16-hex SHA-256 hash of the resolved aggression profile and parameters."""
    if isinstance(profile_name_or_config, Mapping):
        name = resolve_aggression_name(profile_name_or_config)
    elif profile_name_or_config in DRIVER_AGGRESSION_PROFILES:
        name = str(profile_name_or_config)
    else:
        name = "standard"
    multipliers = resolve_aggression_multipliers(name)
    payload = {
        "profile": name,
        "multipliers": multipliers,
        "safe_deceleration": 4.0,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
