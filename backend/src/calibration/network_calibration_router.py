"""Stateless network calibration endpoints, ``/api/v2/calibration/network-fit``.

Nothing is stored: each call takes the graph, the OD flows and the count CSV
and answers from them (same inputs, same report; see ``manifest.hash``).
Compute is bounded (nodes, rows, budget, duration) and holds a compute slot.
Same auth as the V1.8 calibration router, whose paths do not overlap.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from src.api.auth import get_current_user_id
from src.api.request_limits import compute_slot
from src.api.security import require_api_key
from src.calibration.network_counts import CountSet, load_counts_csv
from src.calibration.network_fit import (
    FitOptions,
    NetworkCalibrationError,
    SimSettings,
    calibrate_network,
)
from src.calibration.network_metrics import GCalCriteria
from src.calibration.network_recalibration import DEFAULT_DRIFT_THRESHOLD, recalibrate
from src.networks.graph import RoadGraph, parse_graph
from src.networks.network_sim import Flow

MAX_ROUTER_NODES = 400
MAX_ROUTER_FLOWS = 60
MAX_ROUTER_BUDGET = 300
MAX_ROUTER_DURATION = 1800.0
MAX_ROUTER_CSV_CHARS = 8_000_000

router = APIRouter(
    prefix="/api/v2/calibration",
    tags=["calibration"],
    dependencies=[Depends(require_api_key), Depends(get_current_user_id)],
)


class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class FlowIn(_Body):
    origin: str
    destination: str
    vehicles_per_hour: float = Field(..., ge=0, alias="vehiclesPerHour")


class CriteriaIn(_Body):
    geh_limit: float = Field(default=5.0, gt=0, alias="gehLimit")
    min_fraction: float = Field(default=0.85, gt=0, le=1, alias="minFraction")
    max_mape: Optional[float] = Field(default=None, gt=0, alias="maxMape")
    max_rmse: Optional[float] = Field(default=None, gt=0, alias="maxRmse")


class OptionsIn(_Body):
    budget: int = Field(default=150, ge=2, le=MAX_ROUTER_BUDGET)
    seed: int = 1
    calibrate_demand: bool = Field(default=True, alias="calibrateDemand")
    calibrate_speed: bool = Field(default=True, alias="calibrateSpeed")
    speed_groups: Optional[Dict[str, List[str]]] = Field(
        default=None, alias="speedGroups"
    )
    min_observed_vph: float = Field(default=10.0, ge=0, alias="minObservedVph")
    criteria: CriteriaIn = Field(default_factory=lambda: CriteriaIn())


class SimIn(_Body):
    duration: float = Field(default=600.0, gt=0, le=MAX_ROUTER_DURATION)
    seed: int = 1


class NetworkFitRequest(_Body):
    graph: Dict[str, Any]
    flows: List[FlowIn] = Field(..., min_length=1, max_length=MAX_ROUTER_FLOWS)
    counts_csv: str = Field(..., alias="countsCsv", max_length=MAX_ROUTER_CSV_CHARS)
    interval_seconds: Optional[float] = Field(
        default=None, gt=0, alias="intervalSeconds"
    )
    options: OptionsIn = Field(default_factory=lambda: OptionsIn())
    sim: SimIn = Field(default_factory=lambda: SimIn())
    source: str = Field(default="upload", max_length=200)


class RecalibrateRequest(NetworkFitRequest):
    previous: Dict[str, float] = Field(..., min_length=1)
    window_intervals: Optional[int] = Field(default=None, ge=1, alias="windowIntervals")
    drift_threshold: float = Field(
        default=DEFAULT_DRIFT_THRESHOLD, gt=0, alias="driftThreshold"
    )


class ValidateCountsRequest(_Body):
    graph: Dict[str, Any]
    counts_csv: str = Field(..., alias="countsCsv", max_length=MAX_ROUTER_CSV_CHARS)
    interval_seconds: Optional[float] = Field(
        default=None, gt=0, alias="intervalSeconds"
    )


def _graph_or_400(raw: Dict[str, Any]) -> RoadGraph:
    graph, errors = parse_graph(raw)
    if graph is None:
        raise HTTPException(
            status_code=400, detail="Invalid graph: " + "; ".join(errors)
        )
    if len(graph.nodes) > MAX_ROUTER_NODES:
        raise HTTPException(
            status_code=400,
            detail=f"The graph has {len(graph.nodes)} nodes; this endpoint accepts {MAX_ROUTER_NODES}",
        )
    return graph


def _counts(
    graph: RoadGraph, csv_text: str, interval: Optional[float], source: str
) -> CountSet:
    return load_counts_csv(
        csv_text, interval_seconds=interval, known_links=graph.link_map(), source=source
    )


def _options(o: OptionsIn) -> FitOptions:
    return FitOptions(
        budget=o.budget,
        seed=o.seed,
        calibrate_demand=o.calibrate_demand,
        calibrate_speed=o.calibrate_speed,
        speed_groups=o.speed_groups,
        min_observed_vph=o.min_observed_vph,
        criteria=GCalCriteria(
            o.criteria.geh_limit,
            o.criteria.min_fraction,
            o.criteria.max_mape,
            o.criteria.max_rmse,
        ),
    )


def _flows(req: NetworkFitRequest) -> List[Flow]:
    return [Flow(f.origin, f.destination, f.vehicles_per_hour) for f in req.flows]


@router.post("/network-fit/validate-counts")
def validate_counts(req: ValidateCountsRequest) -> Dict[str, Any]:
    """Always 200 once the graph parses: ``valid`` is false and ``errors`` say
    why when the count file is unusable."""
    graph = _graph_or_400(req.graph)
    counts = _counts(graph, req.counts_csv, req.interval_seconds, "upload")
    return {
        "valid": counts.valid,
        "errors": counts.errors,
        "warnings": counts.warnings,
        "provenance": counts.provenance(),
        "linkFlowsVph": {k: round(v, 3) for k, v in counts.link_flows_vph().items()},
    }


@router.post("/network-fit", dependencies=[Depends(compute_slot)])
def network_fit(req: NetworkFitRequest) -> Dict[str, Any]:
    """Calibrate demand and free-flow speed scales against the counts and
    return the calibration report (see network_fit.calibrate_network)."""
    graph = _graph_or_400(req.graph)
    counts = _counts(graph, req.counts_csv, req.interval_seconds, req.source)
    try:
        return calibrate_network(
            graph,
            _flows(req),
            counts,
            _options(req.options),
            SimSettings(duration=req.sim.duration, seed=req.sim.seed),
        )
    except NetworkCalibrationError as err:
        raise HTTPException(status_code=400, detail="; ".join(err.errors))


@router.post("/network-fit/recalibrate", dependencies=[Depends(compute_slot)])
def network_recalibrate(req: RecalibrateRequest) -> Dict[str, Any]:
    """Re-fit on the last ``windowIntervals`` of the counts, warm-started from
    ``previous`` (a report's ``parameters.fitted``); adds ``recalibration``
    with the drift."""
    graph = _graph_or_400(req.graph)
    counts = _counts(graph, req.counts_csv, req.interval_seconds, req.source)
    try:
        return recalibrate(
            graph,
            _flows(req),
            counts,
            req.previous,
            window_intervals=req.window_intervals,
            options=_options(req.options),
            sim=SimSettings(duration=req.sim.duration, seed=req.sim.seed),
            drift_threshold=req.drift_threshold,
        )
    except NetworkCalibrationError as err:
        raise HTTPException(status_code=400, detail="; ".join(err.errors))
