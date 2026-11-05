"""Confidence intervals and paired tests: textbook values, properties, determinism."""

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.uncertainty.comparison import (
    bootstrap_mean_interval,
    compare_paired,
    mean_confidence_interval,
    paired_bootstrap_test,
    paired_t_test,
    t_cdf,
    t_ppf,
    verdict,
)


@pytest.mark.parametrize(
    "q, df, expected",
    [
        # Standard t table values.
        (0.975, 1, 12.7062),
        (0.975, 4, 2.7764),
        (0.975, 9, 2.2622),
        (0.975, 29, 2.0452),
        (0.995, 10, 3.1693),
        (0.95, 5, 2.0150),
    ],
)
def test_t_ppf_matches_table(q: float, df: int, expected: float) -> None:
    assert t_ppf(q, df) == pytest.approx(expected, abs=1e-4)


def test_t_cdf_symmetry_and_median() -> None:
    assert t_cdf(0.0, 7) == pytest.approx(0.5)
    assert t_cdf(1.3, 7) + t_cdf(-1.3, 7) == pytest.approx(1.0)
    assert t_cdf(math.inf, 3) == 1.0 and t_cdf(-math.inf, 3) == 0.0
    # df = 1 is the Cauchy distribution: P(T <= 1) = 0.75.
    assert t_cdf(1.0, 1) == pytest.approx(0.75)


@given(st.floats(0.01, 0.99), st.integers(1, 60))
def test_t_ppf_inverts_t_cdf(q: float, df: int) -> None:
    assert t_cdf(t_ppf(q, df), df) == pytest.approx(q, abs=1e-9)


def test_t_functions_reject_bad_input() -> None:
    with pytest.raises(ValueError):
        t_cdf(0.0, 0)
    with pytest.raises(ValueError):
        t_ppf(1.0, 5)


def test_mean_interval_hand_computed() -> None:
    # n=5, mean 3, sd sqrt(2.5): half = 2.7764 * sqrt(2.5)/sqrt(5)
    result = mean_confidence_interval([1, 2, 3, 4, 5])
    half = 2.7764 * math.sqrt(2.5) / math.sqrt(5)
    assert result.mean == 3.0 and result.method == "t" and result.n == 5
    assert result.lower == pytest.approx(3 - half, abs=1e-3)
    assert result.upper == pytest.approx(3 + half, abs=1e-3)


def test_paired_t_hand_computed() -> None:
    a = [10.0, 12.0, 9.0, 11.0, 13.0, 10.0]
    b = [11.0, 14.0, 9.5, 12.5, 14.0, 12.0]
    # differences: -1, -2, -0.5, -1.5, -1, -2 -> mean -1.3333, sd 0.60551
    r = paired_t_test(a, b)
    assert r.method == "paired_t" and r.n_pairs == 6
    assert r.difference == pytest.approx(-4 / 3)
    assert r.statistic == pytest.approx(-5.3936, abs=1e-3)
    assert r.p_value == pytest.approx(0.002958, abs=1e-5)  # closed form for df = 5
    half = 2.5706 * 0.60551 / math.sqrt(6)
    assert r.ci_lower == pytest.approx(-4 / 3 - half, abs=1e-3)
    assert r.ci_upper == pytest.approx(-4 / 3 + half, abs=1e-3)
    assert r.significant and r.direction == "a_lower"
    assert r.mean_a == pytest.approx(65 / 6) and r.alpha == pytest.approx(0.05)


def test_identical_series_have_no_difference() -> None:
    for fn in (paired_t_test, paired_bootstrap_test):
        r = fn([1.0, 2.0, 3.0], [1.0, 2.0, 3.0])
        assert r.difference == 0.0 and r.p_value == 1.0
        assert not r.significant and r.direction == "none"


def test_constant_shift_has_zero_variance_and_is_significant() -> None:
    r = paired_t_test([1.0, 2.0, 3.0], [2.0, 3.0, 4.0])
    assert r.ci_lower == r.ci_upper == -1.0
    assert r.p_value == 0.0 and r.statistic is None and r.direction == "a_lower"


def test_swapping_a_and_b_negates_the_difference_and_keeps_p() -> None:
    a = [5.0, 6.5, 4.0, 7.0, 5.5, 6.0]
    b = [4.0, 6.0, 3.5, 5.0, 5.0, 4.5]
    ab, ba = paired_t_test(a, b), paired_t_test(b, a)
    assert ab.difference == pytest.approx(-ba.difference)
    assert ab.p_value == pytest.approx(ba.p_value)
    assert ab.ci_lower == pytest.approx(-ba.ci_upper)


def test_higher_confidence_widens_interval() -> None:
    a = [5.0, 6.5, 4.0, 7.0, 5.5, 6.0]
    b = [4.0, 6.0, 3.5, 5.0, 5.0, 4.5]
    narrow, wide = paired_t_test(a, b, 0.90), paired_t_test(a, b, 0.99)
    assert wide.ci_upper - wide.ci_lower > narrow.ci_upper - narrow.ci_lower


def test_bootstrap_is_deterministic_per_seed_and_varies_across_seeds() -> None:
    a = [5.0, 6.5, 4.0, 7.0, 5.5, 6.0, 8.0, 3.0]
    b = [4.0, 6.0, 3.5, 5.0, 5.0, 4.5, 6.0, 3.5]
    one = paired_bootstrap_test(a, b, resamples=500, seed=3)
    assert one == paired_bootstrap_test(a, b, resamples=500, seed=3)
    other = paired_bootstrap_test(a, b, resamples=500, seed=4)
    assert (one.ci_lower, one.ci_upper) != (other.ci_lower, other.ci_upper)
    assert one.method == "paired_bootstrap"


def test_bootstrap_interval_brackets_the_mean_and_agrees_with_t_roughly() -> None:
    values = [float(v) for v in range(1, 41)]
    boot = bootstrap_mean_interval(values, resamples=4000, seed=1)
    t = mean_confidence_interval(values)
    assert boot.lower < boot.mean < boot.upper
    assert boot.lower == pytest.approx(t.lower, abs=0.8)
    assert boot.upper == pytest.approx(t.upper, abs=0.8)


def test_sign_flip_p_value_exact_for_small_n() -> None:
    # n=3, all differences positive: only the all-plus and all-minus patterns reach |sum|: p = 2/8.
    r = paired_bootstrap_test([2.0, 3.0, 4.0], [1.0, 1.5, 2.0], resamples=100)
    assert r.p_value == pytest.approx(0.25)


def test_sign_flip_monte_carlo_never_zero_and_detects_clear_effect() -> None:
    a = [10.0 + i * 0.1 for i in range(20)]
    b = [x - 5.0 + (i % 3) * 0.1 for i, x in enumerate(a)]
    r = paired_bootstrap_test(a, b, resamples=2000, seed=9)
    assert 0.0 < r.p_value < 0.01
    assert r.significant and r.direction == "a_higher"


def test_null_effect_is_rarely_significant() -> None:
    import random

    rng = random.Random(11)
    hits = 0
    trials = 200
    for _ in range(trials):
        a = [rng.gauss(0, 1) for _ in range(12)]
        b = [rng.gauss(0, 1) for _ in range(12)]
        hits += paired_t_test(a, b).significant
    # Nominal 5 %; allow generous slack for 200 trials.
    assert hits / trials < 0.12


def test_interval_coverage_is_near_nominal() -> None:
    import random

    rng = random.Random(5)
    covered = 0
    trials = 300
    for _ in range(trials):
        sample = [rng.gauss(2.0, 1.0) for _ in range(10)]
        ci = mean_confidence_interval(sample)
        covered += ci.lower <= 2.0 <= ci.upper
    assert 0.90 < covered / trials < 0.99


def test_low_sample_caution() -> None:
    assert paired_t_test([1.0, 2.0], [2.0, 4.0]).cautions
    assert not paired_t_test([1.0, 2, 3, 4, 5], [2.0, 4, 5, 9, 7]).cautions


def test_validation() -> None:
    with pytest.raises(ValueError, match="same length"):
        paired_t_test([1.0, 2.0], [1.0])
    with pytest.raises(ValueError, match="at least two"):
        paired_t_test([1.0], [2.0])
    with pytest.raises(ValueError, match="finite"):
        paired_t_test([1.0, math.nan], [1.0, 2.0])
    with pytest.raises(ValueError, match="confidence"):
        paired_t_test([1.0, 2.0], [2.0, 1.0], confidence=1.0)
    with pytest.raises(ValueError, match="resamples"):
        paired_bootstrap_test([1.0, 2.0], [2.0, 1.0], resamples=0)
    with pytest.raises(ValueError, match="method"):
        compare_paired([1.0, 2.0], [2.0, 1.0], method="mann_whitney")
    with pytest.raises(ValueError):
        mean_confidence_interval([1.0])


def test_compare_paired_dispatches_and_serialises() -> None:
    a, b = [1.0, 2.0, 3.0, 4.0], [2.0, 2.5, 4.5, 5.0]
    assert compare_paired(a, b).method == "paired_t"
    boot = compare_paired(a, b, method="paired_bootstrap", resamples=200, seed=2)
    assert boot.method == "paired_bootstrap"
    data = boot.to_dict()
    assert data["method"] == "paired_bootstrap" and isinstance(data["cautions"], list)


def test_verdict_names_winner_method_interval_and_p() -> None:
    a = [10.0, 12.0, 9.0, 11.0, 13.0, 10.0]
    b = [11.0, 14.0, 9.5, 12.5, 14.0, 12.0]
    r = paired_t_test(a, b)
    assert verdict(r).startswith("A beats B")
    assert verdict(r, lower_is_better=False).startswith("B beats A")
    text = verdict(r)
    assert "paired_t" in text and "p = " in text and "95% interval" in text
    flat = paired_t_test([1.0, 2.0, 3.0], [1.0, 2.0, 3.0])
    assert verdict(flat).startswith("No reliable difference")


@settings(max_examples=60, deadline=None)
@given(
    st.lists(
        st.tuples(st.floats(-1e3, 1e3), st.floats(-1e3, 1e3)), min_size=2, max_size=15
    )
)
def test_paired_t_properties(pairs: list) -> None:
    a = [p[0] for p in pairs]
    b = [p[1] for p in pairs]
    r = paired_t_test(a, b)
    assert 0.0 <= r.p_value <= 1.0
    assert r.ci_lower <= r.difference <= r.ci_upper
    assert r.significant == (r.p_value < r.alpha)
    # The interval excludes zero exactly when the test rejects (same t distribution), within rounding.
    if r.statistic is not None and abs(r.p_value - r.alpha) > 1e-6:
        assert (r.ci_lower > 0 or r.ci_upper < 0) == r.significant
