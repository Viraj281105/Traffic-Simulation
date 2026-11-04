"""``/api/v2/twin``: stateless digital-twin endpoints (F14).

Nothing is stored. Each request carries its observations inline (and,
optionally, the road graph and base flows; the two-junction corridor is the
default), so the same request always gives the same answer.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from src.networks.corridor import build_two_junction_corridor, corridor_flows
from src.networks.graph import RoadGraph
from src.networks.network_sim import Flow
from src.twin.models import Observation
from src.twin.runner import MAX_WINDOWS, TwinRunner
from src.twin.whatif import Scenario, what_if

router = APIRouter(prefix="/api/v2/twin", tags=["twin"])

MAX_OBSERVATIONS = 20000
MAX_FLOWS = 200
MAX_INTERVAL = 3600.0
MAX_WARMUP = 1800.0


class FlowIn(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    origin: str = Field(..., min_length=1, max_length=64)
    destination: str = Field(..., min_length=1, max_length=64)
    vehicles_per_hour: float = Field(..., alias="vehiclesPerHour", ge=0, le=100000)


class TwinRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    observations: List[Observation] = Field(..., max_length=MAX_OBSERVATIONS)
    graph: Optional[RoadGraph] = None  # default: the two-junction corridor
    flows: Optional[List[FlowIn]] = Field(
        None, max_length=MAX_FLOWS
    )  # default: corridor flows
    interval_seconds: float = Field(
        60.0, alias="intervalSeconds", gt=0, le=MAX_INTERVAL
    )
    warmup_seconds: float = Field(120.0, alias="warmupSeconds", ge=0, le=MAX_WARMUP)
    start: float = Field(0.0, ge=0)
    seed: int = 1
    alert_threshold_pct: float = Field(25.0, alias="alertThresholdPct", gt=0)


class ScenarioIn(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    close_links: List[str] = Field(default_factory=list, alias="closeLinks")
    demand_scale: float = Field(1.0, alias="demandScale", ge=0, le=10)
    lanes: Dict[str, int] = Field(default_factory=dict)
    speed_factors: Dict[str, float] = Field(default_factory=dict, alias="speedFactors")


class WhatIfRequest(TwinRequest):
    scenario: ScenarioIn
    horizon_windows: int = Field(1, alias="horizonWindows", ge=1, le=12)


def _build_twin(payload: TwinRequest) -> TwinRunner:
    graph = payload.graph or build_two_junction_corridor()
    flows = (
        [Flow(f.origin, f.destination, f.vehicles_per_hour) for f in payload.flows]
        if payload.flows is not None
        else corridor_flows()
    )
    twin = TwinRunner(
        graph,
        flows,
        interval=payload.interval_seconds,
        warmup=payload.warmup_seconds,
        seed=payload.seed,
        start=payload.start,
        alert_threshold_pct=payload.alert_threshold_pct,
    )
    twin.ingest(payload.observations)
    if twin.latest_window is not None and twin.latest_window + 1 > MAX_WINDOWS:
        raise HTTPException(
            status_code=400,
            detail=f"Observations span more than {MAX_WINDOWS} windows.",
        )
    return twin


@router.post("/compare")
def compare_endpoint(payload: TwinRequest) -> Dict[str, Any]:
    """Run the twin over the observations and return its state: the
    prediction timeline, per-link and network MAE / MAPE / bias, lag and alerts."""
    twin = _build_twin(payload)
    twin.run()
    return twin.state()


@router.post("/whatif")
def whatif_endpoint(payload: WhatIfRequest) -> Dict[str, Any]:
    """Fork the twin at the latest observation and return the scenario's
    delta against the baseline prediction for the next windows."""
    twin = _build_twin(payload)
    s = payload.scenario
    try:
        return what_if(
            twin,
            Scenario(
                close_links=s.close_links,
                demand_scale=s.demand_scale,
                lanes=s.lanes,
                speed_factors=s.speed_factors,
            ),
            payload.horizon_windows,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
