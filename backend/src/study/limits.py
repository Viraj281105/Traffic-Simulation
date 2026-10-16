"""Bounds on study workloads requested over HTTP.

The study endpoints run whole simulations, and their cost is the product of
their parameters: a sweep runs two simulations (signal and roundabout) per
arrival rate, and Monte Carlo validation runs one per seed. Unbounded, a
single request could pin a worker for hours, which on an open demo
deployment is a denial of service with no exploit required.

The caps are set well above every legitimate use: the default sweep uses 8
arrival rates at 60 s, and the documented study workflows stay inside these
limits.
"""

from typing import Annotated, Any, Dict, Optional

from pydantic import Field

# The longest simulated duration any study or scenario may ask for; it matches
# SimulationSection.duration's own ceiling.
MAX_STUDY_DURATION_SECONDS = 3600.0
MIN_STUDY_DURATION_SECONDS = 1.0

MAX_SWEEP_ARRIVAL_RATES = 20
MAX_MONTE_CARLO_SEEDS = 30

# Each swept arrival rate is bounded by the same range the scenario config
# already enforces for traffic.arrivalRate, so a sweep cannot ask for a
# workload the simulator would reject if configured directly.
StudyArrivalRate = Annotated[float, Field(gt=0, le=10.0)]

# Study runs honour customConfig.simulation.timeStep (the dashboards offer
# 0.05 / 0.1 / 0.2 s). Cost scales with 1/timeStep, so it is bounded like
# every other workload parameter: the floor is the finest step the dashboards
# offer, the ceiling the scenario schema's own maximum.
MIN_STUDY_TIME_STEP_SECONDS = 0.05
MAX_STUDY_TIME_STEP_SECONDS = 1.0

# Signal control comparison (V1.3): fixed-time signal vs adaptive signal vs
# roundabout over demand levels and seeds. At most 6 levels x 10 seeds x 3
# controls of at most 15 simulated minutes each.
MAX_CONTROL_COMPARISON_SEEDS = 10
MAX_CONTROL_COMPARISON_DURATION_SECONDS = 900.0

# A suite batch runs len(arrivalRate) x numSeeds simulations of one geometry:
# capped at the Monte Carlo study's largest workload (MAX_MONTE_CARLO_SEEDS
# seeds x two geometries). The dashboard's batch runs 5 rates x 3 seeds.
MAX_BATCH_SIMULATIONS = 2 * MAX_MONTE_CARLO_SEEDS


def check_study_time_step(custom_config: Optional[Dict[str, Any]]) -> None:
    """Raises ValueError when a configuration's simulation.timeStep is set
    and outside the study bounds."""
    sim = (custom_config or {}).get("simulation")
    if not isinstance(sim, dict) or "timeStep" not in sim:
        return
    step = sim["timeStep"]
    if (
        not isinstance(step, (int, float))
        or isinstance(step, bool)
        or not (MIN_STUDY_TIME_STEP_SECONDS <= step <= MAX_STUDY_TIME_STEP_SECONDS)
    ):
        raise ValueError(
            "customConfig.simulation.timeStep must be a number between "
            f"{MIN_STUDY_TIME_STEP_SECONDS} and {MAX_STUDY_TIME_STEP_SECONDS} s"
        )
