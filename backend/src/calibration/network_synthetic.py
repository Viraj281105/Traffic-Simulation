"""Synthetic ground truth for network calibration (package 1B proof).

Builds a small signalised grid, simulates it with known parameters, and
writes the link flows out as an interval count file, optionally with seeded
multiplicative noise. The calibration pipeline is then run from perturbed
parameters to show it recovers the known ones. Not real data: the real
dataset hookup is decision D1.
"""

from __future__ import annotations

import random
from typing import Dict, List, Mapping, Sequence, Tuple

from src.calibration.network_counts import CountRecord, counts_to_csv
from src.calibration.network_fit import FitOptions, SimSettings, simulate_link_flows
from src.networks.graph import GraphLink, GraphNode, RoadGraph
from src.networks.network_sim import Flow


def demo_grid(
    rows: int = 2, cols: int = 2, spacing: float = 400.0, speed: float = 13.89
) -> RoadGraph:
    """``rows x cols`` signalised junctions ``J<r><c>`` with a gate on every
    open end (``GW/GE<r>``, ``GN/GS<c>``) and two-way single-lane links named
    ``A>B``."""
    pos: Dict[str, Tuple[float, float]] = {}
    for r in range(rows):
        for c in range(cols):
            pos[f"J{r}{c}"] = (c * spacing, -r * spacing)
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
    pairs: List[Tuple[str, str]] = []
    for r in range(rows):
        chain = [f"GW{r}"] + [f"J{r}{c}" for c in range(cols)] + [f"GE{r}"]
        pairs += list(zip(chain, chain[1:]))
    for c in range(cols):
        chain = [f"GN{c}"] + [f"J{r}{c}" for r in range(rows)] + [f"GS{c}"]
        pairs += list(zip(chain, chain[1:]))
    links = []
    for a, b in pairs:
        length = abs(pos[a][0] - pos[b][0]) + abs(pos[a][1] - pos[b][1])
        for p, q in ((a, b), (b, a)):
            links.append(
                GraphLink(
                    id=f"{p}>{q}",
                    **{"from": p, "to": q},
                    length=length,
                    lanes=1,
                    speed=speed,
                )
            )
    return RoadGraph(
        name=f"{rows}x{cols} demo grid", source="synthetic", nodes=nodes, links=links
    )


def demo_flows(rows: int = 2, cols: int = 2, vph: float = 360.0) -> List[Flow]:
    flows: List[Flow] = []
    for r in range(rows):
        flows.append(Flow(f"GW{r}", f"GE{r}", vph))
        flows.append(Flow(f"GE{r}", f"GW{r}", vph * 0.8))
    for c in range(cols):
        flows.append(Flow(f"GN{c}", f"GS{c}", vph * 0.6))
        flows.append(Flow(f"GS{c}", f"GN{c}", vph * 0.5))
    return flows


def generate_counts(
    graph: RoadGraph,
    flows: Sequence[Flow],
    truth: Mapping[str, float],
    *,
    options: FitOptions = FitOptions(),
    sim: SimSettings = SimSettings(),
    intervals: int = 4,
    interval_seconds: float = 900.0,
    noise: float = 0.0,
    noise_seed: int = 7,
    start_time: float = 0.0,
    sensor_prefix: str = "S-",
    min_vph: float = 1.0,
) -> str:
    """Count CSV for the links the truth parameters load. Each interval's
    count is the true rate x interval length, rounded, times ``1 + N(0,
    noise)`` when ``noise`` > 0 (seeded). Links under ``min_vph`` get no
    sensor."""
    rates = simulate_link_flows(graph, flows, truth, options, sim)
    rng = random.Random(noise_seed)
    records: List[CountRecord] = []
    for i in range(intervals):
        start = start_time + i * interval_seconds
        for link, rate in sorted(rates.items()):
            if rate < min_vph:
                continue
            mean = rate * interval_seconds / 3600.0
            if noise > 0:
                mean *= max(0.0, 1.0 + rng.gauss(0.0, noise))
            records.append(
                CountRecord(
                    link,
                    start,
                    f"{start:g}",
                    float(round(mean)),
                    f"{sensor_prefix}{link}",
                )
            )
    return counts_to_csv(records)
