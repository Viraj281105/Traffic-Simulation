from typing import Dict, List

from src.vehicles.vehicle import Vehicle


def calculate_average_travel_speed(active_vehicles: List[Vehicle]) -> float:
    """Calculates average travel speed (ATS) of all active vehicles."""
    if not active_vehicles:
        return 0.0
    return sum(v.speed for v in active_vehicles) / len(active_vehicles)


def calculate_queue_spillback_index(
    active_vehicles: List[Vehicle],
    wait_speed_threshold: float,
    lane_lengths: Dict[str, float],
) -> float:
    """Calculates max Queue Spillback Index (QSI) across all lanes.

    QSI = (queued_vehicles_count * 7.5) / lane_length
    """
    if not active_vehicles or not lane_lengths:
        return 0.0

    # Count queued vehicles per lane
    queued_counts: Dict[str, int] = {}
    for v in active_vehicles:
        if v.lane_id and v.speed < wait_speed_threshold:
            queued_counts[v.lane_id] = queued_counts.get(v.lane_id, 0) + 1

    max_qsi = 0.0
    for lane_id, count in queued_counts.items():
        lane_len = lane_lengths.get(lane_id, 100.0)  # default 100m if not found
        qsi = (count * 7.5) / lane_len
        if qsi > max_qsi:
            max_qsi = qsi

    return min(1.0, max_qsi)  # Cap at 1.0 (100% spillback)


def calculate_space_footprint_area(active_vehicles: List[Vehicle]) -> float:
    """Calculates total space footprint area (length * width) of all active vehicles."""
    return sum(v.length * v.width for v in active_vehicles)
