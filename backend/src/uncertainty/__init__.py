"""Robustness Lab (W1, #151): uncertainty specification, seeded stratified sampler and analysis core.

Pure computation -- no simulation, no HTTP exposure. See ADR-015 and strategy section 5.
"""

from .analysis import (
    ConditionResult,
    analyze,
    classify,
    result_fingerprint,
)
from .apply import FactorApplicationError, apply_factors, preflight
from .runner import (
    EnsembleRefusedError,
    EnsembleRun,
    RunAlternative,
    run_ensemble,
    run_experiment,
)
from .sampler import Condition, derive_seed, inverse_cdf, sample_conditions
from .spec import (
    SPEC_FORMAT,
    SPEC_VERSION,
    Distribution,
    Factor,
    UncertaintySpec,
    fingerprint,
    run_counts,
)
from .stats import variance_decomposition

__all__ = [
    "Condition",
    "ConditionResult",
    "EnsembleRefusedError",
    "EnsembleRun",
    "FactorApplicationError",
    "RunAlternative",
    "Distribution",
    "Factor",
    "SPEC_FORMAT",
    "SPEC_VERSION",
    "UncertaintySpec",
    "analyze",
    "apply_factors",
    "classify",
    "derive_seed",
    "fingerprint",
    "inverse_cdf",
    "preflight",
    "result_fingerprint",
    "run_ensemble",
    "run_experiment",
    "run_counts",
    "sample_conditions",
    "variance_decomposition",
]
