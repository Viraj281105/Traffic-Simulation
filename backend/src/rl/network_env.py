"""Gymnasium environment over the road-network simulator (F18, W44).

One central agent controls **every signalised node** of a
:class:`~src.networks.graph.RoadGraph`, driven through
:class:`~src.rl.network_stepper.NetworkStepper`.

* **Action** -- ``MultiDiscrete([2] * n_nodes)``: for each signalised node
  (sorted by id, see ``signal_nodes``) which phase to serve for the next
  decision interval (0 = east-west, 1 = north-south). A minimum green is
  enforced here and a clearance (lost time) by the stepper, so the agent can
  be inefficient but not unsafe.
* **Observation** -- ``Box(n_nodes * NODE_FEATURES,)`` in [0, 1]. Per node:
  waiting vehicles on its east-west and north-south approaches, occupancy of
  the east-west and north-south links leaving it (spillback warning), the
  serving phase as a one-hot, an in-clearance flag, time in phase, and the
  mean east-west / north-south waiting of the adjacent signalised nodes
  (the neighbour view).
* **Reward** -- negative delay: minus the vehicle-seconds spent waiting at stop
  lines over the interval, over ``reward_scale`` (``"queue"`` mode: minus the
  waiting vehicles at the end of the interval over ``queue_cap`` times the
  number of nodes).
* **Determinism** -- ``reset(seed=s)`` fixes the arrival stream. Same seed and
  same actions give the same episode.

Needs ``gymnasium`` and ``numpy`` (``backend/requirements-rl.txt``).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from src.networks.graph import GraphLink, GraphNode, RoadGraph
from src.networks.network_sim import Flow
from src.rl.network_stepper import NetworkStepper

NODE_FEATURES = 10


def demo_network(
    rows: int = 2,
    cols: int = 2,
    spacing: float = 200.0,
    vehicles_per_hour: float = 450.0,
    lanes: int = 1,
) -> Tuple[RoadGraph, List[Flow]]:
    """A small signalised grid with gates on every open end and through flows.

    Self-contained on purpose (it does not depend on the grid scenario module),
    so the RL package works on any checkout.
    """
    if rows < 1 or cols < 1:
        raise ValueError("rows and cols must be >= 1")
    pos: Dict[str, Tuple[float, float]] = {}
    for r in range(rows):
        for c in range(cols):
            pos[f"J{r}{c}"] = (c * spacing, -r * spacing)
    for r in range(rows):
        pos[f"GW{r}"] = (-spacing, -r * spacing)
        pos[f"GE{r}"] = (cols * spacing, -r * spacing)
    for c in range(cols):
        pos[f"GN{c}"] = (c * spacing, spacing)
        pos[f"GS{c}"] = (c * spacing, -rows * spacing)
    nodes = [
        GraphNode(
            id=n,
            x=x,
            y=y,
            kind="junction" if n.startswith("J") else "gate",
            control="signal" if n.startswith("J") else None,
        )
        for n, (x, y) in sorted(pos.items())
    ]

    def road(a: str, b: str) -> List[GraphLink]:
        (ax, ay), (bx, by) = pos[a], pos[b]
        length = abs(bx - ax) + abs(by - ay)
        return [
            GraphLink(id=f"{p}>{q}", **{"from": p, "to": q}, length=length, lanes=lanes)
            for p, q in ((a, b), (b, a))
        ]

    links: List[GraphLink] = []
    for r in range(rows):
        links += road(f"GW{r}", f"J{r}0")
        for c in range(cols - 1):
            links += road(f"J{r}{c}", f"J{r}{c + 1}")
        links += road(f"J{r}{cols - 1}", f"GE{r}")
    for c in range(cols):
        links += road(f"GN{c}", f"J0{c}")
        for r in range(rows - 1):
            links += road(f"J{r}{c}", f"J{r + 1}{c}")
        links += road(f"J{rows - 1}{c}", f"GS{c}")
    graph = RoadGraph(
        name=f"{rows}x{cols} demo grid", source="demo", nodes=nodes, links=links
    )
    flows: List[Flow] = []
    for r in range(rows):
        flows.append(Flow(f"GW{r}", f"GE{r}", vehicles_per_hour))
        flows.append(Flow(f"GE{r}", f"GW{r}", vehicles_per_hour))
    for c in range(cols):
        flows.append(Flow(f"GN{c}", f"GS{c}", vehicles_per_hour * 0.6))
        flows.append(Flow(f"GS{c}", f"GN{c}", vehicles_per_hour * 0.6))
    return graph, flows


class NetworkSignalEnv(gym.Env):  # type: ignore[misc]
    metadata = {"render_modes": []}

    def __init__(
        self,
        graph: Optional[RoadGraph] = None,
        flows: Optional[Sequence[Flow]] = None,
        episode_seconds: float = 300.0,
        decision_interval: float = 5.0,
        min_green: float = 5.0,
        clearance: float = 2.0,
        dt: float = 1.0,
        queue_cap: float = 12.0,
        reward_mode: str = "delay",
        reward_scale: float = 50.0,
        max_phase_norm: float = 60.0,
        demand_scale: float = 1.0,
    ) -> None:
        super().__init__()
        if reward_mode not in ("delay", "queue"):
            raise ValueError("reward_mode must be 'delay' or 'queue'")
        if decision_interval < dt or episode_seconds < decision_interval:
            raise ValueError("need dt <= decision_interval <= episode_seconds")
        if graph is None:
            graph, default_flows = demo_network()
            flows = flows if flows is not None else default_flows
        elif flows is None:
            raise ValueError("flows are required with a custom graph")
        self.graph = graph
        self.flows: List[Flow] = [
            Flow(f.origin, f.destination, f.vehicles_per_hour * demand_scale)
            for f in flows
        ]
        self.params: Dict[str, Any] = {
            "graph": graph.name,
            "episode_seconds": episode_seconds,
            "decision_interval": decision_interval,
            "min_green": min_green,
            "clearance": clearance,
            "dt": dt,
            "queue_cap": queue_cap,
            "reward_mode": reward_mode,
            "reward_scale": reward_scale,
            "max_phase_norm": max_phase_norm,
            "demand_scale": demand_scale,
            "flows": [
                [f.origin, f.destination, f.vehicles_per_hour] for f in self.flows
            ],
        }
        probe = NetworkStepper(graph, self.flows, seed=0, dt=dt, clearance=clearance)
        self.signal_nodes: List[str] = list(probe.signal_nodes)
        if not self.signal_nodes:
            raise ValueError("the network has no signalised node to control")
        self._neighbours = self._neighbour_map(probe)
        n = len(self.signal_nodes)
        self.action_space = spaces.MultiDiscrete([2] * n)
        self.observation_space = spaces.Box(0.0, 1.0, (n * NODE_FEATURES,), np.float32)
        self.stepper: Optional[NetworkStepper] = None
        self.episode_seed = 0
        self.sim_time = 0.0
        self._ticks = max(1, int(round(decision_interval / dt)))
        self._return = 0.0

    def _neighbour_map(self, probe: NetworkStepper) -> Dict[str, List[str]]:
        sig = set(self.signal_nodes)
        nb: Dict[str, set] = {n: set() for n in self.signal_nodes}
        for link in self.graph.links:
            if link.from_ in sig and link.to in sig:
                nb[link.from_].add(link.to)
                nb[link.to].add(link.from_)
        return {n: sorted(v) for n, v in nb.items()}

    # ------------------------------------------------------------------
    def reset(
        self, *, seed: Optional[int] = None, options: Optional[Dict[str, Any]] = None
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        super().reset(seed=seed)
        if options and "episode_seed" in options:
            self.episode_seed = int(options["episode_seed"])
        elif seed is not None:
            self.episode_seed = int(seed)
        else:
            self.episode_seed = int(self.np_random.integers(1, 2**31 - 1))
        p = self.params
        self.stepper = NetworkStepper(
            self.graph,
            self.flows,
            seed=self.episode_seed,
            dt=p["dt"],
            clearance=p["clearance"],
        )
        self.sim_time = 0.0
        self._return = 0.0
        return self._observe(), self._info()

    # ------------------------------------------------------------------
    def _node_features(
        self, nid: str, axis_wait: Dict[str, Dict[str, int]]
    ) -> List[float]:
        assert self.stepper is not None
        st, p = self.stepper, self.params
        cap = p["queue_cap"]
        out_occ = {"ew": [], "ns": []}
        for link in st.outgoing.get(nid, []):
            out_occ[st.axis[link.id]].append(st.occupancy(link.id))
        nbs = self._neighbours[nid]
        nb_ew = float(np.mean([axis_wait[b]["ew"] for b in nbs])) if nbs else 0.0
        nb_ns = float(np.mean([axis_wait[b]["ns"] for b in nbs])) if nbs else 0.0
        ph = st.phase[nid]
        return [
            axis_wait[nid]["ew"] / cap,
            axis_wait[nid]["ns"] / cap,
            float(np.mean(out_occ["ew"])) if out_occ["ew"] else 0.0,
            float(np.mean(out_occ["ns"])) if out_occ["ns"] else 0.0,
            1.0 if ph == 0 else 0.0,
            1.0 if ph == 1 else 0.0,
            1.0 if st.in_transition(nid) else 0.0,
            st.time_in_phase[nid] / p["max_phase_norm"],
            nb_ew / cap,
            nb_ns / cap,
        ]

    def _axis_waiting(self) -> Dict[str, Dict[str, int]]:
        assert self.stepper is not None
        return {n: self.stepper.node_axis_waiting(n) for n in self.signal_nodes}

    def _observe(self) -> np.ndarray:
        aw = self._axis_waiting()
        flat: List[float] = []
        for n in self.signal_nodes:
            flat += self._node_features(n, aw)
        return np.clip(np.asarray(flat, dtype=np.float32), 0.0, 1.0)

    def _info(self) -> Dict[str, Any]:
        assert self.stepper is not None
        st = self.stepper
        aw = self._axis_waiting()
        nodes = {
            n: {
                "queues": {"ew": float(aw[n]["ew"]), "ns": float(aw[n]["ns"])},
                "pressure": st.node_pressure(n),
                "active_phase": st.phase[n],
                "in_transition": st.in_transition(n),
                "time_in_phase": st.time_in_phase[n],
            }
            for n in self.signal_nodes
        }
        return {
            "sim_time": self.sim_time,
            "episode_seed": self.episode_seed,
            "nodes": nodes,
            "waiting": float(sum(st.waiting(k) for k in st.links)),
            "throughput": st.completed,
        }

    def step(self, action: Any) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        if self.stepper is None:
            raise RuntimeError("call reset() before step()")
        st, p = self.stepper, self.params
        acts = np.asarray(action).reshape(-1)
        if acts.shape[0] != len(self.signal_nodes):
            raise ValueError(
                f"expected {len(self.signal_nodes)} actions, got {acts.shape[0]}"
            )
        phases: Dict[str, int] = {}
        for nid, a in zip(self.signal_nodes, acts):
            want = int(a)
            if want != st.phase[nid] and st.time_in_phase[nid] < p["min_green"] - 1e-9:
                want = st.phase[nid]  # minimum green not yet served
            phases[nid] = want
        before = st.waiting_seconds
        for _ in range(self._ticks):
            st.step(phases)
        interval_wait = st.waiting_seconds - before
        self.sim_time = st.time
        if p["reward_mode"] == "queue":
            now = float(sum(st.waiting(k) for k in st.links))
            reward = -now / (p["queue_cap"] * len(self.signal_nodes))
        else:
            reward = -interval_wait / p["reward_scale"]
        self._return += reward
        truncated = self.sim_time >= p["episode_seconds"] - 1e-9
        return self._observe(), float(reward), False, truncated, self._info()

    # ------------------------------------------------------------------
    def episode_metrics(self) -> Dict[str, float]:
        """Whole-episode figures for evaluation (valid any time after reset)."""
        assert self.stepper is not None
        st = self.stepper
        s = st.summary()
        entered = max(st.entered, 1)
        mean_delay = s["meanDelaySeconds"]
        return {
            "mean_wait_s": st.waiting_seconds / entered,
            "total_wait_s": st.waiting_seconds,
            "stopped_veh_s": st.waiting_seconds,
            "mean_queue": st.waiting_seconds / max(self.sim_time, 1e-9),
            "throughput": float(st.completed),
            "vehicles": float(st.entered),
            "switches": float(sum(st.switches.values())),
            "episode_return": float(self._return),
            "mean_delay_s": float(mean_delay) if mean_delay is not None else 0.0,
            "blocked": float(st.blocked),
        }
