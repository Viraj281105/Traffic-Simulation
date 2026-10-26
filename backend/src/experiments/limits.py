"""Quotas and limits of ``/api/v3/experiments`` (W1 base; personal-access-token quotas arrive in W7).

All values are **proposals**: they bound what one user can ask of a shared server and are reported by
``GET /api/v3/capabilities`` so a client can show them. The step budget is derived from one measurement on
a development machine (about 12-17 s of wall time per 240 s simulation at a 0.1 s step, one process) and is
*unverified* elsewhere. Work is counted in engine **steps** (duration / time step), not seconds: a run costs
one engine step per time step (core/limits.py), and the config contract allows a step as small as 0.05 s.
"""

from __future__ import annotations

from src.core.limits import MAX_DOCUMENT_DEPTH as _MAX_DOCUMENT_DEPTH

# Experiments running or queued at once. Each fills the shared worker pool, so more would only queue.
MAX_ACTIVE_EXPERIMENTS = 2
MAX_ACTIVE_EXPERIMENTS_PER_USER = 1

# Experiments one user may keep (finished or failed ones are deleted by the owner).
MAX_STORED_EXPERIMENTS_PER_USER = 50

# Size of one experiment.
MAX_ALTERNATIVES = 6
MAX_RUNS_PER_EXPERIMENT = 2000  # conditions x alternatives x replications
MAX_SIMULATION_STEPS_PER_EXPERIMENT = (
    2_500_000  # runs x duration / time step (250 000 s at 0.1 s)
)

# Structure of a request document. Real documents nest about 8 levels (a scenario patch is the deepest);
# anything much deeper is an attack on the parser or the merge, and is refused before any work is done.
MAX_DOCUMENT_DEPTH = _MAX_DOCUMENT_DEPTH

# Hard backstop on the alternatives list, checked while the request is parsed; the quota above is checked
# first, by hand, so its message can name it.
MAX_ALTERNATIVES_PARSED = 64

# W7 platform quotas (ADR-013). Process-local where noted: a single uvicorn process is assumed.
PER_TOKEN_REQUESTS_PER_MINUTE = 60  # per personal access token, sliding 60 s window
MAX_DAILY_SIMULATED_SECONDS_PER_USER = 86_400  # 24 h of simulated time per UTC day
MAX_PACKAGE_BYTES = 10 * 1024 * 1024  # a .ufpkg as uploaded or exported
MAX_PACKAGE_UNCOMPRESSED_BYTES = 50 * 1024 * 1024  # all members together, actually read
MAX_PACKAGE_ENTRIES = 50

# Listing page size.
DEFAULT_PAGE_SIZE = 25

QUOTA_NAMES = {
    "activeExperiments": "maxActiveExperiments",
    "activeExperimentsPerUser": "maxActiveExperimentsPerUser",
    "storedExperimentsPerUser": "maxStoredExperimentsPerUser",
    "alternatives": "maxAlternatives",
    "runsPerExperiment": "maxRunsPerExperiment",
    "simulationStepsPerExperiment": "maxSimulationStepsPerExperiment",
    "dailySimulatedSecondsPerUser": "maxDailySimulatedSecondsPerUser",
    "requestsPerTokenPerMinute": "perTokenRequestsPerMinute",
    "packageBytes": "maxPackageBytes",
}

# Extensible quota registration seam (W7 / ADR-013).
# Future modules (e.g. W5 Copilot proposals, W6 Discovery budgets) register their quotas here
# when built without modifying base platform limits.
_EXTENSION_QUOTAS: dict[str, float | int] = {}


def register_quota(
    name: str, value: float | int, internal_key: str | None = None
) -> None:
    """Register an extension quota dynamically."""
    _EXTENSION_QUOTAS[name] = value
    if internal_key:
        QUOTA_NAMES[internal_key] = name


def quotas() -> dict[str, float | int]:
    base: dict[str, float | int] = {
        "maxActiveExperiments": MAX_ACTIVE_EXPERIMENTS,
        "maxActiveExperimentsPerUser": MAX_ACTIVE_EXPERIMENTS_PER_USER,
        "maxStoredExperimentsPerUser": MAX_STORED_EXPERIMENTS_PER_USER,
        "maxAlternatives": MAX_ALTERNATIVES,
        "maxRunsPerExperiment": MAX_RUNS_PER_EXPERIMENT,
        "maxSimulationStepsPerExperiment": MAX_SIMULATION_STEPS_PER_EXPERIMENT,
        "maxDailySimulatedSecondsPerUser": MAX_DAILY_SIMULATED_SECONDS_PER_USER,
        "perTokenRequestsPerMinute": PER_TOKEN_REQUESTS_PER_MINUTE,
        "maxPackageBytes": MAX_PACKAGE_BYTES,
    }
    base.update(_EXTENSION_QUOTAS)
    return base
