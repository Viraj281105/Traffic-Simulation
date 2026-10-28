"""Seeded Latin-hypercube sampler and engine-seed derivation (B0-5 skeleton).

Pure Python (standard library only; NumPy is not approved, decision D2). For each factor the unit interval
is cut into N equal-probability strata; one point is drawn per stratum (jittered), the strata are shuffled
independently per factor, and the point is mapped through the factor's inverse CDF restricted to its
bounds. Same specification, same result: sampling uses ``random.Random`` seeded from the spec and the factor
id only, never global state.

The sampler returns conditions; it never runs a simulation and never repairs a value (a perturbed
scenario that later fails validation is rejected and counted by the runner, strategy section 5.1).
"""

from __future__ import annotations

import hashlib
import math
import random
from dataclasses import dataclass
from statistics import NormalDist
from typing import Dict, List, Tuple

from .spec import Distribution, Factor, UncertaintySpec

_STD = NormalDist()
_EDGE = 1e-12  # keep probabilities strictly inside (0, 1)
# Sampled values are rounded so that fingerprints never depend on float formatting
# (e.g. 1.4400000000000002), then clamped back into the factor bounds.
VALUE_DECIMALS = 6


@dataclass(frozen=True)
class Condition:
    index: int
    values: Dict[str, float]  # factor id -> sampled value
    strata: Dict[
        str, int
    ]  # factor id -> stratum (0..N-1), kept for later flip analysis
    seeds: List[int]  # one engine seed per replication


def derive_seed(base_seed: int, condition_index: int, replication: int) -> int:
    """Deterministic engine seed for (base seed, condition index, replication); a 31-bit integer."""
    digest = hashlib.sha256(
        f"urbanflow-uncertainty-v1:{base_seed}:{condition_index}:{replication}".encode()
    ).digest()
    return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF


def _factor_rng(spec_seed: int, factor_id: str) -> random.Random:
    digest = hashlib.sha256(
        f"urbanflow-uncertainty-v1:sample:{spec_seed}:{factor_id}".encode()
    ).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def _clamp01(p: float) -> float:
    return min(max(p, _EDGE), 1.0 - _EDGE)


def inverse_cdf(distribution: Distribution, low: float, high: float, u: float) -> float:
    """Map a unit-interval probability to a value, truncated to [low, high]."""
    u = _clamp01(u)
    kind = distribution.kind
    if kind == "uniform":
        return low + u * (high - low)
    if kind == "triangular":
        assert distribution.mode is not None  # guaranteed by the spec validator
        mode = distribution.mode
        fc = (mode - low) / (high - low)
        if u < fc:
            return low + math.sqrt(u * (high - low) * (mode - low))
        return high - math.sqrt((1.0 - u) * (high - low) * (high - mode))
    if kind == "truncated_normal":
        assert distribution.mean is not None and distribution.sd is not None
        dist = NormalDist(distribution.mean, distribution.sd)
        lo_p, hi_p = dist.cdf(low), dist.cdf(high)
        return dist.inv_cdf(_clamp01(lo_p + u * (hi_p - lo_p)))
    # lognormal: truncate in log space
    assert distribution.mu is not None and distribution.sigma is not None
    dist = NormalDist(distribution.mu, distribution.sigma)
    lo_p, hi_p = dist.cdf(math.log(low)), dist.cdf(math.log(high))
    return math.exp(dist.inv_cdf(_clamp01(lo_p + u * (hi_p - lo_p))))


def _sample_factor(
    factor: Factor, n: int, spec_seed: int
) -> Tuple[List[float], List[int]]:
    """One jittered point per equal-probability stratum, strata shuffled per factor."""
    rng = _factor_rng(spec_seed, factor.id)
    order = list(range(n))
    rng.shuffle(order)
    low, high = factor.bounds
    values: List[float] = []
    strata: List[int] = []
    for stratum in order:
        u = (stratum + rng.random()) / n
        value = round(inverse_cdf(factor.distribution, low, high, u), VALUE_DECIMALS)
        values.append(min(max(value, low), high))
        strata.append(stratum)
    return values, strata


def sample_conditions(spec: UncertaintySpec) -> List[Condition]:
    """Draw ``spec.conditions`` conditions (Latin-hypercube stratified, seeded)."""
    n = spec.conditions
    per_factor = {f.id: _sample_factor(f, n, spec.seed) for f in spec.factors}
    conditions = []
    for i in range(n):
        conditions.append(
            Condition(
                index=i,
                values={fid: per_factor[fid][0][i] for fid in per_factor},
                strata={fid: per_factor[fid][1][i] for fid in per_factor},
                seeds=[derive_seed(spec.seed, i, r) for r in range(spec.replications)],
            )
        )
    return conditions
