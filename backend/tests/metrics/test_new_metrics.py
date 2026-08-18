import pytest

from src.metrics.definitions.new_metrics import (
    calculate_average_travel_speed,
    calculate_queue_spillback_index,
    calculate_space_footprint_area,
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


def test_calculate_queue_spillback_index(mock_vehicles: list[Vehicle]) -> None:
    # v2 is queued (speed 0.0 < 0.5 threshold) on lane_1 (length 100.0)
    # QSI: (1 * 7.5) / 100.0 = 0.075
    lane_lengths = {"lane_1": 100.0}
    qsi = calculate_queue_spillback_index(mock_vehicles, 0.5, lane_lengths)
    assert pytest.approx(qsi) == 0.075

    assert calculate_queue_spillback_index([], 0.5, {}) == 0.0


def test_calculate_space_footprint_area(mock_vehicles: list[Vehicle]) -> None:
    # areas: (4 * 2) + (5 * 2) = 8 + 10 = 18.0
    area = calculate_space_footprint_area(mock_vehicles)
    assert area == 18.0

    assert calculate_space_footprint_area([]) == 0.0
