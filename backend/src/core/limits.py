"""Shared run limits.

DEFAULT_TOTAL_VEHICLES is the spawner's cap on vehicles generated per run
(``traffic.totalVehicles``). Once reached, no more vehicles are created for
the rest of the run, so at high demand x long duration the demand actually
offered is truncated. The metric collector reports the limit and whether it
was reached (``vehicleLimit`` / ``vehicleLimitReached``) so no evaluation
built on such a run can silently read truncated demand as full demand.
"""

import math

DEFAULT_TOTAL_VEHICLES: int = 200

# ``traffic.totalVehicles`` is schema-capped at 5000 (core/config_models.py).
MAX_TOTAL_VEHICLES: int = 5000

# Headroom over the expected number of arrivals when deriving a limit from a
# scenario, so ordinary Poisson variation never reaches it.
DEMAND_LIMIT_HEADROOM: float = 1.5
DEMAND_LIMIT_MARGIN: int = 50


def demand_vehicle_limit(arrival_rate: float, duration: float) -> int:
    """A vehicle limit that will not truncate the demand a scenario asks for.

    The bare default (200) silently cut off demand for high-rate x long-run
    scenarios (for example 2 lanes, 0.8 veh/s, 300 s), so the app's own
    scenario builders (the dashboard compiler and the study runners) size the
    limit from the scenario: expected arrivals x 1.5 + 50, never below the
    default and never above the schema maximum. A run whose demand is so high
    that even that maximum is reached is flagged by the collector
    (``vehicleLimitReached``), never silently truncated.

    Memory/CPU: vehicles are small objects and the pool keeps exited ones, so
    the cost is linear in vehicles generated; at the 5000 maximum that is the
    same order the published calibrated baseline already runs at.
    """
    expected = max(0.0, arrival_rate) * max(0.0, duration)
    derived = math.ceil(expected * DEMAND_LIMIT_HEADROOM) + DEMAND_LIMIT_MARGIN
    return int(min(MAX_TOTAL_VEHICLES, max(DEFAULT_TOTAL_VEHICLES, derived)))
