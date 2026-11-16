"""``/api/v2/aim``: signal-free (reservation-based) intersection vs fixed-time
signal comparison (F20). Stateless: nothing is stored.

Register in ``main.py`` (same dependencies as the other network routers)::

    from src.aim.router import router as aim_router
    app.include_router(
        aim_router,
        dependencies=[Depends(require_api_key), Depends(get_current_user_id)],
    )
"""

from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.aim.experiment import (
    ASSUMPTIONS,
    DEFAULT_DEMANDS,
    DEFAULT_LOSSES,
    run_comparison,
)
from src.aim.geometry import MOVEMENTS, build_geometry
from src.aim.manager import SignalPlan
from src.aim.trajectory import KinParams
from src.uncertainty.comparison import METHODS

router = APIRouter(prefix="/api/v2/aim", tags=["aim"])

MAX_SEEDS = 10
MAX_DURATION = 600.0
MAX_DEMAND = 900.0
# seeds x duration x simulated runs per seed (2 per demand + 1 per loss level)
MAX_WORK_SECONDS = 36_000.0


class StressIn(BaseModel):
    demandVehPerHourPerApproach: float = Field(default=450.0, gt=0, le=MAX_DEMAND)
    lossProbabilities: List[float] = Field(
        default_factory=lambda: list(DEFAULT_LOSSES), min_length=1, max_length=5
    )


class ComparisonRequest(BaseModel):
    durationSeconds: float = Field(default=300.0, ge=30, le=MAX_DURATION)
    seeds: List[int] = Field(
        default_factory=lambda: [1, 2, 3, 4, 5], min_length=2, max_length=MAX_SEEDS
    )
    demandsVehPerHourPerApproach: List[float] = Field(
        default_factory=lambda: list(DEFAULT_DEMANDS), min_length=1, max_length=6
    )
    leftFraction: float = Field(default=0.15, ge=0, le=0.5)
    rightFraction: float = Field(default=0.15, ge=0, le=0.5)
    greenSeconds: float = Field(default=25.0, ge=5, le=60)
    yellowSeconds: float = Field(default=3.0, ge=1, le=6)
    allRedSeconds: float = Field(default=2.0, ge=0, le=6)
    messageLoss: Optional[StressIn] = None
    confidence: float = Field(default=0.95, gt=0.5, lt=1)
    method: Literal["paired_t", "paired_bootstrap"] = "paired_t"


def _unit(values: List[float], name: str) -> None:
    if any(not 0.0 <= v <= 1.0 for v in values):
        raise HTTPException(422, detail=[f"{name} values must lie in [0, 1]"])


@router.post("/comparison")
def comparison(req: ComparisonRequest) -> Dict[str, Any]:
    """AIM vs fixed-time signal over the same seeds, per demand level (paired,
    AIM minus signal), plus an optional message-loss stress test. Every result
    carries the G-AIM ``safety`` object and the in-model best-case caveat."""
    if len(set(req.seeds)) != len(req.seeds):
        raise HTTPException(422, detail=["seeds must be distinct"])
    if any(not 0 < d <= MAX_DEMAND for d in req.demandsVehPerHourPerApproach):
        raise HTTPException(
            422, detail=[f"demands must lie in (0, {MAX_DEMAND:g}] veh/h/approach"]
        )
    if req.leftFraction + req.rightFraction > 1.0:
        raise HTTPException(422, detail=["leftFraction + rightFraction must be <= 1"])
    losses = req.messageLoss.lossProbabilities if req.messageLoss else []
    _unit(losses, "lossProbabilities")
    work = (
        len(req.seeds)
        * req.durationSeconds
        * (
            2 * len(req.demandsVehPerHourPerApproach)
            + len(losses)
            + (1 if losses else 0)
        )
    )
    if work > MAX_WORK_SECONDS:
        raise HTTPException(
            422,
            detail=[
                "request too large: reduce seeds, duration, demands or loss levels "
                f"(work {work:g} > {MAX_WORK_SECONDS:g} seed-seconds)"
            ],
        )
    return run_comparison(
        req.seeds,
        req.demandsVehPerHourPerApproach,
        duration=req.durationSeconds,
        left_fraction=req.leftFraction,
        right_fraction=req.rightFraction,
        signal=SignalPlan(req.greenSeconds, req.yellowSeconds, req.allRedSeconds),
        loss_probabilities=losses,
        stress_demand=(
            req.messageLoss.demandVehPerHourPerApproach if req.messageLoss else 450.0
        ),
        confidence=req.confidence,
        method=req.method,
    )


@router.get("/catalogue")
def catalogue() -> Dict[str, Any]:
    geo = build_geometry()
    p = KinParams()
    sig = SignalPlan()
    return {
        "geometry": {
            "boxMetres": geo.box,
            "tileMetres": geo.tile,
            "tiles": geo.tile_count,
            "laneOffsetMetres": geo.lane_offset,
            "approaches": ["south", "west", "north", "east"],
            "movements": list(MOVEMENTS),
        },
        "kinematics": {
            "vmax": p.vmax,
            "accel": p.accel,
            "decel": p.decel,
            "boxSpeedStraight": p.box_speed_straight,
            "boxSpeedTurn": p.box_speed_turn,
        },
        "controllers": {
            "aim": "first-come-first-served tile reservations with a time buffer",
            "signal": {
                "type": "fixed-time two-phase",
                "greenSeconds": sig.green,
                "yellowSeconds": sig.yellow,
                "allRedSeconds": sig.all_red,
            },
        },
        "metrics": {
            "meanDelay": "seconds, lower is better",
            "stopsPerVehicle": "lower is better",
            "throughputVph": "vehicles entering the box per hour, higher is better",
        },
        "safetyChecks": [
            "no two footprints share a tile at any step",
            "no deadlock",
            "minimum time gap",
            "speed and acceleration bounds",
        ],
        "limits": {
            "maxSeeds": MAX_SEEDS,
            "maxDurationSeconds": MAX_DURATION,
            "maxDemandVehPerHourPerApproach": MAX_DEMAND,
            "maxWorkSeedSeconds": MAX_WORK_SECONDS,
        },
        "defaults": {
            "demandsVehPerHourPerApproach": list(DEFAULT_DEMANDS),
            "lossProbabilities": list(DEFAULT_LOSSES),
        },
        "methods": list(METHODS),
        "assumptions": list(ASSUMPTIONS),
    }
