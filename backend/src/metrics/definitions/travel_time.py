import math
from typing import List

from src.vehicles.vehicle import Vehicle


def _calculate_median(lst: List[float]) -> float:
    if not lst:
        return 0.0
    s = sorted(lst)
    n = len(s)
    if n % 2 == 1:
        return s[n // 2]
    else:
        return (s[n // 2 - 1] + s[n // 2]) / 2.0


def _calculate_percentile(lst: List[float], p: float) -> float:
    if not lst:
        return 0.0
    s = sorted(lst)
    k = (len(s) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return s[int(k)]
    d0 = s[int(f)] * (c - k)
    d1 = s[int(c)] * (k - f)
    return d0 + d1


def calculate_travel_time_reliability(exited_vehicles: List[Vehicle]) -> float:
    """Computes the Planning Time Index (PTI) for exited vehicles in pure Python.

    PTI = 95th percentile travel time / median (50th percentile) travel time.
    If no exited vehicles or zero/no variance, returns 1.0.
    """
    if not exited_vehicles:
        return 1.0

    travel_times = []
    for v in exited_vehicles:
        spawn = getattr(v, "spawn_time", 0.0)
        exit_t = getattr(v, "exit_time", None)
        if exit_t is not None:
            travel_times.append(max(0.0, exit_t - spawn))

    if not travel_times:
        return 1.0

    median_t = _calculate_median(travel_times)
    if median_t <= 0:
        return 1.0

    p95_t = _calculate_percentile(travel_times, 95.0)
    return p95_t / median_t
