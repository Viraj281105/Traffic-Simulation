"""``urbanflow-network`` v1: the network domain model.

Nodes reference junction scenarios (or are origin/destination gates), edges
connect node arms, routes are ordered edge chains and demand is per route.
Pydantic ``extra="forbid"`` like ``urbanflow-scenario``; nothing is
normalised (a vehicle mix summing to 0.95 is reported, not rescaled).
"""

import hashlib
import json
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

from src.core.enums import Direction
from src.core.scenario import ScenarioDocument, scenario_fingerprint

NETWORK_FORMAT = "urbanflow-network"
NETWORK_VERSION = 1
EXECUTION_MODEL = "one-way-coupled-sequential"

ARMS = tuple(d.value for d in Direction)
Movement = Literal["left", "straight", "right", "uturn"]
VEHICLE_CLASSES = ("car", "suv", "bus", "truck", "motorcycle")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ScenarioRef(_Strict):
    """A junction defined elsewhere (a saved scenario id)."""

    ref: str = Field(..., min_length=1, max_length=128)


class NodeSpec(_Strict):
    id: str = Field(..., min_length=1, max_length=64)
    kind: Literal["junction", "origin", "destination"]
    # Junction nodes carry a scenario (inline or by reference); gates none.
    scenario: Optional[Union[ScenarioDocument, ScenarioRef]] = None
    # Optional restatement of the scenario's junction type; checked, not trusted.
    junctionType: Optional[
        Literal["fixed_time_signal", "adaptive_signal", "roundabout"]
    ] = None

    def resolved_junction_type(self) -> Optional[str]:
        if isinstance(self.scenario, ScenarioDocument):
            return self.scenario.junction.type
        return self.junctionType


class EdgePort(_Strict):
    node: str = Field(..., min_length=1, max_length=64)
    # The junction slot the edge leaves from / enters. Absent for gates.
    arm: Optional[Direction] = None


class LaneSpec(_Strict):
    """Optional per-lane metadata, lane 1 next to the centre line first."""

    index: int = Field(..., ge=1, le=8)
    movements: Optional[List[Movement]] = None
    width: Optional[float] = Field(None, gt=2.0, le=5.0)


class EdgeSpec(_Strict):
    id: str = Field(..., min_length=1, max_length=64)
    from_: EdgePort = Field(..., alias="from")
    to: EdgePort
    lengthMeters: float = Field(..., gt=0, le=20000)
    lanes: int = Field(..., ge=1, le=8)
    speedLimit: float = Field(13.89, gt=0, le=45)
    laneWidth: Optional[float] = Field(None, gt=2.5, le=5.0)
    direction: Literal["oneway"] = "oneway"
    laneMetadata: Optional[List[LaneSpec]] = None


class RouteSpec(_Strict):
    id: str = Field(..., min_length=1, max_length=64)
    origin: str = Field(..., min_length=1, max_length=64)
    destination: str = Field(..., min_length=1, max_length=64)
    path: List[str] = Field(..., min_length=1)


class DemandSpec(_Strict):
    routeId: str = Field(..., min_length=1, max_length=64)
    vehiclesPerHour: float = Field(..., ge=0, le=7200)
    vehicleMix: Optional[Dict[str, float]] = None


class NetworkSimulationSpec(_Strict):
    duration: float = Field(300.0, gt=0, le=3600)
    warmup: float = Field(30.0, ge=0)
    seed: int = 1
    seeds: int = Field(1, ge=1, le=20)


class NetworkDocument(_Strict):
    format: Literal["urbanflow-network"] = "urbanflow-network"
    version: Literal[1] = 1
    name: str = Field("Custom network", max_length=120)
    description: str = Field("", max_length=2000)
    nodes: List[NodeSpec] = Field(..., min_length=1)
    edges: List[EdgeSpec] = Field(default_factory=list)
    routes: List[RouteSpec] = Field(default_factory=list)
    demand: List[DemandSpec] = Field(default_factory=list)
    simulation: NetworkSimulationSpec = Field(
        default_factory=lambda: NetworkSimulationSpec.model_validate({})
    )


def _canonical_node(node: NodeSpec) -> Dict[str, Any]:
    body: Dict[str, Any] = {"id": node.id, "kind": node.kind}
    jtype = node.resolved_junction_type()
    if jtype is not None:
        body["junctionType"] = jtype
    if isinstance(node.scenario, ScenarioDocument):
        body["scenarioFingerprint"] = scenario_fingerprint(node.scenario)
    elif isinstance(node.scenario, ScenarioRef):
        body["scenarioRef"] = node.scenario.ref
    return body


def canonical_network(doc: NetworkDocument) -> Dict[str, Any]:
    """The identity of a network: nodes, edges, routes and demand sorted by
    id (list order in the request never matters), scenarios reduced to their
    own fingerprints, name/description excluded. Route paths keep their
    order, which is meaningful."""
    return {
        "format": doc.format,
        "version": doc.version,
        "nodes": [_canonical_node(n) for n in sorted(doc.nodes, key=lambda n: n.id)],
        "edges": [
            e.model_dump(by_alias=True, exclude_none=True)
            for e in sorted(doc.edges, key=lambda e: e.id)
        ],
        "routes": [r.model_dump() for r in sorted(doc.routes, key=lambda r: r.id)],
        "demand": [
            d.model_dump(exclude_none=True)
            for d in sorted(doc.demand, key=lambda d: d.routeId)
        ],
        "simulation": doc.simulation.model_dump(),
    }


def network_fingerprint(doc: NetworkDocument) -> str:
    """16-hex SHA-256 of the canonical network (JSON round-tripped so enum
    members hash as their values)."""
    body = json.loads(json.dumps(canonical_network(doc), default=_json_default))
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def _json_default(value: Any) -> Any:
    if hasattr(value, "value"):
        return value.value
    raise TypeError(f"not serialisable: {type(value).__name__}")


def serialize_network(doc: NetworkDocument) -> Dict[str, Any]:
    """Deterministic JSON-ready form (ids sorted, aliases; nulls kept so 3-arm
    scenarios stay valid); parses
    back to an equal document via ``NetworkDocument.model_validate``."""
    body = doc.model_dump(by_alias=True, mode="json")
    body["nodes"] = sorted(body["nodes"], key=lambda n: n["id"])
    body["edges"] = sorted(body["edges"], key=lambda e: e["id"])
    body["routes"] = sorted(body["routes"], key=lambda r: r["id"])
    body["demand"] = sorted(body["demand"], key=lambda d: d["routeId"])
    return body
