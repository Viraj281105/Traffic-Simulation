"""Robustness Lab (W1, #151): uncertainty specification, seeded stratified sampler and analysis core.

Pure computation -- no simulation, no HTTP exposure. See ADR-015 and strategy section 5.
"""

from .analysis import (
    ConditionResult,
    analyze,
    classify,
    result_fingerprint,
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

__all__ = [
    "Condition",
    "ConditionResult",
    "Distribution",
    "Factor",
    "SPEC_FORMAT",
    "SPEC_VERSION",
    "UncertaintySpec",
    "analyze",
    "classify",
    "derive_seed",
    "fingerprint",
    "inverse_cdf",
    "result_fingerprint",
    "run_counts",
    "sample_conditions",
]
