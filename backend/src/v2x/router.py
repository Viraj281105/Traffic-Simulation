"""``/api/v2/v2x``: cooperative vs non-cooperative V2X experiments and the
message schemas (F19). Stateless: nothing is stored.

Register in ``main.py`` (same dependencies as the other network routers)::

    from src.v2x.router import router as v2x_router
    app.include_router(
        v2x_router,
        dependencies=[Depends(require_api_key), Depends(get_current_user_id)],
    )
"""

from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.netmetrics.router import FlowIn, GridSpec, RunRequest
from src.netmetrics.router import _resolve as _resolve_network
from src.uncertainty.comparison import METHODS
from src.v2x.behaviour import BehaviourConfig, Hazard
from src.v2x.channel import ChannelConfig, LatencyKind
from src.v2x.experiment import DEFAULT_PENETRATIONS, SensitivitySpec, run_experiment
from src.v2x.messages import KINDS, schemas

router = APIRouter(prefix="/api/v2/v2x", tags=["v2x"])

MAX_SEEDS = 10
MAX_DURATION = 900.0
MAX_LINKS = 200


class GridIn(GridSpec):
    rows: int = Field(default=3, ge=1, le=5)
    cols: int = Field(default=3, ge=1, le=5)


class ChannelIn(BaseModel):
    latencyKind: LatencyKind = "constant"
    latencyMs: float = Field(default=0.0, ge=0, le=10_000)
    jitterMs: float = Field(default=0.0, ge=0, le=10_000)
    lossProbability: float = Field(default=0.0, ge=0, le=1)
    rangeM: Optional[float] = Field(default=None, gt=0, le=5000)


class BehaviourIn(BaseModel):
    advisoryHorizonSeconds: float = Field(default=15.0, gt=0, le=60)
    minLeadSeconds: float = Field(default=2.0, ge=0, le=30)
    minSpeedFraction: float = Field(default=0.4, gt=0, le=1)
    spatPeriodSeconds: float = Field(default=1.0, ge=0.1, le=10)
    startupLossSeconds: float = Field(default=2.0, ge=0, le=10)


class HazardIn(BaseModel):
    linkId: str = Field(..., min_length=1, max_length=64)
    startSeconds: float = Field(default=0.0, ge=0, le=MAX_DURATION)
    delaySeconds: float = Field(default=60.0, gt=0, le=600)


class SensitivityIn(BaseModel):
    penetration: float = Field(default=1.0, ge=0, le=1)
    latenciesMs: List[float] = Field(
        default_factory=lambda: [0.0, 100.0, 500.0, 2000.0, 5000.0],
        min_length=1,
        max_length=6,
    )
    lossProbabilities: List[float] = Field(
        default_factory=lambda: [0.0, 0.1, 0.3, 0.6, 0.9], min_length=1, max_length=6
    )


class ExperimentRequest(BaseModel):
    # Give `graph` (with `flows`) or a `grid`; with neither, a 3x3 grid runs.
    graph: Optional[Dict[str, Any]] = None
    grid: Optional[GridIn] = None
    flows: Optional[List[FlowIn]] = None
    duration: float = Field(default=600.0, gt=0, le=MAX_DURATION)
    seeds: List[int] = Field(
        default_factory=lambda: [1, 2, 3, 4, 5], min_length=2, max_length=MAX_SEEDS
    )
    penetrations: List[float] = Field(
        default_factory=lambda: list(DEFAULT_PENETRATIONS), min_length=1, max_length=6
    )
    channel: ChannelIn = Field(default_factory=lambda: ChannelIn())
    behaviour: BehaviourIn = Field(default_factory=lambda: BehaviourIn())
    hazard: Optional[HazardIn] = None
    sensitivity: Optional[SensitivityIn] = None
    confidence: float = Field(default=0.95, gt=0.5, lt=1)
    method: Literal["paired_t", "paired_bootstrap"] = "paired_t"


def _check_unit_interval(values: List[float], name: str) -> None:
    bad = [v for v in values if not 0.0 <= v <= 1.0]
    if bad:
        raise HTTPException(422, detail=[f"{name} values must lie in [0, 1]: {bad}"])


@router.post("/experiment")
def experiment(req: ExperimentRequest) -> Dict[str, Any]:
    """Run a cooperative vs non-cooperative experiment. For each penetration
    rate, per-vehicle delay, stops, fuel and CO2 are compared with the
    baseline over the same seeds (paired; cooperative minus baseline, so
    negative is a benefit), with message delivery ratio and mean message age
    at use. ``sensitivity`` adds a latency x loss grid at one penetration.
    The response's ``provenance`` records the channel, behaviour, seeds and the
    modelling assumptions."""
    _check_unit_interval(req.penetrations, "penetrations")
    if len(set(req.seeds)) != len(req.seeds):
        raise HTTPException(422, detail=["seeds must be distinct"])
    if req.sensitivity is not None:
        _check_unit_interval(req.sensitivity.lossProbabilities, "lossProbabilities")
        if any(not 0.0 <= v <= 10_000 for v in req.sensitivity.latenciesMs):
            raise HTTPException(
                422, detail=["latenciesMs values must lie in [0, 10000]"]
            )
    # Reuse the network router's resolution (graph/grid, flows, node cap).
    graph, flows = _resolve_network(
        RunRequest(
            graph=req.graph,
            grid=req.grid,
            flows=req.flows,
            duration=req.duration,
            bucketSeconds=30.0,
            originLat=None,
            originLon=None,
        )
    )
    if len(graph.links) > MAX_LINKS:
        raise HTTPException(422, detail=[f"At most {MAX_LINKS} links are allowed"])
    if req.hazard is not None and req.hazard.linkId not in graph.link_map():
        raise HTTPException(422, detail=[f"Unknown hazard link {req.hazard.linkId!r}"])
    try:
        channel = ChannelConfig(
            latency_kind=req.channel.latencyKind,
            latency_ms=req.channel.latencyMs,
            jitter_ms=req.channel.jitterMs,
            loss_probability=req.channel.lossProbability,
            range_m=req.channel.rangeM,
        )
        b = req.behaviour
        behaviour = BehaviourConfig(
            advisory_horizon_s=b.advisoryHorizonSeconds,
            min_lead_s=b.minLeadSeconds,
            min_speed_fraction=b.minSpeedFraction,
            spat_period_s=b.spatPeriodSeconds,
            startup_loss_s=b.startupLossSeconds,
        )
        hazard = (
            Hazard(req.hazard.linkId, req.hazard.startSeconds, req.hazard.delaySeconds)
            if req.hazard
            else None
        )
        sens = (
            SensitivitySpec(
                req.sensitivity.penetration,
                tuple(req.sensitivity.latenciesMs),
                tuple(req.sensitivity.lossProbabilities),
            )
            if req.sensitivity
            else None
        )
        return run_experiment(
            graph,
            flows,
            duration=req.duration,
            seeds=req.seeds,
            penetrations=req.penetrations,
            channel=channel,
            behaviour=behaviour,
            hazard=hazard,
            sensitivity=sens,
            confidence=req.confidence,
            method=req.method,
        )
    except ValueError as err:
        raise HTTPException(422, detail=[str(err)])


@router.get("/schemas")
def message_schemas() -> Dict[str, Any]:
    """JSON Schemas (wire field names) of the V2X messages, the MQTT topic
    layout and the accepted comparison methods."""
    return {
        "kinds": list(KINDS),
        "topic": "urbanflow/v2x/<kind>/<node>",
        "schemas": schemas(),
        "methods": list(METHODS),
    }
