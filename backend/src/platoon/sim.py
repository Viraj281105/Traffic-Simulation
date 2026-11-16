"""Self-contained 1-D single-lane platoon simulation (does not use the engine).

Vehicles are ordered front to back (index 0 is the head of the line); nobody
overtakes, so the vehicle ahead of ``i`` is always ``i - 1``. Vehicle 0 follows
a script: it holds ``speed`` and may brake in a pulse.

Messaging: each step the predecessor's acceleration is offered to a platoon
member through a channel-like callable ``channel(t, receiver_index, rng)`` that
returns the delivery latency in seconds, or ``None`` when the message is lost.
A member uses the newest delivered message; once its age exceeds ``timeout_s``
the member drops to FALLBACK (IDM, widened time gap) until messages have been
fresh for ``recover_s``.

Safety rules: (1) CACC acceleration is bounded; (2) if the stopping distance
at ``safe_decel`` leaves less than twice ``min_gap_m`` the vehicle brakes at
``safe_decel`` whatever its controller says; (3) a gap below ``min_gap_m`` sends
a member to FALLBACK. Collisions (gap <= 0) are counted, not hidden.
"""

from __future__ import annotations

import math
import random
from collections import deque
from dataclasses import dataclass, field, replace
from typing import Callable, Deque, Dict, List, Optional, Sequence, Tuple

from src.platoon import control as fsm
from src.platoon.dynamics import (
    CACCParams,
    IDMParams,
    cacc_accel,
    cacc_desired_gap,
    idm_accel,
    idm_equilibrium_gap,
    idm_free_accel,
)

Channel = Callable[[float, int, random.Random], Optional[float]]


def make_channel(
    latency_s: float = 0.0, loss: float = 0.0, jitter_s: float = 0.0
) -> Channel:
    """Channel with fixed latency plus uniform jitter and Bernoulli loss."""

    def channel(t: float, receiver: int, rng: random.Random) -> Optional[float]:
        if loss > 0.0 and rng.random() < loss:
            return None
        return latency_s + (rng.uniform(0.0, jitter_s) if jitter_s > 0.0 else 0.0)

    return channel


@dataclass(frozen=True)
class SimConfig:
    dt: float = 0.1
    timeout_s: float = 0.5
    recover_s: float = 1.0
    join_range_m: float = 60.0
    min_gap_m: float = 2.0
    max_size: int = 10
    safe_decel: float = 7.0
    fallback_time_gap: float = 1.5
    reaction_s: float = 0.0  # human perception delay for IDM-driven vehicles
    auto_form: bool = False
    cacc: CACCParams = field(default_factory=CACCParams)


@dataclass(frozen=True)
class LeadScript:
    """Vehicle 0 brakes at ``decel`` from ``t0`` for ``duration`` s, else IDM free road."""

    t0: float = 20.0
    decel: float = 0.0
    duration: float = 2.0


@dataclass
class Vehicle:
    id: int
    x: float  # front bumper position, m
    v: float
    idm: IDMParams
    state: str = fsm.FREE
    platoon: Optional[int] = None
    a: float = 0.0
    inbox: List[Tuple[float, float, float]] = field(default_factory=list)
    msg_sent: Optional[float] = None
    msg_a: float = 0.0
    fresh_since: Optional[float] = None
    seen: Deque[Tuple[float, float]] = field(default_factory=deque)  # (gap, lead v)

    @property
    def length(self) -> float:
        return self.idm.length


class Simulation:
    def __init__(
        self,
        vehicles: Sequence[Vehicle],
        cfg: SimConfig,
        lead: LeadScript,
        channel: Optional[Channel] = None,
        seed: int = 0,
    ) -> None:
        self.vs = list(vehicles)
        self.cfg = cfg
        self.lead = lead
        self.channel = channel
        self.rng = random.Random(seed * 7919 + 1)
        self.t = 0.0
        self.platoons: Dict[int, List[int]] = {}
        self._next_pid = 0
        self.min_gap_seen = math.inf
        self.collisions = 0
        self.log: List[Tuple[float, int, str, str]] = []  # (t, vehicle, event, new)
        self.denied: List[fsm.SlotRequest] = []
        self._splits: List[Tuple[int, int, Optional[float], Optional[float]]] = []

    # -- state machine ---------------------------------------------------

    def _fire(self, ve: Vehicle, event: str) -> None:
        ve.state = fsm.transition(ve.state, event)
        self.log.append((self.t, ve.id, event, ve.state))

    def _new_platoon(self, members: List[int]) -> int:
        pid = self._next_pid
        self._next_pid += 1
        self.platoons[pid] = members
        for i in members:
            self.vs[i].platoon = pid
        return pid

    def _grace(self, ve: Vehicle) -> None:
        ve.msg_sent = self.t
        ve.msg_a = 0.0
        ve.fresh_since = None

    # -- platoon operations ---------------------------------------------

    def form(self, indices: Sequence[int]) -> int:
        """Instantly form a platoon from contiguous vehicles (head is LEADER)."""
        idx = list(indices)
        if len(idx) > self.cfg.max_size or idx != list(
            range(idx[0], idx[0] + len(idx))
        ):
            raise ValueError("platoon must be contiguous and within max_size")
        pid = self._new_platoon(idx)
        self._fire(self.vs[idx[0]], "lead")
        for i in idx[1:]:
            self._fire(self.vs[i], "join")
            self._fire(self.vs[i], "join_complete")
            self._grace(self.vs[i])
        return pid

    def merge(self, front_pid: int, rear_pid: int) -> bool:
        """Append the rear platoon behind the front one; rear leader becomes a follower."""
        front, rear = self.platoons.get(front_pid), self.platoons.get(rear_pid)
        if front is None or rear is None or front_pid == rear_pid:
            return False
        if rear[0] != front[-1] + 1 or len(front) + len(rear) > self.cfg.max_size:
            return False
        head = self.vs[rear[0]]
        if self._gap(rear[0]) > self.cfg.join_range_m:
            return False
        self._fire(head, "merge")
        self._grace(head)
        front.extend(rear)
        for i in rear:
            self.vs[i].platoon = front_pid
        del self.platoons[rear_pid]
        return True

    def split(self, pid: int, at_index: int) -> Optional[int]:
        """Split platoon ``pid`` so vehicle index ``at_index`` leads a new platoon."""
        members = self.platoons.get(pid)
        if members is None or at_index not in members or at_index == members[0]:
            return None
        cut = members.index(at_index)
        tail = members[cut:]
        del members[cut:]
        new_pid = self._new_platoon(tail)
        self._fire(self.vs[at_index], "split")
        return new_pid

    def schedule_split(
        self,
        pid: int,
        at_index: int,
        at_time: Optional[float] = None,
        at_position: Optional[float] = None,
    ) -> None:
        """Split when time >= at_time or the platoon head reaches at_position."""
        if at_time is None and at_position is None:
            raise ValueError("give at_time or at_position")
        self._splits.append((pid, at_index, at_time, at_position))

    def _run_scheduled_splits(self) -> None:
        pending = []
        for pid, idx, at_t, at_x in self._splits:
            members = self.platoons.get(pid)
            if members is None:
                continue
            head_x = self.vs[members[0]].x
            if (at_t is not None and self.t >= at_t) or (
                at_x is not None and head_x >= at_x
            ):
                self.split(pid, idx)
            else:
                pending.append((pid, idx, at_t, at_x))
        self._splits = pending

    def _auto_form(self) -> None:
        requests: List[fsm.SlotRequest] = []
        for i in range(1, len(self.vs)):
            ve, ahead = self.vs[i], self.vs[i - 1]
            if ve.state != fsm.FREE or self._gap(i) > self.cfg.join_range_m:
                continue
            if ahead.platoon is not None:
                members = self.platoons[ahead.platoon]
                if members[-1] != i - 1 or len(members) >= self.cfg.max_size:
                    continue
                slot = (ahead.platoon, len(members))
            elif ahead.state == fsm.FREE:
                slot = (-(i - 1) - 1, 1)  # a new platoon led by the vehicle ahead
            else:
                continue
            requests.append(fsm.SlotRequest(i, slot, self._gap(i)))
        granted, denied = fsm.resolve_slot_conflicts(requests)
        self.denied.extend(denied)
        for r in granted:
            i = r.vehicle_id
            if r.slot[0] < 0:
                if self.vs[i - 1].state != fsm.FREE:
                    continue  # the vehicle ahead joined elsewhere this step; retry
                self._new_platoon([i - 1])
                self._fire(self.vs[i - 1], "lead")
            pid = self.vs[i - 1].platoon
            assert pid is not None
            self.platoons[pid].append(i)
            self.vs[i].platoon = pid
            self._fire(self.vs[i], "join")
            self._grace(self.vs[i])
        # Adjacent platoons within range merge (rear leader becomes a follower).
        for front_pid in sorted(self.platoons):
            front = self.platoons.get(front_pid)
            if front is None:
                continue
            for rear_pid, rear in sorted(self.platoons.items()):
                if rear[0] == front[-1] + 1 and self.merge(front_pid, rear_pid):
                    break

    # -- dynamics ---------------------------------------------------------

    def _gap(self, i: int) -> float:
        ahead = self.vs[i - 1]
        return ahead.x - ahead.length - self.vs[i].x

    def _read_messages(self, ve: Vehicle) -> None:
        keep = []
        for arrive, sent, a in ve.inbox:
            if arrive <= self.t + 1e-9:
                if ve.msg_sent is None or sent > ve.msg_sent:
                    ve.msg_sent, ve.msg_a = sent, a
            else:
                keep.append((arrive, sent, a))
        ve.inbox = keep

    def _update_state(self, ve: Vehicle, gap: float) -> None:
        cfg = self.cfg
        age = math.inf if ve.msg_sent is None else self.t - ve.msg_sent
        if ve.state in (fsm.JOINING, fsm.FOLLOWER):
            if age > cfg.timeout_s:
                self._fire(ve, "message_stale")
                ve.fresh_since = None
            elif gap < cfg.min_gap_m:
                self._fire(ve, "unsafe_gap")
                ve.fresh_since = None
        elif ve.state == fsm.FALLBACK:
            if age <= cfg.timeout_s and gap >= cfg.min_gap_m:
                if ve.fresh_since is None:
                    ve.fresh_since = self.t
                if self.t - ve.fresh_since >= cfg.recover_s:
                    self._fire(ve, "message_fresh")
                    self._grace(ve)
            else:
                ve.fresh_since = None

    def _accel(self, i: int, gap: float) -> float:
        cfg, ve, lead = self.cfg, self.vs[i], self.vs[i - 1]
        dv = ve.v - lead.v
        # Human drivers (IDM) see the gap and the leader's speed `reaction_s` late.
        ve.seen.append((gap, lead.v))
        lag = int(round(cfg.reaction_s / cfg.dt))
        while len(ve.seen) > lag + 1:
            ve.seen.popleft()
        gap_h, lead_v_h = ve.seen[0]
        dv_h = ve.v - lead_v_h
        a_idm = idm_accel(ve.v, gap_h, dv_h, ve.idm)
        if ve.state == fsm.FALLBACK:
            wide = replace(ve.idm, time_gap=max(ve.idm.time_gap, cfg.fallback_time_gap))
            a = idm_accel(ve.v, gap_h, dv_h, wide)
        elif ve.state in (fsm.JOINING, fsm.FOLLOWER):
            age = math.inf if ve.msg_sent is None else self.t - ve.msg_sent
            a_msg = ve.msg_a if age <= cfg.timeout_s else 0.0
            a = cacc_accel(ve.v, gap, lead.v, a_msg, cfg.cacc)
            if ve.state == fsm.JOINING:
                # Approach: IDM tuned to the platoon spacing keeps closing safe.
                join = replace(
                    ve.idm,
                    v0=cfg.cacc.v_max,
                    time_gap=cfg.cacc.time_gap,
                    min_gap=cfg.cacc.standstill,
                )
                a = min(a, idm_accel(ve.v, gap, dv, join))
            if ve.v >= cfg.cacc.v_max:
                a = min(a, 0.0)
        else:
            a = a_idm
        stop = max(0.0, ve.v**2 - lead.v**2) / (2.0 * cfg.safe_decel)
        if gap - stop < 2.0 * cfg.min_gap_m and ve.v > lead.v:
            a = min(a, -cfg.safe_decel)
        return max(-9.0, a)

    def _lead_accel(self) -> float:
        ve, s = self.vs[0], self.lead
        if s.decel > 0.0 and s.t0 <= self.t < s.t0 + s.duration:
            return -s.decel if ve.v > 0.0 else 0.0
        return idm_free_accel(ve.v, ve.idm)

    def step(self) -> None:
        cfg, n = self.cfg, len(self.vs)
        accs: List[float] = []
        for i, ve in enumerate(self.vs):
            if i == 0:
                a = self._lead_accel()
            else:
                self._read_messages(ve)
                gap = self._gap(i)
                self.min_gap_seen = min(self.min_gap_seen, gap)
                if gap <= 0.0:
                    self.collisions += 1
                self._update_state(ve, gap)
                a = self._accel(i, gap)
            accs.append(a)
            nxt = i + 1
            if nxt < n and self.vs[nxt].platoon is not None and self.channel:
                lat = self.channel(self.t, nxt, self.rng)
                if lat is not None:
                    self.vs[nxt].inbox.append((self.t + lat, self.t, a))
            elif nxt < n and self.vs[nxt].platoon is not None:
                self.vs[nxt].inbox.append((self.t, self.t, a))
        for ve, a in zip(self.vs, accs):
            ve.a = a
            v1 = max(0.0, ve.v + a * cfg.dt)
            ve.x += 0.5 * (ve.v + v1) * cfg.dt
            ve.v = v1
        self.t += cfg.dt
        for i in range(1, n):
            ve = self.vs[i]
            if ve.state == fsm.JOINING:
                d = cacc_desired_gap(ve.v, cfg.cacc)
                if self._gap(i) <= 1.25 * d and abs(ve.v - self.vs[i - 1].v) < 0.5:
                    self._fire(ve, "join_complete")
        self._run_scheduled_splits()
        if cfg.auto_form:
            self._auto_form()


# -- scenario builder and runner -----------------------------------------


@dataclass(frozen=True)
class ScenarioSpec:
    vehicles: int = 10
    duration: float = 200.0
    speed: float = 25.0
    time_gap: float = 0.6  # CACC time gap
    human_time_gap: float = 1.5  # IDM T
    pulse_decel: float = 4.0
    pulse_s: float = 2.0
    pulse_window: Tuple[float, float] = (15.0, 25.0)
    jitter: float = 1.0  # 0 gives identical vehicles
    channel: Optional[Channel] = None
    cfg: SimConfig = field(default_factory=SimConfig)


def build(spec: ScenarioSpec, mode: str, seed: int) -> Simulation:
    """Build a seeded scenario. ``mode``: 'cacc' (formed platoon) or 'idm'.

    The same seed draws the same pulse and per-driver jitter in both modes, so
    runs are paired.
    """
    if mode not in ("cacc", "idm"):
        raise ValueError("mode must be 'cacc' or 'idm'")
    rng = random.Random(seed)
    lo, hi = spec.pulse_window
    t0 = rng.uniform(lo, hi)
    decel = spec.pulse_decel * rng.uniform(0.9, 1.1)
    vs: List[Vehicle] = []
    x = spec.vehicles * 100.0
    for i in range(spec.vehicles):
        tj, aj, gj = rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1)
        tj, aj, gj = (max(-2.0, min(2.0, z)) for z in (tj, aj, gj))
        idm = IDMParams(
            v0=spec.speed if i == 0 else spec.speed * 1.2,
            time_gap=spec.human_time_gap * (1.0 + 0.1 * spec.jitter * tj),
            a_max=1.4 * (1.0 + 0.1 * spec.jitter * aj),
        )
        if i > 0:
            prev = vs[-1]
            if mode == "cacc":
                gap = spec.cfg.cacc.standstill + spec.time_gap * spec.speed
            else:
                gap = idm_equilibrium_gap(spec.speed, idm)
            gap *= 1.0 + 0.05 * spec.jitter * gj
            x = prev.x - prev.length - gap
        vs.append(Vehicle(id=i, x=x, v=spec.speed, idm=idm))
    cfg = replace(
        spec.cfg,
        max_size=max(spec.cfg.max_size, spec.vehicles),
        cacc=replace(spec.cfg.cacc, time_gap=spec.time_gap),
    )
    sim = Simulation(
        vs, cfg, LeadScript(t0, decel, spec.pulse_s), spec.channel, seed=seed
    )
    if mode == "cacc" and spec.vehicles >= 2:
        sim.form(range(spec.vehicles))
    return sim


@dataclass
class RunResult:
    dt: float
    speeds: List[List[float]]  # per vehicle, one sample per step
    min_gap_m: float
    collisions: int
    fallback_events: int
    window_spacing_m: float  # mean front-to-front spacing, second half of the run
    window_speed_mps: float

    @property
    def throughput_vph(self) -> float:
        """Steady-state flow estimate, 3600 * mean speed / mean spacing."""
        if self.window_spacing_m <= 0.0:
            return 0.0
        return 3600.0 * self.window_speed_mps / self.window_spacing_m


def run(spec: ScenarioSpec, mode: str, seed: int) -> RunResult:
    sim = build(spec, mode, seed)
    n, dt = spec.vehicles, spec.cfg.dt
    steps = int(round(spec.duration / dt))
    speeds: List[List[float]] = [[] for _ in range(n)]
    sp_sum = v_sum = 0.0
    count = 0
    for k in range(steps):
        for i, ve in enumerate(sim.vs):
            speeds[i].append(ve.v)
        if k >= steps // 2 and n > 1:
            for i in range(1, n):
                sp_sum += sim.vs[i - 1].x - sim.vs[i].x
                v_sum += sim.vs[i].v
                count += 1
        sim.step()
    fallbacks = sum(1 for _, _, ev, new in sim.log if new == fsm.FALLBACK)
    return RunResult(
        dt=dt,
        speeds=speeds,
        min_gap_m=sim.min_gap_seen if n > 1 else math.inf,
        collisions=sim.collisions,
        fallback_events=fallbacks,
        window_spacing_m=sp_sum / count if count else 0.0,
        window_speed_mps=v_sum / count if count else 0.0,
    )
