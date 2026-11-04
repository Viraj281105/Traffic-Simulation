"""Step-wise interface to the network simulator (F18, W44).

``src.networks.network_sim.simulate_network`` runs a whole episode in one call
with a hard-wired two-phase fixed schedule, so a learning agent cannot act
between ticks. Its loop keeps all state in locals, so it cannot be driven from
outside without editing it. This module is the minimal stepping API instead:
:class:`NetworkStepper` reuses the module's public constants, ``Flow``,
``_Vehicle`` and ``_capacity`` and replays the *same* per-tick rules (gate
arrivals from one ``random.Random(seed)``, nodes in id order, saturation
credit, spillback, signal axis gating), changing only where the signal phase
comes from.

* With ``phases=None`` every signalised node follows the original fixed
  schedule and the stepper reproduces ``simulate_network`` exactly (a test
  checks completed, delay and per-link counts).
* With ``phases={node: 0|1}`` a node serves that phase (0 = east-west,
  1 = north-south, as in the original). Changing a node's phase costs
  ``clearance`` seconds in which that node passes nothing (lost time), so
  flicker is never free.

Standard library only; it does not touch ``backend/src/networks``.
"""

from __future__ import annotations

import random
from collections import deque
from typing import Any, Deque, Dict, List, Mapping, Optional, Tuple

from src.networks.graph import GraphLink, RoadGraph, shortest_path
from src.networks.network_sim import (
    RESULT_FORMAT,
    SATURATION_PER_LANE,
    SIGNAL_CYCLE,
    Flow,
    _capacity,
    _Vehicle,
)

PHASE_EW = 0
PHASE_NS = 1


class NetworkStepper:
    """One network run advanced ``dt`` seconds at a time."""

    def __init__(
        self,
        graph: RoadGraph,
        flows: List[Flow],
        seed: int = 1,
        dt: float = 1.0,
        signal_cycle: float = SIGNAL_CYCLE,
        clearance: float = 0.0,
    ) -> None:
        if dt <= 0:
            raise ValueError("dt must be positive")
        if clearance < 0:
            raise ValueError("clearance must be >= 0")
        self.graph = graph
        self.flows = list(flows)
        self.seed = seed
        self.dt = dt
        self.signal_cycle = signal_cycle
        self.clearance = clearance
        self.rng = random.Random(seed)
        self.nodes = graph.node_map()
        self.links = graph.link_map()
        self.incoming = graph.incoming()
        self.outgoing = graph.outgoing()

        self.routes: List[Optional[List[str]]] = []
        self.unroutable: List[str] = []
        for f in self.flows:
            path = shortest_path(graph, f.origin, f.destination)
            if not path:
                self.unroutable.append(f"{f.origin}->{f.destination}")
                path = None
            self.routes.append(path)

        self.queues: Dict[str, Deque[Tuple[_Vehicle, float]]] = {
            k: deque() for k in self.links
        }
        self.credit: Dict[str, float] = {k: 0.0 for k in self.links}
        self.peak: Dict[str, int] = {k: 0 for k in self.links}
        self.passed_link: Dict[str, int] = {k: 0 for k in self.links}
        self.passed_node: Dict[str, int] = {n: 0 for n in self.nodes}
        self.axis: Dict[str, str] = {}
        for k in self.links.values():
            a, b = self.nodes[k.from_], self.nodes[k.to]
            self.axis[k.id] = "ew" if abs(b.x - a.x) >= abs(b.y - a.y) else "ns"

        # Nodes a controller can act on: signalised, with traffic arriving.
        self.signal_nodes: List[str] = sorted(
            n
            for n, node in self.nodes.items()
            if node.control == "signal" and self.incoming[n]
        )
        self.phase: Dict[str, int] = {n: PHASE_EW for n in self.signal_nodes}
        self.time_in_phase: Dict[str, float] = {n: 0.0 for n in self.signal_nodes}
        self.clear_left: Dict[str, float] = {n: 0.0 for n in self.signal_nodes}
        self._pending: Dict[str, int] = {n: PHASE_EW for n in self.signal_nodes}
        self.switches: Dict[str, int] = {n: 0 for n in self.signal_nodes}

        self.step_index = 0
        self.generated = self.entered = self.blocked = self.completed = 0
        self.travel_total = 0.0
        self.delay_total = 0.0
        self.waiting_seconds = 0.0
        self._next_id = 0

    # -- clock -------------------------------------------------------
    @property
    def time(self) -> float:
        return self.step_index * self.dt

    def scheduled_phase(self, t: float) -> int:
        """The original fixed schedule: east-west first, then north-south."""
        return int(t // (self.signal_cycle / 2.0)) % 2

    # -- queries (read only) ------------------------------------------
    def waiting(self, link_id: str) -> int:
        """Vehicles at the stop line of ``link_id`` (arrived and not yet served)."""
        t = self.time
        n = 0
        for _veh, ready in self.queues[link_id]:
            if ready > t:
                break
            n += 1
        return n

    def occupancy(self, link_id: str) -> float:
        """Fraction of the link's storage in use, 0..1."""
        return min(1.0, len(self.queues[link_id]) / _capacity(self.links[link_id]))

    def node_axis_waiting(self, node_id: str) -> Dict[str, int]:
        out = {"ew": 0, "ns": 0}
        for link in self.incoming[node_id]:
            out[self.axis[link.id]] += self.waiting(link.id)
        return out

    def node_pressure(self, node_id: str) -> Dict[str, float]:
        """Max-pressure per axis: waiting upstream minus vehicles on the
        straight-ahead downstream link (0 when that link leaves at a gate)."""
        out = {"ew": 0.0, "ns": 0.0}
        for link in self.incoming[node_id]:
            ax = self.axis[link.id]
            down = 0.0
            for nxt in self.outgoing.get(node_id, []):
                if self.axis[nxt.id] == ax and nxt.to != link.from_:
                    if self.nodes[nxt.to].kind != "gate":
                        down += len(self.queues[nxt.id])
                    break
            out[ax] += self.waiting(link.id) - down
        return out

    def in_transition(self, node_id: str) -> bool:
        return self.clear_left[node_id] > 0.0

    def active_vehicles(self) -> int:
        return sum(len(q) for q in self.queues.values())

    # -- step ----------------------------------------------------------
    def _update_signals(self, phases: Optional[Mapping[str, int]], t: float) -> None:
        if phases is None:
            p = self.scheduled_phase(t)
            for n in self.signal_nodes:
                if p != self.phase[n]:
                    self.switches[n] += 1
                    self.time_in_phase[n] = 0.0
                self.phase[n] = p
                self.time_in_phase[n] += self.dt
            return
        for n in self.signal_nodes:
            if self.clear_left[n] > 0.0:
                self.clear_left[n] -= self.dt
                if self.clear_left[n] <= 1e-9:
                    self.clear_left[n] = 0.0
                    self.phase[n] = self._pending[n]
                    self.time_in_phase[n] = 0.0
                continue
            want = int(phases.get(n, self.phase[n]))
            if want not in (PHASE_EW, PHASE_NS):
                raise ValueError(f"phase for {n!r} must be 0 or 1, got {want}")
            if want != self.phase[n]:
                self.switches[n] += 1
                if self.clearance <= 0.0:
                    self.phase[n] = want
                    self.time_in_phase[n] = 0.0
                else:
                    self._pending[n] = want
                    self.clear_left[n] = self.clearance
                    continue
            self.time_in_phase[n] += self.dt

    def step(self, phases: Optional[Mapping[str, int]] = None) -> None:
        """Advance one ``dt``. ``phases=None`` runs the fixed schedule."""
        t = self.time
        dt = self.dt
        links, queues, credit = self.links, self.queues, self.credit
        for f, path in zip(self.flows, self.routes):
            if path is None or f.vehicles_per_hour <= 0:
                continue
            if self.rng.random() < min(1.0, f.vehicles_per_hour / 3600.0 * dt):
                self.generated += 1
                first = links[path[0]]
                if len(queues[first.id]) >= _capacity(first):
                    self.blocked += 1
                    continue
                ff = sum(links[p].length / links[p].speed for p in path)
                veh = _Vehicle(self._next_id, path, 0, t, ff)
                self._next_id += 1
                self.entered += 1
                queues[first.id].append((veh, t + first.length / first.speed))
                self.peak[first.id] = max(self.peak[first.id], len(queues[first.id]))

        self._update_signals(phases, t)

        for node_id in sorted(self.nodes):
            node = self.nodes[node_id]
            for link in self.incoming[node_id]:
                credit[link.id] = min(
                    credit[link.id] + link.lanes * SATURATION_PER_LANE * dt,
                    float(link.lanes),
                )
                if node.control == "signal":
                    if self.clear_left.get(node_id, 0.0) > 0.0:
                        continue
                    if (self.axis[link.id] == "ew") != (
                        self.phase[node_id] == PHASE_EW
                    ):
                        continue
                self._serve(link, node_id, t)

        self.step_index += 1
        self.waiting_seconds += sum(self.waiting(k) for k in self.links) * dt

    def _serve(self, link: GraphLink, node_id: str, t: float) -> None:
        q = self.queues[link.id]
        while q and self.credit[link.id] >= 1.0 and q[0][1] <= t:
            veh = q[0][0]
            if veh.index == len(veh.path) - 1:  # arrives at its destination
                q.popleft()
                self.credit[link.id] -= 1.0
                self.passed_link[link.id] += 1
                self.passed_node[node_id] += 1
                self.completed += 1
                elapsed = t - veh.entered_at
                self.travel_total += elapsed
                self.delay_total += max(0.0, elapsed - veh.free_flow)
                continue
            nxt = self.links[veh.path[veh.index + 1]]
            if len(self.queues[nxt.id]) >= _capacity(nxt):
                break  # spillback: head of line waits
            q.popleft()
            self.credit[link.id] -= 1.0
            self.passed_link[link.id] += 1
            self.passed_node[node_id] += 1
            veh.index += 1
            self.queues[nxt.id].append((veh, t + nxt.length / nxt.speed))
            self.peak[nxt.id] = max(self.peak[nxt.id], len(self.queues[nxt.id]))

    # -- result ----------------------------------------------------------
    def summary(self) -> Dict[str, Any]:
        """Same keys as ``simulate_network`` (minus ``routes``) plus step extras."""
        active = self.active_vehicles()
        done = self.completed
        return {
            "format": RESULT_FORMAT,
            "version": 1,
            "seed": self.seed,
            "duration": self.time,
            "generated": self.generated,
            "entered": self.entered,
            "blockedAtEntry": self.blocked,
            "completed": done,
            "active": active,
            "conserved": self.entered == done + active,
            "meanTravelSeconds": round(self.travel_total / done, 3) if done else None,
            "meanDelaySeconds": round(self.delay_total / done, 3) if done else None,
            "unroutable": list(self.unroutable),
            "perLink": {
                k: {
                    "passed": self.passed_link[k],
                    "peakOccupancy": self.peak[k],
                    "occupancy": len(self.queues[k]),
                }
                for k in sorted(self.links)
            },
            "perNode": {n: {"passed": self.passed_node[n]} for n in sorted(self.nodes)},
            "waitingVehicleSeconds": self.waiting_seconds,
            "switches": dict(self.switches),
        }
