"""Delay and travel-time metrics from per-vehicle trip records (pure functions).

Definitions
-----------
    travel time  T = exit time - entry time                       (s)
    free-flow    T0 = distance / desired speed                    (s)
                 (or supplied directly as ``freeFlowTimeS``)
    trip delay   D = max(0, T - T0)                               (s)
    planning time index  PTI = p95(T) / median(T)                 (-)
    delay ratio  = sum(D) / sum(T)                                (-)
    total delay  = sum(D) / 3600                                  (vehicle-hours)

Assumptions
-----------
* The free-flow time is the time the same journey takes at the driver's own
  desired speed with no interaction, matching the engine's ``averageDelay``.
  Delay therefore includes slowing the layout itself forces.
* Percentiles use linear interpolation between order statistics.
* Records with a non-finite or negative time, or no usable free-flow time,
  are skipped and counted in ``skipped``; nothing is invented for them.
* Below ``MIN_RELIABLE_SAMPLE_SIZE`` trips the percentiles are flagged
  ``lowSample`` (same cut-off as the planning time index).
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Mapping, Optional, Sequence

MIN_RELIABLE_SAMPLE_SIZE = 20


def free_flow_time(distance_m: float, desired_speed_mps: float) -> Optional[float]:
    """Seconds to cover ``distance_m`` at ``desired_speed_mps``; None if undefined."""
    if not (math.isfinite(distance_m) and math.isfinite(desired_speed_mps)):
        return None
    if distance_m < 0.0 or desired_speed_mps <= 0.0:
        return None
    return distance_m / desired_speed_mps


def trip_delay(travel_time_s: float, free_flow_time_s: float) -> float:
    """Delay of one trip in seconds, never negative."""
    return max(0.0, travel_time_s - free_flow_time_s)


def percentile(values: Sequence[float], p: float) -> Optional[float]:
    """Linear-interpolation percentile (``p`` in 0..100); None for no values."""
    if not values:
        return None
    s = sorted(values)
    k = (len(s) - 1) * (p / 100.0)
    lo, hi = math.floor(k), math.ceil(k)
    if lo == hi:
        return s[int(k)]
    return s[lo] * (hi - k) + s[hi] * (k - lo)


def _number(record: Mapping[str, Any], key: str) -> Optional[float]:
    v = record.get(key)
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return float(v) if math.isfinite(v) else None


def _free_flow_of(record: Mapping[str, Any]) -> Optional[float]:
    direct = _number(record, "freeFlowTimeS")
    if direct is not None:
        return direct if direct >= 0.0 else None
    d, v = _number(record, "distanceM"), _number(record, "desiredSpeedMps")
    if d is None or v is None:
        return None
    return free_flow_time(d, v)


def summarize_trips(trips: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """Travel-time and delay summary of ``trips``.

    Each trip is a mapping with ``travelTimeS`` and either ``freeFlowTimeS`` or
    both ``distanceM`` and ``desiredSpeedMps``. Statistics are ``None`` when no
    valid trip exists.
    """
    times: List[float] = []
    delays: List[float] = []
    skipped = 0
    for rec in trips:
        t = _number(rec, "travelTimeS")
        t0 = _free_flow_of(rec)
        if t is None or t < 0.0 or t0 is None:
            skipped += 1
            continue
        times.append(t)
        delays.append(trip_delay(t, t0))

    n = len(times)
    out: Dict[str, Any] = {
        "n": n,
        "skipped": skipped,
        "lowSample": n < MIN_RELIABLE_SAMPLE_SIZE,
        "meanTravelTimeS": None,
        "medianTravelTimeS": None,
        "p95TravelTimeS": None,
        "planningTimeIndex": None,
        "meanDelayS": None,
        "medianDelayS": None,
        "p95DelayS": None,
        "maxDelayS": None,
        "totalDelayVehicleHours": 0.0,
        "delayRatio": None,
    }
    if n == 0:
        return out
    total_t, total_d = math.fsum(times), math.fsum(delays)
    median_t = percentile(times, 50.0)
    p95_t = percentile(times, 95.0)
    assert median_t is not None and p95_t is not None
    out.update(
        meanTravelTimeS=total_t / n,
        medianTravelTimeS=median_t,
        p95TravelTimeS=p95_t,
        # A zero median is a data error, so no ratio is invented.
        planningTimeIndex=(p95_t / median_t) if median_t else None,
        meanDelayS=total_d / n,
        medianDelayS=percentile(delays, 50.0),
        p95DelayS=percentile(delays, 95.0),
        maxDelayS=max(delays),
        totalDelayVehicleHours=total_d / 3600.0,
        delayRatio=(total_d / total_t) if total_t > 0.0 else None,
    )
    return out
