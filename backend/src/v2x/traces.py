"""Per-vehicle traces of a mesoscopic network run.

``simulate_network`` reports only totals, and ``src.networks`` is not to be
changed, so the V2X harness reads the run through the simulator's read-only
``observer`` hook: after every step it sees each link's FIFO queue, and a
vehicle's journey is rebuilt from when it appears in a queue (it entered the
link, and is ready at the stop line one free-flow crossing later) and when it
disappears (it was handed to the next link or left the network).

Nothing here influences the run, so the baseline is exactly the plain
``simulate_network`` result for the same seed.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence

from src.networks.graph import RoadGraph
from src.networks.network_sim import Flow, simulate_network


@dataclass
class Leg:
    """One vehicle on one link: it entered at ``enter``, reached the stop line
    at ``ready`` and was released at ``depart`` (None while still queued)."""

    link: str
    enter: float
    ready: float
    depart: Optional[float] = None

    @property
    def wait(self) -> float:
        return max(
            0.0, (self.depart if self.depart is not None else self.ready) - self.ready
        )


@dataclass
class VehicleTrace:
    vid: int
    path: List[str]
    legs: List[Leg] = field(default_factory=list)

    @property
    def completed(self) -> bool:
        return len(self.legs) == len(self.path) and self.legs[-1].depart is not None


class TraceRecorder:
    """Observer for ``simulate_network`` that builds :class:`VehicleTrace` s."""

    def __init__(self, link_cross_seconds: Mapping[str, float]) -> None:
        self._cross = link_cross_seconds
        self._present: Dict[str, Dict[int, Leg]] = {}
        self.traces: Dict[int, VehicleTrace] = {}

    def __call__(
        self, t: float, queues: Mapping[str, Any], passed: Mapping[str, int]
    ) -> None:
        for lid, q in queues.items():
            prev = self._present.get(lid, {})
            cur: Dict[int, Leg] = {}
            for veh, ready in q:
                leg = prev.get(veh.vid)
                if leg is None:
                    leg = Leg(lid, ready - self._cross[lid], ready)
                    trace = self.traces.get(veh.vid)
                    if trace is None:
                        trace = self.traces[veh.vid] = VehicleTrace(
                            veh.vid, list(veh.path)
                        )
                    trace.legs.append(leg)
                cur[veh.vid] = leg
            for vid, leg in prev.items():
                if vid not in cur:
                    leg.depart = t
            self._present[lid] = cur


def run_traced(
    graph: RoadGraph, flows: Sequence[Flow], duration: float, seed: int
) -> tuple[Dict[str, Any], List[VehicleTrace]]:
    """Run the network once and return ``(result, completed traces)``, the
    traces ordered by vehicle id."""
    links = graph.link_map()
    rec = TraceRecorder({k: v.length / v.speed for k, v in links.items()})
    result = simulate_network(graph, list(flows), duration, seed, observer=rec)
    done = [tr for _, tr in sorted(rec.traces.items()) if tr.completed]
    return result, done
