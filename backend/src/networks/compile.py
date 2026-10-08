"""Compile a validated network into an execution plan.

The plan is pure data: the junction order, what flows the routes imply on
each arm, the per-junction scenario copies those flows rewrite, and edge /
route free-flow times. It does not simulate anything.
"""

from typing import Any, Dict, List, Tuple

from src.core.scenario import ScenarioDocument, scenario_fingerprint, validate_scenario
from src.networks.models import (
    EXECUTION_MODEL,
    NetworkDocument,
    network_fingerprint,
)
from src.networks.validate import (
    arm_movement_flows,
    node_adjacency,
    resolve_route,
    topological_order,
)

PLAN_FORMAT = "urbanflow-network-plan"
PLAN_VERSION = 1

LIMITATIONS = [
    "Edges carry flow, not vehicles: no queue spillback between junctions.",
    "Edge travel time is free-flow (length / speed limit); no platoon dispersion.",
    "Junctions are coupled one way, upstream to downstream; cyclic networks are "
    "rejected.",
    "Route demand sets each arm's volume and turning shares; the single-junction "
    "engine is not modified.",
]


def _shares(by_move: Dict[str, float]) -> Dict[str, float]:
    total = sum(by_move.values())
    return {m: v / total for m, v in sorted(by_move.items())} if total > 0 else {}


def derive_node_scenarios(
    doc: NetworkDocument,
) -> Tuple[Dict[str, Dict[str, Any]], List[str]]:
    """Per inline junction, a *copy* of its scenario whose arms carry the
    route-implied volume and turning. Arms no route reaches keep their own
    values. Returns ``({node: scenario}, errors)``; the original documents
    are never modified."""
    flows = arm_movement_flows(doc)
    derived: Dict[str, Dict[str, Any]] = {}
    errors: List[str] = []
    for node in sorted(doc.nodes, key=lambda n: n.id):
        if node.kind != "junction" or not isinstance(node.scenario, ScenarioDocument):
            continue
        body = node.scenario.model_dump(mode="json")
        for arm, spec in body["approaches"].items():
            by_move = flows.get((node.id, arm))
            if spec is None or not by_move:
                continue
            spec["vehiclesPerHour"] = sum(by_move.values())
            shares = _shares(by_move)
            turning = {m: shares.get(m, 0.0) for m in ("left", "straight", "right")}
            if shares.get("uturn"):
                turning["uturn"] = shares["uturn"]
            spec["turning"] = turning
        result = validate_scenario(body, None)
        if not result["valid"]:
            errors.extend(
                f"Node {node.id!r} with route demand: {e}" for e in result["errors"]
            )
        derived[node.id] = body
    return derived, errors


def compile_network(doc: NetworkDocument) -> Dict[str, Any]:
    """The execution plan for a network that has passed ``validate_network``."""
    adjacency = node_adjacency(doc)
    order = topological_order(adjacency)
    if order is None:
        raise ValueError("network contains a cycle")
    flows = arm_movement_flows(doc)
    derived, _ = derive_node_scenarios(doc)
    nodes_by_id = {n.id: n for n in doc.nodes}
    demand = {d.routeId: d for d in doc.demand}
    edges_by_id = {e.id: e for e in doc.edges}

    upstream: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for edge in sorted(doc.edges, key=lambda e: e.id):
        target = nodes_by_id[edge.to.node]
        if target.kind == "junction" and edge.to.arm is not None:
            source = nodes_by_id[edge.from_.node]
            upstream[(target.id, edge.to.arm.value)] = {
                "edge": edge.id,
                "fromNode": source.id,
                "fromKind": source.kind,
                "fromArm": edge.from_.arm.value if edge.from_.arm else None,
            }

    plan_nodes: List[Dict[str, Any]] = []
    for node_id in order:
        node = nodes_by_id[node_id]
        entry: Dict[str, Any] = {
            "id": node.id,
            "kind": node.kind,
            "junctionType": node.resolved_junction_type(),
        }
        if node.kind == "junction":
            arms = sorted(a for (n, a) in upstream if n == node.id)
            entry["inflowByArm"] = {
                a: sum(flows.get((node.id, a), {}).values()) for a in arms
            }
            entry["turningByArm"] = {
                a: _shares(flows[(node.id, a)]) for a in arms if (node.id, a) in flows
            }
            entry["upstream"] = {a: upstream[(node.id, a)] for a in arms}
            if node.id in derived:
                entry["scenarioFingerprint"] = scenario_fingerprint(
                    ScenarioDocument.model_validate(derived[node.id])
                )
            else:
                entry["scenarioRef"] = getattr(node.scenario, "ref", None)
        plan_nodes.append(entry)

    edge_flow: Dict[str, float] = {e.id: 0.0 for e in doc.edges}
    plan_routes: List[Dict[str, Any]] = []
    for route in sorted(doc.routes, key=lambda r: r.id):
        item = demand.get(route.id)
        vph = item.vehiclesPerHour if item else 0.0
        free_flow = 0.0
        for edge_id in route.path:
            edge_flow[edge_id] += vph
            e = edges_by_id[edge_id]
            free_flow += e.lengthMeters / e.speedLimit
        plan_routes.append(
            {
                "id": route.id,
                "origin": route.origin,
                "destination": route.destination,
                "path": list(route.path),
                "demandVph": vph,
                "freeFlowSeconds": round(free_flow, 3),
                "passages": resolve_route(doc, route)[0],
            }
        )

    plan_edges = [
        {
            "id": e.id,
            "from": e.from_.model_dump(mode="json"),
            "to": e.to.model_dump(mode="json"),
            "lengthMeters": e.lengthMeters,
            "lanes": e.lanes,
            "speedLimit": e.speedLimit,
            "freeFlowSeconds": round(e.lengthMeters / e.speedLimit, 3),
            "demandVph": edge_flow[e.id],
            "laneMetadata": [
                m.model_dump(mode="json", exclude_none=True)
                for m in sorted(e.laneMetadata or [], key=lambda m: m.index)
            ],
        }
        for e in sorted(doc.edges, key=lambda e: e.id)
    ]
    return {
        "format": PLAN_FORMAT,
        "version": PLAN_VERSION,
        "fingerprint": network_fingerprint(doc),
        "executionModel": EXECUTION_MODEL,
        "order": order,
        "nodes": plan_nodes,
        "edges": plan_edges,
        "routes": plan_routes,
        "limitations": list(LIMITATIONS),
    }
