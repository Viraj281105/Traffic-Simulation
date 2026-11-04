"""Confidence intervals and paired significance tests for "is A better than B?" (V3.2 W32, F6).

Standard library only, like ``stats.py``. Every function is pure; the bootstrap and the randomisation
test take an explicit seed, so a result repeats exactly.

A comparison is *paired*: strategy A and strategy B are run on the same seeds, and the unit of analysis is
the per-seed difference ``a[i] - b[i]``. Pairing removes the seed-to-seed variation the two strategies
share, which is most of it. The input sequences must therefore be the same length and in the same seed order.

Two methods are offered and every result names the one used:

``paired_t``
    Student's t interval and two-sided t test on the mean difference. Assumes the differences are roughly
    normal; reasonable for means over many vehicles, weak for very few seeds.
``paired_bootstrap``
    Percentile bootstrap interval for the mean difference, and a two-sided sign-flip randomisation test for
    the p-value (exact when ``n`` is small, Monte Carlo otherwise). Makes no normality assumption, but
    needs enough seeds for resampling to mean anything.

``significant`` is only ``p_value < alpha``; it says nothing about whether the difference matters. Read it
with the interval, which is in the metric's own units.
"""

from __future__ import annotations

import itertools
import math
import random
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .stats import percentile_sorted

METHODS: Tuple[str, ...] = ("paired_t", "paired_bootstrap")

DEFAULT_CONFIDENCE = 0.95
DEFAULT_RESAMPLES = 10_000
MAX_RESAMPLES = 200_000
# Below this many pairs the methods run but the result carries a caution.
LOW_SAMPLE_PAIRS = 5
# Up to 2**EXACT_FLIP_LIMIT sign patterns are enumerated; beyond it they are sampled.
EXACT_FLIP_LIMIT = 14


# -- Student's t distribution (regularised incomplete beta, continued fraction) --


def _betacf(a: float, b: float, x: float) -> float:
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 500):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-15:
            break
    return h


def _regularized_beta(x: float, a: float, b: float) -> float:
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    log_front = (
        math.lgamma(a + b)
        - math.lgamma(a)
        - math.lgamma(b)
        + a * math.log(x)
        + b * math.log1p(-x)
    )
    front = math.exp(log_front)
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def t_cdf(t: float, df: float) -> float:
    """P(T <= t) for Student's t with ``df`` degrees of freedom."""
    if df <= 0:
        raise ValueError("degrees of freedom must be positive")
    if math.isinf(t):
        return 1.0 if t > 0 else 0.0
    tail = 0.5 * _regularized_beta(df / (df + t * t), df / 2.0, 0.5)
    return 1.0 - tail if t > 0 else tail


def t_ppf(q: float, df: float) -> float:
    """Quantile of Student's t: the ``t`` with ``t_cdf(t, df) == q``, for q in (0, 1)."""
    if not 0.0 < q < 1.0:
        raise ValueError("q must lie strictly between 0 and 1")
    if q == 0.5:
        return 0.0
    if q < 0.5:
        return -t_ppf(1.0 - q, df)
    lo, hi = 0.0, 1.0
    while t_cdf(hi, df) < q and hi < 1e12:
        hi *= 2.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if t_cdf(mid, df) < q:
            lo = mid
        else:
            hi = mid
        if hi - lo <= 1e-14 * max(1.0, hi):
            break
    return 0.5 * (lo + hi)


# -- Results --


@dataclass(frozen=True)
class MeanInterval:
    n: int
    mean: float
    lower: float
    upper: float
    confidence: float
    method: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PairedComparison:
    """Outcome of comparing A with B over paired seeds. ``difference`` is mean(a - b)."""

    method: str
    n_pairs: int
    mean_a: float
    mean_b: float
    difference: float
    ci_lower: float
    ci_upper: float
    confidence: float
    p_value: float
    alpha: float
    significant: bool
    # "a_lower", "a_higher" or "none" (not significant, or no difference).
    direction: str
    # The t statistic for ``paired_t``; None for the bootstrap and for zero-variance pairs.
    statistic: Optional[float]
    cautions: Tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        out = asdict(self)
        out["cautions"] = list(self.cautions)
        return out


# -- Helpers --


def _check_confidence(confidence: float) -> None:
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must lie strictly between 0 and 1")


def _finite(values: Sequence[float], name: str) -> List[float]:
    out = [float(v) for v in values]
    if any(not math.isfinite(v) for v in out):
        raise ValueError(f"{name} must contain only finite numbers")
    return out


def _paired_differences(a: Sequence[float], b: Sequence[float]) -> List[float]:
    if len(a) != len(b):
        raise ValueError("a and b must have the same length (one value per seed)")
    if len(a) < 2:
        raise ValueError("a paired comparison needs at least two pairs")
    fa, fb = _finite(a, "a"), _finite(b, "b")
    return [x - y for x, y in zip(fa, fb)]


def _sample_sd(values: Sequence[float], mean: float) -> float:
    return math.sqrt(math.fsum((v - mean) ** 2 for v in values) / (len(values) - 1))


def _cautions(n: int) -> Tuple[str, ...]:
    if n < LOW_SAMPLE_PAIRS:
        return (
            f"only {n} paired seeds: the interval is wide and the p-value is unreliable",
        )
    return ()


def _direction(significant: bool, difference: float) -> str:
    if not significant or difference == 0.0:
        return "none"
    return "a_lower" if difference < 0 else "a_higher"


def _bootstrap_bounds(
    diffs: Sequence[float], confidence: float, resamples: int, seed: int
) -> Tuple[float, float]:
    if not 1 <= resamples <= MAX_RESAMPLES:
        raise ValueError(f"resamples must lie in [1, {MAX_RESAMPLES}]")
    rng = random.Random(seed)
    n = len(diffs)
    means = sorted(math.fsum(rng.choices(diffs, k=n)) / n for _ in range(resamples))
    tail = (1.0 - confidence) / 2.0
    return percentile_sorted(means, tail), percentile_sorted(means, 1.0 - tail)


def _sign_flip_p_value(diffs: Sequence[float], resamples: int, seed: int) -> float:
    """Two-sided randomisation p-value for mean(diffs) == 0 under random sign flips."""
    n = len(diffs)
    observed = abs(math.fsum(diffs))
    # Tolerance so sums that differ only by rounding count as ties.
    cutoff = observed - 1e-12 * max(1.0, observed)
    if n <= EXACT_FLIP_LIMIT:
        hits = 0
        for signs in itertools.product((1.0, -1.0), repeat=n):
            if abs(math.fsum(s * d for s, d in zip(signs, diffs))) >= cutoff:
                hits += 1
        return hits / (1 << n)
    rng = random.Random(seed ^ 0x5F3759DF)
    hits = 0
    for _ in range(resamples):
        flipped = math.fsum(d if rng.random() < 0.5 else -d for d in diffs)
        if abs(flipped) >= cutoff:
            hits += 1
    # The observed pattern is itself one valid arrangement: never report p == 0.
    return (hits + 1) / (resamples + 1)


def _build(
    method: str,
    a: Sequence[float],
    b: Sequence[float],
    mean_d: float,
    lower: float,
    upper: float,
    confidence: float,
    p_value: float,
    statistic: Optional[float],
) -> PairedComparison:
    n = len(a)
    alpha = 1.0 - confidence
    significant = p_value < alpha
    return PairedComparison(
        method=method,
        n_pairs=n,
        mean_a=math.fsum(a) / n,
        mean_b=math.fsum(b) / n,
        difference=mean_d,
        ci_lower=lower,
        ci_upper=upper,
        confidence=confidence,
        p_value=p_value,
        alpha=alpha,
        significant=significant,
        direction=_direction(significant, mean_d),
        statistic=statistic,
        cautions=_cautions(n),
    )


# -- Public API --


def mean_confidence_interval(
    values: Sequence[float], confidence: float = DEFAULT_CONFIDENCE
) -> MeanInterval:
    """t-based confidence interval for the mean of ``values`` (at least two)."""
    _check_confidence(confidence)
    data = _finite(values, "values")
    n = len(data)
    if n < 2:
        raise ValueError("a confidence interval needs at least two values")
    mean = math.fsum(data) / n
    half = t_ppf(0.5 + confidence / 2.0, n - 1) * _sample_sd(data, mean) / math.sqrt(n)
    return MeanInterval(n, mean, mean - half, mean + half, confidence, "t")


def bootstrap_mean_interval(
    values: Sequence[float],
    confidence: float = DEFAULT_CONFIDENCE,
    resamples: int = DEFAULT_RESAMPLES,
    seed: int = 0,
) -> MeanInterval:
    """Percentile bootstrap interval for the mean of ``values`` (at least two)."""
    _check_confidence(confidence)
    data = _finite(values, "values")
    n = len(data)
    if n < 2:
        raise ValueError("a confidence interval needs at least two values")
    lower, upper = _bootstrap_bounds(data, confidence, resamples, seed)
    return MeanInterval(
        n, math.fsum(data) / n, lower, upper, confidence, "bootstrap_percentile"
    )


def paired_t_test(
    a: Sequence[float],
    b: Sequence[float],
    confidence: float = DEFAULT_CONFIDENCE,
) -> PairedComparison:
    """Paired Student t test and interval for mean(a - b)."""
    _check_confidence(confidence)
    diffs = _paired_differences(a, b)
    n = len(diffs)
    mean_d = math.fsum(diffs) / n
    se = _sample_sd(diffs, mean_d) / math.sqrt(n)
    statistic: Optional[float]
    if se == 0.0:
        # Every pair differs by the same amount: no sampling variation to test against.
        lower = upper = mean_d
        statistic = None
        p_value = 1.0 if mean_d == 0.0 else 0.0
    else:
        half = t_ppf(0.5 + confidence / 2.0, n - 1) * se
        lower, upper = mean_d - half, mean_d + half
        statistic = mean_d / se
        p_value = min(1.0, 2.0 * (1.0 - t_cdf(abs(statistic), n - 1)))
    return _build(
        "paired_t", a, b, mean_d, lower, upper, confidence, p_value, statistic
    )


def paired_bootstrap_test(
    a: Sequence[float],
    b: Sequence[float],
    confidence: float = DEFAULT_CONFIDENCE,
    resamples: int = DEFAULT_RESAMPLES,
    seed: int = 0,
) -> PairedComparison:
    """Percentile bootstrap interval for mean(a - b) with a sign-flip randomisation p-value."""
    _check_confidence(confidence)
    diffs = _paired_differences(a, b)
    mean_d = math.fsum(diffs) / len(diffs)
    lower, upper = _bootstrap_bounds(diffs, confidence, resamples, seed)
    p_value = _sign_flip_p_value(diffs, resamples, seed)
    return _build(
        "paired_bootstrap", a, b, mean_d, lower, upper, confidence, p_value, None
    )


def compare_paired(
    a: Sequence[float],
    b: Sequence[float],
    *,
    method: str = "paired_t",
    confidence: float = DEFAULT_CONFIDENCE,
    resamples: int = DEFAULT_RESAMPLES,
    seed: int = 0,
) -> PairedComparison:
    """Compare strategy A with B over the same seeds with the named ``method``."""
    if method == "paired_t":
        return paired_t_test(a, b, confidence)
    if method == "paired_bootstrap":
        return paired_bootstrap_test(a, b, confidence, resamples, seed)
    raise ValueError(f"method must be one of {list(METHODS)}")


def verdict(comparison: PairedComparison, lower_is_better: bool = True) -> str:
    """Plain-words reading of a comparison, naming the method, interval and p-value.

    ``lower_is_better`` is true for delay and queue length, false for throughput.
    """
    pct = round(comparison.confidence * 100)
    detail = (
        f"{comparison.difference:.4g} (A minus B, {pct}% interval "
        f"{comparison.ci_lower:.4g} to {comparison.ci_upper:.4g}, "
        f"p = {comparison.p_value:.3g}, {comparison.method}, n = {comparison.n_pairs})"
    )
    if comparison.direction == "none":
        return f"No reliable difference between A and B: {detail}"
    a_wins = (comparison.direction == "a_lower") == lower_is_better
    return f"{'A beats B' if a_wins else 'B beats A'}: {detail}"
