from typing import List

from src.vehicles.vehicle import Vehicle


def calculate_average_wait_time(exited_vehicles: List[Vehicle]) -> float:
    """Calculates the mean cumulative wait time across all exited vehicles.

    Returns 0.0 if no vehicles have exited.
    """
    if not exited_vehicles:
        return 0.0

    total_wait = sum(v.wait_time for v in exited_vehicles)
    return total_wait / len(exited_vehicles)
