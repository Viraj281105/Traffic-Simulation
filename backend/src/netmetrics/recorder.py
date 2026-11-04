"""Per-step recording of a network run (read-only observer of
``simulate_network``): occupancy, queue, blocking and cumulative departures
for every link, as numpy matrices of shape ``(steps, links)``."""

from typing import Any, Deque, Dict, List, Tuple

import numpy as np

from src.networks.graph import RoadGraph
from src.networks.network_sim import Flow, _capacity, simulate_network

MAX_CELLS = 6_000_000  # steps x links; bounds memory (about 80 MB of matrices)


class Recorder:
    """Pass an instance as ``observer=`` to :func:`simulate_network`.

    * ``occ``     vehicles on the link (in transit plus queued)
    * ``queue``   vehicles that have reached the link end and wait to be passed
    * ``blocked`` the head vehicle is ready but the next link is full: the
                  index of that next link, or -1 (this is spillback)
    * ``cum``     cumulative vehicles passed at the link end
    """

    def __init__(self, graph: RoadGraph, steps: int, dt: float) -> None:
        self.link_ids: List[str] = sorted(k.id for k in graph.links)
        self.index: Dict[str, int] = {k: i for i, k in enumerate(self.link_ids)}
        links = graph.link_map()
        n = len(self.link_ids)
        if steps * n > MAX_CELLS:
            raise ValueError(
                f"{steps} steps x {n} links is too large to analyse "
                f"(limit {MAX_CELLS} cells); shorten the run or use a larger step"
            )
        self.steps = steps
        self.dt = dt
        self.capacity = np.array(
            [_capacity(links[k]) for k in self.link_ids], dtype=np.int64
        )
        self.occ = np.zeros((steps, n), dtype=np.int32)
        self.queue = np.zeros((steps, n), dtype=np.int32)
        self.blocked = np.full((steps, n), -1, dtype=np.int16)
        self.cum = np.zeros((steps, n), dtype=np.int32)
        self._cap = {k: int(self.capacity[i]) for i, k in enumerate(self.link_ids)}
        self._i = 0

    def __call__(
        self,
        t: float,
        queues: Dict[str, Deque[Tuple[Any, float]]],
        passed: Dict[str, int],
    ) -> None:
        i = self._i
        if i >= self.steps:
            return
        self._i += 1
        occ, queue, blocked, cum = (
            self.occ[i],
            self.queue[i],
            self.blocked[i],
            self.cum[i],
        )
        for j, lid in enumerate(self.link_ids):
            q = queues[lid]
            n = len(q)
            cum[j] = passed[lid]
            if not n:
                continue
            occ[j] = n
            transit = 0
            for _, ready in reversed(q):  # ready times grow along the deque
                if ready > t:
                    transit += 1
                else:
                    break
            queue[j] = n - transit
            head, ready = q[0]
            if ready <= t and head.index < len(head.path) - 1:
                nxt = head.path[head.index + 1]
                if len(queues[nxt]) >= self._cap[nxt]:
                    blocked[j] = self.index[nxt]


def run_recorded(
    graph: RoadGraph,
    flows: List[Flow],
    duration: float,
    seed: int = 1,
    dt: float = 1.0,
) -> Tuple[Dict[str, Any], Recorder]:
    steps = int(round(duration / dt))
    rec = Recorder(graph, steps, dt)
    result = simulate_network(
        graph, flows, duration=duration, seed=seed, dt=dt, observer=rec
    )
    return result, rec


def bucketize(arr: np.ndarray, steps_per_bucket: int, how: str = "mean") -> np.ndarray:
    """Reduce rows (time) to buckets: ``mean``, ``max`` or ``sum``. The last
    bucket may be shorter; its mean uses only the steps it has."""
    n = arr.shape[0]
    starts = np.arange(0, n, steps_per_bucket)
    if how == "max":
        return np.maximum.reduceat(arr, starts, axis=0)
    total = np.add.reduceat(arr.astype(np.float64), starts, axis=0)
    if how == "sum":
        return total
    counts = np.diff(np.append(starts, n)).astype(np.float64)
    shape = (-1,) + (1,) * (arr.ndim - 1)
    return total / counts.reshape(shape)
