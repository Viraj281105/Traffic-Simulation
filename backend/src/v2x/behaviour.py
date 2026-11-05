"""Behavioural model of connected vehicles, applied to recorded baseline traces.

The mesoscopic simulator has no per-vehicle behaviour hook, so the baseline
(non-cooperative) run is simulated once per seed and the cooperative outcome is
derived from each vehicle's trace (see ``traces.py``) by an *overlay*. This is
deliberately simple. ASSUMPTIONS, all of which favour or disfavour the result in
a known direction and are returned in the experiment's provenance:

1. A vehicle is connected with probability ``penetration``, drawn once per
   vehicle (nested: a vehicle connected at 25% is also connected at 50%).
2. SPaT is broadcast by each signalised node every ``spat_period_s``. Each
   broadcast reaches each connected vehicle on the approach through the
   channel (loss, latency, range). A message older than ``spat_max_age_s`` on
   receipt is discarded. Signals are fixed-time with equal phases and the
   vehicle knows the cycle (as the simulator's signals are), so a received
   SPaT predicts the signal exactly; staleness costs lead time, not accuracy.
3. Green-light optimal speed advisory (GLOSA): from the first valid SPaT, a
   vehicle that would reach a red stop line can slow to at most
   ``min_speed_fraction`` of the link speed, absorbing up to
   ``lead x (1/fraction - 1)`` seconds of red as slow rolling instead of
   standing. If what remains of its baseline wait is within ``STOP_MIN_WAIT``
   it no longer stops and saves ``startup_loss_s`` (no standing start).
   Waiting behind a queue is not reduced, and a connected vehicle's travel
   time is otherwise unchanged (rolling slowly is still delay).
4. No second-order effects: other vehicles' queues, discharge rate and the
   baseline signal operation are untouched (no capacity gain from fewer
   standing starts, no platoon interaction). This understates network-level
   benefit and ignores harm to followers of a slowing vehicle.
5. Hazard: from ``start_s`` every vehicle that enters the hazard link pays
   ``delay_s`` extra. A connected vehicle that receives the warning (broadcast
   from the hazard link's upstream node every ``hazard_period_s``, subject to
   the channel and its distance along its route) before it leaves some earlier
   junction may take the free-flow-shortest detour avoiding the hazard link
   from that junction if that beats ``delay_s`` by ``reroute_min_gain_s``.
   Detours are costed at free-flow time, with the same signal/queue waits as
   the original remainder; congestion created by the diverted traffic is not
   modelled.
6. Fuel/CO2 are proxies of *excess* over free flow, for relative comparison:
   idling at ``IDLE_L_PER_S``, each standing start costing
   ``STOP_EQUIV_IDLE_S`` seconds of idling, detour seconds at cruise rate.
"""

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from src.networks.graph import GraphLink, GraphNode, RoadGraph, shortest_path
from src.networks.network_sim import SIGNAL_CYCLE
from src.v2x.channel import Channel
from src.v2x.messages import HazardWarning, PhaseState, SignalPhaseAndTiming
from src.v2x.traces import Leg, VehicleTrace

STOP_MIN_WAIT = 1.5  # s; a wait longer than this is a stop (> one 1 s step)
IDLE_L_PER_S = 0.00017  # about 0.6 L/h
STOP_EQUIV_IDLE_S = 8.0
CRUISE_L_PER_S = 0.00097  # about 7 L/100 km at 50 km/h
CO2_KG_PER_L = 2.31  # petrol
HALF_CYCLE = SIGNAL_CYCLE / 2.0


@dataclass(frozen=True)
class BehaviourConfig:
    advisory_horizon_s: float = 15.0  # SPaT is useful this long before the stop line
    min_lead_s: float = 2.0  # too late to adapt below this
    min_speed_fraction: float = 0.4
    spat_period_s: float = 1.0
    spat_max_age_s: float = 5.0
    startup_loss_s: float = 2.0
    hazard_period_s: float = 1.0
    hazard_max_age_s: float = 10.0
    reroute_min_gain_s: float = 5.0

    def __post_init__(self) -> None:
        if not 0.0 < self.min_speed_fraction <= 1.0:
            raise ValueError("min_speed_fraction must lie in (0, 1]")
        for name in ("spat_period_s", "hazard_period_s", "advisory_horizon_s"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")

    def to_dict(self) -> Dict[str, float]:
        return {k: float(v) for k, v in self.__dict__.items()}


@dataclass(frozen=True)
class Hazard:
    link_id: str
    start_s: float
    delay_s: float


@dataclass
class Outcome:
    """Totals over the completed vehicles of one run (one seed, one scenario)."""

    vehicles: int = 0
    connected: int = 0
    delay_s: float = 0.0
    stops: int = 0
    idle_s: float = 0.0
    hazard_s: float = 0.0
    detour_s: float = 0.0
    stops_avoided: int = 0
    reroutes: int = 0
    spat_attempts: int = 0
    spat_delivered: int = 0
    spat_used: int = 0
    hazard_attempts: int = 0
    hazard_delivered: int = 0
    hazard_used: int = 0
    age_sum_s: float = 0.0  # over used messages
    ages: List[float] = field(default_factory=list)

    @property
    def fuel_l(self) -> float:
        return (
            self.idle_s + self.hazard_s + self.stops * STOP_EQUIV_IDLE_S
        ) * IDLE_L_PER_S + self.detour_s * CRUISE_L_PER_S

    @property
    def co2_kg(self) -> float:
        return self.fuel_l * CO2_KG_PER_L

    def per_vehicle(self) -> Dict[str, float]:
        n = max(1, self.vehicles)
        return {
            "delaySeconds": self.delay_s / n,
            "stops": self.stops / n,
            "fuelLitres": self.fuel_l / n,
            "co2Kg": self.co2_kg / n,
        }

    def comms(self) -> Dict[str, Optional[float]]:
        attempts = self.spat_attempts + self.hazard_attempts
        delivered = self.spat_delivered + self.hazard_delivered
        used = self.spat_used + self.hazard_used
        return {
            "deliveryRatio": delivered / attempts if attempts else None,
            "meanAgeAtUseSeconds": self.age_sum_s / used if used else None,
            "messagesAttempted": float(attempts),
            "messagesDelivered": float(delivered),
            "messagesUsed": float(used),
        }


# -- signal knowledge --------------------------------------------------------


def _ttc(t: float) -> Tuple[bool, float]:
    """(east-west is green, seconds until the phase changes) at time ``t``."""
    phase = int(t // HALF_CYCLE) % 2
    return phase == 0, (int(t // HALF_CYCLE) + 1) * HALF_CYCLE - t


def spat_for(node: str, t: float) -> SignalPhaseAndTiming:
    """The SPaT a signalised node would broadcast at simulation time ``t``."""
    ew_green, ttc = _ttc(t)
    return SignalPhaseAndTiming(
        intersection=node,
        timestamp=t,
        phases=[
            PhaseState(
                group="ew", state="green" if ew_green else "red", timeToChange=ttc
            ),
            PhaseState(
                group="ns", state="red" if ew_green else "green", timeToChange=ttc
            ),
        ],
    )


def seconds_to_green(msg: SignalPhaseAndTiming, group: str, at: float) -> float:
    """Predicted wait for ``group`` to be green at time ``at`` (0 if green),
    from a received SPaT, assuming the fixed two-phase cycle."""
    ph = next(p for p in msg.phases if p.group == group)
    boundary = msg.timestamp + ph.time_to_change
    green_now = ph.state == "green"
    if at < boundary:
        return 0.0 if green_now else boundary - at
    # After the first change, the group alternates: HALF_CYCLE of the other state.
    pos = (at - boundary) % (2.0 * HALF_CYCLE)
    if green_now:  # next is red for a half-cycle, then green
        return HALF_CYCLE - pos if pos < HALF_CYCLE else 0.0
    return 0.0 if pos < HALF_CYCLE else 2.0 * HALF_CYCLE - pos


def hazard_message(hz: Hazard) -> HazardWarning:
    """The warning broadcast for ``hz``."""
    return HazardWarning(
        hazardId=f"h-{hz.link_id}",
        hazard="incident",
        linkId=hz.link_id,
        severity=3,
        timestamp=hz.start_s,
    )


def _unit(seed: int, vid: int) -> float:
    return random.Random(f"v2x-connected:{seed}:{vid}").random()


class _Routes:
    """Cached free-flow detours for the hazard model."""

    def __init__(self, graph: RoadGraph, hazard: Hazard) -> None:
        self.graph = graph
        self.links = graph.link_map()
        self.hazard = hazard
        self._cache: Dict[Tuple[str, str], Optional[float]] = {}

    def ff(self, link_ids: Sequence[str]) -> float:
        return sum(self.links[i].length / self.links[i].speed for i in link_ids)

    def alt_cost(self, node: str, dest: str) -> Optional[float]:
        key = (node, dest)
        if key not in self._cache:
            path = shortest_path(
                self.graph, node, dest, penalty={self.hazard.link_id: 1.0e6}
            )
            ok = path is not None and self.hazard.link_id not in path
            self._cache[key] = self.ff(path) if ok and path is not None else None
        return self._cache[key]


def evaluate(
    graph: RoadGraph,
    traces: Sequence[VehicleTrace],
    *,
    penetration: float,
    channel: Optional[Channel],
    seed: int,
    config: BehaviourConfig = BehaviourConfig(),
    hazard: Optional[Hazard] = None,
) -> Outcome:
    """Totals for ``traces`` with a share ``penetration`` of connected vehicles.

    ``penetration`` 0 (or no channel) is the non-cooperative baseline: the same
    accounting with every vehicle unconnected."""
    if not 0.0 <= penetration <= 1.0:
        raise ValueError("penetration must lie in [0, 1]")
    nodes = graph.node_map()
    links = graph.link_map()
    routes = _Routes(graph, hazard) if hazard is not None else None
    out = Outcome()
    for tr in traces:
        connected = (
            channel is not None
            and penetration > 0.0
            and _unit(seed, tr.vid) < penetration
        )
        ch = channel.fork(tr.vid) if connected and channel is not None else None
        out.vehicles += 1
        out.connected += 1 if connected else 0
        for leg in tr.legs:
            link = links[leg.link]
            w = leg.wait
            if w <= 0.0:
                continue
            stopped = w
            delay = w
            if (
                ch is not None
                and nodes[link.to].control == "signal"
                and w > STOP_MIN_WAIT
            ):
                stopped, delay = _glosa(out, ch, config, leg, link, nodes, w)
            out.delay_s += delay
            out.idle_s += stopped
            if stopped > STOP_MIN_WAIT:
                out.stops += 1
        if hazard is not None and routes is not None:
            _hazard(out, ch, config, hazard, routes, tr, connected)
    return out


def _glosa(
    out: Outcome,
    ch: Channel,
    cfg: BehaviourConfig,
    leg: Leg,
    link: GraphLink,
    nodes: Dict[str, GraphNode],
    w: float,
) -> Tuple[float, float]:
    """(stopped seconds, delay seconds) at one signal approach for a connected
    vehicle whose baseline wait is ``w``."""
    a, b = nodes[link.from_], nodes[link.to]
    group = "ew" if abs(b.x - a.x) >= abs(b.y - a.y) else "ns"
    r = leg.ready
    t0 = max(leg.enter, r - cfg.advisory_horizon_s)
    k = int(t0 // cfg.spat_period_s)
    if k * cfg.spat_period_s < t0:
        k += 1
    first: Optional[Tuple[float, float]] = None  # (send time, latency)
    while True:
        s = k * cfg.spat_period_s
        k += 1
        if s > r - cfg.min_lead_s:
            break
        tx = ch.transmit(max(0.0, (r - s) * link.speed))
        out.spat_attempts += 1
        if not tx.delivered:
            continue
        out.spat_delivered += 1
        if first is None and tx.latency_s <= cfg.spat_max_age_s:
            if r - (s + tx.latency_s) >= cfg.min_lead_s:
                first = (s, tx.latency_s)
    if first is None:
        return w, w
    s, lat = first
    out.spat_used += 1
    out.age_sum_s += lat
    out.ages.append(lat)
    msg = spat_for(link.to, s)
    g = seconds_to_green(msg, group, r)
    lead = r - (s + lat)
    absorbable = lead * (1.0 / cfg.min_speed_fraction - 1.0)
    absorbed = min(g, absorbable, w)
    stopped = w - absorbed
    delay = w
    if stopped <= STOP_MIN_WAIT:
        out.stops_avoided += 1
        stopped = 0.0
        delay = max(0.0, w - cfg.startup_loss_s)
    return stopped, delay


def _hazard(
    out: Outcome,
    ch: Optional[Channel],
    cfg: BehaviourConfig,
    hz: Hazard,
    routes: _Routes,
    tr: VehicleTrace,
    connected: bool,
) -> None:
    try:
        ih = tr.path.index(hz.link_id)
    except ValueError:
        return
    legs = tr.legs
    if legs[ih].enter < hz.start_s:
        return
    penalty = hz.delay_s
    if connected and ch is not None and ih > 0:
        penalty = _try_reroute(out, ch, cfg, hz, routes, tr, ih)
    out.hazard_s += penalty
    out.delay_s += penalty


def _try_reroute(
    out: Outcome,
    ch: Channel,
    cfg: BehaviourConfig,
    hz: Hazard,
    routes: _Routes,
    tr: VehicleTrace,
    ih: int,
) -> float:
    """Reroute a connected vehicle if it can. Returns the hazard delay it
    still pays (``hz.delay_s`` if it does not reroute, 0 if it does; the detour
    is added to ``out`` here)."""
    legs, links = tr.legs, routes.links
    last_decision = legs[ih - 1].depart
    assert last_decision is not None
    k = int(max(hz.start_s, legs[0].enter) // cfg.hazard_period_s)
    first: Optional[Tuple[float, float]] = None
    while True:
        s = k * cfg.hazard_period_s
        k += 1
        if s >= last_decision:
            break
        if s < max(hz.start_s, legs[0].enter):
            continue
        dist = _distance_to(routes, tr, ih, s)
        if dist is None:
            continue
        tx = ch.transmit(dist)
        out.hazard_attempts += 1
        if not tx.delivered:
            continue
        out.hazard_delivered += 1
        if first is None and tx.latency_s <= cfg.hazard_max_age_s:
            if s + tx.latency_s < last_decision:
                first = (s, tx.latency_s)
    if first is None:
        return hz.delay_s
    s, lat = first
    hazard_message(hz)  # the (validated) message the vehicle acted on
    t_rx = s + lat
    dest = links[tr.path[-1]].to
    best_gain, best_detour = cfg.reroute_min_gain_s, None
    for j in range(ih):
        dep = legs[j].depart
        assert dep is not None
        if dep < t_rx:
            continue
        node = links[tr.path[j]].to
        alt = routes.alt_cost(node, dest)
        if alt is None:
            continue
        orig = routes.ff(tr.path[j + 1 :]) + hz.delay_s
        gain = orig - alt
        if gain >= best_gain:
            best_gain, best_detour = gain, max(0.0, alt - routes.ff(tr.path[j + 1 :]))
    out.hazard_used += 1
    out.age_sum_s += lat
    out.ages.append(lat)
    if best_detour is None:
        return hz.delay_s
    out.reroutes += 1
    out.detour_s += best_detour
    out.delay_s += best_detour
    return 0.0


def _distance_to(
    routes: _Routes, tr: VehicleTrace, ih: int, s: float
) -> Optional[float]:
    """Route distance from the vehicle (at time ``s``) to the start of leg
    ``ih``; None if it is not yet on the network or already past the junction
    before the hazard."""
    legs, links = tr.legs, routes.links
    if s < legs[0].enter:
        return None
    for m in range(ih):
        dep = legs[m].depart
        assert dep is not None
        if s < dep:
            cross = max(1e-9, legs[m].ready - legs[m].enter)
            frac = min(1.0, max(0.0, (s - legs[m].enter) / cross))
            rest = sum(links[i].length for i in tr.path[m + 1 : ih])
            return (1.0 - frac) * links[tr.path[m]].length + rest
    return None
