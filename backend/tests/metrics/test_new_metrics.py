import pytest

from src.metrics.definitions.derived_metrics import (
    calculate_average_travel_speed,
    calculate_queue_stability_index,
    calculate_space_footprint_consumed,
)
from src.roads.lane import Lane
from src.vehicles.vehicle import Vehicle


@pytest.fixture
def mock_vehicles() -> list[Vehicle]:
    lane_1 = Lane("lane_1", 0.0, 0.0, 0.0, 100.0)
    v1 = Vehicle(
        "v1",
        length=4.0,
        width=2.0,
        desired_speed=10.0,
        route=[lane_1],
        initial_speed=8.0,
    )
    v2 = Vehicle(
        "v2",
        length=5.0,
        width=2.0,
        desired_speed=10.0,
        route=[lane_1],
        initial_speed=0.0,
    )
    return [v1, v2]


def test_calculate_average_travel_speed(mock_vehicles: list[Vehicle]) -> None:
    # speeds: 8.0 and 0.0 -> average should be 4.0
    ats = calculate_average_travel_speed(mock_vehicles)
    assert ats == 4.0

    assert calculate_average_travel_speed([]) == 0.0


def test_calculate_queue_stability_index() -> None:
    # queue lengths over history: [2, 4, 3] -> mean = 3
    # values: [2, 4, 3], variance = ((2-3)^2 + (4-3)^2 + (3-3)^2) / 2 = (1 + 1 + 0) / 2 = 1.0 -> SD = 1.0
    # QSI = SD / mean = 1.0 / 3 = 0.333
    q_history = [
        {"north": 1, "south": 1},
        {"north": 2, "south": 2},
        {"north": 1, "south": 2},
    ]
    qsi = calculate_queue_stability_index(q_history)
    assert qsi == pytest.approx(0.333, abs=1e-3)

    assert calculate_queue_stability_index([]) == 0.0


def test_calculate_space_footprint_consumed() -> None:
    # Roundabout footprint: outerRadius = 20 -> Area = pi * 20^2 = 1256.64
    config_roundabout = {
        "geometry": {"intersectionType": "roundabout"},
        "controller": {"outerRadius": 20.0},
    }
    assert calculate_space_footprint_consumed(config_roundabout) == pytest.approx(
        1256.64, abs=1e-2
    )

    # Signal footprint: lanes = 2, laneWidth = 3.5 -> width = 14 -> Area = 14 * 14 = 196.0
    config_signal = {
        "geometry": {"intersectionType": "fixed_time_signal"},
        "roads": {"lanesPerApproach": 2, "laneWidth": 3.5},
    }
    assert calculate_space_footprint_consumed(config_signal) == 196.0

    # Signal footprint with dict lanes:
    config_dict_lanes = {
        "geometry": {"intersectionType": "fixed_time_signal"},
        "roads": {"lanesPerApproach": {"north": 3, "south": 2}, "laneWidth": 3.0},
    }
    assert calculate_space_footprint_consumed(config_dict_lanes) == 324.0

    # QSI with 1 entry and 0 entry
    assert calculate_queue_stability_index([{"north": 1}]) == 0.0
    assert calculate_queue_stability_index([{"north": 0}, {"north": 0}]) == 0.0


def test_speed_thresholds_are_read_from_metrics_section() -> None:
    """Regression: the contract/schema/typed model put waitSpeedThreshold and
    stopSpeedThreshold under ``metrics``, but the collector and spawner only
    read ``vehicleGeneration`` — so a contract-conformant value was ignored."""
    from src.core.config_models import ScenarioConfiguration
    from src.metrics.collector import MetricCollector
    from src.roads.network import RoadNetwork
    from src.vehicles.spawner import VehicleSpawner

    config = ScenarioConfiguration(
        simulation={"duration": 60, "randomSeed": 1},
        geometry={"intersectionType": "fixed_time_signal"},
        metrics={"waitSpeedThreshold": 2.0, "stopSpeedThreshold": 1.0},
    ).model_dump(exclude_none=True)
    collector = MetricCollector(config)
    assert collector.wait_speed_threshold == 2.0
    assert collector.stop_speed_threshold == 1.0

    network = RoadNetwork()
    network.setup_default_intersection(200.0, 3.5, 1)
    assert VehicleSpawner(config, network).wait_speed_threshold == 2.0


def test_speed_thresholds_legacy_vehicle_generation_location_still_works() -> None:
    from src.metrics.collector import MetricCollector

    collector = MetricCollector(
        {"vehicleGeneration": {"waitSpeedThreshold": 0.7, "stopSpeedThreshold": 0.2}}
    )
    assert collector.wait_speed_threshold == 0.7
    assert collector.stop_speed_threshold == 0.2
    # metrics wins when both are given
    both = MetricCollector(
        {
            "metrics": {"waitSpeedThreshold": 1.1},
            "vehicleGeneration": {"waitSpeedThreshold": 0.7},
        }
    )
    assert both.wait_speed_threshold == 1.1


class _NoIterList(list):  # type: ignore[type-arg]
    def __iter__(self):  # type: ignore[no-untyped-def]
        raise AssertionError("get_metrics() rescanned the whole queue history")


def test_queue_statistics_match_history_without_rescanning_it() -> None:
    """Regression: get_metrics() rebuilt every queue statistic by scanning the
    full per-tick queue history, and SnapshotBuilder calls it every tick, so a
    run's per-tick cost grew linearly with elapsed time. The statistics now
    come from running aggregates — they must equal the rescanned values, and
    must not touch the history at all."""
    import math

    from src.controllers.factory import build_tick_callback, create_controller
    from src.core.clock import Clock
    from src.core.engine import SimulationEngine
    from src.metrics.collector import MetricCollector
    from src.metrics.definitions.derived_metrics import (
        calculate_queue_stability_index,
    )

    config = {
        "simulation": {
            "duration": 120,
            "timeStep": 0.1,
            "randomSeed": 5,
            "warmupTime": 5,
        },
        "geometry": {"intersectionType": "fixed_time_signal"},
        "roads": {"lanesPerApproach": 1},
        "traffic": {"arrivalRate": 0.6},
    }
    clock = Clock(0.1)
    engine = SimulationEngine(clock, 120, config)
    controller = create_controller(config, engine.network)
    engine.controller = controller
    collector = MetricCollector(config)
    engine.register_tick_callback(
        build_tick_callback(controller, clock, engine, collector)
    )
    while engine.status.value.lower() != "completed":
        engine.step()

    history = list(collector.queue_history)
    totals = [sum(q.values()) for q in history]
    nonzero = [t for t in totals if t > 0]
    mean_t = sum(totals) / len(totals)
    expected = {
        "maxQueueLength": max(max(q.values()) for q in history),
        "averageQueueLength": round(
            sum(sum(q[d] for q in history) / len(history) for d in history[0]) / 4, 2
        ),
        "activeAverageQueueLength": round(sum(nonzero) / len(nonzero), 2),
        "queueStdDev": round(
            math.sqrt(sum((t - mean_t) ** 2 for t in totals) / (len(totals) - 1)), 2
        ),
        "queueStabilityIndex": calculate_queue_stability_index(history),
    }
    assert expected["maxQueueLength"] > 0  # the scenario really queues

    collector.queue_history = _NoIterList(history)
    metrics = collector.get_metrics(
        clock.get_elapsed_time(),
        engine.pool.active_vehicles,
        engine.pool.exited_vehicles,
        engine.spawner.spawned_count if engine.spawner else 0,
    )
    for key, value in expected.items():
        assert metrics[key] == value, (key, metrics[key], value)
