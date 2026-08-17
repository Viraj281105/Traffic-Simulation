from src.core.enums import Direction
from src.metrics.definitions.fairness import calculate_directional_fairness
from src.metrics.definitions.idle_loss import calculate_idle_loss_tick
from src.metrics.definitions.queue_length import get_current_queue_lengths
from src.metrics.definitions.speed_variance import calculate_speed_variance_index
from src.metrics.definitions.stop_count import (
    update_vehicle_stops,
)
from src.metrics.definitions.throughput import (
    calculate_throughput,
    calculate_throughput_rate,
)
from src.metrics.definitions.travel_time import calculate_travel_time_reliability
from src.metrics.definitions.wait_time import calculate_average_wait_time
from src.vehicles.vehicle import Vehicle


class DummyLane:
    def __init__(self, lane_id: str) -> None:
        self.lane_id = lane_id


class DummyVehicle:
    def __init__(self, speed: float, wait_time: float, stop_count: int, spawn_time: float = 0.0, exit_time: float = None, route=None) -> None:
        self.vehicle_id = "test"
        self.speed = speed
        self.wait_time = wait_time
        self.stop_count = stop_count
        self.spawn_time = spawn_time
        self.exit_time = exit_time
        self.route = route
        self.lane = route[0] if route else None
        self.length = 4.5
        self.width = 2.0
        self.position = 10.0
        self.acceleration = 0.0
        self.heading = 0.0


def test_wait_time_calculator() -> None:
    v1 = DummyVehicle(0.0, 10.0, 2)
    v2 = DummyVehicle(0.0, 20.0, 3)
    assert calculate_average_wait_time([v1, v2]) == 15.0
    assert calculate_average_wait_time([]) == 0.0


def test_throughput_calculators() -> None:
    v1 = DummyVehicle(10.0, 0.0, 0, exit_time=15.0)
    v2 = DummyVehicle(10.0, 0.0, 0, exit_time=45.0)

    assert calculate_throughput([v1, v2]) == 2
    # Setting current_time=60.0 means the actual window is 60.0, rate = (2 / 60) * 60 = 2.0
    assert calculate_throughput_rate([v1, v2], current_time=60.0, window_size=60.0) == 2.0


def test_queue_length_calculator() -> None:
    lane_n = DummyLane("n_in_0")
    lane_s = DummyLane("s_in_0")
    v1 = DummyVehicle(0.05, 0.0, 0, route=[lane_n])
    v2 = DummyVehicle(10.0, 0.0, 0, route=[lane_s])

    queues = get_current_queue_lengths([v1, v2], wait_speed_threshold=0.5)
    assert queues["north"] == 1
    assert queues["south"] == 0


def test_stop_count_hysteresis() -> None:
    class MockVehicle(Vehicle):
        def __init__(self):
            self.vehicle_id = "veh_test"
            self.speed = 10.0
            self.stop_count = 0
            self.length = 4.5

    v = MockVehicle()
    # Initialize the state (speed = 10.0 -> False stopped)
    update_vehicle_stops(v, 0.1)
    assert v._hysteresis_stopped is False
    assert v.stop_count == 0

    # Speed drops below 0.1 -> Stop
    v.speed = 0.05
    update_vehicle_stops(v, 0.1)
    assert v.stop_count == 1
    assert v._hysteresis_stopped is True

    # Speed goes slightly up but below 0.2 -> remains stopped
    v.speed = 0.15
    update_vehicle_stops(v, 0.1)
    assert v.stop_count == 1
    assert v._hysteresis_stopped is True

    # Speed goes above 2 * 0.1 -> unstopped
    v.speed = 0.25
    update_vehicle_stops(v, 0.1)
    assert v._hysteresis_stopped is False

    # Speed drops below 0.1 again -> Stop 2
    v.speed = 0.02
    update_vehicle_stops(v, 0.1)
    assert v.stop_count == 2


def test_speed_variance() -> None:
    v1 = DummyVehicle(10.0, 0.0, 0)
    v2 = DummyVehicle(12.0, 0.0, 0)
    assert calculate_speed_variance_index([v1, v2]) > 0.0
    assert calculate_speed_variance_index([v1]) == 1.0


def test_travel_time_reliability() -> None:
    v1 = DummyVehicle(10.0, 0.0, 0, spawn_time=0.0, exit_time=10.0)
    v2 = DummyVehicle(10.0, 0.0, 0, spawn_time=0.0, exit_time=20.0)
    assert calculate_travel_time_reliability([v1, v2]) > 1.0


def test_idle_loss() -> None:
    lane_n = DummyLane("n_in_0")
    # v1 is waiting on North (RED)
    v1 = DummyVehicle(0.05, 0.0, 0, route=[lane_n])
    # South is GREEN but has no vehicles
    signals = {Direction.NORTH: "red", Direction.SOUTH: "green", Direction.EAST: "red", Direction.WEST: "red"}

    assert calculate_idle_loss_tick([v1], signals, wait_speed_threshold=0.5) is True


def test_directional_fairness() -> None:
    lane_n = DummyLane("n_in_0")
    v1 = DummyVehicle(0.0, 10.0, 0, route=[lane_n])
    assert 0.0 < calculate_directional_fairness([v1]) <= 1.0
