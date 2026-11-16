"""Reservation-based intersection manager and the fixed-time signal baseline.

A vehicle sends a ``Request`` (arrival time at the box entry, box speed,
movement, length). The manager books every tile the vehicle will occupy for
the interval ``[t + s_enter/v, t + (s_exit + L)/v]`` widened by
``time_buffer`` seconds each side, using the (margin-inflated) geometry. If
any tile is booked in that interval it proposes the earliest later arrival
that is free and for which the vehicle can actually build a trajectory
(``plan_fn``). Requests are served first come, first served in the order the
simulator presents them; the simulator's deterministic tie-break is
(demand arrival time, approach index, vehicle id).

The same manager also serves the signalised baseline: with a ``SignalPlan``
a candidate entry must additionally fall in the approach's green or yellow
window (permissive turns are resolved by the same tile gap acceptance).
"""

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from src.aim.geometry import Geometry
from src.aim.trajectory import Plan


@dataclass(frozen=True)
class Request:
    vid: int
    approach: int
    movement: str
    length: float
    arrival_time: float  # desired (earliest feasible) box entry time
    speed: float  # box speed


@dataclass(frozen=True)
class Reservation:
    vid: int
    approach: int
    movement: str
    t_entry: float
    speed: float
    length: float
    plan: Plan
    counter_offer: bool  # True when later than the requested arrival
    tile_intervals: Tuple[Tuple[int, float, float], ...]


@dataclass(frozen=True)
class SignalPlan:
    """Fixed-time two-phase signal: phase 0 serves approaches 0 and 2, phase 1
    serves 1 and 3. Entry is allowed during green and yellow; all-red clears."""

    green: float = 25.0
    yellow: float = 3.0
    all_red: float = 2.0

    @property
    def cycle(self) -> float:
        return 2 * (self.green + self.yellow + self.all_red)

    def next_allowed(self, approach: int, t: float) -> float:
        phase = approach % 2
        start = phase * (self.green + self.yellow + self.all_red)
        pos = (t - start) % self.cycle
        if pos < self.green + self.yellow:
            return t
        return t + (self.cycle - pos)


@dataclass
class ManagerConfig:
    time_buffer: float = 0.5
    horizon: float = 180.0
    retry_step: float = 0.25


@dataclass
class ReservationManager:
    geometry: Geometry
    config: ManagerConfig = field(default_factory=ManagerConfig)
    signal: Optional[SignalPlan] = None
    table: Dict[int, List[Tuple[float, float, int]]] = field(default_factory=dict)
    history: List[Reservation] = field(default_factory=list)
    keep_history: bool = True

    def intervals(
        self, approach: int, movement: str, t: float, speed: float, length: float
    ) -> List[Tuple[int, float, float]]:
        return [
            (tile, t + s_in / speed, t + (s_out + length) / speed)
            for tile, s_in, s_out in self.geometry.windows[(approach, movement)]
        ]

    def conflict_shift(self, req: Request, t: float) -> float:
        """0 if every tile is free at entry time ``t``, else the delay that
        clears the latest conflicting booking."""
        buf = self.config.time_buffer
        shift = 0.0
        for tile, a, b in self.intervals(
            req.approach, req.movement, t, req.speed, req.length
        ):
            for a2, b2, _ in self.table.get(tile, ()):
                if a - buf < b2 and a2 < b + buf:
                    shift = max(shift, b2 - (a - buf) + 1e-6)
        return shift

    def propose(
        self, req: Request, plan_fn: Callable[[float], Optional[Plan]]
    ) -> Optional[Tuple[float, Plan]]:
        """Earliest feasible ``(entry_time, plan)`` at or after the requested
        arrival, without booking; None if none within the horizon."""
        t = req.arrival_time
        limit = t + self.config.horizon
        step = self.config.retry_step
        while t <= limit:
            shift = self.conflict_shift(req, t)
            if shift > 0:
                t += shift
                continue
            if self.signal is not None:
                allowed = self.signal.next_allowed(req.approach, t)
                if allowed > t + 1e-9:
                    t = allowed
                    continue
            plan = plan_fn(t)
            if plan is not None:
                return t, plan
            t += step
            step = min(step * 1.15, 1.0)
        return None

    def book(self, req: Request, t: float, plan: Plan) -> Reservation:
        """Book ``t`` for ``req``; refuses a conflicting slot."""
        if self.conflict_shift(req, t) > 0:
            raise ValueError("slot conflicts with an existing reservation")
        ivals = self.intervals(req.approach, req.movement, t, req.speed, req.length)
        for tile, a, b in ivals:
            self.table.setdefault(tile, []).append((a, b, req.vid))
        res = Reservation(
            req.vid,
            req.approach,
            req.movement,
            t,
            req.speed,
            req.length,
            plan,
            t > req.arrival_time + 1e-6,
            tuple(ivals),
        )
        if self.keep_history:
            self.history.append(res)
        return res

    def request(
        self, req: Request, plan_fn: Callable[[float], Optional[Plan]]
    ) -> Optional[Reservation]:
        found = self.propose(req, plan_fn)
        if found is None:
            return None
        return self.book(req, found[0], found[1])

    def prune(self, now: float) -> None:
        for tile in list(self.table):
            kept = [e for e in self.table[tile] if e[1] >= now - 5.0]
            if kept:
                self.table[tile] = kept
            else:
                del self.table[tile]
