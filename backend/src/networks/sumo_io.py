"""SUMO ``.net.xml`` import and export.

Import reads junction positions and types, edges with their lanes (lane count,
speed and length from the first lane) and counts what it does not keep
(lane-level connections, traffic-light programs, internal edges). Export
writes a net that SUMO's tools can read and that this importer reads back to
an equal graph (ids, topology, geometry, lanes, speed, gates, signals).
"""

from collections import Counter
from typing import Dict, List
from xml.sax.saxutils import quoteattr

from src.networks.graph import GraphLink, GraphNode, RoadGraph
from src.networks.import_common import ImportResult, parse_xml_safely


def import_sumo(text: str) -> ImportResult:
    result = ImportResult(format="sumo")
    try:
        root = parse_xml_safely(text)
    except ValueError as err:
        result.errors.append(str(err))
        return result
    if root.tag != "net":
        result.errors.append(f"Not a SUMO net file: root element is <{root.tag}>, expected <net>")
        return result

    nodes: Dict[str, GraphNode] = {}
    skipped: Counter = Counter()
    for j in root.findall("junction"):
        jid, jtype = j.get("id", ""), j.get("type", "priority")
        if not jid or jid.startswith(":") or jtype == "internal":
            skipped["internal junctions"] += 1
            continue
        try:
            x, y = float(j.get("x", "0")), float(j.get("y", "0"))
        except ValueError:
            result.messages.append(f"Junction {jid!r} skipped: x/y are not numbers")
            continue
        nodes[jid] = GraphNode(
            id=jid,
            x=x,
            y=y,
            kind="gate" if jtype == "dead_end" else "junction",
            control="signal" if jtype.startswith("traffic_light") else None,
        )
        if jtype not in ("priority", "dead_end", "traffic_light", "traffic_light_unregulated"):
            result.messages.append(
                f"Junction {jid!r} has type {jtype!r}, treated as an ordinary junction"
            )

    links: List[GraphLink] = []
    for e in root.findall("edge"):
        eid = e.get("id", "")
        if e.get("function") == "internal" or eid.startswith(":"):
            skipped["internal edges"] += 1
            continue
        a, b = e.get("from"), e.get("to")
        if a not in nodes or b not in nodes:
            result.messages.append(f"Edge {eid!r} skipped: it connects an unknown junction")
            continue
        lanes = e.findall("lane")
        if not lanes:
            result.messages.append(f"Edge {eid!r} skipped: it has no lanes")
            continue
        try:
            length = float(lanes[0].get("length", "0"))
            speed = float(lanes[0].get("speed", "13.89"))
        except ValueError:
            result.messages.append(f"Edge {eid!r} skipped: lane length or speed is not a number")
            continue
        if length <= 0 or speed <= 0:
            result.messages.append(f"Edge {eid!r} skipped: lane length and speed must be positive")
            continue
        links.append(
            GraphLink(
                id=eid,
                **{"from": a, "to": b},
                length=length,
                lanes=len(lanes),
                speed=speed,
                name=e.get("name", ""),
            )
        )
    n_conn = len(root.findall("connection"))
    if n_conn:
        result.messages.append(
            f"{n_conn} lane connection(s) read but not kept: the network model routes "
            "by link, not by lane"
        )
    if root.findall("tlLogic"):
        result.messages.append(
            f"{len(root.findall('tlLogic'))} traffic-light program(s) ignored: "
            "signals use the default two-phase timing"
        )
    if root.findall("roundabout"):
        result.messages.append("Roundabout definitions ignored; their edges are imported as plain links")
    if skipped:
        result.messages.append(
            "Skipped " + ", ".join(f"{v} {k}" for k, v in sorted(skipped.items()))
        )
    if not links:
        result.errors.append("No usable edges found in this SUMO net")
        return result
    result.graph = RoadGraph(
        name="SUMO import",
        source="sumo",
        nodes=sorted(nodes.values(), key=lambda n: n.id),
        links=links,
    )
    result.stats = {"nodes": len(nodes), "links": len(links), "connections": n_conn}
    return result


def _num(value: float) -> str:
    return format(value, ".10g")


def export_sumo(graph: RoadGraph) -> str:
    """Write the graph as a SUMO ``.net.xml`` string (deterministic)."""
    nodes = graph.node_map()
    xs = [n.x for n in graph.nodes] or [0.0]
    ys = [n.y for n in graph.nodes] or [0.0]
    boundary = f"{_num(min(xs))},{_num(min(ys))},{_num(max(xs))},{_num(max(ys))}"
    out: List[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<net version="1.16" junctionCornerDetail="5" limitTurnSpeed="5.50">',
        f'    <location netOffset="0.00,0.00" convBoundary={quoteattr(boundary)} '
        f'origBoundary={quoteattr(boundary)} projParameter="!"/>',
    ]
    incoming = graph.incoming()
    for link in sorted(graph.links, key=lambda k: k.id):
        a, b = nodes[link.from_], nodes[link.to]
        shape = f"{_num(a.x)},{_num(a.y)} {_num(b.x)},{_num(b.y)}"
        out.append(
            f"    <edge id={quoteattr(link.id)} from={quoteattr(link.from_)} "
            f'to={quoteattr(link.to)} priority="-1"'
            + (f" name={quoteattr(link.name)}" if link.name else "")
            + ">"
        )
        for i in range(link.lanes):
            out.append(
                f"        <lane id={quoteattr(f'{link.id}_{i}')} index=\"{i}\" "
                f'speed="{_num(link.speed)}" length="{_num(link.length)}" '
                f"shape={quoteattr(shape)}/>"
            )
        out.append("    </edge>")
    for node in sorted(graph.nodes, key=lambda n: n.id):
        jtype = (
            "dead_end" if node.kind == "gate"
            else "traffic_light" if node.control == "signal" else "priority"
        )
        inc = " ".join(
            f"{k.id}_{i}" for k in incoming[node.id] for i in range(k.lanes)
        )
        out.append(
            f"    <junction id={quoteattr(node.id)} type=\"{jtype}\" "
            f'x="{_num(node.x)}" y="{_num(node.y)}" incLanes={quoteattr(inc)} intLanes=""/>'
        )
    outgoing = graph.outgoing()
    for node in sorted(graph.nodes, key=lambda n: n.id):
        for i in incoming[node.id]:
            for o in outgoing[node.id]:
                if o.to == i.from_ and len(outgoing[node.id]) > 1:
                    continue  # no U-turn when another way on exists
                out.append(
                    f"    <connection from={quoteattr(i.id)} to={quoteattr(o.id)} "
                    'fromLane="0" toLane="0"/>'
                )
    out.append("</net>")
    return "\n".join(out) + "\n"
