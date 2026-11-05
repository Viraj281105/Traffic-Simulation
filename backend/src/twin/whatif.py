"""What-if fork: run a scenario variant from the twin's current state.

A scenario is a handful of simple parameter changes on the graph and demand
(close a link, reduce lanes, scale speeds, scale demand). The baseline and the
variant run on the same demand (the latest observations' implied flows), the
same seed and the same horizon, so the delta is the effect of the change.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.networks.graph import RoadGraph
from src.networks.network_sim import Flow
from src.twin.runner import TwinRunner, predict_counts


@dataclass(frozen=True)
class Scenario:
    close_links: List[str] = field(default_factory=list)
    demand_scale: float = 1.0
    lanes: Dict[str, int] = field(default_factory=dict)  # link id -> new lane count
    speed_factors: Dict[str, float] = field(
        default_factory=dict
    )  # link id -> multiplier


def apply_scenario(
    graph: RoadGraph, flows: List[Flow], scenario: Scenario
) -> Tuple[RoadGraph, List[Flow]]:
    """Return ``(graph, flows)`` with the scenario applied; the inputs are
    not modified. Unknown link ids raise ``ValueError``."""
    known = graph.link_map()
    named = (
        set(scenario.close_links) | set(scenario.lanes) | set(scenario.speed_factors)
    )
    unknown = sorted(named - set(known))
    if unknown:
        raise ValueError(f"unknown link(s): {', '.join(unknown)}")
    if scenario.demand_scale < 0:
        raise ValueError("demand_scale must not be negative")
    if any(f <= 0 for f in scenario.speed_factors.values()):
        raise ValueError("speed factors must be positive")
    if any(n < 1 for n in scenario.lanes.values()):
        raise ValueError("lane counts must be at least 1 (close the link instead)")
    links = []
    for link in graph.links:
        if link.id in scenario.close_links:
            continue
        changes: Dict[str, Any] = {}
        if link.id in scenario.lanes:
            changes["lanes"] = scenario.lanes[link.id]
        if link.id in scenario.speed_factors:
            changes["speed"] = link.speed * scenario.speed_factors[link.id]
        links.append(link.model_copy(update=changes) if changes else link)
    variant = graph.model_copy(update={"links": links})
    scaled = [
        Flow(f.origin, f.destination, f.vehicles_per_hour * scenario.demand_scale)
        for f in flows
    ]
    return variant, scaled


def _delta(a: Optional[float], b: Optional[float]) -> Optional[float]:
    return None if a is None or b is None else round(b - a, 6)


def what_if(
    twin: TwinRunner, scenario: Scenario, horizon_windows: int = 1
) -> Dict[str, Any]:
    """Fork ``twin`` and compare baseline with variant over the next
    ``horizon_windows`` windows. The twin itself is not changed."""
    if horizon_windows < 1:
        raise ValueError("horizon_windows must be at least 1")
    flows = twin.current_flows()
    window = (twin.latest_window + 1) if twin.latest_window is not None else 0
    seed = twin.seed + window
    base = predict_counts(
        twin.graph, flows, twin.interval, twin.warmup, seed, horizon_windows
    )
    graph, scaled = apply_scenario(twin.graph, flows, scenario)
    var = predict_counts(
        graph, scaled, twin.interval, twin.warmup, seed, horizon_windows
    )
    links = sorted(twin.graph.link_map())
    per_link = {
        k: {
            "baseline": base["counts"][k],
            "variant": var["counts"].get(k),  # None: the link is closed
            "delta": None
            if k not in var["counts"]
            else var["counts"][k] - base["counts"][k],
            "peakOccupancyDelta": None
            if k not in var["peakOccupancy"]
            else var["peakOccupancy"][k] - base["peakOccupancy"][k],
        }
        for k in links
    }
    return {
        "window": window,
        "horizonWindows": horizon_windows,
        "scenario": {
            "closeLinks": list(scenario.close_links),
            "demandScale": scenario.demand_scale,
            "lanes": dict(scenario.lanes),
            "speedFactors": dict(scenario.speed_factors),
        },
        "baseline": {
            k: base[k] for k in ("completed", "meanDelaySeconds", "meanTravelSeconds")
        },
        "variant": {
            **{
                k: var[k]
                for k in ("completed", "meanDelaySeconds", "meanTravelSeconds")
            },
            "unroutable": var["unroutable"],
        },
        "delta": {
            "completed": var["completed"] - base["completed"],
            "meanDelaySeconds": _delta(
                base["meanDelaySeconds"], var["meanDelaySeconds"]
            ),
            "meanTravelSeconds": _delta(
                base["meanTravelSeconds"], var["meanTravelSeconds"]
            ),
        },
        "perLink": per_link,
    }
