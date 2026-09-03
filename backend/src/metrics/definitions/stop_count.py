from typing import List

from src.vehicles.vehicle import Vehicle


def update_vehicle_stops(vehicle: Vehicle, stop_speed_threshold: float = 0.1) -> None:
    """Updates the stop count on a vehicle using speed hysteresis to prevent oscillation counting.

    - A stop is detected when speed drops below stop_speed_threshold.
    - Hysteresis: speed must exceed 2 * stop_speed_threshold before another stop can be counted.
    """
    if vehicle._hysteresis_stopped:
        # If currently marked as stopped, check if speed has recovered above 2 * threshold
        if vehicle.speed >= 2 * stop_speed_threshold:
            vehicle._hysteresis_stopped = False
    else:
        # If currently marked as moving, check if speed has dropped below threshold
        if vehicle.speed < stop_speed_threshold:
            vehicle._hysteresis_stopped = True
            vehicle.stop_count += 1


def calculate_average_stops(exited_vehicles: List[Vehicle]) -> float:
    """Computes the average number of stops per exited vehicle."""
    if not exited_vehicles:
        return 0.0

    total_stops = sum(v.stop_count for v in exited_vehicles)
    return total_stops / len(exited_vehicles)
