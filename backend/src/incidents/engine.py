"""Network run with time-varying disruptions (F13).

EXECUTION CHOICE. ``simulate_network`` is a batch loop with every rule inlined
and hard-wired constants (lane count, link speed, a single signal plan), so
disruptions that change a link at a given second cannot be injected without
editing it. Adding hooks would put the bit-identical guarantee for everything
that already uses it at risk. Instead this module is a *second runner* that
replays the same per-tick rules in the same order (gate arrivals from one
``random.Random(seed)``, nodes in id order, saturation credit, spillback,
signal axis gating) and re-reads per-link parameters only at the instants a
disruption starts or ends ("segments"). Nothing in ``src.networks`` is
modified. With an empty scenario and the ``fixed_time`` strategy it reproduces
``simulate_network`` exactly (a test compares counts, delay and per-link
figures), so the no-disruption baseline is the original engine's result.

What a disruption changes, per segment:

* lane loss (crash, blocked lane): the link's lanes, hence its storage
  capacity and discharge rate, drop; a crash also slows the link;
* full block (all lanes lost, or a closure): storage capacity 0, so nothing
  may enter; vehicles already on the link ``drain`` at the normal rate
  (closure default) or are ``hold``-ed until it reopens (all-lanes crash);
* weather: speed, saturation flow and headway multipliers (``weather.py``);
* surge: the matching gate flows' arrival probability is multiplied.

Rerouting. When the set of fully blocked links changes and ``reroute`` is on,
each flow's path is recomputed with ``shortest_path`` and a large penalty on
blocked links, and vehicles already driving whose remaining path crosses a
blocked link are re-planned from the end of their current link (a U-turn onto
the reverse link is penalised). A flow with no alternative keeps its path:
its vehicles wait upstream, and arrivals onto a blocked first link are counted
as ``blockedAtEntry``. Vehicles are never created or destroyed except at
gates, so ``generated = blockedAtEntry + completed + active`` holds.

Delay is always measured against the free-flow time of the flow's original
(undisturbed) route, so a detour counts as delay.

Signal strategies: ``fixed_time`` (the engine's own two-phase schedule, no lost
time) and ``max_pressure`` (per node, serve the axis with more waiting vehicles
minus the straight-ahead downstream vehicles, with a minimum hold and a
clearance during which the node passes nothing; the same rule as
``rl.network_baselines.NetworkMaxPressure``, re-implemented here so this
package needs neither numpy nor the optional RL stack).
"""

import random
from collections import deque
from typing import Any, Deque, Dict, FrozenSet, List, Optional, Set, Tuple

from src.incidents.model import Scenario
from src.incidents.weather import WeatherFactors, combine, weather_factors
from src.networks.graph import RoadGraph, shortest_path
from src.networks.network_sim import (
    SATURATION_PER_LANE,
    SIGNAL_CYCLE,
    VEHICLE_SPACE,
    Flow,
)

RUN_FORMAT = "urbanflow-incident-run"
STRATEGIES = ("fixed_time", "max_pressure")
CLOSED_PENALTY = 1.0e6  # seconds added to a blocked link when routing
UTURN_PENALTY = 1.0e4
EPS = 1e-9


class _V:
    __slots__ = (
        "path",
        "index",
        "entered_at",
        "ff_base",
        "link_enter",
        "ff_own",
        "prog",
    )

    def __init__(self, path: List[str], t: float, ff_base: float, ff_own: float):
        self.path = path
        self.index = 0
        self.entered_at = t
        self.ff_base = ff_base
        self.link_enter = t
        self.ff_own = ff_own
        self.prog = 0.0  # free-flow seconds of the links already left


def _active(start: float, duration: float, t: float) -> bool:
    return start - EPS <= t < start + duration - EPS


def _boundaries(scenario: Scenario, duration: float) -> List[float]:
    pts = {0.0}
    for s, e in scenario.windows():
        for x in (s, e):
            if 0.0 < x < duration:
                pts.add(x)
    return sorted(pts)


def run_disruption(
    graph: RoadGraph,
    flows: List[Flow],
    scenario: Optional[Scenario] = None,
    *,
    duration: float = 900.0,
    seed: int = 1,
    strategy: str = "fixed_time",
    dt: float = 1.0,
    bucket_seconds: float = 30.0,
    signal_cycle: float = SIGNAL_CYCLE,
    clearance: float = 2.0,
    min_hold: float = 10.0,
    switch_margin: float = 1.0,
) -> Dict[str, Any]:
    """Run ``graph`` under ``scenario``. Deterministic under ``seed``.

    Returns the ``simulate_network`` counters plus ``series`` (per bucket:
    mean accrued delay of the vehicles in the network, active, completed,
    entered and blocked counts), rerouting counters and ``segments``."""
    if strategy not in STRATEGIES:
        raise ValueError(f"unknown strategy {strategy!r}; use one of {STRATEGIES}")
    if dt <= 0 or duration <= 0 or bucket_seconds <= 0:
        raise ValueError("dt, duration and bucket_seconds must be positive")
    scenario = scenario or Scenario()
    rng = random.Random(seed)
    nodes = graph.node_map()
    links = graph.link_map()
    incoming = graph.incoming()
    outgoing = graph.outgoing()

    cross0 = {k: v.length / v.speed for k, v in links.items()}
    base_routes: List[Optional[List[str]]] = []
    unroutable: List[str] = []
    for f in flows:
        p = shortest_path(graph, f.origin, f.destination)
        if not p:
            unroutable.append(f"{f.origin}->{f.destination}")
            p = None
        base_routes.append(p)
    ff_base = [
        sum(cross0[x] for x in p) if p else 0.0 for p in base_routes
    ]  # undisturbed free-flow seconds per flow
    live = [
        i
        for i, (f, p) in enumerate(zip(flows, base_routes))
        if p is not None and f.vehicles_per_hour > 0
    ]
    surge_flows = [
        [i for i, f in enumerate(flows) if s.matches(f)] for s in scenario.surges
    ]

    queues: Dict[str, Deque[Tuple[_V, float]]] = {k: deque() for k in links}
    credit: Dict[str, float] = {k: 0.0 for k in links}
    peak: Dict[str, int] = {k: 0 for k in links}
    passed_link: Dict[str, int] = {k: 0 for k in links}
    passed_node: Dict[str, int] = {n: 0 for n in nodes}
    axis: Dict[str, str] = {}
    for k in links.values():
        a, b = nodes[k.from_], nodes[k.to]
        axis[k.id] = "ew" if abs(b.x - a.x) >= abs(b.y - a.y) else "ns"

    plan = [
        (
            nid,
            nodes[nid].control == "signal",
            tuple((k.id, axis[k.id] == "ew", queues[k.id], k) for k in incoming[nid]),
        )
        for nid in sorted(nodes)
    ]
    half_cycle = signal_cycle / 2.0

    # Max-pressure state (signalised nodes that receive traffic).
    sig_nodes = sorted(n for n, node in nodes.items() if node.control == "signal")
    mp = strategy == "max_pressure"
    mp_phase = {n: 0 for n in sig_nodes}
    mp_tip = {n: 0.0 for n in sig_nodes}
    mp_clear = {n: 0.0 for n in sig_nodes}
    mp_pending = {n: 0 for n in sig_nodes}
    switches = {n: 0 for n in sig_nodes}
    # straight-ahead downstream link for pressure (None when it leaves at a gate)
    straight: Dict[str, Optional[str]] = {}
    for nid in sig_nodes:
        for link in incoming[nid]:
            straight[link.id] = None
            for nxt in outgoing.get(nid, []):
                if axis[nxt.id] == axis[link.id] and nxt.to != link.from_:
                    if nodes[nxt.to].kind != "gate":
                        straight[link.id] = nxt.id
                    break

    # Per-segment parameters (rebuilt at each boundary).
    cap: Dict[str, int] = {}
    cross: Dict[str, float] = {}
    refill: Dict[str, float] = {}
    lim: Dict[str, float] = {}
    hold: FrozenSet[str] = frozenset()
    paths: List[List[str]] = [list(p) if p else [] for p in base_routes]
    ff_path = list(ff_base)
    p_arr: Dict[int, float] = {}
    closed: FrozenSet[str] = frozenset()
    segments: List[Dict[str, Any]] = []
    rerouted_vehicles = 0
    reroute_events = 0

    def apply(t: float) -> None:
        nonlocal cap, cross, refill, lim, hold, paths, ff_path, p_arr, closed
        nonlocal rerouted_vehicles, reroute_events
        lost: Dict[str, int] = {}
        slow: Dict[str, float] = {}
        full: Set[str] = set()
        held: Set[str] = set()
        for inc in scenario.incidents:
            if not _active(inc.start, inc.duration, t):
                continue
            for lid in inc.links:
                if lid not in links:
                    continue
                if inc.type == "closure":
                    full.add(lid)
                    if inc.policy == "hold":
                        held.add(lid)
                else:
                    lost[lid] = max(lost.get(lid, 0), inc.lanesBlocked)
                slow[lid] = slow.get(lid, 1.0) * inc.speed_factor()
        for lid, n_lost in lost.items():
            if n_lost >= links[lid].lanes:
                full.add(lid)
                held.add(lid)
        wf: WeatherFactors = combine(
            weather_factors(w.kind, w.severity)
            for w in scenario.weather
            if _active(w.start, w.duration, t)
        )
        disch = wf.discharge
        new_cap: Dict[str, int] = {}
        new_cross: Dict[str, float] = {}
        new_refill: Dict[str, float] = {}
        new_lim: Dict[str, float] = {}
        for lid, link in links.items():
            if lid in full:
                new_cap[lid] = 0
            elif lid in lost:
                new_cap[lid] = max(
                    1, int((link.lanes - lost[lid]) * link.length / VEHICLE_SPACE)
                )
            else:
                new_cap[lid] = max(1, int(link.lanes * link.length / VEHICLE_SPACE))
            f_speed = wf.speed * slow.get(lid, 1.0)
            new_cross[lid] = link.length / (link.speed * f_speed)
            if lid in full:
                serve_lanes = 0 if lid in held else link.lanes  # drain or hold
            else:
                serve_lanes = link.lanes - lost.get(lid, 0)
            r = serve_lanes * SATURATION_PER_LANE * dt
            if disch != 1.0:
                r = r * disch
            new_refill[lid] = r
            new_lim[lid] = max(1.0, float(serve_lanes))
        cap, cross, refill, lim = new_cap, new_cross, new_refill, new_lim
        hold = frozenset(held)

        scale = {i: 1.0 for i in live}
        for s, idxs in zip(scenario.surges, surge_flows):
            if _active(s.start, s.duration, t):
                for i in idxs:
                    if i in scale:
                        scale[i] *= s.multiplier
        p_arr = {
            i: min(1.0, flows[i].vehicles_per_hour * scale[i] / 3600.0 * dt)
            for i in live
        }

        new_closed = frozenset(full) if scenario.reroute else frozenset()
        if new_closed != closed:
            grew = bool(new_closed - closed)
            closed = new_closed
            pen = {lid: CLOSED_PENALTY for lid in closed}
            for i in live:
                paths[i] = list(base_routes[i] or [])
                if closed:
                    alt = shortest_path(
                        graph, flows[i].origin, flows[i].destination, pen
                    )
                    if alt and not (set(alt) & closed):
                        paths[i] = list(alt)
                ff_path[i] = sum(cross0[x] for x in paths[i])
            if grew:
                n_new, _ = _reroute_active(t)
                rerouted_vehicles += n_new
            reroute_events += 1
        segments.append(
            {
                "start": t,
                "fullyBlocked": sorted(full),
                "laneLoss": dict(sorted(lost.items())),
                "weather": {
                    "speed": round(wf.speed, 4),
                    "saturation": round(wf.saturation, 4),
                    "headway": round(wf.headway, 4),
                },
                "surgeActive": any(v != 1.0 for v in scale.values()),
            }
        )

    def _reroute_active(t: float) -> Tuple[int, int]:
        cache: Dict[Tuple[str, str, str], Optional[List[str]]] = {}
        changed = looked = 0
        for lid, q in queues.items():
            cur = links[lid]
            for veh, _ in q:
                rest = veh.path[veh.index + 1 :]
                if not rest or not (set(rest) & closed):
                    continue
                looked += 1
                dest = links[veh.path[-1]].to
                key = (cur.to, dest, cur.from_)
                if key not in cache:
                    pen = {k: CLOSED_PENALTY for k in closed}
                    for out_link in outgoing.get(cur.to, []):
                        if out_link.to == cur.from_:
                            pen.setdefault(out_link.id, UTURN_PENALTY)
                    alt = shortest_path(graph, cur.to, dest, pen)
                    cache[key] = alt if alt and not (set(alt) & closed) else None
                alt2 = cache[key]
                if alt2 is None:
                    continue
                veh.path = veh.path[: veh.index + 1] + list(alt2)
                veh.ff_own = sum(cross0[x] for x in veh.path)
                changed += 1
        return changed, looked

    bounds = _boundaries(scenario, duration)
    bi = 0

    generated = entered = blocked = completed = 0
    travel_total = delay_total = 0.0
    rand = rng.random
    steps = int(round(duration / dt))
    spb = max(1, int(round(bucket_seconds / dt)))
    s_time: List[float] = []
    s_delay: List[float] = []
    s_active: List[int] = []
    s_completed: List[int] = []
    s_entered: List[int] = []
    s_blocked: List[int] = []
    b_completed = b_entered = b_blocked = 0
    node_phase = 0

    for step in range(steps):
        t = step * dt
        if bi < len(bounds) and bounds[bi] <= t + EPS:
            while bi < len(bounds) and bounds[bi] <= t + EPS:
                bi += 1
            apply(t)
        # Gates: Bernoulli arrivals approximate Poisson at small dt.
        for i in live:
            if rand() < p_arr[i]:
                generated += 1
                path = paths[i]
                first_id = path[0]
                fq = queues[first_id]
                if len(fq) >= cap[first_id]:
                    blocked += 1
                    b_blocked += 1
                    continue
                veh = _V(path, t, ff_base[i], ff_path[i])
                entered += 1
                b_entered += 1
                fq.append((veh, t + cross[first_id]))
                if len(fq) > peak[first_id]:
                    peak[first_id] = len(fq)
        phase = int(t // half_cycle) % 2
        if mp:
            for nid in sig_nodes:
                if mp_clear[nid] > 0.0:
                    mp_clear[nid] -= dt
                    if mp_clear[nid] <= EPS:
                        mp_clear[nid] = 0.0
                        mp_phase[nid] = mp_pending[nid]
                        mp_tip[nid] = 0.0
                    continue
                want = mp_phase[nid]
                if mp_tip[nid] >= min_hold:
                    pr = {"ew": 0.0, "ns": 0.0}
                    for link in incoming[nid]:
                        w = 0
                        for _v, ready in queues[link.id]:
                            if ready > t:
                                break
                            w += 1
                        down = straight.get(link.id)
                        pr[axis[link.id]] += w - (len(queues[down]) if down else 0)
                    mine = pr["ew"] if want == 0 else pr["ns"]
                    other = pr["ns"] if want == 0 else pr["ew"]
                    if other > mine + switch_margin:
                        want = 1 - want
                if want != mp_phase[nid]:
                    switches[nid] += 1
                    if clearance <= 0.0:
                        mp_phase[nid] = want
                        mp_tip[nid] = 0.0
                    else:
                        mp_pending[nid] = want
                        mp_clear[nid] = clearance
                        continue
                mp_tip[nid] += dt
        for node_id, is_signal, ins in plan:
            if is_signal and mp:
                node_phase = -1 if mp_clear[node_id] > 0.0 else mp_phase[node_id]
            else:
                node_phase = phase
            for lid, is_ew, q, link in ins:
                c = credit[lid] + refill[lid]
                lm = lim[lid]
                if c > lm:
                    c = lm
                if is_signal and (node_phase < 0 or is_ew != (node_phase == 0)):
                    credit[lid] = c
                    continue
                if hold and lid in hold:
                    credit[lid] = c
                    continue
                while q and c >= 1.0 and q[0][1] <= t:
                    veh = q[0][0]
                    if veh.index == len(veh.path) - 1:  # arrives at its destination
                        q.popleft()
                        c -= 1.0
                        passed_link[lid] += 1
                        passed_node[node_id] += 1
                        completed += 1
                        b_completed += 1
                        elapsed = t - veh.entered_at
                        travel_total += elapsed
                        delay_total += max(0.0, elapsed - veh.ff_base)
                        continue
                    nid_ = veh.path[veh.index + 1]
                    nq = queues[nid_]
                    if len(nq) >= cap[nid_]:
                        break  # spillback: head of line waits
                    q.popleft()
                    c -= 1.0
                    passed_link[lid] += 1
                    passed_node[node_id] += 1
                    veh.prog += cross0[lid]
                    veh.index += 1
                    veh.link_enter = t
                    nq.append((veh, t + cross[nid_]))
                    if len(nq) > peak[nid_]:
                        peak[nid_] = len(nq)
                credit[lid] = c
        if (step + 1) % spb == 0:
            tn = (step + 1) * dt
            total = 0.0
            n_act = 0
            for lid, q in queues.items():
                if not q:
                    continue
                c0 = cross0[lid]
                for veh, _ in q:
                    done = veh.prog + min(c0, tn - veh.link_enter)
                    total += (tn - veh.entered_at) - veh.ff_base * done / veh.ff_own
                    n_act += 1
            s_time.append(round(tn, 6))
            s_delay.append(round(max(0.0, total / n_act), 4) if n_act else 0.0)
            s_active.append(n_act)
            s_completed.append(b_completed)
            s_entered.append(b_entered)
            s_blocked.append(b_blocked)
            b_completed = b_entered = b_blocked = 0

    active = sum(len(q) for q in queues.values())
    return {
        "format": RUN_FORMAT,
        "version": 1,
        "strategy": strategy,
        "seed": seed,
        "duration": duration,
        "generated": generated,
        "entered": entered,
        "blockedAtEntry": blocked,
        "completed": completed,
        "active": active,
        "conserved": entered == completed + active and generated == entered + blocked,
        "meanTravelSeconds": round(travel_total / completed, 3) if completed else None,
        "meanDelaySeconds": round(delay_total / completed, 3) if completed else None,
        "totalTravelSeconds": round(travel_total, 3),
        "totalDelaySeconds": round(delay_total, 3),
        "unroutable": unroutable,
        "reroutedVehicles": rerouted_vehicles,
        "rerouteEvents": reroute_events,
        "switches": dict(switches) if mp else {},
        "perLink": {
            k: {
                "passed": passed_link[k],
                "peakOccupancy": peak[k],
                "occupancy": len(queues[k]),
            }
            for k in sorted(links)
        },
        "perNode": {n: {"passed": passed_node[n]} for n in sorted(nodes)},
        "segments": segments,
        "series": {
            "bucketSeconds": spb * dt,
            "time": s_time,
            "meanAccruedDelay": s_delay,
            "active": s_active,
            "completed": s_completed,
            "entered": s_entered,
            "blocked": s_blocked,
        },
    }
