"""String stability and steady-state throughput (estimates).

String stability: the lead vehicle brakes in a mild pulse; the peak absolute
speed deviation from the cruise speed is measured for every vehicle. With
``peak[k]`` the peak of vehicle k,

* ``stepRatioMax``  = max over k >= 1 of peak[k] / peak[k-1];
* ``amplification`` = peak[last] / peak[0]  (end-to-end);
* ``stable``        = stepRatioMax <= 1 (perturbations do not grow down the string).

Throughput at steady state (all vehicles at ``speed``, equal gaps)::

    q = 3600 * speed / (length + gap_eq)     vehicles per hour per lane

with gap_eq = standstill + time_gap * speed for CACC and the IDM equilibrium
gap for human drivers. A capacity-style upper estimate: it ignores lane
changes, signals and the gaps between platoons.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Dict, List, Optional, Sequence

from src.platoon.dynamics import (
    CACCParams,
    IDMParams,
    cacc_desired_gap,
    idm_equilibrium_gap,
)
from src.platoon.sim import Channel, ScenarioSpec, SimConfig, build

_PEAK_EPS = 1e-6


def throughput_vph(
    speed: float,
    controller: str,
    time_gap: float,
    cacc: Optional[CACCParams] = None,
    idm: Optional[IDMParams] = None,
) -> float:
    """Steady-state vehicles per hour per lane at ``speed`` (m/s)."""
    idm = idm or IDMParams(v0=speed * 1.2, time_gap=time_gap)
    if controller == "cacc":
        c = replace(cacc or CACCParams(), time_gap=time_gap)
        gap = cacc_desired_gap(speed, c)
    elif controller == "idm":
        gap = idm_equilibrium_gap(speed, replace(idm, time_gap=time_gap))
    else:
        raise ValueError("controller must be 'cacc' or 'idm'")
    return 3600.0 * speed / (idm.length + gap)


def string_stability(
    n: int,
    time_gap: float,
    controller: str,
    *,
    speed: float = 25.0,
    pulse_decel: float = 1.0,
    pulse_s: float = 2.0,
    duration: float = 120.0,
    channel: Optional[Channel] = None,
    reaction_s: float = 0.0,
) -> Dict[str, Any]:
    """Peak speed-perturbation amplification down a string of ``n`` identical vehicles."""
    if n < 2:
        raise ValueError("need at least 2 vehicles")
    spec = ScenarioSpec(
        vehicles=n,
        duration=duration,
        speed=speed,
        time_gap=time_gap,
        human_time_gap=time_gap,
        pulse_decel=pulse_decel,
        pulse_s=pulse_s,
        pulse_window=(10.0, 10.0),
        jitter=0.0,
        channel=channel,
        cfg=SimConfig(reaction_s=reaction_s),
    )
    sim = build(spec, controller, seed=0)
    peaks = [0.0] * n
    for _ in range(int(round(duration / spec.cfg.dt))):
        sim.step()
        for i, ve in enumerate(sim.vs):
            peaks[i] = max(peaks[i], abs(ve.v - speed))
    ratios: List[float] = [peaks[k] / max(peaks[k - 1], _PEAK_EPS) for k in range(1, n)]
    step_max = max(ratios)
    return {
        "vehicles": n,
        "timeGapSeconds": time_gap,
        "controller": controller,
        "peakSpeedDeviationMps": peaks,
        "stepRatioMax": step_max,
        "amplification": peaks[-1] / max(peaks[0], _PEAK_EPS),
        "stable": step_max <= 1.0 + 1e-3,
        "minGapM": sim.min_gap_seen,
        "collisions": sim.collisions,
    }


def stability_sweep(
    sizes: Sequence[int], time_gaps: Sequence[float], controller: str, **kw: Any
) -> List[Dict[str, Any]]:
    """String stability for every (size, time gap) pair."""
    return [string_stability(n, h, controller, **kw) for n in sizes for h in time_gaps]
