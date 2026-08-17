import math
from typing import List

from src.vehicles.vehicle import Vehicle


def calculate_speed_variance_index(active_vehicles: List[Vehicle]) -> float:
    """Computes the Coefficient of Variation (CV) of speed for active vehicles.

    If variance is zero (or empty/one vehicle), returns 1.0.
    """
    if not active_vehicles:
        return 1.0

    speeds = [v.speed for v in active_vehicles]
    n = len(speeds)
    if n <= 1:
        return 1.0

    mean_speed = sum(speeds) / n
    if mean_speed <= 0:
        return 1.0

    variance = sum((s - mean_speed) ** 2 for s in speeds) / (n - 1)
    if variance <= 0:
        return 1.0

    std_dev = math.sqrt(variance)
    return std_dev / mean_speed
