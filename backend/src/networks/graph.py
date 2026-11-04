"""``urbanflow-graph`` v1: the general road-network graph (ADR-021).

Nodes carry a position in local metres; links are directed. This is the
import/export and vehicle-level simulation model. The older
``urbanflow-network`` document (``models.py``) stays the junction-scenario
coupling model; :func:`graph_to_network` converts the compatible subset.
"""

import heapq
import math
from typing import Any, Dict, List, Literal, Optional, Set, Tuple

from pydantic import BaseModel, ConfigDict, Field, ValidationError

GRAPH_FORMAT = "urbanflow-graph"
GRAPH_VERSION = 1
MAX_LINK_METERS = 20000.0
MAX_LANES = 8
MAX_SPEED = 45.0
MAX_NODES = 20000


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class GraphNode(_Strict):
    id: str = Field(..., min_length=1, max_length=64)
    x: float = 0.0  # local metres east
    y: float = 0.0  # local metres north
    # junction: vehicles are handed between links here; gate: a network
    # boundary where vehicles enter or leave.
    kind: Literal["junction", "gate"] = "junction"
    control: Optional[Literal["signal"]] = None
    lat: Optional[float] = None
    lon: Optional[float] = None


class GraphLink(_Strict):
    id: str = Field(..., min_length=1, max_length=64)
    from_: str = Field(..., alias="from", min_length=1, max_length=64)
    to: str = Field(..., min_length=1, max_length=64)
    length: float = Field(..., gt=0)
    lanes: int = Field(1, ge=1)
    speed: float = Field(13.89, gt=0)  # m/s
    name: str = ""


class RoadGraph(_Strict):
    format: Literal["urbanflow-graph"] = "urbanflow-graph"
    version: Literal[1] = 1
    name: str = "Road graph"
    source: str = "native"
    nodes: List[GraphNode] = Field(default_factory=list)
    links: List[GraphLink] = Field(default_factory=list)

    def node_map(self) -> Dict[str, GraphNode]:
        return {n.id: n for n in self.nodes}

    def link_map(self) -> Dict[str, GraphLink]:
        return {k.id: k for k in self.links}

    def outgoing(self) -> Dict[str, List[GraphLink]]:
        out: Dict[str, List[GraphLink]] = {n.id: [] for n in self.nodes}
        for link in sorted(self.links, key=lambda k: k.id):
            out.setdefault(link.from_, []).append(link)
        return out

    def incoming(self) -> Dict[str, List[GraphLink]]:
        inc: Dict[str, List[GraphLink]] = {n.id: [] for n in self.nodes}
        for link in sorted(self.links, key=lambda k: k.id):
            inc.setdefault(link.to, []).append(link)
        return inc


def free_flow_seconds(link: GraphLink) -> float:
    return link.length / link.speed


def shortest_path(
    graph: RoadGraph,
    origin: str,
    destination: str,
    penalty: Optional[Dict[str, float]] = None,
) -> Optional[List[str]]:
    """Dijkstra on free-flow time (plus optional per-link ``penalty`` seconds,
    which is how congestion-aware routing plugs in). Returns link ids, or
    None when unreachable. Ties break on link id, so it is deterministic."""
    out = graph.outgoing()
    if origin not in out or destination not in out:
        return None
    if origin == destination:
        return []
    penalty = penalty or {}
    best: Dict[str, float] = {origin: 0.0}
    via: Dict[str, GraphLink] = {}
    heap: List[Tuple[float, str]] = [(0.0, origin)]
    done: Set[str] = set()
    while heap:
        cost, node = heapq.heappop(heap)
        if node in done:
            continue
        done.add(node)
        if node == destination:
            break
        for link in out.get(node, []):
            step = cost + free_flow_seconds(link) + penalty.get(link.id, 0.0)
            if step < best.get(link.to, math.inf) - 1e-12:
                best[link.to] = step
                via[link.to] = link
                heapq.heappush(heap, (step, link.to))
    if destination not in via:
        return None
    path: List[str] = []
    node = destination
    while node != origin:
        link = via[node]
        path.append(link.id)
        node = link.from_
    return path[::-1]


def parse_graph(payload: Any) -> Tuple[Optional[RoadGraph], List[str]]:
    if not isinstance(payload, dict):
        return None, ["A graph must be a JSON object"]
    try:
        return RoadGraph.model_validate(payload), []
    except ValidationError as err:
        msgs = []
        for e in err.errors():
            where = ".".join(str(p) for p in e.get("loc", ()))
            msgs.append(f"{where}: {e['msg']}" if where else str(e["msg"]))
        return None, msgs


def serialize_graph(graph: RoadGraph) -> Dict[str, Any]:
    body = graph.model_dump(by_alias=True, mode="json", exclude_none=True)
    body["nodes"] = sorted(body["nodes"], key=lambda n: n["id"])
    body["links"] = sorted(body["links"], key=lambda k: k["id"])
    return body


def _components(graph: RoadGraph) -> List[List[str]]:
    adj: Dict[str, Set[str]] = {n.id: set() for n in graph.nodes}
    for k in graph.links:
        if k.from_ in adj and k.to in adj:
            adj[k.from_].add(k.to)
            adj[k.to].add(k.from_)
    seen: Set[str] = set()
    comps: List[List[str]] = []
    for start in sorted(adj):
        if start in seen:
            continue
        comp, stack = [], [start]
        seen.add(start)
        while stack:
            cur = stack.pop()
            comp.append(cur)
            for nxt in adj[cur]:
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        comps.append(sorted(comp))
    comps.sort(key=lambda c: (-len(c), c[0]))
    return comps


def validate_graph(payload: Any) -> Dict[str, Any]:
    """Human-readable validation for an upload screen. Never raises.

    ``errors`` block use of the graph; ``warnings`` do not. Order is
    deterministic. ``stats`` summarises what was read.
    """
    errors: List[str] = []
    warnings: List[str] = []
    if isinstance(payload, RoadGraph):
        graph: Optional[RoadGraph] = payload
    else:
        graph, errors = parse_graph(payload)
    if graph is None:
        return {"valid": False, "errors": errors, "warnings": [], "stats": {}}
    if not graph.nodes:
        errors.append("The network has no nodes; nothing was imported")
    if len(graph.nodes) > MAX_NODES:
        errors.append(
            f"The network has {len(graph.nodes)} nodes; the limit is {MAX_NODES}. "
            "Import a smaller area"
        )
    if graph.nodes and not graph.links:
        errors.append("The network has no links (roads); nothing can be simulated")
    ids: Set[str] = set()
    for n in graph.nodes:
        if n.id in ids:
            errors.append(f"Duplicate node id {n.id!r}")
        ids.add(n.id)
    link_ids: Set[str] = set()
    for k in graph.links:
        tag = f"Link {k.id!r}" + (f" ({k.name})" if k.name else "")
        if k.id in link_ids:
            errors.append(f"Duplicate link id {k.id!r}")
        link_ids.add(k.id)
        for end, label in ((k.from_, "starts at"), (k.to, "ends at")):
            if end not in ids:
                errors.append(f"{tag} {label} unknown node {end!r}")
        if k.from_ == k.to:
            errors.append(f"{tag} starts and ends at the same node {k.from_!r}")
        if k.length > MAX_LINK_METERS:
            errors.append(
                f"{tag} is {k.length:g} m long; the limit is {MAX_LINK_METERS:g} m"
            )
        elif k.length < 3.0:
            warnings.append(f"{tag} is only {k.length:g} m long; check for duplicate nodes")
        if k.lanes > MAX_LANES:
            errors.append(f"{tag} has {k.lanes} lanes; the limit is {MAX_LANES}")
        if k.speed > MAX_SPEED:
            errors.append(
                f"{tag} has speed {k.speed:g} m/s; the limit is {MAX_SPEED:g} m/s"
            )
        elif k.speed < 2.0:
            warnings.append(f"{tag} has speed {k.speed:g} m/s, which is very slow")
    if not errors:
        comps = _components(graph)
        if len(comps) > 1:
            warnings.append(
                f"The network is split into {len(comps)} separate parts; vehicles "
                f"cannot travel between them (the largest has {len(comps[0])} nodes)"
            )
        out, inc = graph.outgoing(), graph.incoming()
        for n in sorted(graph.nodes, key=lambda n: n.id):
            o, i = len(out[n.id]), len(inc[n.id])
            if o == 0 and i == 0:
                warnings.append(f"Node {n.id!r} has no links and will be ignored")
            elif n.kind == "junction" and (o == 0 or i == 0):
                warnings.append(
                    f"Junction {n.id!r} has no {'exit' if o == 0 else 'entry'} link: "
                    "vehicles would be trapped or never arrive"
                )
        gates = [n for n in graph.nodes if n.kind == "gate"]
        if not any(out[g.id] for g in gates):
            warnings.append("No entry gate: the network has no demand source")
        if not any(inc[g.id] for g in gates):
            warnings.append("No exit gate: vehicles have nowhere to leave")
    stats = {
        "nodes": len(graph.nodes),
        "links": len(graph.links),
        "junctions": sum(1 for n in graph.nodes if n.kind == "junction"),
        "gates": sum(1 for n in graph.nodes if n.kind == "gate"),
        "signals": sum(1 for n in graph.nodes if n.control == "signal"),
        "totalLengthMeters": round(sum(k.length for k in graph.links), 1),
    }
    return {"valid": not errors, "errors": errors, "warnings": warnings, "stats": stats}


def _arm_towards(a: GraphNode, b: GraphNode) -> str:
    dx, dy = b.x - a.x, b.y - a.y
    if abs(dx) >= abs(dy):
        return "east" if dx >= 0 else "west"
    return "north" if dy >= 0 else "south"


def graph_to_network(
    graph: RoadGraph, junction_ref: str = "scenario:default"
) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    """Best-effort conversion to an ``urbanflow-network`` document (junction
    nodes reference ``junction_ref``; no routes or demand). Returns
    ``(document, notes)``; the document is None when a gate is both an entry
    and an exit, which the older model cannot express. The caller validates
    the result with ``validate_network`` (arm clashes, cycles)."""
    notes: List[str] = []
    nodes_by_id = graph.node_map()
    out, inc = graph.outgoing(), graph.incoming()
    nodes: List[Dict[str, Any]] = []
    for n in sorted(graph.nodes, key=lambda n: n.id):
        if n.kind == "junction":
            nodes.append(
                {"id": n.id, "kind": "junction", "scenario": {"ref": junction_ref}}
            )
        elif out[n.id] and inc[n.id]:
            notes.append(
                f"Gate {n.id!r} is both an entry and an exit; the network model "
                "needs one role per gate"
            )
            return None, notes
        else:
            nodes.append(
                {"id": n.id, "kind": "origin" if out[n.id] else "destination"}
            )
    edges: List[Dict[str, Any]] = []
    for k in sorted(graph.links, key=lambda k: k.id):
        a, b = nodes_by_id[k.from_], nodes_by_id[k.to]
        src: Dict[str, Any] = {"node": a.id}
        dst: Dict[str, Any] = {"node": b.id}
        if a.kind == "junction":
            src["arm"] = _arm_towards(a, b)
        if b.kind == "junction":
            dst["arm"] = _arm_towards(b, a)
        edges.append(
            {
                "id": k.id,
                "from": src,
                "to": dst,
                "lengthMeters": k.length,
                "lanes": min(k.lanes, MAX_LANES),
                "speedLimit": k.speed,
            }
        )
    return (
        {
            "format": "urbanflow-network",
            "version": 1,
            "name": graph.name,
            "nodes": nodes,
            "edges": edges,
            "routes": [],
            "demand": [],
        },
        notes,
    )
