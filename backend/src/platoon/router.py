"""``/api/v2/platoon``: platoon (CACC) vs human (IDM) experiments (F20).
Stateless: nothing is stored. Estimates from a 1-D single-lane model.

Register in ``main.py`` (same dependencies as the other network routers)::

    from src.platoon.router import router as platoon_router
    app.include_router(
        platoon_router,
        dependencies=[Depends(require_api_key), Depends(get_current_user_id)],
    )
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.platoon.analysis import string_stability, throughput_vph
from src.platoon.control import STATES, TRANSITIONS
from src.platoon.dynamics import CACCParams, IDMParams
from src.platoon.experiment import (
    HUMAN_REACTION_S,
    LABEL,
    ExperimentSpec,
    channel_sweep,
    run_experiment,
)
from src.uncertainty.comparison import METHODS

router = APIRouter(prefix="/api/v2/platoon", tags=["platoon"])

MAX_VEHICLES = 20
MAX_DURATION = 600.0
MAX_SEEDS = 10
MAX_WORK = 3_000_000  # vehicle-steps (runs x vehicles x steps) per request


class SweepIn(BaseModel):
    latenciesMs: List[float] = Field(
        default_factory=lambda: [0.0, 200.0, 500.0], min_length=1, max_length=3
    )
    lossProbabilities: List[float] = Field(
        default_factory=lambda: [0.0, 0.2, 0.5], min_length=1, max_length=3
    )


class ExperimentRequest(BaseModel):
    vehicles: int = Field(default=10, ge=2, le=MAX_VEHICLES)
    durationSeconds: float = Field(default=200.0, ge=30, le=MAX_DURATION)
    speedMps: float = Field(default=25.0, ge=5, le=35)
    timeGapSeconds: float = Field(default=0.6, ge=0.3, le=3.0)
    latencyMs: float = Field(default=0.0, ge=0, le=2000)
    lossProbability: float = Field(default=0.0, ge=0, le=1)
    brakeDecelMps2: float = Field(default=4.0, ge=0.5, le=8.0)
    seeds: List[int] = Field(
        default_factory=lambda: [1, 2, 3, 4, 5], min_length=2, max_length=MAX_SEEDS
    )
    method: str = "paired_t"
    confidence: float = Field(default=0.95, gt=0.5, lt=1.0)
    channelSweep: Optional[SweepIn] = None


@router.post("/experiment")
def experiment(req: ExperimentRequest) -> Dict[str, Any]:
    if req.method not in METHODS:
        raise HTTPException(
            status_code=422, detail=f"method must be one of {list(METHODS)}"
        )
    runs = 2 * len(req.seeds)
    if req.channelSweep is not None:
        cells = len(req.channelSweep.latenciesMs) * len(
            req.channelSweep.lossProbabilities
        )
        runs += cells * len(req.seeds)
    work = runs * req.vehicles * int(req.durationSeconds / 0.1)
    if work > MAX_WORK:
        raise HTTPException(
            status_code=422,
            detail=f"request too large ({work} vehicle-steps, limit {MAX_WORK}); "
            "reduce vehicles, duration, seeds or the sweep",
        )
    spec = ExperimentSpec(
        vehicles=req.vehicles,
        duration=req.durationSeconds,
        speed=req.speedMps,
        time_gap=req.timeGapSeconds,
        latency_s=req.latencyMs / 1000.0,
        loss=req.lossProbability,
        pulse_decel=req.brakeDecelMps2,
        seeds=tuple(req.seeds),
        confidence=req.confidence,
        method=req.method,
    )
    try:
        out = run_experiment(spec)
        if req.channelSweep is not None:
            out["channelSweep"] = channel_sweep(
                spec,
                [m / 1000.0 for m in req.channelSweep.latenciesMs],
                req.channelSweep.lossProbabilities,
            )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    out["stringStability"] = string_stability(
        min(req.vehicles, 10), req.timeGapSeconds, "cacc", speed=min(req.speedMps, 25.0)
    )
    out["throughputSteadyState"] = {
        "cacc": throughput_vph(req.speedMps, "cacc", req.timeGapSeconds),
        "idm": throughput_vph(req.speedMps, "idm", 1.5),
    }
    return out


@router.get("/catalogue")
def catalogue() -> Dict[str, Any]:
    return {
        "states": list(STATES),
        "transitions": [
            {"from": s, "event": e, "to": t} for (s, e), t in TRANSITIONS.items()
        ],
        "controllers": {
            "cacc": CACCParams().__dict__,
            "idm": IDMParams().__dict__,
        },
        "humanReactionSeconds": HUMAN_REACTION_S,
        "limits": {
            "vehicles": MAX_VEHICLES,
            "durationSeconds": MAX_DURATION,
            "seeds": MAX_SEEDS,
            "workVehicleSteps": MAX_WORK,
        },
        "methods": list(METHODS),
        "metrics": ["throughputVph", "fuelLPer100Km", "co2GPerKm"],
        "isEstimate": True,
        "label": LABEL,
    }
