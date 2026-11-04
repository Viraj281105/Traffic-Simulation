"""Fuel / CO2 estimates and time-to-collision from trajectories (pure functions).

ESTIMATES AND PROXIES, NOT MEASUREMENTS
---------------------------------------
Emissions reuse the speed/idle/acceleration fuel model documented in
``definitions/environmental_estimates.py``::

    fuel_rate (L/s) = a0 + a1 * v + a2 * max(accel, 0)       CO2 = 2.31 kg/L

so a stopped vehicle burns the idle rate, and braking burns only that. A
generic petrol car is assumed; no vehicle class, grade, cold start or
electrification. Outputs must be labelled "estimated".

Acceleration is the forward difference of consecutive speed samples (the first
sample uses 0). Each speed sample is held for ``dt`` seconds. A sample counts as
idling when speed < ``IDLE_SPEED_MPS``.

Time-to-collision (TTC) for a follower behind a leader on the same lane::

    closing = v_follower - v_leader
    TTC = gap / closing        if closing > 0 and gap > 0
    TTC = 0                    if gap <= 0 (already touching)
    TTC undefined (None)       if the pair is not closing

where ``gap`` is bumper-to-bumper distance in metres. TTC is a surrogate
safety PROXY: constant speeds are assumed and it does not predict crashes.
Summary measures (threshold default 1.5 s, matching the engine's
``ttcThresholdSeconds``):

* ``minTtcS``  smallest defined TTC;
* ``timeExposedTtcS`` (TET)  seconds with TTC below the threshold;
* ``timeIntegratedTtcS`` (TIT)  sum of (threshold - TTC) * dt over those samples;
* ``conflictEvents``  separate episodes: a run of consecutive below-threshold
  samples in one pair counts once, so one long close call is one event.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Mapping, Optional, Sequence

from src.metrics.definitions.environmental_estimates import (
    estimate_co2_kg,
    estimate_fuel_liters_per_vehicle_per_tick,
)

IDLE_SPEED_MPS = 0.1
DEFAULT_TTC_THRESHOLD_S = 1.5
_MIN_CLOSING_SPEED_MPS = 0.1

EMISSIONS_LABEL = (
    "Model estimate from a simple speed/idle fuel model, not a measurement."
)
SAFETY_LABEL = "Surrogate safety proxy (constant-speed TTC), not a crash prediction."


def trajectory_emissions(speeds_mps: Sequence[float], dt: float) -> Dict[str, Any]:
    """Estimated fuel and CO2 for one vehicle's speed samples (one per ``dt`` s)."""
    if not (math.isfinite(dt) and dt > 0.0):
        raise ValueError("dt must be a positive number of seconds")
    fuel = 0.0
    distance = 0.0
    idle_s = 0.0
    prev: Optional[float] = None
    for raw in speeds_mps:
        v = max(0.0, float(raw)) if math.isfinite(raw) else 0.0
        accel = 0.0 if prev is None else (v - prev) / dt
        fuel += estimate_fuel_liters_per_vehicle_per_tick(v, accel, dt)
        distance += v * dt
        if v < IDLE_SPEED_MPS:
            idle_s += dt
        prev = v
    co2 = estimate_co2_kg(fuel)
    km = distance / 1000.0
    return {
        "samples": len(speeds_mps),
        "durationS": len(speeds_mps) * dt,
        "distanceM": distance,
        "idleTimeS": idle_s,
        "fuelLiters": fuel,
        "co2Kg": co2,
        # Intensities are undefined (None) when the vehicle barely moved.
        "fuelLPer100Km": (fuel / km * 100.0) if km >= 0.01 else None,
        "co2GPerKm": (co2 * 1000.0 / km) if km >= 0.01 else None,
    }


def summarize_emissions(
    trajectories: Sequence[Sequence[float]], dt: float
) -> Dict[str, Any]:
    """Totals and fleet intensity over several vehicles' speed samples."""
    per = [trajectory_emissions(t, dt) for t in trajectories]
    fuel = math.fsum(p["fuelLiters"] for p in per)
    co2 = math.fsum(p["co2Kg"] for p in per)
    dist = math.fsum(p["distanceM"] for p in per)
    idle = math.fsum(p["idleTimeS"] for p in per)
    total_t = math.fsum(p["durationS"] for p in per)
    km = dist / 1000.0
    return {
        "vehicles": len(per),
        "fuelLiters": fuel,
        "co2Kg": co2,
        "distanceKm": km,
        "idleTimeS": idle,
        "idleShare": (idle / total_t) if total_t > 0.0 else None,
        "fuelLPer100Km": (fuel / km * 100.0) if km >= 0.01 else None,
        "co2GPerKm": (co2 * 1000.0 / km) if km >= 0.01 else None,
        "isEstimate": True,
        "label": EMISSIONS_LABEL,
    }


def time_to_collision(
    gap_m: float, follower_speed_mps: float, leader_speed_mps: float
) -> Optional[float]:
    """TTC in seconds for a follower and leader, or None when not closing."""
    if gap_m <= 0.0:
        return 0.0
    closing = follower_speed_mps - leader_speed_mps
    if closing < _MIN_CLOSING_SPEED_MPS:
        return None
    return gap_m / closing


def summarize_ttc(
    pairs: Sequence[Sequence[Mapping[str, float]]],
    dt: float,
    threshold_s: float = DEFAULT_TTC_THRESHOLD_S,
) -> Dict[str, Any]:
    """TTC safety proxies over leader-follower pairs.

    ``pairs`` holds one series per pair; each sample has ``gapM``,
    ``followerSpeedMps`` and ``leaderSpeedMps``, taken every ``dt`` seconds.
    """
    if not (math.isfinite(dt) and dt > 0.0):
        raise ValueError("dt must be a positive number of seconds")
    if not (math.isfinite(threshold_s) and threshold_s > 0.0):
        raise ValueError("threshold_s must be positive")
    ttcs: List[float] = []
    below = 0
    tit = 0.0
    events = 0
    samples = 0
    for series in pairs:
        in_event = False
        for s in series:
            samples += 1
            ttc = time_to_collision(
                float(s["gapM"]),
                float(s["followerSpeedMps"]),
                float(s["leaderSpeedMps"]),
            )
            if ttc is None:
                in_event = False
                continue
            ttcs.append(ttc)
            if ttc < threshold_s:
                below += 1
                tit += (threshold_s - ttc) * dt
                if not in_event:
                    events += 1
                in_event = True
            else:
                in_event = False
    return {
        "pairs": len(pairs),
        "samples": samples,
        "observations": len(ttcs),
        "thresholdS": threshold_s,
        "minTtcS": min(ttcs) if ttcs else None,
        "meanTtcS": (math.fsum(ttcs) / len(ttcs)) if ttcs else None,
        "timeExposedTtcS": below * dt,
        "timeIntegratedTtcS": tit,
        "conflictEvents": events,
        "isProxy": True,
        "label": SAFETY_LABEL,
    }
