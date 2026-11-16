"""Discrete-time kinematic simulation of one 4-way intersection (F20).

Self-contained: it does not touch the traffic engine. One inbound lane per
approach (FIFO, no overtaking), Poisson demand per approach, a movement mix of
straight/left/right. ``mode="aim"`` uses the reservation manager;
``mode="signal"`` uses a fixed-time two-phase signal with permissive turns
resolved by the same tile gap acceptance, so the comparison is like-for-like
(same vehicles, same demand, same kinematics, same box speeds).

Modelling scope, stated plainly: this is an in-model, all-vehicles-connected
best case. Every vehicle is automated and connected, follows its granted
trajectory exactly, and nothing else (pedestrians, cyclists, unconnected or
misbehaving vehicles, sensing or actuation error) exists. Results are not
evidence about real-world performance.

Unreserved vehicles run a conservative default: cruise, then stop at a queue
position behind their leader, retrying the request every ``retry_interval``.
With ``loss_probability`` a request/response exchange is lost with that
probability, so vehicles keep retrying while they approach.
"""

import math
import random
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional, Tuple

from src.aim.geometry import build_geometry
from src.aim.manager import (
    ManagerConfig,
    Request,
    ReservationManager,
    SignalPlan,
)
from src.aim.safety import SafetyReport, Track, validate
from src.aim.trajectory import KinParams, Plan, min_entry_time, plan_for

LENGTHS = (4.2, 4.5, 5.0, 7.0)
LENGTH_WEIGHTS = (0.25, 0.45, 0.2, 0.1)


@dataclass(frozen=True)
class SimConfig:
    mode: str = "aim"  # "aim" or "signal"
    duration: float = 300.0  # seconds of demand generation
    demand_vph: float = 400.0  # vehicles per hour per approach
    left_fraction: float = 0.15
    right_fraction: float = 0.15
    seed: int = 1
    dt: float = 0.1
    loss_probability: float = 0.0
    retry_interval: float = 0.5
    drain_limit: float = 900.0
    time_buffer: float = 0.5
    footprint_radius: float = 1.0  # physical half width
    footprint_margin: float = 0.5  # extra radius the manager books
    signal: SignalPlan = field(default_factory=SignalPlan)
    params: KinParams = field(default_factory=KinParams)


@dataclass
class SimResult:
    mode: str
    metrics: Dict[str, float]
    safety: SafetyReport
    tracks: List[Track]
    manager: ReservationManager

    def to_dict(self) -> Dict[str, Any]:
        return {"mode": self.mode, **self.metrics, "safety": self.safety.to_dict()}


class _Veh:
    def __init__(
        self,
        vid: int,
        approach: int,
        movement: str,
        length: float,
        arrival: float,
        vf: float,
        free_entry: float,
    ) -> None:
        self.vid, self.approach, self.movement = vid, approach, movement
        self.length, self.arrival, self.vf = length, arrival, vf
        self.free_entry = free_entry  # unimpeded entry time given the spawn time
        self.x = 0.0
        self.v = 0.0
        self.xn = 0.0
        self.plan: Optional[Plan] = None
        self.next_request = 0.0
        self.leader: Optional["_Veh"] = None
        self.track: Optional[Track] = None
        self.entry: Optional[float] = None
        self.armed = True
        self.stops = 0
        self.requests = 0
        self.losses = 0
        self.done = False

    def constraining(self) -> bool:
        lead = self.leader
        return lead is not None and not lead.done and lead.x - lead.length < 0


def _arrivals(cfg: SimConfig) -> List[Deque[Tuple[float, str, float]]]:
    rng = random.Random(cfg.seed)
    rate = cfg.demand_vph / 3600.0
    out: List[Deque[Tuple[float, str, float]]] = []
    for _ in range(4):
        t = 0.0
        items: Deque[Tuple[float, str, float]] = deque()
        while rate > 0:
            t += rng.expovariate(rate)
            if t > cfg.duration:
                break
            u = rng.random()
            if u < cfg.left_fraction:
                movement = "left"
            elif u < cfg.left_fraction + cfg.right_fraction:
                movement = "right"
            else:
                movement = "straight"
            length = rng.choices(LENGTHS, LENGTH_WEIGHTS)[0]
            items.append((t, movement, length))
        out.append(items)
    return out


def run(cfg: SimConfig, keep_tracks: bool = True) -> SimResult:
    if cfg.mode not in ("aim", "signal"):
        raise ValueError("mode must be 'aim' or 'signal'")
    p = cfg.params
    margin_geo = build_geometry(radius=cfg.footprint_radius + cfg.footprint_margin)
    phys_geo = build_geometry(radius=cfg.footprint_radius)
    manager = ReservationManager(
        margin_geo,
        ManagerConfig(time_buffer=cfg.time_buffer),
        cfg.signal if cfg.mode == "signal" else None,
    )
    loss_rng = random.Random(cfg.seed * 7919 + 13)
    pending = _arrivals(cfg)
    x0, dt = -p.approach_length, cfg.dt
    free = {
        m: min_entry_time(x0, p.vmax, 0.0, p.box_speed(m), 0.0, p)
        for m in ("straight", "left", "right")
    }
    last: List[Optional[_Veh]] = [None] * 4
    active: List[_Veh] = []
    finished: List[_Veh] = []
    next_vid = 0
    k = 0
    hard_stop = cfg.duration + cfg.drain_limit
    while True:
        t = k * dt
        if t > hard_stop or (t > cfg.duration and not active and not any(pending)):
            break
        # -- spawn (virtual queue upstream of the lane start)
        for a in range(4):
            while pending[a] and pending[a][0][0] <= t + 1e-9:
                lead = last[a]
                if lead is not None and not lead.done:
                    need = (
                        p.standstill_gap
                        + p.vmax * 0.5
                        + max(0.0, p.vmax**2 - lead.v**2) / (2 * p.comfort_decel)
                    )
                    if lead.x - lead.length - x0 < need:
                        break
                arrival, movement, length = pending[a].popleft()
                vf = p.box_speed(movement)
                veh = _Veh(
                    next_vid,
                    a,
                    movement,
                    length,
                    arrival,
                    vf,
                    arrival + free[movement],  # type: ignore[operator]
                )
                next_vid += 1
                veh.x, veh.v, veh.next_request = x0, p.vmax, t
                veh.leader = lead
                veh.track = Track(veh.vid, a, movement, length, t, [x0], [p.vmax])
                last[a] = veh
                active.append(veh)
        # -- queue reference positions (leaders first)
        for veh in active:
            nominal = -(veh.vf**2) / (2 * p.accel)
            veh.xn = nominal
            if veh.constraining():
                assert veh.leader is not None
                veh.xn = min(
                    nominal, veh.leader.xn - veh.leader.length - p.standstill_gap
                )
        # -- reservation requests, first come first served
        due = [
            v
            for v in active
            if v.plan is None
            and t >= v.next_request - 1e-9
            and (
                not v.constraining()
                or v.leader is not None
                and v.leader.plan is not None
            )
        ]
        due.sort(key=lambda v: (v.arrival, v.approach, v.vid))
        for veh in due:
            _request(veh, t, cfg, p, manager, loss_rng)
        if cfg.mode == "aim" or k % 10 == 0:
            manager.prune(t)
        # -- advance
        tn = t + dt
        for veh in active:
            _advance(veh, tn, dt, p, cfg)
        survivors: List[_Veh] = []
        for veh in active:
            assert veh.track is not None
            if veh.x - veh.length >= phys_geo.length[(veh.approach, veh.movement)]:
                veh.done = True
                veh.track.exited = True
                finished.append(veh)
            else:
                survivors.append(veh)
        active = survivors
        k += 1
    unspawned = sum(len(q) for q in pending)
    everyone = finished + active
    tracks = [v.track for v in everyone if v.track is not None]
    tracks.sort(key=lambda tr: tr.vid)
    report = validate(tracks, phys_geo, dt, p, unspawned=unspawned)
    return SimResult(
        cfg.mode,
        _metrics(cfg, everyone, unspawned),
        report,
        tracks if keep_tracks else [],
        manager,
    )


def _request(
    veh: _Veh,
    t: float,
    cfg: SimConfig,
    p: KinParams,
    manager: ReservationManager,
    loss_rng: random.Random,
) -> None:
    veh.requests += 1
    veh.next_request = t + cfg.retry_interval
    if cfg.mode == "aim" and cfg.loss_probability > 0:
        if loss_rng.random() < cfg.loss_probability:
            veh.losses += 1
            return
    desired = min_entry_time(veh.x, veh.v, t, veh.vf, veh.xn, p)
    if desired is None:
        return
    lead = veh.leader if veh.constraining() else None

    def plan_fn(entry: float) -> Optional[Plan]:
        plan = plan_for(veh.x, veh.v, t, entry, veh.vf, veh.xn, p)
        if plan is None or lead is None or lead.plan is None:
            return plan
        gap = lead.length + p.standstill_gap
        tt = t
        while tt < entry + 0.2:
            tq = min(tt, entry)
            if plan.state(tq)[0] > lead.plan.state(tq)[0] - gap + 1e-6:
                return None
            tt += 0.2
        return plan

    req = Request(veh.vid, veh.approach, veh.movement, veh.length, desired, veh.vf)
    res = manager.request(req, plan_fn)
    if res is None:
        veh.next_request = t + 1.0
        return
    veh.plan = res.plan
    veh.entry = res.t_entry
    if res.plan.stops and veh.v > 0.05:
        veh.armed = True


def _advance(veh: _Veh, tn: float, dt: float, p: KinParams, cfg: SimConfig) -> None:
    assert veh.track is not None
    if veh.plan is not None:
        veh.x, veh.v = veh.plan.state(tn)
    else:
        v_new = min(p.vmax, veh.v + p.accel * dt)
        gap_stop = veh.xn - 1.0 - veh.x  # 1 m slack for step overshoot
        v_new = min(
            v_new, math.sqrt(2 * p.comfort_decel * gap_stop) if gap_stop > 0 else 0.0
        )
        lead = veh.leader
        if veh.constraining() and lead is not None:
            room = lead.x - lead.length - p.standstill_gap - (veh.x + veh.v * dt)
            v_new = min(
                v_new, math.sqrt(lead.v**2 + 2 * p.comfort_decel * max(0.0, room))
            )
        v_new = max(0.0, max(v_new, veh.v - p.decel * dt))
        veh.x += 0.5 * (veh.v + v_new) * dt
        veh.v = v_new
    if veh.v > 0.5:
        veh.armed = True
    elif veh.v < 0.1 and veh.armed:
        veh.stops += 1
        veh.armed = False
    veh.track.xs.append(veh.x)
    veh.track.vs.append(veh.v)


def _metrics(cfg: SimConfig, vehicles: List[_Veh], unspawned: int) -> Dict[str, float]:
    entered = [v for v in vehicles if v.entry is not None]
    delays = sorted(v.entry - v.free_entry for v in entered if v.entry is not None)
    n = len(delays)
    in_window = sum(
        1 for v in entered if v.entry is not None and v.entry <= cfg.duration
    )
    requests = sum(v.requests for v in vehicles)
    return {
        "vehicles": float(len(vehicles) + unspawned),
        "entered": float(n),
        "meanDelay": sum(delays) / n if n else 0.0,
        "p95Delay": delays[min(n - 1, int(0.95 * n))] if n else 0.0,
        "maxDelay": delays[-1] if n else 0.0,
        "stopsPerVehicle": sum(v.stops for v in vehicles) / len(vehicles)
        if vehicles
        else 0.0,
        "throughputVph": in_window * 3600.0 / cfg.duration,
        "requests": float(requests),
        "lostMessages": float(sum(v.losses for v in vehicles)),
    }
