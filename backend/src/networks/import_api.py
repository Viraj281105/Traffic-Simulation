"""``/api/v2/network-graphs``: validate, import, export and run road graphs.

Stateless. Import endpoints take the file text read by the browser (no live
network calls, nothing stored) and answer 200 with ``ok: false`` and readable
``errors`` for bad files, so an upload screen can show them directly.
"""

import base64
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.networks.corridor import build_two_junction_corridor, corridor_flows
from src.networks.graph import (
    graph_to_network,
    parse_graph,
    serialize_graph,
    validate_graph,
)
from src.networks.import_common import ImportResult
from src.networks.network_sim import Flow, simulate_network
from src.networks.osm_import import import_osm
from src.networks.sumo_io import export_sumo, import_sumo
from src.networks.transit_import import import_gtfs, import_gtfs_zip, import_synchro

router = APIRouter(prefix="/api/v2/network-graphs", tags=["network-graphs"])

MAX_CONTENT_CHARS = 8_000_000


class GraphRequest(BaseModel):
    graph: Dict[str, Any]


class ImportRequest(BaseModel):
    format: Literal["osm", "sumo", "gtfs", "synchro"]
    # Text of the file (osm, sumo, synchro), or for gtfs a {name: text} map
    # in `files`, or a base64 zip in `contentBase64`.
    content: Optional[str] = Field(None, max_length=MAX_CONTENT_CHARS)
    files: Optional[Dict[str, str]] = None
    contentBase64: Optional[str] = Field(None, max_length=MAX_CONTENT_CHARS)
    filename: Optional[str] = None


class FlowIn(BaseModel):
    origin: str
    destination: str
    vehiclesPerHour: float = Field(..., ge=0, le=7200)


class SimulateRequest(BaseModel):
    graph: Optional[Dict[str, Any]] = None  # omitted: the two-junction corridor
    flows: Optional[List[FlowIn]] = None
    duration: float = Field(300.0, gt=0, le=3600)
    seed: int = 1


def _fail(fmt: str, message: str) -> Dict[str, Any]:
    r = ImportResult(format=fmt)
    r.errors.append(message)
    return r.to_json()


@router.post("/validate")
def validate_endpoint(payload: GraphRequest) -> Dict[str, Any]:
    """Always 200: ``{valid, errors[], warnings[], stats}``."""
    return validate_graph(payload.graph)


@router.post("/import")
def import_endpoint(payload: ImportRequest) -> Dict[str, Any]:
    """``{format, ok, errors[], messages[], stats, graph|null, validation|null}``.
    ``messages`` are non-fatal notes (what was skipped or assumed)."""
    fmt = payload.format
    if fmt == "gtfs":
        if payload.files:
            result = import_gtfs(payload.files)
        elif payload.contentBase64:
            try:
                result = import_gtfs_zip(base64.b64decode(payload.contentBase64, validate=True))
            except ValueError:
                return _fail(fmt, "The zip content is not valid base64")
        else:
            return _fail(fmt, "Send the GTFS files as `files` or a zip as `contentBase64`")
    else:
        if not payload.content or not payload.content.strip():
            return _fail(fmt, "The file is empty")
        result = {"osm": import_osm, "sumo": import_sumo, "synchro": import_synchro}[fmt](
            payload.content
        )
    return result.to_json()


@router.post("/export/sumo")
def export_sumo_endpoint(payload: GraphRequest) -> Dict[str, Any]:
    """``{format: "sumo", filename, content}``; 400 with the validation
    errors when the graph is invalid."""
    graph, errors = parse_graph(payload.graph)
    if graph is not None:
        errors = validate_graph(graph)["errors"]
    if graph is None or errors:
        raise HTTPException(status_code=400, detail=f"Invalid graph: {'; '.join(errors)}")
    return {"format": "sumo", "filename": "network.net.xml", "content": export_sumo(graph)}


@router.post("/to-network")
def to_network_endpoint(payload: GraphRequest) -> Dict[str, Any]:
    """``{network|null, notes[]}``: the graph as an ``urbanflow-network``."""
    graph, errors = parse_graph(payload.graph)
    if graph is None:
        raise HTTPException(status_code=400, detail=f"Invalid graph: {'; '.join(errors)}")
    network, notes = graph_to_network(graph)
    return {"network": network, "notes": notes}


@router.get("/corridor")
def corridor_endpoint() -> Dict[str, Any]:
    """The built-in two-junction corridor graph and its default flows."""
    return {
        "graph": serialize_graph(build_two_junction_corridor()),
        "flows": [
            {"origin": f.origin, "destination": f.destination, "vehiclesPerHour": f.vehicles_per_hour}
            for f in corridor_flows()
        ],
    }


@router.post("/simulate")
def simulate_endpoint(payload: SimulateRequest) -> Dict[str, Any]:
    """Run vehicles through a graph; returns the ``urbanflow-graph-result``
    (counts, ``conserved``, per-link and per-node tallies)."""
    if payload.graph is None:
        graph = build_two_junction_corridor()
    else:
        graph, errors = parse_graph(payload.graph)
        if graph is not None:
            errors = validate_graph(graph)["errors"]
        if graph is None or errors:
            raise HTTPException(status_code=400, detail=f"Invalid graph: {'; '.join(errors)}")
    if payload.flows is None:
        flows = corridor_flows() if payload.graph is None else []
    else:
        flows = [Flow(f.origin, f.destination, f.vehiclesPerHour) for f in payload.flows]
    return simulate_network(graph, flows, duration=payload.duration, seed=payload.seed)
