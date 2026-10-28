"""Small statistical helpers for the Robustness Lab analysis (standard library only; NumPy is not approved).

Every function is pure and deterministic. Randomness (the bootstrap) takes an explicit ``random.Random`` so
the caller controls the seed; nothing here touches global state.
"""

from __future__ import annotations

import math
import random
from statistics import NormalDist
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

Z95 = NormalDist().inv_cdf(0.975)  # 1.959963984540054


def wilson_interval(successes: int, n: int, z: float = Z95) -> Tuple[float, float]:
    """Wilson score interval for a binomial proportion (default 95 %).

    Behaves sensibly at 0 and n successes, unlike the normal-approximation interval; that is why the
    contract (strategy section 5.4) names it. ``n`` must be positive.
    """
    if n <= 0:
        raise ValueError("a proportion needs at least one observation")
    if not 0 <= successes <= n:
        raise ValueError("successes must lie between 0 and n")
    p = successes / n
    z2 = z * z
    denominator = 1.0 + z2 / n
    centre = (p + z2 / (2.0 * n)) / denominator
    half = (z / denominator) * math.sqrt(p * (1.0 - p) / n + z2 / (4.0 * n * n))
    return max(0.0, centre - half), min(1.0, centre + half)


def percentile_sorted(sorted_values: Sequence[float], q: float) -> float:
    """Percentile ``q`` in [0, 1] of an ascending sequence, by linear interpolation between order
    statistics (the common "type 7" definition: position ``q * (n - 1)``)."""
    n = len(sorted_values)
    if n == 0:
        raise ValueError("percentile of an empty sample")
    if not 0.0 <= q <= 1.0:
        raise ValueError("q must lie in [0, 1]")
    position = q * (n - 1)
    lower = math.floor(position)
    upper = min(lower + 1, n - 1)
    fraction = position - lower
    return sorted_values[lower] + fraction * (
        sorted_values[upper] - sorted_values[lower]
    )


def percentile(values: Sequence[float], q: float) -> float:
    return percentile_sorted(sorted(values), q)


def mean_sorted(sorted_values: Sequence[float]) -> float:
    return math.fsum(sorted_values) / len(sorted_values)


# A statistic is computed from a resample already sorted ascending.
SortedStatistic = Callable[[Sequence[float]], float]


def bootstrap_intervals(
    values: Sequence[float],
    statistics: Mapping[str, SortedStatistic],
    rng: random.Random,
    resamples: int = 2000,
    level: float = 0.95,
) -> Dict[str, Tuple[float, float]]:
    """Percentile bootstrap intervals for several statistics of one sample.

    The sample's units (here: conditions) are resampled with replacement ``resamples`` times; each
    statistic is evaluated on every resample and the central ``level`` of its distribution is returned.
    The same resamples serve every statistic, so the intervals are consistent with one another.
    """
    n = len(values)
    if n == 0:
        raise ValueError("cannot bootstrap an empty sample")
    if resamples < 1:
        raise ValueError("resamples must be positive")
    if not 0.0 < level < 1.0:
        raise ValueError("level must lie strictly between 0 and 1")
    draws: Dict[str, List[float]] = {name: [] for name in statistics}
    indexes = range(n)
    for _ in range(resamples):
        resample = sorted(values[i] for i in rng.choices(indexes, k=n))
        for name, statistic in statistics.items():
            draws[name].append(statistic(resample))
    tail = (1.0 - level) / 2.0
    intervals: Dict[str, Tuple[float, float]] = {}
    for name, series in draws.items():
        series.sort()
        intervals[name] = (
            percentile_sorted(series, tail),
            percentile_sorted(series, 1.0 - tail),
        )
    return intervals


def variance_decomposition(
    condition_runs: Sequence[Sequence[float]],
) -> Dict[str, Any]:
    """Between-condition versus within-condition variance decomposition (one-way ANOVA).

    ``condition_runs`` contains the outcomes for each valid condition across its replications
    (i.e., a sequence of rows, one per condition, each holding r replication outcomes).
    Requires at least 2 conditions and at least 2 replications per condition.

    ``between``/``within``/``total`` are sums of squares (between + within = total) and the shares
    are their fractions of the total; ``msBetween``/``msWithin`` are the mean squares. The shares
    describe the observed partition, not variance components (E[MS_between] still contains the
    within-condition noise).
    """
    n = len(condition_runs)
    if n < 2:
        raise ValueError("variance decomposition requires at least 2 conditions")
    r = len(condition_runs[0])
    if r < 2:
        raise ValueError("variance decomposition requires at least 2 replications")
    for row in condition_runs:
        if len(row) != r:
            raise ValueError("all conditions must have the same number of replications")

    condition_means = [math.fsum(row) / r for row in condition_runs]
    grand_mean = math.fsum(condition_means) / n

    ss_between = r * math.fsum((m - grand_mean) ** 2 for m in condition_means)
    ss_within = math.fsum(
        math.fsum((val - m) ** 2 for val in row)
        for row, m in zip(condition_runs, condition_means)
    )
    ss_total = ss_between + ss_within

    df_between = n - 1
    df_within = n * (r - 1)

    ms_between = ss_between / df_between if df_between > 0 else 0.0
    ms_within = ss_within / df_within if df_within > 0 else 0.0

    # No variation at all: the shares are undefined, reported as None (not 0 and 0).
    between_share: Optional[float] = None
    within_share: Optional[float] = None
    if ss_total > 1e-12:
        between_share = round(ss_between / ss_total, 6) + 0.0
        within_share = round(ss_within / ss_total, 6) + 0.0

    return {
        "between": round(ss_between, 6) + 0.0,
        "within": round(ss_within, 6) + 0.0,
        "total": round(ss_total, 6) + 0.0,
        "dfBetween": df_between,
        "dfWithin": df_within,
        "msBetween": round(ms_between, 6) + 0.0,
        "msWithin": round(ms_within, 6) + 0.0,
        "betweenShare": between_share,
        "withinShare": within_share,
    }
