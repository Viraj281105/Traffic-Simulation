"""Pure graph validation for ``urbanflow-network`` documents (no simulation)."""

from typing import Any, Dict, List, Optional, Set, Tuple

from pydantic import ValidationError

from src.core.limits import MAX_TOTAL_VEHICLES, demand_vehicle_limit
from src.core.scenario import ScenarioDocument, validate_scenario
from src.networks.models import (
    NETWORK_FORMAT,
    NETWORK_VERSION,
    VEHICLE_CLASSES,
    EdgeSpec,
    NetworkDocument,
    NodeSpec,
    RouteSpec,
    network_fingerprint,
    serialize_network,
)

MAX_ARM_VPH = 7200.0  # ApproachSpec.vehiclesPerHour ceiling
MIX_TOLERANCE = 0.01

_CLOCKWISE = {"north": 0, "east": 1, "south": 2, "west": 3}


def movement_between(entry_arm: str, exit_arm: str) -> str:
    """The turn a vehicle makes entering a junction through ``entry_arm`` and
    leaving through ``exit_arm`` (the arm slots of the scenario model)."""
    diff = (_CLOCKWISE[exit_arm] - _CLOCKWISE[entry_arm]) % 4
    return ("uturn", "left", "straight", "right")[diff]


def _message(error: Dict[str, Any]) -> str:
    where = ".".join(str(p) for p in error.get("loc", ()))
    return f"{where}: {error.get('msg', 'invalid')}" if where else str(error["msg"])


def parse_network(payload: Any) -> Tuple[Optional[NetworkDocument], List[str]]:
    """Parse a document, returning it or every structural error found."""
    if not isinstance(payload, dict):
        return None, ["A network must be a JSON object"]
    body = payload.get("network", payload) if "nodes" not in payload else payload
    if not isinstance(body, dict):
        return None, ["A network must be a JSON object"]
    fmt = body.get("format", NETWORK_FORMAT)
    if fmt != NETWORK_FORMAT:
        return None, [
            f"Not an UrbanFlow network: format is {fmt!r}, expected {NETWORK_FORMAT!r}"
        ]
    version = body.get("version", NETWORK_VERSION)
    if version != NETWORK_VERSION:
        return None, [
            f"Network version {version!r} is not supported by this server, "
            f"which reads version {NETWORK_VERSION}"
        ]
    try:
        return NetworkDocument.model_validate(body), []
    except ValidationError as err:
        return None, [_message(dict(e)) for e in err.errors()]


def inline_arms(node: NodeSpec) -> Optional[Set[str]]:
    """Arms the node's scenario has, or None when unknown (a reference)."""
    if isinstance(node.scenario, ScenarioDocument):
        return {d.value for d in node.scenario.approaches.present()}
    return None


def resolve_route(
    doc: NetworkDocument, route: RouteSpec
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Walk a route's edge chain. Returns the junction passages
    ``[{node, edgeIn, edgeOut, entryArm, exitArm, movement}]`` and errors."""
    nodes = {n.id: n for n in doc.nodes}
    edges = {e.id: e for e in doc.edges}
    errors: List[str] = []
    tag = f"Route {route.id!r}"
    chain: List[EdgeSpec] = []
    for edge_id in route.path:
        if edge_id not in edges:
            errors.append(f"{tag}: unknown edge {edge_id!r}")
        else:
            chain.append(edges[edge_id])
    if errors:
        return [], errors
    if len(set(route.path)) != len(route.path):
        errors.append(f"{tag}: an edge is used more than once")
    if chain[0].from_.node != route.origin:
        errors.append(
            f"{tag}: first edge {chain[0].id!r} leaves {chain[0].from_.node!r}, "
            f"not the origin {route.origin!r}"
        )
    if chain[-1].to.node != route.destination:
        errors.append(
            f"{tag}: last edge {chain[-1].id!r} enters {chain[-1].to.node!r}, "
            f"not the destination {route.destination!r}"
        )
    for before, after in zip(chain, chain[1:]):
        if before.to.node != after.from_.node:
            errors.append(
                f"{tag}: edges {before.id!r} and {after.id!r} are not connected "
                f"({before.to.node!r} -> {after.from_.node!r})"
            )
    for end, label in ((route.origin, "origin"), (route.destination, "destination")):
        if end not in nodes:
            errors.append(f"{tag}: {label} {end!r} is not a node")
    if route.origin in nodes and nodes[route.origin].kind == "destination":
        errors.append(f"{tag}: origin {route.origin!r} is a destination gate")
    if route.destination in nodes and nodes[route.destination].kind == "origin":
        errors.append(f"{tag}: destination {route.destination!r} is an origin gate")
    if errors:
        return [], errors

    passages: List[Dict[str, Any]] = []
    for before, after in zip(chain, chain[1:]):
        entry, leave = before.to.arm, after.from_.arm
        if entry is None or leave is None:
            continue  # the edge-level check reports the missing arm
        passages.append(
            {
                "node": before.to.node,
                "edgeIn": before.id,
                "edgeOut": after.id,
                "entryArm": entry.value,
                "exitArm": leave.value,
                "movement": movement_between(entry.value, leave.value),
            }
        )
    return passages, errors


def _check_nodes(doc: NetworkDocument, errors: List[str], warnings: List[str]) -> None:
    seen: Set[str] = set()
    for node in doc.nodes:
        if node.id in seen:
            errors.append(f"Duplicate node id {node.id!r}")
        seen.add(node.id)
        if node.kind != "junction":
            if node.scenario is not None or node.junctionType is not None:
                errors.append(f"Node {node.id!r}: a {node.kind} gate has no scenario")
            continue
        if node.scenario is None:
            errors.append(f"Node {node.id!r}: a junction needs a scenario or ref")
        elif isinstance(node.scenario, ScenarioDocument):
            result = validate_scenario(node.scenario.model_dump(mode="json"), None)
            errors.extend(f"Node {node.id!r}: {e}" for e in result["errors"])
            warnings.extend(f"Node {node.id!r}: {w}" for w in result["warnings"])
            declared = node.junctionType
            if declared and declared != node.scenario.junction.type:
                errors.append(
                    f"Node {node.id!r}: junctionType {declared!r} does not "
                    f"match its scenario ({node.scenario.junction.type!r})"
                )
        else:
            warnings.append(
                f"Node {node.id!r}: scenario reference {node.scenario.ref!r} "
                "is not resolved here; its arms are not checked"
            )


def _check_edges(doc: NetworkDocument, errors: List[str], warnings: List[str]) -> None:
    nodes = {n.id: n for n in doc.nodes}
    seen: Set[str] = set()
    exits: Set[Tuple[str, str]] = set()
    entries: Set[Tuple[str, str]] = set()
    for edge in doc.edges:
        tag = f"Edge {edge.id!r}"
        if edge.id in seen:
            errors.append(f"Duplicate edge id {edge.id!r}")
        seen.add(edge.id)
        for port, side in ((edge.from_, "from"), (edge.to, "to")):
            node = nodes.get(port.node)
            if node is None:
                errors.append(f"{tag}: {side} references unknown node {port.node!r}")
                continue
            if node.kind == "junction":
                if port.arm is None:
                    errors.append(f"{tag}: {side} junction {node.id!r} needs an arm")
                    continue
                arms = inline_arms(node)
                if arms is not None and port.arm.value not in arms:
                    errors.append(
                        f"{tag}: {side} arm {port.arm.value!r} does not exist "
                        f"on junction {node.id!r}"
                    )
                key = (node.id, port.arm.value)
                used, word = (
                    (exits, "leaves") if side == "from" else (entries, "enters")
                )
                if key in used:
                    errors.append(
                        f"{tag}: arm {key[1]!r} of {node.id!r} already has an "
                        f"edge that {word} it"
                    )
                used.add(key)
            else:
                if port.arm is not None:
                    errors.append(f"{tag}: {side} gate {node.id!r} takes no arm")
                if side == "from" and node.kind == "destination":
                    errors.append(f"{tag}: leaves destination gate {node.id!r}")
                if side == "to" and node.kind == "origin":
                    errors.append(f"{tag}: enters origin gate {node.id!r}")
        if edge.from_.node == edge.to.node:
            errors.append(f"{tag}: connects node {edge.from_.node!r} to itself")
        _check_lane_metadata(edge, errors)
        receiver = nodes.get(edge.to.node)
        if (
            receiver is not None
            and edge.to.arm is not None
            and isinstance(receiver.scenario, ScenarioDocument)
        ):
            arm = receiver.scenario.approaches.present().get(edge.to.arm)
            if arm is not None and edge.lanes < arm.lanes:
                warnings.append(
                    f"{tag}: {edge.lanes} lane(s) feed arm {edge.to.arm.value!r} "
                    f"of {receiver.id!r}, which has {arm.lanes}"
                )


def _check_lane_metadata(edge: EdgeSpec, errors: List[str]) -> None:
    if not edge.laneMetadata:
        return
    indices = [lane.index for lane in edge.laneMetadata]
    if len(set(indices)) != len(indices):
        errors.append(f"Edge {edge.id!r}: duplicate lane index in laneMetadata")
    too_high = sorted(i for i in indices if i > edge.lanes)
    if too_high:
        errors.append(
            f"Edge {edge.id!r}: laneMetadata lane {too_high} exceeds its "
            f"{edge.lanes} lane(s)"
        )


def node_adjacency(doc: NetworkDocument) -> Dict[str, Set[str]]:
    ids = {n.id for n in doc.nodes}
    adjacency: Dict[str, Set[str]] = {i: set() for i in ids}
    for edge in doc.edges:
        a, b = edge.from_.node, edge.to.node
        if a in ids and b in ids and a != b:
            adjacency[a].add(b)
    return adjacency


def _check_graph(doc: NetworkDocument, errors: List[str]) -> None:
    adjacency = node_adjacency(doc)
    undirected: Dict[str, Set[str]] = {i: set() for i in adjacency}
    for a, targets in adjacency.items():
        for b in targets:
            undirected[a].add(b)
            undirected[b].add(a)
    start = sorted(adjacency)[0]
    reached, stack = {start}, [start]
    while stack:
        for nxt in undirected[stack.pop()]:
            if nxt not in reached:
                reached.add(nxt)
                stack.append(nxt)
    if reached != set(adjacency):
        errors.append(
            "Network is disconnected: node(s) "
            f"{sorted(set(adjacency) - reached)} are not connected to "
            f"{sorted(reached)}"
        )
    if topological_order(adjacency) is None:
        errors.append(
            "Network contains a cycle: cyclic networks need iteration and are "
            "not supported in V1.9"
        )


def topological_order(adjacency: Dict[str, Set[str]]) -> Optional[List[str]]:
    """Kahn's algorithm with id-sorted tie-breaking (deterministic); None if
    the graph has a cycle."""
    indegree = {n: 0 for n in adjacency}
    for targets in adjacency.values():
        for t in targets:
            indegree[t] += 1
    ready = sorted(n for n, d in indegree.items() if d == 0)
    order: List[str] = []
    while ready:
        node = ready.pop(0)
        order.append(node)
        for t in sorted(adjacency[node]):
            indegree[t] -= 1
            if indegree[t] == 0:
                ready.append(t)
        ready.sort()
    return order if len(order) == len(adjacency) else None


def _check_mix(
    route_id: str,
    mix: Optional[Dict[str, float]],
    errors: List[str],
    warnings: List[str],
) -> None:
    if mix is None:
        return
    unknown = sorted(set(mix) - set(VEHICLE_CLASSES))
    if unknown:
        errors.append(
            f"Demand {route_id!r}: unknown vehicle class(es) {unknown}; "
            f"expected some of {list(VEHICLE_CLASSES)}"
        )
    if any(v < 0 for v in mix.values()):
        errors.append(f"Demand {route_id!r}: vehicleMix shares must not be negative")
    elif abs(sum(mix.values()) - 1.0) > MIX_TOLERANCE:
        warnings.append(
            f"Demand {route_id!r}: vehicleMix sums to {sum(mix.values()):g}, not 1"
        )


def arm_movement_flows(
    doc: NetworkDocument,
) -> Dict[Tuple[str, str], Dict[str, float]]:
    """Demand-implied veh/h by movement entering each (junction, arm), summed
    over routes. Assumes the document's routes already resolve."""
    demand = {d.routeId: d.vehiclesPerHour for d in doc.demand}
    flows: Dict[Tuple[str, str], Dict[str, float]] = {}
    for route in sorted(doc.routes, key=lambda r: r.id):
        vph = demand.get(route.id, 0.0)
        for p in resolve_route(doc, route)[0]:
            by_move = flows.setdefault((p["node"], p["entryArm"]), {})
            by_move[p["movement"]] = by_move.get(p["movement"], 0.0) + vph
    return flows


def arm_route_flows(doc: NetworkDocument) -> Dict[Tuple[str, str], float]:
    """Demand-implied total veh/h entering each (junction, arm)."""
    return {k: sum(v.values()) for k, v in arm_movement_flows(doc).items()}


def _check_routes_and_demand(
    doc: NetworkDocument, errors: List[str], warnings: List[str]
) -> None:
    route_ids: Set[str] = set()
    for route in doc.routes:
        if route.id in route_ids:
            errors.append(f"Duplicate route id {route.id!r}")
        route_ids.add(route.id)
        errors.extend(resolve_route(doc, route)[1])
    demanded: Set[str] = set()
    for item in doc.demand:
        if item.routeId not in route_ids:
            errors.append(f"Demand references unknown route {item.routeId!r}")
        if item.routeId in demanded:
            errors.append(f"More than one demand entry for route {item.routeId!r}")
        demanded.add(item.routeId)
        _check_mix(item.routeId, item.vehicleMix, errors, warnings)
    for rid in sorted(route_ids - demanded):
        warnings.append(f"Route {rid!r} has no demand")
    if doc.simulation.warmup >= doc.simulation.duration:
        errors.append("simulation.warmup must be shorter than simulation.duration")
    if errors:
        return
    for (node, arm), vph in sorted(arm_route_flows(doc).items()):
        if vph > MAX_ARM_VPH:
            errors.append(
                f"Demand through arm {arm!r} of {node!r} is {vph:g} veh/h, "
                f"above the {MAX_ARM_VPH:g} veh/h a single arm supports"
            )
    total = sum(d.vehiclesPerHour for d in doc.demand)
    if (
        demand_vehicle_limit(total / 3600.0, doc.simulation.duration)
        >= MAX_TOTAL_VEHICLES
    ):
        warnings.append(
            f"Network demand ({total:g} veh/h for {doc.simulation.duration:g} s) "
            f"reaches the {MAX_TOTAL_VEHICLES} vehicle limit; demand may truncate"
        )


def validate_network(payload: Any) -> Dict[str, Any]:
    """Validate a network. Never raises: ``valid`` is false and ``errors``
    says why. Error order is deterministic."""
    doc, errors = parse_network(payload)
    if doc is None:
        return {"valid": False, "errors": errors, "warnings": [], "fingerprint": None}
    warnings: List[str] = []
    _check_nodes(doc, errors, warnings)
    _check_edges(doc, errors, warnings)
    _check_graph(doc, errors)
    _check_routes_and_demand(doc, errors, warnings)
    if not errors:
        from src.networks.compile import derive_node_scenarios

        errors.extend(derive_node_scenarios(doc)[1])
    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "fingerprint": network_fingerprint(doc),
        "network": serialize_network(doc),
    }
