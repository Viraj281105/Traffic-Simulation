import pytest
from pydantic import ValidationError

from src.core.config_models import (
    ApproachItem,
    ControllerSection,
    DirectionalSplit,
    GeometrySection,
    IntersectionCenter,
    MetricsSection,
    MinMaxRange,
    RoadsSection,
    ScenarioConfiguration,
    SimulationSection,
    TrafficSection,
    TurnProbabilities,
    VehicleGenerationSection,
    VisualizationSection,
)


def test_config_models_full_instantiation() -> None:
    sim = SimulationSection(
        duration=100.0,
        timeStep=0.1,
        warmupTime=10.0,
        randomSeed=123,
        snapshotFrequency=5.0,
    )
    assert sim.duration == 100.0

    split = DirectionalSplit(north=0.25, south=0.25, east=0.25, west=0.25)
    turns = TurnProbabilities(left=0.2, straight=0.6, right=0.2)
    traffic = TrafficSection(
        totalVehicles=100,
        arrivalRate=1.5,
        arrivalDistribution="exponential",
        directionalSplit=split,
        turnProbabilities=turns,
    )
    assert traffic.totalVehicles == 100

    center = IntersectionCenter(x=10.0, y=20.0)
    geom = GeometrySection(intersectionType="signal", intersectionCenter=center)
    assert geom.intersectionType == "signal"

    approach = ApproachItem(direction="north", lanes=3, speedLimit=15.0)
    roads = RoadsSection(
        approachLength=250.0,
        laneWidth=3.5,
        lanesPerApproach=2,
        speedLimit=13.89,
        approaches=[approach],
    )
    assert roads.lanesPerApproach == 2

    veh_gen = VehicleGenerationSection(
        vehicleLength=MinMaxRange(min=4.0, max=5.0),
        vehicleWidth=MinMaxRange(min=1.8, max=2.2),
        desiredSpeed=MinMaxRange(min=10.0, max=15.0),
        maxAcceleration=2.5,
        comfortDeceleration=3.5,
        minimumGap=2.0,
        desiredTimeHeadway=1.5,
        idmDelta=4.0,
    )
    assert veh_gen.maxAcceleration == 2.5

    ctrl = ControllerSection(
        greenTime=25.0,
        yellowTime=3.0,
        allRedTime=1.0,
        innerRadius=12.0,
        outerRadius=24.0,
        circulatingLanes=2,
        criticalGap=3.5,
        followUpTime=2.0,
        entrySpeed=6.0,
        circulatingSpeed=9.0,
    )
    assert ctrl.greenTime == 25.0

    metrics = MetricsSection(
        enabled=["wait_time", "throughput"],
        updateFrequency=2.0,
        rollingWindowSize=30.0,
        waitSpeedThreshold=0.6,
        stopSpeedThreshold=0.2,
    )
    assert metrics.updateFrequency == 2.0

    vis = VisualizationSection(
        canvasWidth=1000,
        canvasHeight=1000,
        pixelsPerMeter=4.0,
        showVehicleIds=True,
        showQueueLengths=True,
        colorScheme="dark",
        trailLength=5,
    )
    assert vis.canvasWidth == 1000

    scenario = ScenarioConfiguration(
        simulation=sim,
        traffic=traffic,
        geometry=geom,
        roads=roads,
        vehicleGeneration=veh_gen,
        controller=ctrl,
        metrics=metrics,
        visualization=vis,
    )
    assert scenario.simulation.duration == 100.0


def test_config_models_validation_errors() -> None:
    with pytest.raises(ValidationError):
        SimulationSection(duration=0)  # ge=1

    with pytest.raises(ValidationError):
        DirectionalSplit(north=-0.1, south=0.5, east=0.5, west=0.1)

    with pytest.raises(ValidationError):
        RoadsSection(approachLength=10.0)  # gt=50
