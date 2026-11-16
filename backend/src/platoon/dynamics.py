"""Longitudinal vehicle laws: IDM (human) and CACC (cooperative).

Both are textbook models, used here as ESTIMATES: a single lane, point-mass
vehicles, no actuator lag, no grade. ``gap`` is bumper to bumper in metres.

IDM (Treiber et al.)::

    a = A * (1 - (v/v0)^4 - (s*/gap)^2)
    s* = s0 + max(0, v*T + v*dv / (2*sqrt(A*B)))      dv = v - v_leader

CACC (predecessor following with the leader's acceleration received by
message)::

    d_des = standstill + time_gap * v
    a = ka * a_leader_msg + kv * (v_leader - v) + kg * (gap - d_des)
    a clamped to [-b_max, a_max]

The speed and gap come from the vehicle's own radar (no delay); only the
leader's acceleration travels over the channel. Without a fresh message the
caller passes ``a_leader_msg = 0`` (and the controller normally falls back to
IDM, see ``sim``).
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class IDMParams:
    v0: float = 33.3  # desired speed, m/s
    time_gap: float = 1.5  # T, s
    min_gap: float = 2.0  # s0, m
    a_max: float = 1.4  # A, m/s^2
    b_comf: float = 2.0  # B, m/s^2
    length: float = 4.5  # m


@dataclass(frozen=True)
class CACCParams:
    time_gap: float = 0.6  # h, s
    standstill: float = 2.0  # m
    kg: float = 0.25  # gap error gain, 1/s^2
    kv: float = 0.7  # speed error gain, 1/s
    ka: float = 1.0  # feed-forward of the leader's acceleration (message)
    a_max: float = 2.0  # m/s^2, bounded acceleration
    b_max: float = 4.0  # m/s^2, bounded (comfort) deceleration
    v_max: float = 40.0  # m/s


def idm_accel(v: float, gap: float, dv: float, p: IDMParams) -> float:
    """IDM acceleration; ``dv`` is v - v_leader (positive when closing)."""
    gap = max(gap, 0.01)
    s_star = p.min_gap + max(
        0.0, v * p.time_gap + v * dv / (2.0 * math.sqrt(p.a_max * p.b_comf))
    )
    return p.a_max * (1.0 - (v / p.v0) ** 4 - (s_star / gap) ** 2)


def idm_free_accel(v: float, p: IDMParams) -> float:
    """IDM acceleration with no leader."""
    return p.a_max * (1.0 - (v / p.v0) ** 4)


def idm_equilibrium_gap(v: float, p: IDMParams) -> float:
    """Gap at which IDM holds speed ``v`` with a leader at the same speed."""
    ratio = (v / p.v0) ** 4
    if ratio >= 1.0:
        raise ValueError("speed must be below the desired speed v0")
    return (p.min_gap + v * p.time_gap) / math.sqrt(1.0 - ratio)


def cacc_desired_gap(v: float, p: CACCParams) -> float:
    return p.standstill + p.time_gap * v


def cacc_accel(
    v: float, gap: float, v_lead: float, a_lead_msg: float, p: CACCParams
) -> float:
    """CACC acceleration, bounded to [-b_max, a_max]."""
    a = p.ka * a_lead_msg + p.kv * (v_lead - v) + p.kg * (gap - cacc_desired_gap(v, p))
    return min(p.a_max, max(-p.b_max, a))
