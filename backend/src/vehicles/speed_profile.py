"""Speed assumptions shared by every geometry.

Two rules live here, and they apply identically to the signalised junction
and the roundabout, because the vehicle population is the same in both:

1. **Desired speed follows the road's speed limit.** Unless a scenario sets
   ``vehicleGeneration.desiredSpeed`` explicitly, drivers want to travel at
   ``DESIRED_SPEED_LIMIT_FACTORS`` × ``roads.speedLimit`` (default limit
   13.89 m/s = 50 km/h, so 11.8-14.6 m/s). The limit used to be accepted,
   validated and documented but never read: every vehicle drew a desired speed
   of 18-25 m/s (65-90 km/h) regardless of it.

2. **Curves are taken at a speed the same lateral-acceleration limit allows.**
   On any curved connection lane a vehicle's speed is limited to
   ``sqrt(a_lat · R)``, where R is the path radius, and it brakes for the curve
   at its comfortable deceleration before reaching it. This held for nothing
   at the signal before — turning vehicles went through a 5-9 m radius turn at
   whatever speed they had, often over 10 m/s (more than 2 g) — while the
   roundabout was slowed by its own entry and circulating caps. One rule for
   both is what makes their travel times comparable.

The default ``DEFAULT_MAX_LATERAL_ACCELERATION`` of 3.0 m/s^2 is the value the
FHWA/NCHRP 672 fastest-path speed-radius relationship implies at roundabout and
urban-turn radii (V = 8.76·R^0.3673 km/h with e = -0.02 gives 2.9 m/s^2 at
R = 15 m and 3.2 m/s^2 at R = 10 m). It is a model input, not a finding.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_SPEED_LIMIT: float = 13.89
DESIRED_SPEED_LIMIT_FACTORS: Tuple[float, float] = (0.85, 1.05)
DEFAULT_MAX_LATERAL_ACCELERATION: float = 3.0

# Curvature is measured between points this far either side of each sample
# (metres of path). Drivers follow a smoothed line, not the polyline's
# vertices, and a chord of about one vehicle length removes the artificial
# kinks where a straight stub meets an arc without flattening real curves.
_CURVATURE_HALF_CHORD: float = 5.0
# Sampling step along a lane (metres).
_SAMPLE_STEP: float = 1.0
_UNLIMITED: float = math.inf


def resolve_speed_limit(config: Dict[str, Any]) -> float:
    roads = config.get("roads") or {}
    try:
        limit = float(roads.get("speedLimit", DEFAULT_SPEED_LIMIT))
    except (TypeError, ValueError):
        limit = DEFAULT_SPEED_LIMIT
    return limit if limit > 0 else DEFAULT_SPEED_LIMIT


def resolve_desired_speed_range(config: Dict[str, Any]) -> Tuple[float, float]:
    """(min, max) desired speed: explicit config wins, else the speed limit."""
    veh_gen = config.get("vehicleGeneration") or {}
    explicit = veh_gen.get("desiredSpeed")
    if isinstance(explicit, dict) and "min" in explicit and "max" in explicit:
        return float(explicit["min"]), float(explicit["max"])
    limit = resolve_speed_limit(config)
    lo, hi = DESIRED_SPEED_LIMIT_FACTORS
    return limit * lo, limit * hi


def resolve_max_lateral_acceleration(config: Dict[str, Any]) -> float:
    veh_gen = config.get("vehicleGeneration") or {}
    try:
        value = float(
            veh_gen.get("maxLateralAcceleration", DEFAULT_MAX_LATERAL_ACCELERATION)
        )
    except (TypeError, ValueError):
        value = DEFAULT_MAX_LATERAL_ACCELERATION
    return value if value > 0 else DEFAULT_MAX_LATERAL_ACCELERATION


def _radius(
    a: Tuple[float, float], b: Tuple[float, float], c: Tuple[float, float]
) -> float:
    """Circumradius of three points (inf when they are collinear)."""
    ab = math.hypot(b[0] - a[0], b[1] - a[1])
    bc = math.hypot(c[0] - b[0], c[1] - b[1])
    ca = math.hypot(a[0] - c[0], a[1] - c[1])
    cross = abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]))
    if cross < 1e-9:
        return _UNLIMITED
    return (ab * bc * ca) / (2.0 * cross)


def curve_speed_samples(lane: Any, max_lateral_accel: float) -> List[float]:
    """Curve speed limit at each ``_SAMPLE_STEP`` along ``lane``.

    Straight lanes (two waypoints) return an empty list: nothing to limit.
    """
    waypoints = getattr(lane, "waypoints", None)
    if not waypoints or len(waypoints) <= 2:
        return []
    length = float(lane.length)
    n = max(1, int(math.ceil(length / _SAMPLE_STEP)))
    samples: List[float] = []
    for i in range(n + 1):
        s = min(length, i * _SAMPLE_STEP)
        a = lane.get_point_at_distance(max(0.0, s - _CURVATURE_HALF_CHORD))
        b = lane.get_point_at_distance(s)
        c = lane.get_point_at_distance(min(length, s + _CURVATURE_HALF_CHORD))
        r = _radius(a, b, c)
        samples.append(
            _UNLIMITED if r == _UNLIMITED else math.sqrt(max_lateral_accel * r)
        )
    return samples


class _LaneEnvelope:
    """Highest speed from which a vehicle can still meet every curve ahead
    on this lane, braking at ``decel``: ``min over s' >= s of
    sqrt(v_curve(s')^2 + 2·decel·(s' - s))``, sampled every metre."""

    __slots__ = ("values", "entry")

    def __init__(self, samples: List[float], decel: float) -> None:
        values = list(samples)
        for i in range(len(values) - 2, -1, -1):
            nxt = values[i + 1]
            if nxt != _UNLIMITED:
                reach = math.sqrt(nxt * nxt + 2.0 * decel * _SAMPLE_STEP)
                if reach < values[i]:
                    values[i] = reach
        self.values = values
        self.entry = values[0] if values else _UNLIMITED

    def at(self, position: float) -> float:
        if not self.values:
            return _UNLIMITED
        idx = int(position / _SAMPLE_STEP)
        if idx < 0:
            idx = 0
        if idx >= len(self.values) - 1:
            return self.values[-1]
        # Conservative: the tighter of the two neighbouring samples.
        return min(self.values[idx], self.values[idx + 1])


def _envelope(lane: Any, max_lateral_accel: float, decel: float) -> _LaneEnvelope:
    key = (max_lateral_accel, decel)
    cache: Optional[Dict[Tuple[float, float], _LaneEnvelope]] = getattr(
        lane, "_speed_envelope_cache", None
    )
    if cache is None:
        cache = {}
        try:
            lane._speed_envelope_cache = cache
        except AttributeError:
            return _LaneEnvelope(curve_speed_samples(lane, max_lateral_accel), decel)
    env = cache.get(key)
    if env is None:
        env = _LaneEnvelope(curve_speed_samples(lane, max_lateral_accel), decel)
        cache[key] = env
    return env


def curve_speed_ceiling(vehicle: Any, max_lateral_accel: float, decel: float) -> float:
    """Speed ceiling for ``vehicle`` from the curves on the rest of its route.

    Looks along the current lane and the next lane of the route (routes are
    incoming -> connection -> outgoing, so the next lane is the only other one
    that can hold a curve within braking distance).
    """
    lane = getattr(vehicle, "lane", None)
    if lane is None:
        return _UNLIMITED
    ceiling = _envelope(lane, max_lateral_accel, decel).at(vehicle.position)
    route = getattr(vehicle, "route", None) or []
    try:
        idx = route.index(lane)
    except ValueError:
        return ceiling
    if idx + 1 < len(route):
        nxt_entry = _envelope(route[idx + 1], max_lateral_accel, decel).entry
        if nxt_entry != _UNLIMITED:
            remaining = max(0.0, lane.length - vehicle.position)
            ceiling = min(
                ceiling, math.sqrt(nxt_entry * nxt_entry + 2.0 * decel * remaining)
            )
    return ceiling
