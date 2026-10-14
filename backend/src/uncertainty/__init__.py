"""Robustness Lab skeleton (task B0-5): uncertainty specification and seeded stratified sampler.

Design prototype -- no runner, no analysis, no HTTP exposure. See ADR-015 and strategy section 5.
"""

from .sampler import Condition, derive_seed, inverse_cdf, sample_conditions
from .spec import (
    SPEC_FORMAT,
    SPEC_VERSION,
    Distribution,
    Factor,
    UncertaintySpec,
    fingerprint,
)

__all__ = [
    "Condition",
    "Distribution",
    "Factor",
    "SPEC_FORMAT",
    "SPEC_VERSION",
    "UncertaintySpec",
    "derive_seed",
    "fingerprint",
    "inverse_cdf",
    "sample_conditions",
]
