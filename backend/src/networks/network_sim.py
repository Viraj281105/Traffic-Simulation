"""Vehicle-level network run over a :class:`RoadGraph` (ADR-021).

A mesoscopic model: a vehicle crosses a link in its free-flow time, waits in
that link's FIFO queue, and is handed to the next link of its route when its
node lets it through. A node passes at most ``lanes x 0.5 veh/s`` per
incoming link (saturation flow), only while the next link has room (so queues
spill back), and, at signalised nodes, only while the incoming link's axis has
green (two phases, east-west then north-south). Vehicles are never created
or destroyed except at gates, so the count is conserved by construction and
checked in the result.

It does not replace the single-junction engine; it answers "how do vehicles
move between junctions", which the one-way flow coupling in ``compile.py``
cannot (it carries flow, not vehicles).
"""

import random
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple

from src.networks.graph import GraphLink, RoadGraph, shortest_path

RESULT_FORMAT = "urbanflow-graph-result"
SATURATION_PER_LANE = 0.5  # veh/s/lane
VEHICLE_SPACE = 7.5  # metres of link storage per vehicle per lane
SIGNAL_CYCLE = 60.0  # seconds, split evenly between the two axes


@dataclass(frozen=True)
class Flow:
    origin: str
    destination: str
    vehicles_per_hour: float


@dataclass
class _Vehicle:
    vid: int
    path: List[str]
    index: int
    entered_at: float
    free_flow: float


def _capacity(link: GraphLink) -> int:
    return max(1, int(link.lanes * link.length / VEHICLE_SPACE))


# observer(t, queues, passed_per_link) is called once per step after all nodes
# have moved; it must not mutate its arguments.
Observer = Callable[
    [float, Dict[str, Deque[Tuple["_Vehicle", float]]], Dict[str, int]], None
]


def simulate_network(
    graph: RoadGraph,
    flows: List[Flow],
    duration: float = 300.0,
    seed: int = 1,
    dt: float = 1.0,
    signal_cycle: float = SIGNAL_CYCLE,
    observer: Optional[Observer] = None,
) -> Dict[str, Any]:
    """Run the network for ``duration`` seconds. Deterministic under ``seed``.

    ``observer`` (optional, read-only) sees the queues after every step; the
    congestion analysis in ``src.netmetrics`` uses it. It does not affect
    the run."""
    rng = random.Random(seed)
    nodes = graph.node_map()
    links = graph.link_map()
    incoming = graph.incoming()

    routes: List[Optional[List[str]]] = []
    unroutable: List[str] = []
    for f in flows:
        path = shortest_path(graph, f.origin, f.destination)
        if not path:
            unroutable.append(f"{f.origin}->{f.destination}")
            path = None
        routes.append(path)

    queues: Dict[str, Deque[Tuple[_Vehicle, float]]] = {k: deque() for k in links}
    credit: Dict[str, float] = {k: 0.0 for k in links}
    peak: Dict[str, int] = {k: 0 for k in links}
    passed_link: Dict[str, int] = {k: 0 for k in links}
    passed_node: Dict[str, int] = {n: 0 for n in nodes}
    axis: Dict[str, str] = {}
    for k in links.values():
        a, b = nodes[k.from_], nodes[k.to]
        axis[k.id] = "ew" if abs(b.x - a.x) >= abs(b.y - a.y) else "ns"

    # Per-run constants, hoisted out of the step loop (pure refactor: same
    # arithmetic, same order of operations, same rng draws as before).
    cap = {k: _capacity(v) for k, v in links.items()}
    cross = {k: v.length / v.speed for k, v in links.items()}
    lanes_f = {k: float(v.lanes) for k, v in links.items()}
    refill = {k: v.lanes * SATURATION_PER_LANE * dt for k, v in links.items()}
    live: List[Tuple[Flow, List[str], float, float]] = []
    for f, path in zip(flows, routes):
        if path is None or f.vehicles_per_hour <= 0:
            continue
        live.append(
            (
                f,
                path,
                min(1.0, f.vehicles_per_hour / 3600.0 * dt),
                sum(cross[p] for p in path),
            )
        )
    # (node id, is signal, ((link id, is east-west axis, queue, link) ...))
    plan = [
        (
            nid,
            nodes[nid].control == "signal",
            tuple((k.id, axis[k.id] == "ew", queues[k.id], k) for k in incoming[nid]),
        )
        for nid in sorted(nodes)
    ]
    half_cycle = signal_cycle / 2.0

    generated = entered = blocked = completed = 0
    travel_total = delay_total = 0.0
    next_id = 0
    rand = rng.random
    steps = int(round(duration / dt))
    for step in range(steps):
        t = step * dt
        # Gates: Bernoulli arrivals approximate Poisson at small dt.
        for f, path, p_arrive, ff in live:
            if rand() < p_arrive:
                generated += 1
                first_id = path[0]
                fq = queues[first_id]
                if len(fq) >= cap[first_id]:
                    blocked += 1
                    continue
                veh = _Vehicle(next_id, path, 0, t, ff)
                next_id += 1
                entered += 1
                fq.append((veh, t + cross[first_id]))
                if len(fq) > peak[first_id]:
                    peak[first_id] = len(fq)
        phase = int(t // half_cycle) % 2
        # Nodes in id order; a vehicle moved this tick is ready only later.
        for node_id, is_signal, ins in plan:
            for lid, is_ew, q, link in ins:
                c = credit[lid] + refill[lid]
                lim = lanes_f[lid]
                if c > lim:
                    c = lim
                if is_signal and is_ew != (phase == 0):
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
                        elapsed = t - veh.entered_at
                        travel_total += elapsed
                        delay_total += max(0.0, elapsed - veh.free_flow)
                        continue
                    nid_ = veh.path[veh.index + 1]
                    nq = queues[nid_]
                    if len(nq) >= cap[nid_]:
                        break  # spillback: head of line waits
                    q.popleft()
                    c -= 1.0
                    passed_link[lid] += 1
                    passed_node[node_id] += 1
                    veh.index += 1
                    nq.append((veh, t + cross[nid_]))
                    if len(nq) > peak[nid_]:
                        peak[nid_] = len(nq)
                credit[lid] = c
        if observer is not None:
            observer(t, queues, passed_link)

    active = sum(len(q) for q in queues.values())
    return {
        "format": RESULT_FORMAT,
        "version": 1,
        "seed": seed,
        "duration": duration,
        "generated": generated,
        "entered": entered,
        "blockedAtEntry": blocked,
        "completed": completed,
        "active": active,
        "conserved": entered == completed + active,
        "meanTravelSeconds": round(travel_total / completed, 3) if completed else None,
        "meanDelaySeconds": round(delay_total / completed, 3) if completed else None,
        "totalTravelSeconds": round(travel_total, 3),
        "totalDelaySeconds": round(delay_total, 3),
        "unroutable": unroutable,
        "routes": [
            {
                "origin": f.origin,
                "destination": f.destination,
                "path": p,
                "freeFlowSeconds": (
                    round(sum(links[i].length / links[i].speed for i in p), 3)
                    if p
                    else None
                ),
            }
            for f, p in zip(flows, routes)
        ],
        "perLink": {
            k: {
                "passed": passed_link[k],
                "peakOccupancy": peak[k],
                "occupancy": len(queues[k]),
            }
            for k in sorted(links)
        },
        "perNode": {n: {"passed": passed_node[n]} for n in sorted(nodes)},
    }
