"""``/api/v2/priority``: emergency and transit priority comparisons (F12).
Stateless: nothing is stored, every request runs its simulations and returns.

Register in ``main.py`` (same dependencies as the other v2 routers)::

    from src.priority.router import router as priority_router
    app.include_router(
        priority_router,
        dependencies=[Depends(require_api_key), Depends(get_current_user_id)],
    )

Results are in-model only (the response says so in ``label``).
"""

from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.priority import models as m
from src.priority.comparison import (
    IN_MODEL_LABEL,
    run_emergency_comparison,
    run_transit_comparison,
)
from src.priority.models import (
    EmergencySpec,
    PreemptionConfig,
    ScenarioSpec,
    TransitLineSpec,
    TransitPriorityConfig,
    YieldConfig,
)
from src.priority.vehicles import EMERGENCY_KINDS
from src.uncertainty.comparison import METHODS

router = APIRouter(prefix="/api/v2/priority", tags=["priority"])

Approach = Literal["north", "south", "east", "west"]
Turn = Literal["left", "straight", "right"]
Method = Literal["paired_t", "paired_bootstrap"]


class ScenarioIn(BaseModel):
    durationSeconds: float = Field(
        default=200.0, ge=m.MIN_DURATION_S, le=m.MAX_DURATION_S
    )
    arrivalRate: float = Field(
        default=1.2, ge=0.05, le=2.0, description="vehicles per second, whole junction"
    )
    lanesPerApproach: int = Field(default=2, ge=1, le=3)
    approachLength: float = Field(default=200.0, ge=100, le=500)
    speedLimit: float = Field(default=13.89, ge=5, le=25)
    greenSeconds: float = Field(default=30.0, ge=10, le=90)
    yellowSeconds: float = Field(default=4.0, ge=2, le=8)
    allRedSeconds: float = Field(default=2.0, ge=0, le=8)
    timeStep: float = Field(default=0.1, ge=m.MIN_TIME_STEP_S, le=m.MAX_TIME_STEP_S)
    carOccupancy: float = Field(default=1.3, ge=1, le=4)
    busOccupancy: float = Field(default=35.0, ge=5, le=150)

    def to_spec(self) -> ScenarioSpec:
        return ScenarioSpec(
            duration_s=self.durationSeconds,
            arrival_rate=self.arrivalRate,
            lanes_per_approach=self.lanesPerApproach,
            approach_length_m=self.approachLength,
            speed_limit_mps=self.speedLimit,
            green_s=self.greenSeconds,
            yellow_s=self.yellowSeconds,
            all_red_s=self.allRedSeconds,
            time_step_s=self.timeStep,
            car_occupancy=self.carOccupancy,
            bus_occupancy=self.busOccupancy,
        )


class EmergencyIn(BaseModel):
    kind: Literal["ambulance", "fire_truck"] = "ambulance"
    approach: Approach = "north"
    turn: Turn = "straight"
    timeSeconds: float = Field(default=100.0, ge=0, le=m.MAX_DURATION_S)
    lane: Optional[int] = Field(default=None, ge=0, le=5)


class PreemptionIn(BaseModel):
    detectionDistance: Optional[float] = Field(default=150.0, ge=20, le=1000)
    detectionTime: Optional[float] = Field(default=12.0, ge=1, le=60)
    minGreenSeconds: float = Field(default=7.0, ge=1, le=30)
    maxHoldSeconds: float = Field(default=45.0, ge=5, le=120)
    minRecoverySeconds: float = Field(default=10.0, ge=0, le=120)

    def to_config(self) -> PreemptionConfig:
        return PreemptionConfig(
            enabled=True,
            detection_distance_m=self.detectionDistance,
            detection_time_s=self.detectionTime,
            min_green_s=self.minGreenSeconds,
            max_hold_s=self.maxHoldSeconds,
            min_recovery_s=self.minRecoverySeconds,
        )


class YieldIn(BaseModel):
    enabled: bool = True
    distance: float = Field(default=120.0, ge=10, le=400)
    headwayFactor: float = Field(default=0.6, ge=0.3, le=1.0)
    accelerationFactor: float = Field(default=1.3, ge=1.0, le=2.0)
    speedFloorFactor: float = Field(default=1.0, ge=0.5, le=1.2)

    def to_config(self) -> YieldConfig:
        return YieldConfig(
            enabled=self.enabled,
            distance_m=self.distance,
            headway_factor=self.headwayFactor,
            acceleration_factor=self.accelerationFactor,
            speed_floor_factor=self.speedFloorFactor,
        )


class _ComparisonBase(BaseModel):
    scenario: ScenarioIn = ScenarioIn()
    numSeeds: int = Field(default=4, ge=m.MIN_SEEDS, le=m.MAX_SEEDS)
    baseSeed: int = Field(default=1, ge=0, le=1_000_000)
    method: Method = "paired_t"
    confidence: float = Field(default=0.95, gt=0.5, lt=1.0)

    def seeds(self) -> List[int]:
        return list(range(self.baseSeed, self.baseSeed + self.numSeeds))


class EmergencyComparisonRequest(_ComparisonBase):
    emergencyVehicles: List[EmergencyIn] = Field(
        default_factory=lambda: [EmergencyIn()],
        min_length=1,
        max_length=m.MAX_EMERGENCY_VEHICLES,
    )
    preemption: PreemptionIn = PreemptionIn()
    yielding: YieldIn = YieldIn()


class TransitLineIn(BaseModel):
    lineId: str = Field(default="L1", min_length=1, max_length=24)
    approach: Approach = "north"
    turn: Turn = "straight"
    headwaySeconds: float = Field(default=90.0, ge=30, le=900)
    firstDepartureSeconds: float = Field(default=20.0, ge=0, le=m.MAX_DURATION_S)
    trips: int = Field(default=3, ge=1, le=m.MAX_TRANSIT_TRIPS_PER_LINE)
    dwellSeconds: float = Field(default=15.0, ge=0, le=60)
    stopPosition: Optional[float] = Field(default=None, ge=20, le=400)


class TransitPriorityIn(BaseModel):
    detectionDistance: float = Field(default=120.0, ge=20, le=400)
    latenessThreshold: float = Field(default=15.0, ge=0, le=300)
    schedulePadding: float = Field(default=10.0, ge=0, le=300)
    maxExtensionSeconds: float = Field(default=10.0, ge=0, le=20)
    maxEarlyGreenSeconds: float = Field(default=10.0, ge=0, le=20)
    minGreenSeconds: float = Field(default=7.0, ge=1, le=30)
    minSpacingSeconds: float = Field(default=30.0, ge=0, le=300)
    conditional: bool = True

    def to_config(self) -> TransitPriorityConfig:
        return TransitPriorityConfig(
            enabled=True,
            detection_distance_m=self.detectionDistance,
            lateness_threshold_s=self.latenessThreshold,
            schedule_padding_s=self.schedulePadding,
            max_extension_s=self.maxExtensionSeconds,
            max_early_green_s=self.maxEarlyGreenSeconds,
            min_green_s=self.minGreenSeconds,
            min_spacing_s=self.minSpacingSeconds,
            conditional=self.conditional,
        )


class TransitComparisonRequest(_ComparisonBase):
    lines: List[TransitLineIn] = Field(
        default_factory=lambda: [TransitLineIn()],
        min_length=1,
        max_length=m.MAX_TRANSIT_LINES,
    )
    priority: TransitPriorityIn = TransitPriorityIn()


@router.get("/catalogue")
def catalogue() -> Dict[str, Any]:
    """What can be configured: emergency kinds, defaults and every bound."""
    spec = ScenarioSpec()
    pre, yld, tsp = PreemptionConfig(), YieldConfig(), TransitPriorityConfig()
    return {
        "inModelOnly": True,
        "label": IN_MODEL_LABEL,
        "emergencyKinds": [k.describe() for k in EMERGENCY_KINDS.values()],
        "transitVehicle": {
            "type": "bus",
            "occupancyDefault": spec.bus_occupancy,
            "note": "headway, dwell at a stop before the junction, and a timetable "
            "(free-flow running time + dwell + padding) are modelled",
        },
        "approaches": list(m.APPROACHES),
        "turns": list(m.TURNS),
        "methods": list(METHODS),
        "defaults": {
            "scenario": {
                "durationSeconds": spec.duration_s,
                "arrivalRate": spec.arrival_rate,
                "lanesPerApproach": spec.lanes_per_approach,
                "approachLength": spec.approach_length_m,
                "speedLimit": spec.speed_limit_mps,
                "greenSeconds": spec.green_s,
                "yellowSeconds": spec.yellow_s,
                "allRedSeconds": spec.all_red_s,
                "timeStep": spec.time_step_s,
            },
            "preemption": {
                "detectionDistance": pre.detection_distance_m,
                "detectionTime": pre.detection_time_s,
                "minGreenSeconds": pre.min_green_s,
                "maxHoldSeconds": pre.max_hold_s,
                "minRecoverySeconds": pre.min_recovery_s,
            },
            "yielding": {
                "distance": yld.distance_m,
                "headwayFactor": yld.headway_factor,
                "accelerationFactor": yld.acceleration_factor,
                "speedFloorFactor": yld.speed_floor_factor,
            },
            "transitPriority": {
                "detectionDistance": tsp.detection_distance_m,
                "latenessThreshold": tsp.lateness_threshold_s,
                "schedulePadding": tsp.schedule_padding_s,
                "maxExtensionSeconds": tsp.max_extension_s,
                "maxEarlyGreenSeconds": tsp.max_early_green_s,
                "minGreenSeconds": tsp.min_green_s,
                "minSpacingSeconds": tsp.min_spacing_s,
                "conditional": tsp.conditional,
            },
        },
        "limits": {
            "durationSeconds": [m.MIN_DURATION_S, m.MAX_DURATION_S],
            "seeds": [m.MIN_SEEDS, m.MAX_SEEDS],
            "seedsTimesDurationSeconds": m.MAX_SEED_SECONDS,
            "emergencyVehicles": m.MAX_EMERGENCY_VEHICLES,
            "transitLines": m.MAX_TRANSIT_LINES,
            "tripsPerLine": m.MAX_TRANSIT_TRIPS_PER_LINE,
        },
        "assumptions": [
            "Single four-arm fixed-time signalised junction; pre-emption wraps the "
            "fixed-time plan (adaptive and roundabout controllers are not supported).",
            "Yielding is clearing, not pulling over: followers ahead of the emergency "
            "vehicle close up and move off promptly (the model has no shoulder).",
            "Delay is time lost against desired speed; person delay uses the stated occupancies.",
        ],
    }


def _bad_request(err: ValueError) -> HTTPException:
    return HTTPException(422, detail=[str(err)])


@router.post("/emergency-comparison")
def emergency_comparison(req: EmergencyComparisonRequest) -> Dict[str, Any]:
    """Run each seed with pre-emption on and off, same traffic and emergency
    schedule. Returns per-seed arrays for both arms and the paired comparison
    (interval, p-value, plain-words verdict) of vehicle and collateral delay."""
    try:
        spec = req.scenario.to_spec()
        emergencies = [
            EmergencySpec(e.kind, e.approach, e.turn, e.timeSeconds, e.lane)
            for e in req.emergencyVehicles
        ]
        for item in emergencies:
            item.validate(dict(EMERGENCY_KINDS), spec.duration_s)
        pre = req.preemption.to_config()
        pre.validate()
        yielding = req.yielding.to_config()
        yielding.validate()
        spec.validate()
        return run_emergency_comparison(
            spec,
            emergencies,
            pre,
            yielding,
            req.seeds(),
            method=req.method,
            confidence=req.confidence,
        )
    except ValueError as err:
        raise _bad_request(err)


@router.post("/transit-comparison")
def transit_comparison(req: TransitComparisonRequest) -> Dict[str, Any]:
    """Run each seed with conditional transit priority on and off, same
    traffic and timetable. Returns per-seed arrays for both arms and the paired
    comparison of bus lateness, bus delay, person delay and vehicle delay."""
    try:
        spec = req.scenario.to_spec()
        spec.validate()
        lines = [
            TransitLineSpec(
                line_id=ln.lineId,
                approach=ln.approach,
                turn=ln.turn,
                headway_s=ln.headwaySeconds,
                first_departure_s=ln.firstDepartureSeconds,
                count=ln.trips,
                dwell_s=ln.dwellSeconds,
                stop_position_m=ln.stopPosition,
            )
            for ln in req.lines
        ]
        for line in lines:
            line.validate(spec.duration_s)
        cfg = req.priority.to_config()
        cfg.validate()
        return run_transit_comparison(
            spec, lines, cfg, req.seeds(), method=req.method, confidence=req.confidence
        )
    except ValueError as err:
        raise _bad_request(err)
