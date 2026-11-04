"""``/api/v2/network-metrics``: network-wide metrics, congestion propagation
and grid scenarios (F5). Stateless: nothing is stored.

Register in ``main.py`` (same dependencies as the other network routers)::

    from src.netmetrics.router import router as network_metrics_router
    app.include_router(
        network_metrics_router,
        dependencies=[Depends(require_api_key), Depends(get_current_user_id)],
    )
"""

from typing import Any, Dict, List, Literal, Optional, Tuple

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.netmetrics.congestion import analyse_congestion
from src.netmetrics.mapdata import map_data
from src.netmetrics.metrics import compute_metrics
from src.netmetrics.recorder import run_recorded
from src.networks.graph import RoadGraph, parse_graph, serialize_graph, validate_graph
from src.networks.grid import (
    build_grid,
    build_three_by_three,
    build_twelve_junction_network,
    grid_flows,
)
from src.networks.network_sim import Flow

router = APIRouter(prefix="/api/v2/network-metrics", tags=["network-metrics"])

MAX_NODES = 400


class FlowIn(BaseModel):
    origin: str
    destination: str
    vehiclesPerHour: float = Field(..., ge=0, le=7200)


class GridSpec(BaseModel):
    rows: int = Field(default=3, ge=1, le=12)
    cols: int = Field(default=3, ge=1, le=12)
    spacing: float = Field(default=300.0, ge=20, le=2000)
    vehiclesPerHour: float = Field(default=300.0, ge=0, le=3600)
    preset: Optional[Literal["3x3", "12-junction"]] = None  # overrides rows/cols


class RunRequest(BaseModel):
    # Give `graph` (with `flows`) or a `grid`; with neither, a 3x3 grid runs.
    graph: Optional[Dict[str, Any]] = None
    grid: Optional[GridSpec] = None
    flows: Optional[List[FlowIn]] = None
    duration: float = Field(600.0, gt=0, le=3600)
    seed: int = 1
    bucketSeconds: float = Field(30.0, ge=1, le=600)
    includeMap: bool = False
    originLat: Optional[float] = Field(None, ge=-90, le=90)
    originLon: Optional[float] = Field(None, ge=-180, le=180)


class SimulateRequest(RunRequest):
    perLinkDiagram: bool = False


class CongestionRequest(RunRequest):
    threshold: float = Field(0.3, gt=0, le=1)
    minHoldSeconds: float = Field(10.0, ge=1, le=600)
    minSpillbackSeconds: float = Field(5.0, ge=1, le=600)


def _grid(spec: GridSpec) -> Tuple[RoadGraph, List[Flow]]:
    if spec.preset == "3x3":
        g, rows, cols = build_three_by_three(spec.spacing), 3, 3
    elif spec.preset == "12-junction":
        g, rows, cols = build_twelve_junction_network(spec.spacing), 3, 4
    else:
        rows, cols = spec.rows, spec.cols
        g = build_grid(
            rows,
            cols,
            spec.spacing,
            arterial_rows=(rows // 2,) if rows >= 3 else (),
            arterial_cols=(cols // 2,) if cols >= 3 else (),
        )
    return g, grid_flows(rows, cols, spec.vehiclesPerHour)


def _resolve(req: RunRequest) -> Tuple[RoadGraph, List[Flow]]:
    if req.graph is not None:
        graph, errors = parse_graph(req.graph)
        if graph is None:
            raise HTTPException(422, detail=errors)
        check = validate_graph(graph)
        if check["errors"]:
            raise HTTPException(422, detail=check["errors"])
        if not req.flows:
            raise HTTPException(422, detail=["flows are required with a custom graph"])
        flows = [Flow(f.origin, f.destination, f.vehiclesPerHour) for f in req.flows]
    else:
        graph, default = _grid(req.grid or GridSpec())
        flows = (
            [Flow(f.origin, f.destination, f.vehiclesPerHour) for f in req.flows]
            if req.flows
            else default
        )
    if len(graph.nodes) > MAX_NODES:
        raise HTTPException(422, detail=[f"At most {MAX_NODES} nodes are allowed"])
    ids = {n.id for n in graph.nodes}
    bad = sorted({e for f in flows for e in (f.origin, f.destination) if e not in ids})
    if bad:
        raise HTTPException(
            422, detail=[f"Flow refers to unknown node {b!r}" for b in bad]
        )
    return graph, flows


def _run(req: RunRequest, graph: RoadGraph, flows: List[Flow]) -> Any:
    try:
        return run_recorded(graph, flows, req.duration, req.seed)
    except ValueError as err:  # run too large to analyse
        raise HTTPException(422, detail=[str(err)])


def _map(
    req: RunRequest, graph: RoadGraph, values: Optional[Dict[str, float]], label: str
) -> Dict[str, Any]:
    return map_data(graph, req.originLat, req.originLon, values, label)


@router.post("/simulate")
def simulate(req: SimulateRequest) -> Dict[str, Any]:
    """Run a network and return network-wide metrics (shape: see
    ``compute_metrics``): ``network`` totals, ``perLink``, ``perNode``,
    ``series`` per bucket and ``fundamentalDiagram`` points. With
    ``includeMap`` the response also carries ``map`` (link ``value`` is the
    mean occupancy ratio)."""
    graph, flows = _resolve(req)
    result, rec = _run(req, graph, flows)
    out = compute_metrics(graph, result, rec, req.bucketSeconds, req.perLinkDiagram)
    if req.includeMap:
        vals = {k: v["meanOccupancyRatio"] for k, v in out["perLink"].items()}
        out["map"] = _map(req, graph, vals, "meanOccupancyRatio")
    return out


@router.post("/congestion")
def congestion(req: CongestionRequest) -> Dict[str, Any]:
    """Run a network and return the congestion propagation analysis (shape:
    see ``analyse_congestion``): ``heatmap`` (links x time buckets),
    ``spillback`` events and ``spread`` front. With ``includeMap`` the
    response also carries ``map`` (link ``value`` is the peak occupancy ratio)."""
    graph, flows = _resolve(req)
    result, rec = _run(req, graph, flows)
    out = analyse_congestion(
        graph,
        result,
        rec,
        req.bucketSeconds,
        req.threshold,
        req.minHoldSeconds,
        req.minSpillbackSeconds,
    )
    if req.includeMap:
        vals = {row["id"]: row["peakOccupancyRatio"] for row in out["links"]}
        out["map"] = _map(req, graph, vals, "peakOccupancyRatio")
    return out


@router.get("/grid")
def grid(
    rows: int = Query(3, ge=1, le=12),
    cols: int = Query(3, ge=1, le=12),
    spacing: float = Query(300.0, ge=20, le=2000),
    vehiclesPerHour: float = Query(300.0, ge=0, le=3600),  # noqa: N803
    preset: Optional[Literal["3x3", "12-junction"]] = None,
    originLat: Optional[float] = Query(None, ge=-90, le=90),  # noqa: N803
    originLon: Optional[float] = Query(None, ge=-180, le=180),  # noqa: N803
) -> Dict[str, Any]:
    """A grid scenario: the graph, its default flows and map data."""
    graph, flows = _grid(
        GridSpec(
            rows=rows,
            cols=cols,
            spacing=spacing,
            vehiclesPerHour=vehiclesPerHour,
            preset=preset,
        )
    )
    return {
        "graph": serialize_graph(graph),
        "flows": [
            {
                "origin": f.origin,
                "destination": f.destination,
                "vehiclesPerHour": f.vehicles_per_hour,
            }
            for f in flows
        ],
        "validation": validate_graph(graph),
        "map": map_data(graph, originLat, originLon),
    }
