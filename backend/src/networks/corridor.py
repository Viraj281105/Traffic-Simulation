"""The two-junction corridor scenario (F5): the first network that is not a
single junction. Two signalised junctions 400 m apart on an east-west
arterial, each with a side street, plus gates at every open end."""

from typing import List, Tuple

from src.networks.graph import GraphLink, GraphNode, RoadGraph
from src.networks.network_sim import Flow


def build_two_junction_corridor(
    spacing: float = 400.0, arterial_speed: float = 13.89, oneway: bool = False
) -> RoadGraph:
    """Arterial W - J1 - J2 - E, side streets N1/S1 at J1 and N2/S2 at J2.
    Links are two-way (ids ``A>B``) unless ``oneway``, which keeps only the
    west-to-east arterial and the side-street entries (an acyclic network the
    older ``urbanflow-network`` model can hold)."""
    pos = {
        "W": (-300.0, 0.0),
        "J1": (0.0, 0.0),
        "J2": (spacing, 0.0),
        "E": (spacing + 300.0, 0.0),
        "N1": (0.0, 300.0),
        "S1": (0.0, -300.0),
        "N2": (spacing, 300.0),
        "S2": (spacing, -300.0),
    }
    nodes = [
        GraphNode(
            id=i,
            x=x,
            y=y,
            kind="junction" if i.startswith("J") else "gate",
            control="signal" if i.startswith("J") else None,
        )
        for i, (x, y) in pos.items()
    ]
    pairs: List[Tuple[str, str]] = [
        ("W", "J1"),
        ("J1", "J2"),
        ("J2", "E"),
        ("N1", "J1"),
        ("J1", "S1"),
        ("N2", "J2"),
        ("J2", "S2"),
    ]
    if not oneway:
        pairs += [("E", "J2"), ("J2", "J1"), ("J1", "W"), ("S1", "J1"), ("J1", "N1")]
        pairs += [("S2", "J2"), ("J2", "N2")]
    links = []
    for a, b in pairs:
        (ax, ay), (bx, by) = pos[a], pos[b]
        length = abs(bx - ax) + abs(by - ay)
        side = "J" not in (a + b) or a[0] in "NS" or b[0] in "NS"
        links.append(
            GraphLink(
                id=f"{a}>{b}",
                **{"from": a, "to": b},
                length=length,
                lanes=2 if not side else 1,
                speed=arterial_speed if not side else 11.11,
            )
        )
    return RoadGraph(
        name="Two-junction corridor", source="corridor", nodes=nodes, links=links
    )


def corridor_flows(oneway: bool = False) -> List[Flow]:
    """A through flow each way plus side-street turning flows."""
    flows = [
        Flow("W", "E", 600.0),
        Flow("N1", "S2", 150.0),
        Flow("N2", "E", 150.0),
    ]
    if not oneway:
        flows += [Flow("E", "W", 500.0), Flow("S1", "N2", 120.0)]
    return flows
