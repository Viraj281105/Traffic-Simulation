import pytest

from src.metrics.definitions.new_metrics import (
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
    assert calculate_space_footprint_consumed(config_roundabout) == pytest.approx(1256.64, abs=1e-2)

    # Signal footprint: lanes = 2, laneWidth = 3.5 -> width = 14 -> Area = 14 * 14 = 196.0
    config_signal = {
        "geometry": {"intersectionType": "fixed_time_signal"},
        "roads": {"lanesPerApproach": 2, "laneWidth": 3.5},
    }
    assert calculate_space_footprint_consumed(config_signal) == 196.0
