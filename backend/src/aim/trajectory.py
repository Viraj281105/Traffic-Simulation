"""Trajectory coordination: speed profiles that hit a reserved entry time.

Positions are the distance ``x`` of the vehicle front along its lane, with
``x = 0`` at the box entry line (negative on the approach). A plan is a
sequence of constant-acceleration segments ending at ``x = 0`` at exactly
``t_entry`` with the movement's box speed, after which the vehicle holds that
speed through the box. Accelerations are bounded by ``KinParams``.

Two profile families:

* cruise: change speed to a cruise speed ``u``, hold, change to the box speed
  (``u`` is solved by bisection so the duration matches the slot exactly);
* stop-and-go: cruise, brake to rest at the queue position ``xs``, wait, then
  launch to arrive at the slot (used when the slot is too far away to absorb
  by cruising slowly, e.g. behind a red signal or a long reservation).
"""

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

Segment = Tuple[float, float, float, float, float]  # t0, x0, v0, accel, duration


@dataclass(frozen=True)
class KinParams:
    vmax: float = 13.9
    accel: float = 2.0
    decel: float = 3.0  # hard bound on braking
    comfort_decel: float = 2.5  # used by the unreserved default behaviour
    min_cruise: float = 3.0
    standstill_gap: float = 2.0
    approach_length: float = 150.0
    box_speed_straight: float = 10.0
    box_speed_turn: float = 5.0

    def box_speed(self, movement: str) -> float:
        return (
            self.box_speed_straight if movement == "straight" else self.box_speed_turn
        )


@dataclass(frozen=True)
class Plan:
    t_start: float
    segments: Tuple[Segment, ...]
    t_entry: float
    exit_speed: float
    stops: bool

    def state(self, t: float) -> Tuple[float, float]:
        """``(x, v)`` at time ``t`` (constant box speed after the last segment)."""
        last_t, last_x, last_v = self.t_start, 0.0, self.exit_speed
        for t0, x0, v0, a, dur in self.segments:
            if t <= t0 + dur:
                dt = max(0.0, t - t0)
                return x0 + v0 * dt + 0.5 * a * dt * dt, v0 + a * dt
            last_t = t0 + dur
            last_x = x0 + v0 * dur + 0.5 * a * dur * dur
            last_v = v0 + a * dur
        return last_x + last_v * (t - last_t), last_v


def _legs(d: float, vs: float, ve: float, u: float, p: KinParams) -> Tuple[float, ...]:
    """Durations/distances of speed change, cruise and speed change."""
    r1 = p.accel if u >= vs else p.decel
    r3 = p.accel if ve >= u else p.decel
    t1, t3 = abs(u - vs) / r1, abs(ve - u) / r3
    d1, d3 = 0.5 * (vs + u) * t1, 0.5 * (u + ve) * t3
    d2 = d - d1 - d3
    return t1, d2, t3, (d2 / u if u > 0 else math.inf)


def _cruise_time(d: float, vs: float, ve: float, u: float, p: KinParams) -> float:
    t1, _, t3, t2 = _legs(d, vs, ve, u, p)
    return t1 + t2 + t3


def _top_speed(d: float, vs: float, ve: float, p: KinParams) -> Optional[float]:
    """Highest cruise speed (<= vmax) that fits in ``d``; None if none does."""
    floor = min(max(vs, ve), p.vmax)
    if _legs(d, vs, ve, p.vmax, p)[1] >= 0:
        return p.vmax
    if _legs(d, vs, ve, floor, p)[1] < 0:
        return None
    lo, hi = floor, p.vmax
    for _ in range(50):
        mid = 0.5 * (lo + hi)
        if _legs(d, vs, ve, mid, p)[1] >= 0:
            lo = mid
        else:
            hi = mid
    return lo


def _cruise_segments(
    t: float, x: float, d: float, vs: float, ve: float, u: float, p: KinParams
) -> List[Segment]:
    t1, d2, t3, t2 = _legs(d, vs, ve, u, p)
    out: List[Segment] = []
    cur_t, cur_x = t, x
    for v0, a, dur in (
        (vs, p.accel if u >= vs else -p.decel, t1),
        (u, 0.0, t2),
        (u, p.accel if ve >= u else -p.decel, t3),
    ):
        if dur > 1e-12:
            out.append((cur_t, cur_x, v0, a, dur))
            cur_x += v0 * dur + 0.5 * a * dur * dur
            cur_t += dur
    return out


def _solve_cruise(
    d: float, vs: float, ve: float, duration: float, p: KinParams
) -> Optional[float]:
    """Cruise speed whose profile takes exactly ``duration`` (None if impossible)."""
    top = _top_speed(d, vs, ve, p)
    if top is None or duration < _cruise_time(d, vs, ve, top, p) - 1e-9:
        return None
    lo = p.min_cruise
    if lo >= top or _legs(d, vs, ve, lo, p)[1] < 0:
        return top if abs(duration - _cruise_time(d, vs, ve, top, p)) < 1e-6 else None
    if duration > _cruise_time(d, vs, ve, lo, p) + 1e-9:
        return None
    hi = top
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if _cruise_time(d, vs, ve, mid, p) > duration:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def _stop_go(
    x: float,
    v: float,
    now: float,
    t_entry: Optional[float],
    vf: float,
    xs_max: float,
    p: KinParams,
) -> Optional[Plan]:
    """Brake to rest at ``xs``, wait, launch. ``t_entry=None`` returns the
    earliest feasible plan."""
    moving = v > 0.05
    xs = min(xs_max, -vf * vf / (2 * p.accel))
    if not moving:
        xs, v = x, 0.0
    segs: List[Segment] = []
    t = now
    if moving:
        cruise = (xs - x) - v * v / (2 * p.decel)
        if cruise < -1e-9:
            return None
        if cruise > 1e-12:
            segs.append((t, x, v, 0.0, cruise / v))
            t += cruise / v
        segs.append((t, x + max(cruise, 0.0), v, -p.decel, v / p.decel))
        t += v / p.decel
    d2 = -xs
    top = _top_speed(d2, 0.0, vf, p)
    if top is None:
        return None
    launch = _cruise_time(d2, 0.0, vf, top, p)
    earliest = t + launch
    entry = earliest if t_entry is None else t_entry
    if entry < earliest - 1e-9:
        return None
    wait = entry - earliest
    if wait > 1e-12:
        segs.append((t, xs, 0.0, 0.0, wait))
        t += wait
    segs.extend(_cruise_segments(t, xs, d2, 0.0, vf, top, p))
    return Plan(now, tuple(segs), entry, vf, True)


def min_entry_time(
    x: float, v: float, now: float, vf: float, xs_max: float, p: KinParams
) -> Optional[float]:
    """Earliest time the front can reach ``x = 0`` at speed ``vf``."""
    if v > 0.05:
        top = _top_speed(-x, v, vf, p)
        if top is not None:
            return now + _cruise_time(-x, v, vf, top, p)
    plan = _stop_go(x, v, now, None, vf, xs_max, p)
    return None if plan is None else plan.t_entry


def plan_for(
    x: float,
    v: float,
    now: float,
    t_entry: float,
    vf: float,
    xs_max: float,
    p: KinParams,
) -> Optional[Plan]:
    """A profile from state ``(x, v)`` at ``now`` reaching ``x = 0`` at exactly
    ``t_entry`` with speed ``vf``; None if the slot is infeasible."""
    if x >= 0 or t_entry <= now:
        return None
    if v > 0.05:
        u = _solve_cruise(-x, v, vf, t_entry - now, p)
        if u is not None:
            segs = _cruise_segments(now, x, -x, v, vf, u, p)
            return Plan(now, tuple(segs), t_entry, vf, False)
    return _stop_go(x, v, now, t_entry, vf, xs_max, p)
