from typing import List

from src.vehicles.vehicle import Vehicle


def calculate_throughput(exited_vehicles: List[Vehicle]) -> int:
    """Returns the total number of exited vehicles."""
    return len(exited_vehicles)


def calculate_throughput_rate(
    exited_vehicles: List[Vehicle], current_time: float, window_size: float = 60.0
) -> float:
    """Computes the rolling throughput rate in vehicles per minute over a sliding window."""
    if not exited_vehicles or current_time <= 0:
        return 0.0

    # Collect exit times of vehicles that exited within the sliding window
    start_window = max(0.0, current_time - window_size)
    window_count = 0

    for v in exited_vehicles:
        # Note: we assume exit_time is recorded on Vehicle when state becomes EXITED.
        # Let's verify if v has exit_time. In schema it has exitTime.
        # If exit_time is None or hasattr checks:
        exit_time = getattr(v, "exit_time", None)
        if exit_time is not None and start_window <= exit_time <= current_time:
            window_count += 1

    actual_window = min(current_time, window_size)
    return (window_count / actual_window) * 60.0
