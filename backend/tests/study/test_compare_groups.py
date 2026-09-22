"""Focused tests for src/study/validation.py's statistical comparison.

_compare_groups moved from a normal-distribution (z) p-value approximation
to a proper Welch's t-test (Student's t-distribution with Welch-Satterthwaite
degrees of freedom), because this project's Monte Carlo studies commonly run
with small seed counts (n=5 is run_statistical_validation's own default, and
what Phase A's multi-seed delay study used) where a z-approximation is
anti-conservative. These tests cover:
  - the underlying t-distribution p-value against known textbook critical
    values (numerical correctness of the regularized-incomplete-beta path),
  - small-n behaviour of _compare_groups itself,
  - that large-n behaviour is materially unchanged (the two methods
    converge), and
  - the pre-existing edge-case contract (n<2, zero-variance groups).
"""

import math

from src.study.validation import (
    _calculate_stats,
    _compare_groups,
    _student_t_two_tailed_p_value,
)

# ── _student_t_two_tailed_p_value: numerical correctness ────────────────────
#
# Standard two-tailed alpha=0.05 critical t-values, as published in any
# statistics textbook's t-table. Feeding each (df, critical value) pair in
# should return a p-value of ~0.05 -- this is an independent check of the
# regularized incomplete beta implementation, not of _compare_groups' own
# logic.
_KNOWN_CRITICAL_VALUES = {
    1: 12.706,
    2: 4.303,
    3: 3.182,
    4: 2.776,
    5: 2.571,
    8: 2.306,
    10: 2.228,
    30: 2.042,
    120: 1.980,
}


def test_t_distribution_matches_known_critical_values() -> None:
    for df, t_crit in _KNOWN_CRITICAL_VALUES.items():
        p_value = _student_t_two_tailed_p_value(t_crit, df)
        assert abs(p_value - 0.05) < 0.001, (
            f"df={df}: expected p~=0.05 at the textbook critical value "
            f"{t_crit}, got {p_value}"
        )


def test_t_distribution_at_zero_statistic_is_certainty() -> None:
    assert _student_t_two_tailed_p_value(0.0, 5) == 1.0


def test_t_distribution_converges_to_the_normal_approximation_at_large_df() -> None:
    # z=1.96 is the normal-distribution two-tailed 0.05 critical value; at
    # very large df the t-distribution should reproduce it closely, which is
    # exactly the "does not change behaviour for studies with many seeds"
    # property this module's docstring claims.
    p_value = _student_t_two_tailed_p_value(1.96, 100_000)
    assert abs(p_value - 0.05) < 0.001


def test_t_distribution_is_monotonically_decreasing_in_t() -> None:
    df = 5.0
    p_small = _student_t_two_tailed_p_value(1.0, df)
    p_large = _student_t_two_tailed_p_value(5.0, df)
    assert p_large < p_small


# ── _compare_groups: pre-existing contract, preserved ────────────────────────


def test_compare_groups_requires_at_least_two_samples_per_group() -> None:
    result = _compare_groups([1.0], [1.0, 2.0, 3.0])
    assert result == {"cohensD": 0.0, "pValue": None, "significant": False}


def test_compare_groups_identical_distributions_are_not_significant() -> None:
    values = [10.0, 10.0, 10.0, 10.0, 10.0]
    result = _compare_groups(values, list(values))
    assert result["cohensD"] == 0.0
    assert result["pValue"] == 1.0
    assert result["significant"] is False


def test_compare_groups_clearly_different_distributions_are_significant() -> None:
    # Large, tight, well-separated groups -- should be significant under any
    # reasonable methodology (z or t).
    a = [10.0, 10.1, 9.9, 10.0, 10.1, 9.9, 10.0, 10.1, 9.9, 10.0]
    b = [20.0, 20.1, 19.9, 20.0, 20.1, 19.9, 20.0, 20.1, 19.9, 20.0]
    result = _compare_groups(a, b)
    assert result["significant"] is True
    assert result["pValue"] < 0.001
    assert result["cohensD"] < -5  # a is far below b


def test_compare_groups_zero_variance_groups_return_p_one() -> None:
    result = _compare_groups([5.0, 5.0, 5.0], [5.0, 5.0, 5.0])
    assert result["pValue"] == 1.0
    assert result["significant"] is False


# ── _compare_groups: small-n (n=5) behaviour, the case this fix targets ──────


def test_compare_groups_n5_reports_degrees_of_freedom() -> None:
    a = [15.96, 15.38, 10.71, 12.04, 15.77]  # Phase A signal delays, 360 veh/h
    b = [15.08, 17.29, 15.09, 13.61, 14.30]  # Phase A roundabout delays, 360 veh/h
    result = _compare_groups(a, b)
    assert "degreesOfFreedom" in result
    # Welch-Satterthwaite df for two n=5 samples is at most n_a+n_b-2=8 and
    # at least min(n_a, n_b)-1=4.
    assert 4.0 <= result["degreesOfFreedom"] <= 8.0


def test_compare_groups_n5_p_value_is_more_conservative_than_the_old_z_formula() -> (
    None
):
    """Regression guard: at n=5 the new t-based p-value must not be smaller
    (more "significant") than the z-approximation this replaced would have
    given for the same data -- that was the actual defect being fixed."""
    a = [15.96, 15.38, 10.71, 12.04, 15.77]
    b = [15.08, 17.29, 15.09, 13.61, 14.30]

    n_a, n_b = len(a), len(b)
    mean_a, mean_b = sum(a) / n_a, sum(b) / n_b
    var_a = sum((x - mean_a) ** 2 for x in a) / (n_a - 1)
    var_b = sum((x - mean_b) ** 2 for x in b) / (n_b - 1)
    se = math.sqrt(var_a / n_a + var_b / n_b)
    z = abs(mean_a - mean_b) / se
    old_z_p_value = 2.0 * (0.5 * math.erfc(z / math.sqrt(2)))

    new_result = _compare_groups(a, b)

    assert new_result["pValue"] >= old_z_p_value
    # Cohen's d must be unchanged by the methodology fix -- only the
    # significance test changed, per the "preserve effect-size behaviour"
    # requirement.
    n = len(a)
    pooled_std = math.sqrt((var_a + var_b) / 2.0)
    expected_cohens_d = round((mean_a - mean_b) / pooled_std, 3)
    assert new_result["cohensD"] == expected_cohens_d
    del n  # only used for readability of the surrounding derivation


def test_compare_groups_large_n_p_value_is_close_to_the_old_z_formula() -> None:
    """At large n the fix must not materially change results -- t and z
    converge, so existing large-sample studies keep behaving the same."""
    import random

    rng = random.Random(0)
    a = [rng.gauss(10.0, 1.0) for _ in range(500)]
    b = [rng.gauss(10.5, 1.0) for _ in range(500)]

    n_a, n_b = len(a), len(b)
    mean_a, mean_b = sum(a) / n_a, sum(b) / n_b
    var_a = sum((x - mean_a) ** 2 for x in a) / (n_a - 1)
    var_b = sum((x - mean_b) ** 2 for x in b) / (n_b - 1)
    se = math.sqrt(var_a / n_a + var_b / n_b)
    z = abs(mean_a - mean_b) / se
    old_z_p_value = 2.0 * (0.5 * math.erfc(z / math.sqrt(2)))

    new_result = _compare_groups(a, b)

    assert abs(new_result["pValue"] - old_z_p_value) < 0.005


# ── _calculate_stats: untouched by this fix, spot-checked for no regression ──


def test_calculate_stats_is_unchanged() -> None:
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    result = _calculate_stats(values)
    assert result["mean"] == 3.0
    assert result["min"] == 1.0
    assert result["max"] == 5.0

    # ci95 still uses the pre-existing z=1.96 formula, computed from the
    # *unrounded* std/mean -- out of scope for this fix (see Phase B report:
    # documented as a residual limitation for a later phase rather than
    # changed here).
    n = len(values)
    mean = sum(values) / n
    variance = sum((x - mean) ** 2 for x in values) / (n - 1)
    std = math.sqrt(variance)
    expected_ci95 = round(1.96 * (std / math.sqrt(n)), 2)
    assert result["ci95"] == expected_ci95
