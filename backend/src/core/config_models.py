from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class SimulationSection(BaseModel):
    duration: float = Field(..., ge=1, le=3600)
    timeStep: float = Field(0.1, gt=0, le=1.0)
    warmupTime: float = Field(30.0, ge=0)
    randomSeed: Optional[int] = Field(None, ge=0)
    snapshotFrequency: float = Field(10.0, gt=0, le=60)


class DirectionalSplit(BaseModel):
    north: float = Field(..., ge=0, le=1)
    south: float = Field(..., ge=0, le=1)
    east: float = Field(..., ge=0, le=1)
    west: float = Field(..., ge=0, le=1)


class TurnProbabilities(BaseModel):
    left: float = Field(..., ge=0, le=1)
    straight: float = Field(..., ge=0, le=1)
    right: float = Field(..., ge=0, le=1)


class TrafficSection(BaseModel):
    totalVehicles: int = Field(200, gt=0, le=5000)
    arrivalRate: float = Field(0.5, gt=0, le=10.0)
    arrivalDistribution: str = Field("poisson")
    directionalSplit: Optional[DirectionalSplit] = None
    turnProbabilities: Optional[TurnProbabilities] = None


class IntersectionCenter(BaseModel):
    x: float = Field(0.0)
    y: float = Field(0.0)


class GeometrySection(BaseModel):
    intersectionType: str
    intersectionCenter: Optional[IntersectionCenter] = None


class ApproachItem(BaseModel):
    direction: str
    lanes: Optional[int] = Field(None, ge=1, le=4)
    speedLimit: Optional[float] = Field(None, gt=0)


class LaneChangeSection(BaseModel):
    """Lane changing on multi-lane approaches (V1.2), see vehicles/lane_change.py."""

    enabled: bool = Field(True)
    accelerationThreshold: float = Field(0.2, ge=0, le=2.0)
    safeDeceleration: float = Field(4.0, gt=0, le=9.0)
    # Overrides every vehicle class's own politeness when set.
    politeness: Optional[float] = Field(None, ge=0, le=1)


class RoadsSection(BaseModel):
    approachLength: float = Field(200.0, gt=50, le=1000)
    laneWidth: float = Field(3.5, gt=2.5, le=5.0)
    lanesPerApproach: int = Field(2, ge=1, le=4)
    speedLimit: float = Field(13.89, gt=0, le=30.0)
    # approaches[].lanes overrides lanesPerApproach for that approach (V1.2);
    # approaches[].speedLimit is still reserved (accepted, not read).
    approaches: Optional[List[ApproachItem]] = None
    laneChange: Optional[LaneChangeSection] = None


class MinMaxRange(BaseModel):
    min: float = Field(..., gt=0)
    max: float = Field(..., gt=0)


class VehicleMixSection(BaseModel):
    """Share of arrivals per vehicle class (V1.1); see vehicles/vehicle_types.py.
    Must sum to 1 (config_validation). Omitted classes have no share."""

    car: Optional[float] = Field(None, ge=0, le=1)
    suv: Optional[float] = Field(None, ge=0, le=1)
    bus: Optional[float] = Field(None, ge=0, le=1)
    truck: Optional[float] = Field(None, ge=0, le=1)
    motorcycle: Optional[float] = Field(None, ge=0, le=1)


class VehicleTypeOverrides(BaseModel):
    """Overrides of one vehicle class's default parameters (research use)."""

    length: Optional[MinMaxRange] = None
    width: Optional[MinMaxRange] = None
    desiredSpeedFactor: Optional[MinMaxRange] = None
    maxAcceleration: Optional[float] = Field(None, gt=0)
    comfortDeceleration: Optional[float] = Field(None, gt=0)
    desiredTimeHeadway: Optional[float] = Field(None, gt=0)
    minimumGap: Optional[float] = Field(None, gt=0)
    idmDelta: Optional[float] = Field(None, gt=0)
    maxLateralAcceleration: Optional[float] = Field(None, gt=0, le=8.0)
    laneChangeDuration: Optional[float] = Field(None, gt=0, le=15.0)
    laneChangeMinDistance: Optional[float] = Field(None, gt=0, le=100.0)
    politeness: Optional[float] = Field(None, ge=0, le=1)


class VehicleTypesSection(BaseModel):
    car: Optional[VehicleTypeOverrides] = None
    suv: Optional[VehicleTypeOverrides] = None
    bus: Optional[VehicleTypeOverrides] = None
    truck: Optional[VehicleTypeOverrides] = None
    motorcycle: Optional[VehicleTypeOverrides] = None


class VehicleGenerationSection(BaseModel):
    vehicleLength: Optional[MinMaxRange] = None
    vehicleWidth: Optional[MinMaxRange] = None
    desiredSpeed: Optional[MinMaxRange] = None
    maxAcceleration: float = Field(2.0, gt=0)
    comfortDeceleration: float = Field(3.0, gt=0)
    minimumGap: float = Field(2.0, gt=0)
    desiredTimeHeadway: float = Field(1.5, gt=0)
    idmDelta: float = Field(4.0, gt=0)
    # Lateral-acceleration limit applied to every curved path, at the signal
    # and the roundabout alike (src/vehicles/speed_profile.py). Unset means
    # the model default (3.0 m/s^2).
    maxLateralAcceleration: Optional[float] = Field(None, gt=0, le=8.0)
    # Mixed vehicle classes (V1.1). Unset: the V1.0 single-car population.
    vehicleMix: Optional[VehicleMixSection] = None
    vehicleTypes: Optional[VehicleTypesSection] = None


# The canonical paired NS/EW signal plan (ControllerSection.phaseSequence's
# default), shared with code that needs it without building a model.
DEFAULT_PHASE_SEQUENCE: List[str] = [
    "ns_green",
    "ns_yellow",
    "all_red",
    "ew_green",
    "ew_yellow",
    "all_red",
]


class AdaptiveSignalSection(BaseModel):
    """Adaptive (vehicle-actuated) signal settings (V1.3), see
    controllers/adaptive_signal.py. Cross-field rules live in
    config_validation (maxGreen > minGreen and the rest)."""

    minGreen: float = Field(10.0, ge=5, le=60)
    maxGreen: float = Field(50.0, ge=10, le=180)
    extensionStep: float = Field(2.5, ge=0.5, le=10)
    detectionDistance: float = Field(30.0, ge=5, le=200)
    demandThreshold: int = Field(1, ge=1, le=20)


class ControllerSection(BaseModel):
    greenTime: float = Field(30.0, gt=5, le=120)
    leftDuration: float = Field(5.0, gt=0, le=60)
    yellowTime: float = Field(4.0, gt=2, le=8)
    allRedTime: float = Field(2.0, ge=0, le=5)
    # Canonical aliases used internally by FixedTimeSignalController (see
    # its __init__) and by the legacy live-dashboard config path
    # (backend/src/main.py DEFAULT_CONFIG / update_simulation_config).
    # Optional and unset by default so a config that only sets greenTime/
    # yellowTime/allRedTime behaves exactly as before; when one of these
    # IS provided, ScenarioConfiguration.model_dump(exclude_none=True)
    # (see create_simulation_v2 in main.py) keeps it in the dict passed to
    # the controller, instead of silently dropping it the way an
    # undeclared Pydantic field previously would have. See
    # FixedTimeSignalController.__init__ for the exact precedence between
    # a canonical field and its *Time/*Duration alias when both are set.
    straightRightDuration: Optional[float] = Field(None, gt=5, le=120)
    greenDuration: Optional[float] = Field(None, gt=5, le=120)
    yellowDuration: Optional[float] = Field(None, gt=2, le=8)
    allRedDuration: Optional[float] = Field(None, ge=0, le=5)
    # Optional per-corridor green overrides (asymmetric NS/EW timing). Same
    # bounds as straightRightDuration, which they override when set. Both
    # default to None (unset): a config that omits them keeps using
    # straightRightDuration for every direction, exactly as before these
    # fields existed. See FixedTimeSignalController._green_duration_for.
    nsGreenDuration: Optional[float] = Field(None, gt=5, le=120)
    ewGreenDuration: Optional[float] = Field(None, gt=5, le=120)
    phaseSequence: List[str] = Field(
        default_factory=lambda: list(DEFAULT_PHASE_SEQUENCE)
    )
    offset: float = Field(0.0, ge=0)
    innerRadius: float = Field(10.0, gt=5, le=50)
    outerRadius: float = Field(20.0, gt=5)
    circulatingLanes: int = Field(1, ge=1, le=3)
    criticalGap: float = Field(4.0, gt=0, le=10.0)
    followUpTime: float = Field(2.5, gt=0)
    entrySpeed: float = Field(5.0, gt=0)
    circulatingSpeed: float = Field(8.0, gt=0, le=15.0)
    # V1.3: how a signal times its greens. Unset means fixed-time, so a
    # config that never mentions it dumps (and runs) exactly as before.
    signalControl: Optional[Literal["fixed_time", "adaptive"]] = None
    adaptive: Optional[AdaptiveSignalSection] = None


class MetricsSection(BaseModel):
    enabled: Optional[List[str]] = None
    updateFrequency: float = Field(1.0, gt=0)
    rollingWindowSize: float = Field(60.0, gt=0)
    waitSpeedThreshold: float = Field(0.5, ge=0)
    stopSpeedThreshold: float = Field(0.1, ge=0)
    # TTC/PET thresholds (see metrics/definitions/safety_conflicts.py).
    # Only affect which observed values are counted as "events" for
    # reporting -- never simulation behaviour. Defaults are commonly-cited
    # literature values (TTC: Hayward 1972 and widely reused since; PET:
    # common SSAM-style conflict-study default), not values this project
    # has validated itself.
    ttcThresholdSeconds: float = Field(1.5, gt=0)
    petThresholdSeconds: float = Field(5.0, gt=0)
    ttcSearchRadius: float = Field(50.0, gt=0)


class VisualizationSection(BaseModel):
    canvasWidth: int = Field(800, gt=400)
    canvasHeight: int = Field(800, gt=400)
    pixelsPerMeter: float = Field(3.0, gt=0)
    showVehicleIds: bool = Field(False)
    showQueueLengths: bool = Field(True)
    colorScheme: str = Field("default")
    trailLength: int = Field(0, ge=0)


class ScenarioConfiguration(BaseModel):
    simulation: SimulationSection
    traffic: Optional[TrafficSection] = None
    geometry: GeometrySection
    roads: Optional[RoadsSection] = None
    vehicleGeneration: Optional[VehicleGenerationSection] = None
    controller: Optional[ControllerSection] = None
    metrics: Optional[MetricsSection] = None
    visualization: Optional[VisualizationSection] = None
