"""The twin runner: observations in, a prediction timeline out.

Time is cut into windows of ``interval`` seconds from ``start``. The demand
for window k is implied by the observations of window k-1 (the latest
complete window): the counts on the links leaving each origin gate give that
origin's observed rate, and the base flows from that origin are scaled to
match it. With no observation yet the base flows are used. The network
simulator then runs ``warmup + interval`` seconds under a fixed seed, and the
vehicles that crossed each link in the last ``interval`` seconds (the
cumulative count minus the same run stopped at ``warmup``) are the prediction.
Everything is deterministic under the seed.
"""

import math
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

from src.networks.graph import RoadGraph
from src.networks.network_sim import Flow, simulate_network
from src.twin.compare import compare
from src.twin.models import Observation

STATE_FORMAT = "urbanflow-twin-state"
MAX_WINDOWS = 96


def predict_counts(
    graph: RoadGraph,
    flows: Sequence[Flow],
    interval: float,
    warmup: float,
    seed: int,
    windows: int = 1,
) -> Dict[str, Any]:
    """Run the simulator and return per-link crossings over the last
    ``windows * interval`` seconds plus the whole-run summary."""
    span = interval * windows
    flows = list(flows)
    full = simulate_network(graph, flows, duration=warmup + span, seed=seed)
    if warmup > 0:
        base = simulate_network(graph, flows, duration=warmup, seed=seed)["perLink"]
    else:
        base = {k: {"passed": 0} for k in full["perLink"]}
    counts = {
        k: full["perLink"][k]["passed"] - base[k]["passed"] for k in full["perLink"]
    }
    return {
        "counts": counts,
        "peakOccupancy": {k: v["peakOccupancy"] for k, v in full["perLink"].items()},
        "completed": full["completed"],
        "meanDelaySeconds": full["meanDelaySeconds"],
        "meanTravelSeconds": full["meanTravelSeconds"],
        "unroutable": full["unroutable"],
    }


class TwinRunner:
    def __init__(
        self,
        graph: RoadGraph,
        base_flows: Sequence[Flow],
        interval: float = 60.0,
        warmup: float = 120.0,
        seed: int = 1,
        start: float = 0.0,
        alert_threshold_pct: float = 25.0,
    ) -> None:
        if interval <= 0:
            raise ValueError("interval must be positive")
        if warmup < 0:
            raise ValueError("warmup must not be negative")
        self.graph = graph
        self.base_flows = list(base_flows)
        self.interval = interval
        self.warmup = warmup
        self.seed = seed
        self.start = start
        self.alert_threshold_pct = alert_threshold_pct
        self.observed: Dict[int, Dict[str, float]] = {}
        self.speeds: Dict[int, Dict[str, float]] = {}
        self.predicted: Dict[int, Dict[str, float]] = {}
        self.flows_used: Dict[int, List[Flow]] = {}
        self._links = graph.link_map()
        self._gate_ids = {n.id for n in graph.nodes if n.kind == "gate"}

    # -- ingest -----------------------------------------------------------
    def window_of(self, timestamp: float) -> int:
        return int(math.floor((timestamp - self.start) / self.interval + 1e-9))

    def ingest(self, observations: Iterable[Observation]) -> int:
        """Add observations (same link and window add up). Observations on
        unknown links or before ``start`` are ignored; returns how many were
        taken."""
        taken = 0
        for o in observations:
            w = self.window_of(o.timestamp)
            if w < 0 or o.link_id not in self._links:
                continue
            row = self.observed.setdefault(w, {})
            row[o.link_id] = row.get(o.link_id, 0.0) + o.count
            if o.mean_speed is not None:
                self.speeds.setdefault(w, {})[o.link_id] = o.mean_speed
            taken += 1
        return taken

    @property
    def latest_window(self) -> Optional[int]:
        return max(self.observed) if self.observed else None

    # -- demand -----------------------------------------------------------
    def implied_flows(self, window: Optional[int]) -> List[Flow]:
        """Base flows with each observed origin gate rescaled to the rate the
        entry-link counts of ``window`` show."""
        if window is None or window not in self.observed:
            return list(self.base_flows)
        entry: Dict[str, float] = {}
        seen: Set[str] = set()
        for link_id, count in self.observed[window].items():
            origin = self._links[link_id].from_
            if origin in self._gate_ids:
                entry[origin] = entry.get(origin, 0.0) + count
                seen.add(origin)
        base_rate: Dict[str, float] = {}
        for f in self.base_flows:
            base_rate[f.origin] = base_rate.get(f.origin, 0.0) + f.vehicles_per_hour
        out: List[Flow] = []
        for f in self.base_flows:
            if f.origin in seen and base_rate[f.origin] > 0:
                observed_rate = entry[f.origin] / self.interval * 3600.0
                scale = observed_rate / base_rate[f.origin]
                out.append(Flow(f.origin, f.destination, f.vehicles_per_hour * scale))
            else:
                out.append(f)
        return out

    def current_flows(self) -> List[Flow]:
        """The demand the latest observations imply: what the next window uses."""
        return self.implied_flows(self.latest_window)

    # -- prediction ---------------------------------------------------------
    def predict_window(self, window: int) -> Dict[str, float]:
        flows = self.implied_flows(window - 1) if window > 0 else list(self.base_flows)
        result = predict_counts(
            self.graph, flows, self.interval, self.warmup, self.seed + window
        )
        self.flows_used[window] = flows
        self.predicted[window] = {k: float(v) for k, v in result["counts"].items()}
        return self.predicted[window]

    def run(self) -> None:
        """Predict every window up to and including the latest observed one."""
        last = self.latest_window
        if last is None:
            return
        if last + 1 > MAX_WINDOWS:
            raise ValueError(f"at most {MAX_WINDOWS} windows are supported")
        for w in range(last + 1):
            if w not in self.predicted:
                self.predict_window(w)

    # -- comparison and state ---------------------------------------------
    def compare(self) -> Dict[str, Any]:
        return compare(
            self.predicted, self.observed, self.interval, self.alert_threshold_pct
        )

    def state(self) -> Dict[str, Any]:
        """The twin's state as plain JSON for a dashboard."""
        windows = sorted(self.predicted)
        return {
            "format": STATE_FORMAT,
            "version": 1,
            "graph": self.graph.name,
            "intervalSeconds": self.interval,
            "warmupSeconds": self.warmup,
            "seed": self.seed,
            "start": self.start,
            "latestWindow": self.latest_window,
            "currentFlows": [
                {
                    "origin": f.origin,
                    "destination": f.destination,
                    "vehiclesPerHour": round(f.vehicles_per_hour, 6),
                }
                for f in self.current_flows()
            ],
            "timeline": [
                {
                    "window": w,
                    "time": self.start + w * self.interval,
                    "predicted": self.predicted[w],
                    "observed": self.observed.get(w, {}),
                    "observedSpeed": self.speeds.get(w, {}),
                }
                for w in windows
            ],
            "comparison": self.compare(),
        }
