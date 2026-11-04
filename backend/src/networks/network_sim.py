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
from typing import Any, Deque, Dict, List, Optional, Tuple

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


def simulate_network(
    graph: RoadGraph,
    flows: List[Flow],
    duration: float = 300.0,
    seed: int = 1,
    dt: float = 1.0,
    signal_cycle: float = SIGNAL_CYCLE,
) -> Dict[str, Any]:
    """Run the network for ``duration`` seconds. Deterministic under ``seed``."""
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

    generated = entered = blocked = completed = 0
    travel_total = delay_total = 0.0
    next_id = 0
    steps = int(round(duration / dt))
    for step in range(steps):
        t = step * dt
        # Gates: Bernoulli arrivals approximate Poisson at small dt.
        for f, path in zip(flows, routes):
            if path is None or f.vehicles_per_hour <= 0:
                continue
            if rng.random() < min(1.0, f.vehicles_per_hour / 3600.0 * dt):
                generated += 1
                first = links[path[0]]
                if len(queues[first.id]) >= _capacity(first):
                    blocked += 1
                    continue
                ff = sum(links[p].length / links[p].speed for p in path)
                veh = _Vehicle(next_id, path, 0, t, ff)
                next_id += 1
                entered += 1
                queues[first.id].append((veh, t + first.length / first.speed))
                peak[first.id] = max(peak[first.id], len(queues[first.id]))
        # Nodes in id order; a vehicle moved this tick is ready only later.
        for node_id in sorted(nodes):
            node = nodes[node_id]
            for link in incoming[node_id]:
                credit[link.id] = min(
                    credit[link.id] + link.lanes * SATURATION_PER_LANE * dt,
                    float(link.lanes),
                )
                if node.control == "signal":
                    phase = int(t // (signal_cycle / 2.0)) % 2
                    if (axis[link.id] == "ew") != (phase == 0):
                        continue
                q = queues[link.id]
                while q and credit[link.id] >= 1.0 and q[0][1] <= t:
                    veh = q[0][0]
                    if veh.index == len(veh.path) - 1:  # arrives at its destination
                        q.popleft()
                        credit[link.id] -= 1.0
                        passed_link[link.id] += 1
                        passed_node[node_id] += 1
                        completed += 1
                        elapsed = t - veh.entered_at
                        travel_total += elapsed
                        delay_total += max(0.0, elapsed - veh.free_flow)
                        continue
                    nxt = links[veh.path[veh.index + 1]]
                    if len(queues[nxt.id]) >= _capacity(nxt):
                        break  # spillback: head of line waits
                    q.popleft()
                    credit[link.id] -= 1.0
                    passed_link[link.id] += 1
                    passed_node[node_id] += 1
                    veh.index += 1
                    queues[nxt.id].append((veh, t + nxt.length / nxt.speed))
                    peak[nxt.id] = max(peak[nxt.id], len(queues[nxt.id]))

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
            k: {"passed": passed_link[k], "peakOccupancy": peak[k], "occupancy": len(queues[k])}
            for k in sorted(links)
        },
        "perNode": {n: {"passed": passed_node[n]} for n in sorted(nodes)},
    }
