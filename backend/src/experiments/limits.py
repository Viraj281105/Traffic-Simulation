"""Quotas and limits of ``/api/v3/experiments`` (W1 base; personal-access-token quotas arrive in W7).

All values are **proposals**: they bound what one user can ask of a shared server and are reported by
``GET /api/v3/capabilities`` so a client can show them. The simulated-time figure is derived from one
measurement on a development machine (about 12-17 s of wall time per 240 s simulation on one process) and
is *unverified* elsewhere.
"""

from __future__ import annotations

# Experiments running or queued at once. Each fills the shared worker pool, so more would only queue.
MAX_ACTIVE_EXPERIMENTS = 2
MAX_ACTIVE_EXPERIMENTS_PER_USER = 1

# Experiments one user may keep (finished or failed ones are deleted by the owner).
MAX_STORED_EXPERIMENTS_PER_USER = 50

# Size of one experiment.
MAX_ALTERNATIVES = 6
MAX_RUNS_PER_EXPERIMENT = 2000  # conditions x alternatives x replications
MAX_SIMULATED_SECONDS_PER_EXPERIMENT = 250_000.0  # total runs x scenario duration

# Listing page size.
DEFAULT_PAGE_SIZE = 25

QUOTA_NAMES = {
    "activeExperiments": "maxActiveExperiments",
    "activeExperimentsPerUser": "maxActiveExperimentsPerUser",
    "storedExperimentsPerUser": "maxStoredExperimentsPerUser",
    "alternatives": "maxAlternatives",
    "runsPerExperiment": "maxRunsPerExperiment",
    "simulatedSecondsPerExperiment": "maxSimulatedSecondsPerExperiment",
}


def quotas() -> dict[str, float | int]:
    return {
        "maxActiveExperiments": MAX_ACTIVE_EXPERIMENTS,
        "maxActiveExperimentsPerUser": MAX_ACTIVE_EXPERIMENTS_PER_USER,
        "maxStoredExperimentsPerUser": MAX_STORED_EXPERIMENTS_PER_USER,
        "maxAlternatives": MAX_ALTERNATIVES,
        "maxRunsPerExperiment": MAX_RUNS_PER_EXPERIMENT,
        "maxSimulatedSecondsPerExperiment": MAX_SIMULATED_SECONDS_PER_EXPERIMENT,
    }
