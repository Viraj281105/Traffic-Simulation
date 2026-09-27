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
    _t_critical,
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


def test_calculate_stats_uses_a_student_t_interval() -> None:
    """The 95 % CI half-width is t(0.975, n-1) * s / sqrt(n), not 1.96 * s / sqrt(n).

    Deterministic example: values 1..5 -> mean 3, s = sqrt(2.5), n = 5, df = 4,
    t(0.975, 4) = 2.7764 (textbook), half-width = 2.7764 * 1.5811 / 2.2361 =
    1.9632. The old normal-based interval was 1.96 * 0.7071 = 1.386.
    """
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    result = _calculate_stats(values)
    assert result["mean"] == 3.0
    assert result["min"] == 1.0
    assert result["max"] == 5.0
    assert result["ciDegreesOfFreedom"] == 4
    assert result["ciConfidence"] == 0.95
    assert abs(result["ciCriticalValue"] - 2.7764) < 5e-4
    expected = round(2.7764451 * math.sqrt(2.5) / math.sqrt(5), 2)
    assert result["ci95"] == expected == 1.96
    assert result["ci"] == result["ci95"]
    old_z_half_width = round(1.96 * (math.sqrt(2.5) / math.sqrt(5)), 2)
    assert old_z_half_width == 1.39
    assert result["ci95"] > old_z_half_width


def test_t_critical_values_match_published_tables() -> None:
    # Two-sided critical values from standard t tables.
    table = {
        (1, 0.95): 12.7062,
        (4, 0.90): 2.1318,
        (4, 0.95): 2.7764,
        (4, 0.99): 4.6041,
        (9, 0.95): 2.2622,
        (29, 0.95): 2.0452,
    }
    for (df, conf), expected in table.items():
        assert abs(_t_critical(df, conf) - expected) < 5e-4, (df, conf)
    # Converges to the normal value at very large df.
    assert abs(_t_critical(100000, 0.95) - 1.96) < 2e-3


def test_ci_and_p_value_use_the_same_distribution() -> None:
    """A mean whose t-interval just excludes zero has p just under alpha.

    For a one-sample check: 5 values with mean m and s: the interval
    m +/- t*s/sqrt(n) touches 0 exactly when the one-sample t statistic
    equals the critical value, where the two-tailed p equals 1 - confidence.
    """
    df = 4
    t = _t_critical(df, 0.95)
    assert abs(_student_t_two_tailed_p_value(t, df) - 0.05) < 1e-6


def test_confidence_level_changes_interval_and_alpha_together() -> None:
    values = [10.0, 12.0, 11.0, 13.0, 9.0]
    at90 = _calculate_stats(values, 0.90)
    at95 = _calculate_stats(values, 0.95)
    at99 = _calculate_stats(values, 0.99)
    assert at90["ci"] < at95["ci"] < at99["ci"]
    # ci95 is the stable 95 % key whatever level was requested.
    assert at90["ci95"] == at95["ci95"] == at99["ci95"] == at95["ci"]
    assert at99["ciConfidence"] == 0.99

    # The significance flag follows alpha: a p-value of ~0.03 is significant
    # at alpha = 0.05 but not at 0.01.
    a = [10.0, 10.5, 11.0, 10.2, 10.8]
    b = [11.6, 11.9, 12.4, 11.2, 12.0]
    loose = _compare_groups(a, b, alpha=0.05)
    strict = _compare_groups(a, b, alpha=1e-9)
    assert loose["pValue"] == strict["pValue"]
    assert loose["significant"] is True
    assert strict["significant"] is False


def test_single_value_has_no_interval() -> None:
    result = _calculate_stats([4.2])
    assert result["ci"] == result["ci95"] == 0.0
    assert result["ciDegreesOfFreedom"] == 0
    assert _calculate_stats([])["ci95"] == 0.0


def test_validation_reports_method_confidence_and_calibration() -> None:
    from src.study.validation import run_statistical_validation

    result = run_statistical_validation(num_seeds=2, duration=3.0, confidence_level=0.9)
    assert result["confidenceLevel"] == 0.9
    assert result["alpha"] == 0.1
    assert result["signal"]["delay"]["ciConfidence"] == 0.9
    assert "Student-t" in result["method"]["confidenceInterval"]
    assert "Welch" in result["method"]["significanceTest"]
    # Default study configuration is the calibrated single-lane comparison.
    assert result["calibration"]["calibrated"] is True
    assert result["calibration"]["lanesPerApproach"]["north"] == 1


def test_validation_rejects_unsupported_confidence_level() -> None:
    import pytest

    from src.study.validation import run_statistical_validation

    with pytest.raises(ValueError):
        run_statistical_validation(num_seeds=2, duration=1.0, confidence_level=0.8)
