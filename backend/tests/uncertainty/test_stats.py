"""Statistics helpers: fixtures computed by hand (or from the textbook formula), plus properties."""

import random

import pytest

from src.uncertainty.stats import (
    bootstrap_intervals,
    mean_sorted,
    percentile,
    percentile_sorted,
    wilson_interval,
)


@pytest.mark.parametrize(
    "successes, n, low, high",
    [
        # Standard 95 % Wilson values (textbook formula, z = 1.96; checked independently of the code).
        (5, 10, 0.2366, 0.7634),
        (3, 10, 0.1078, 0.6032),
        (2, 10, 0.0567, 0.5098),
        (7, 10, 0.3968, 0.8922),
        (0, 10, 0.0, 0.2775),
        (10, 10, 0.7225, 1.0),
        (30, 30, 0.8865, 1.0),
        (50, 100, 0.4038, 0.5962),
    ],
)
def test_wilson_interval_matches_hand_values(successes, n, low, high):
    got_low, got_high = wilson_interval(successes, n)
    assert got_low == pytest.approx(low, abs=6e-5)
    assert got_high == pytest.approx(high, abs=6e-5)


def test_wilson_stays_inside_zero_one_and_is_symmetric():
    for n in (1, 5, 30, 200):
        for x in range(n + 1):
            low, high = wilson_interval(x, n)
            assert 0.0 <= low <= x / n <= high <= 1.0
            mirror_low, mirror_high = wilson_interval(n - x, n)
            assert low == pytest.approx(1 - mirror_high)
            assert high == pytest.approx(1 - mirror_low)


def test_wilson_rejects_impossible_input():
    with pytest.raises(ValueError):
        wilson_interval(1, 0)
    with pytest.raises(ValueError):
        wilson_interval(11, 10)
    with pytest.raises(ValueError):
        wilson_interval(-1, 10)


def test_about_97_conditions_are_needed_for_a_ten_point_half_width_at_worst():
    # Strategy section 5.7: the worst case (p = 0.5) needs about 97 valid conditions.
    def half(n):
        low, high = wilson_interval(n // 2, n)
        return (high - low) / 2

    assert half(100) <= 0.10
    assert half(90) > 0.10


@pytest.mark.parametrize(
    "values, q, expected",
    [
        ([1, 2, 3, 4], 0.5, 2.5),  # position 1.5
        ([1, 2, 3, 4], 0.0, 1),
        ([1, 2, 3, 4], 1.0, 4),
        ([1, 2, 3, 4], 0.25, 1.75),  # position 0.75
        ([10, 20], 0.95, 19.5),  # position 0.95
        ([7], 0.3, 7),
        ([-5, -5, -5, -0.2, -0.2, 0.5, 0.5, 0.5, 0.5, 0.5], 0.5, 0.15),
    ],
)
def test_percentile_is_linear_interpolation(values, q, expected):
    assert percentile(values, q) == pytest.approx(expected)


def test_percentile_rejects_bad_input():
    with pytest.raises(ValueError):
        percentile([], 0.5)
    with pytest.raises(ValueError):
        percentile([1, 2], 1.5)


def test_mean_sorted():
    assert mean_sorted([1, 2, 3, 6]) == 3


def test_bootstrap_of_a_constant_sample_is_degenerate():
    out = bootstrap_intervals([4.0] * 12, {"mean": mean_sorted}, random.Random(1), 200)
    assert out["mean"] == (4.0, 4.0)


def test_bootstrap_of_two_points_spans_them():
    # Resample means of [0, 10] are 0, 5 or 10 with probability 1/4, 1/2, 1/4: the central 95 % is [0, 10].
    out = bootstrap_intervals(
        [0.0, 10.0], {"mean": mean_sorted}, random.Random(3), 2000
    )
    assert out["mean"] == (0.0, 10.0)


def test_bootstrap_is_deterministic_for_a_seed_and_varies_with_it():
    values = [float(v) for v in range(1, 41)]
    stats = {"mean": mean_sorted, "median": lambda s: percentile_sorted(s, 0.5)}
    a = bootstrap_intervals(values, stats, random.Random(9), 500)
    b = bootstrap_intervals(values, stats, random.Random(9), 500)
    c = bootstrap_intervals(values, stats, random.Random(10), 500)
    assert a == b
    assert a != c


def test_bootstrap_interval_brackets_the_sample_mean_and_is_ordered():
    values = [float(v % 7) for v in range(60)]
    low, high = bootstrap_intervals(
        values, {"mean": mean_sorted}, random.Random(5), 1000
    )["mean"]
    assert low <= sum(values) / len(values) <= high


def test_bootstrap_rejects_bad_input():
    with pytest.raises(ValueError):
        bootstrap_intervals([], {"mean": mean_sorted}, random.Random(1))
    with pytest.raises(ValueError):
        bootstrap_intervals([1.0], {"mean": mean_sorted}, random.Random(1), resamples=0)
    with pytest.raises(ValueError):
        bootstrap_intervals([1.0], {"mean": mean_sorted}, random.Random(1), level=1.0)
