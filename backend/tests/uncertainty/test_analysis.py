"""Analysis core: a planted dataset whose every number was computed by hand, plus the eligibility,
exclusion, determinism and ordering rules of strategy section 5.4-5.7."""

import copy
import math
import random

import pytest

from src.uncertainty import ConditionResult, analyze, classify, result_fingerprint
from src.uncertainty.analysis import LIMITATIONS, REAL_WORLD_VALIDITY

ALTS = ["base", "A", "B"]


def _planted():
    """10 conditions, 3 alternatives, r = 1, tie tolerance tau = 1.0 s.

    i0-4: base 20, A 15,   B 20.5     (A wins by 5, B ties at +0.5)
    i5-7: base 30, A 29.5, B 25       (A ties at -0.5, B wins by 5)
    i8-9: base 25, A 30,   B 24.8     (A loses by 5, B ties at -0.2)
    """
    rows = [(20, 15, 20.5)] * 5 + [(30, 29.5, 25)] * 3 + [(25, 30, 24.8)] * 2
    return [
        ConditionResult(i, {"f": i}, {"base": [b], "A": [a], "B": [c]})
        for i, (b, a, c) in enumerate(rows)
    ]


def _run(conditions, **kw):
    kw.setdefault("alternatives", ALTS)
    kw.setdefault("baseline", "base")
    kw.setdefault("replications", 1)
    kw.setdefault("factor_ids", ["f"])
    kw.setdefault("tie_tolerance", 1.0)
    kw.setdefault("seed", 4)
    return analyze(conditions, **kw)


# --- the planted dataset, every number by hand ---------------------------------------------------


def test_win_tie_loss_counts_and_wilson_intervals():
    out = _run(_planted())["alternatives"]
    a, b = out["A"]["comparison"], out["B"]["comparison"]
    # A: 5 wins, 3 ties, 2 losses of 10
    assert (a["win"]["count"], a["tie"]["count"], a["loss"]["count"]) == (5, 3, 2)
    assert a["win"]["ci"] == pytest.approx([0.2366, 0.7634], abs=6e-5)
    assert a["tie"]["ci"] == pytest.approx([0.1078, 0.6032], abs=6e-5)
    assert a["loss"]["ci"] == pytest.approx([0.0567, 0.5098], abs=6e-5)
    # B: 3 wins, 7 ties, 0 losses of 10
    assert (b["win"]["count"], b["tie"]["count"], b["loss"]["count"]) == (3, 7, 0)
    assert b["win"]["ci"] == pytest.approx([0.1078, 0.6032], abs=6e-5)
    assert b["tie"]["ci"] == pytest.approx([0.3968, 0.8922], abs=6e-5)
    assert b["loss"]["ci"] == pytest.approx([0.0, 0.2775], abs=6e-5)
    # a tie is a result: win + tie + loss is the whole valid sample
    for block in (a, b):
        assert sum(block[k]["count"] for k in ("win", "tie", "loss")) == 10


def test_paired_difference_point_estimates():
    out = _run(_planted())["alternatives"]
    a = out["A"]["comparison"]["difference"]
    b = out["B"]["comparison"]["difference"]
    # A: D = [-5]*5 + [-0.5]*3 + [5]*2 -> mean -1.65, median -2.75, p5 -5, p95 5
    assert a["mean"]["value"] == pytest.approx(-1.65)
    assert a["median"]["value"] == pytest.approx(-2.75)
    assert a["p5"]["value"] == pytest.approx(-5.0)
    assert a["p95"]["value"] == pytest.approx(5.0)
    # B: D = [0.5]*5 + [-5]*3 + [-0.2]*2 -> mean -1.29, median 0.15, p5 -5, p95 0.5
    assert b["mean"]["value"] == pytest.approx(-1.29)
    assert b["median"]["value"] == pytest.approx(0.15)
    assert b["p5"]["value"] == pytest.approx(-5.0)
    assert b["p95"]["value"] == pytest.approx(0.5)


def test_bootstrap_intervals_bracket_the_point_estimates():
    for alt in ("A", "B"):
        diff = _run(_planted())["alternatives"][alt]["comparison"]["difference"]
        for stat in ("mean", "median", "p5", "p95"):
            low, high = diff[stat]["ci"]
            assert low <= diff[stat]["value"] <= high


def test_regret_and_preference_share():
    out = _run(_planted())["alternatives"]
    # regret = Y(i, a) - min over {base, A, B}
    assert out["base"]["regret"] == {"mean": 4.04, "p95": 5.0, "sampleMax": 5.0}
    assert out["A"]["regret"] == {"mean": 2.39, "p95": 5.2, "sampleMax": 5.2}
    assert out["B"]["regret"] == {"mean": 2.75, "p95": 5.5, "sampleMax": 5.5}
    # preference share: within tau = 1.0 of the best alternative; shares are not ranked
    assert out["base"]["preferenceShare"] == 0.2
    assert out["A"]["preferenceShare"] == 0.5
    assert out["B"]["preferenceShare"] == 0.5
    assert out["base"]["meanOutcome"] == 24.0
    assert out["base"]["isBaseline"] and "comparison" not in out["base"]


def test_counts_keep_conditions_replications_and_runs_separate():
    counts = _run(_planted())["counts"]
    assert counts == {
        "conditions": 10,
        "validConditions": 10,
        "alternatives": 3,
        "replications": 1,
        "totalRuns": 30,
    }


def test_every_output_carries_limitations_and_real_world_validity():
    out = _run(_planted())
    assert out["realWorldValidity"] == REAL_WORLD_VALIDITY
    assert out["realWorldValidity"].startswith("None")
    assert out["limitations"] == LIMITATIONS and len(out["limitations"]) >= 5
    assert out["tolerance"] == {"kind": "absolute", "value": 1.0}


# --- tolerance rule -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "alt, base, tau, expected",
    [
        (15, 20, 1.0, "win"),
        (19.0, 20, 1.0, "tie"),  # |D| = tau is a tie (win needs D < -tau)
        (18.99, 20, 1.0, "win"),
        (21.0, 20, 1.0, "tie"),
        (21.01, 20, 1.0, "loss"),
        (20, 20, 0.0, "tie"),
        (19.9, 20, 0.0, "win"),
    ],
)
def test_explicit_tolerance_classification(alt, base, tau, expected):
    assert classify(alt, base, tau) == expected


@pytest.mark.parametrize(
    "alt, base, expected",
    [
        (20.5, 20.0, "tie"),  # within 1 s
        (105.0, 100.0, "tie"),  # within 5 % of the larger
        (94.0, 100.0, "win"),
        (110.0, 100.0, "loss"),
    ],
)
def test_default_tolerance_uses_the_existing_two_part_rule(alt, base, expected):
    assert classify(alt, base, None) == expected


# --- exclusions -----------------------------------------------------------------------------------


def _uniform_conditions(n):
    """n conditions where A beats base by 10 s in every one (stratum index = condition index)."""
    return [
        ConditionResult(i, {"f": i}, {"base": [50.0, 50.0], "A": [40.0, 40.0]})
        for i in range(n)
    ]


def _two_alt(conditions, **kw):
    kw.setdefault("seed", 1)
    return analyze(
        conditions,
        alternatives=["base", "A"],
        baseline="base",
        replications=2,
        factor_ids=["f"],
        tie_tolerance=1.0,
        **kw,
    )


def test_excluded_condition_is_removed_for_every_alternative_and_counted():
    conds = _uniform_conditions(40)
    conds[3] = ConditionResult(3, {"f": 3}, {"base": [50.0, 50.0]})  # A missing
    conds[5] = ConditionResult(
        5, {"f": 5}, {"base": [50.0, math.nan], "A": [40.0, 40.0]}
    )
    conds[7] = ConditionResult(7, {"f": 7}, {}, exclusion="vehicle_limit")
    conds[9] = ConditionResult(9, {"f": 9}, {}, exclusion="validation_failed")
    out = _two_alt(conds)
    assert out["counts"]["conditions"] == 40
    assert out["counts"]["validConditions"] == 36
    assert (
        out["counts"]["totalRuns"] == 40 * 2 * 2
    )  # runs are reported for all N, valid or not
    assert out["exclusions"]["byReason"] == {
        "missing_run": 1,
        "non_finite": 1,
        "validation_failed": 1,
        "vehicle_limit": 1,
    }
    assert out["exclusions"]["overallShare"] == 0.1
    # the win count uses valid conditions only, and every one of them is a win
    assert out["alternatives"]["A"]["comparison"]["win"]["count"] == 36


def test_unknown_exclusion_reason_is_an_error():
    conds = _uniform_conditions(30)
    conds[0] = ConditionResult(0, {"f": 0}, {}, exclusion="gremlins")
    with pytest.raises(ValueError, match="gremlins"):
        _two_alt(conds)


def test_all_conditions_excluded_gives_an_exploratory_result_without_a_comparison():
    conds = [
        ConditionResult(i, {"f": i}, {}, exclusion="run_failed") for i in range(12)
    ]
    out = _two_alt(conds)
    assert out["counts"]["validConditions"] == 0
    assert out["eligibility"]["class"] == "exploratory"
    assert out["alternatives"]["A"]["comparison"] is None


# --- eligibility ----------------------------------------------------------------------------------


def _criteria(out):
    return {c["id"]: c["passed"] for c in out["eligibility"]["criteria"]}


@pytest.mark.parametrize(
    "n, expected",
    [(29, "exploratory"), (30, "eligible"), (100, "eligible")],
)
def test_sample_size_classes(n, expected):
    # Clean conditions with N >= 30 satisfy all 5 criteria and promote to eligible.
    out = _two_alt(_uniform_conditions(n))
    assert out["eligibility"]["class"] == expected


def test_stability_passing_promotes_to_eligible():
    out = _two_alt(_uniform_conditions(40))
    criteria = _criteria(out)
    assert criteria["precision"] is True
    assert criteria["stability"] is True
    assert criteria["replications"] is True
    assert criteria["exclusions"] is True
    assert criteria["predeclaration"] is True
    assert out["eligibility"]["class"] == "eligible"
    stab = out["stability"]
    assert stab["passed"] is True
    assert stab["splitsEvaluated"] == 20
    assert stab["splitsPassed"] == 20
    assert stab["threshold"] == 18
    assert "20/20 random splits" in stab["detail"]


def test_stability_failing_when_splits_diverge():
    # 40 conditions where half win by 20 and half lose by 20:
    # in random splits, the median D sign flips and proportions diverge, failing stability.
    conds = [
        ConditionResult(
            i,
            {"f": i},
            {"base": [50.0, 50.0], "A": [30.0, 30.0] if i < 20 else [70.0, 70.0]},
        )
        for i in range(40)
    ]
    out = _two_alt(conds)
    criteria = _criteria(out)
    assert criteria["stability"] is False
    assert out["stability"]["passed"] is False
    assert out["stability"]["splitsPassed"] < 18
    assert out["eligibility"]["class"] == "indicative"


def test_stability_insufficient_data():
    # Fewer than 30 conditions: stability is not assessed (passed is None).
    out_24 = _two_alt(_uniform_conditions(24))
    assert out_24["eligibility"]["class"] == "exploratory"
    assert out_24["stability"]["passed"] is None
    assert _criteria(out_24)["stability"] is None
    assert "fewer than 30 valid conditions" in out_24["stability"]["detail"]

    # All conditions excluded: 0 valid conditions
    all_excluded = [
        ConditionResult(i, {"f": i}, {}, exclusion="run_failed") for i in range(12)
    ]
    out_0 = _two_alt(all_excluded)
    assert out_0["stability"]["passed"] is None
    assert "no valid conditions" in out_0["stability"]["detail"]


def test_variance_decomposition_in_analysis_replicated_and_unreplicated():
    # Replicated (r = 2) with known values:
    # 2 conditions: c0 has base [10, 12] and A [20, 22]
    # c1 has base [20, 22] and A [30, 32]
    conds = [
        ConditionResult(0, {"f": 0}, {"base": [10.0, 12.0], "A": [20.0, 22.0]}),
        ConditionResult(1, {"f": 1}, {"base": [20.0, 22.0], "A": [30.0, 32.0]}),
    ]
    out = analyze(
        conds,
        alternatives=["base", "A"],
        baseline="base",
        replications=2,
        factor_ids=["f"],
    )
    v_base = out["alternatives"]["base"]["varianceSplit"]
    assert v_base is not None
    assert v_base["between"] == pytest.approx(100.0)
    assert v_base["within"] == pytest.approx(4.0)
    assert v_base["betweenShare"] == pytest.approx(100.0 / 104.0, abs=1e-5)
    assert out["varianceSplit"]["base"] == v_base
    assert out["varianceSplit"]["A"] == out["alternatives"]["A"]["varianceSplit"]

    # Difference variance split:
    # D for c0: [20-10, 22-12] = [10, 10]; D for c1: [30-20, 32-22] = [10, 10]
    # D is constant 10 everywhere -> zero variance for difference
    diff_v = out["alternatives"]["A"]["comparison"]["difference"]["varianceSplit"]
    assert diff_v is not None
    assert diff_v["total"] == 0.0
    assert diff_v["betweenShare"] == 0.0
    assert diff_v["withinShare"] == 0.0

    # Unreplicated (r = 1): variance decomposition cannot be estimated
    one_rep = [
        ConditionResult(0, {"f": 0}, {"base": [10.0], "A": [20.0]}),
        ConditionResult(1, {"f": 1}, {"base": [20.0], "A": [30.0]}),
    ]
    out_1 = analyze(
        one_rep,
        alternatives=["base", "A"],
        baseline="base",
        replications=1,
        factor_ids=["f"],
    )
    assert out_1["varianceSplit"] is None
    assert out_1["alternatives"]["base"]["varianceSplit"] is None
    assert out_1["alternatives"]["A"]["varianceSplit"] is None
    assert (
        out_1["alternatives"]["A"]["comparison"]["difference"]["varianceSplit"] is None
    )


def test_variance_decomposition_degenerate_zero_variance_in_analysis():
    # All outcomes identical across conditions and replications
    conds = _uniform_conditions(30)
    out = _two_alt(conds)
    v_base = out["alternatives"]["base"]["varianceSplit"]
    assert v_base is not None
    assert v_base["total"] == 0.0
    assert v_base["betweenShare"] == 0.0
    assert v_base["withinShare"] == 0.0


def test_stability_and_variance_deterministic():
    conds = _uniform_conditions(35)
    res1 = _two_alt(conds, seed=42)
    res2 = _two_alt(copy.deepcopy(conds), seed=42)
    assert res1["stability"] == res2["stability"]
    assert res1["varianceSplit"] == res2["varianceSplit"]
    assert result_fingerprint(res1) == result_fingerprint(res2)


def test_precision_criterion_uses_the_wilson_half_width():
    # 30 straight wins: half-widths 0.057 -> passes. A 50/50 split of 40 wins/losses: ~0.15 -> fails.
    assert _criteria(_two_alt(_uniform_conditions(30)))["precision"] is True
    mixed = []
    for i in range(40):
        a = 40.0 if i % 2 == 0 else 60.0
        mixed.append(ConditionResult(i, {"f": i}, {"base": [50.0, 50.0], "A": [a, a]}))
    assert _criteria(_two_alt(mixed))["precision"] is False


def test_replication_criterion():
    one_rep = [
        ConditionResult(i, {"f": i}, {"base": [50.0], "A": [40.0]}) for i in range(40)
    ]
    out = analyze(
        one_rep,
        alternatives=["base", "A"],
        baseline="base",
        replications=1,
        factor_ids=["f"],
        tie_tolerance=1.0,
    )
    assert _criteria(out)["replications"] is False
    assert _criteria(_two_alt(_uniform_conditions(40)))["replications"] is True


def test_overall_exclusion_limit_is_ten_percent():
    conds = _uniform_conditions(100)
    for i in range(0, 100, 10):  # 10 of 100: exactly at the limit, spread across strata
        conds[i] = ConditionResult(i, {"f": i}, {}, exclusion="run_failed")
    assert _criteria(_two_alt(conds))["exclusions"] is True
    conds[1] = ConditionResult(1, {"f": 1}, {}, exclusion="run_failed")  # 11 of 100
    assert _criteria(_two_alt(conds))["exclusions"] is False


def test_stratum_exclusion_limit_is_twenty_percent_even_when_overall_is_small():
    conds = _uniform_conditions(100)
    # factor f stratum = condition index: bucket 0 holds conditions 0-19; drop 5 of them (25 %)
    for i in range(5):
        conds[i] = ConditionResult(i, {"f": i}, {}, exclusion="timeout")
    out = _two_alt(conds)
    assert out["exclusions"]["overallShare"] == 0.05
    assert out["exclusions"]["worstStratumShare"] == 0.25
    assert _criteria(out)["exclusions"] is False


def test_predeclaration_criterion():
    assert _criteria(_two_alt(_uniform_conditions(40)))["predeclaration"] is True
    declared = _two_alt(_uniform_conditions(40), predeclared=False)
    assert _criteria(declared)["predeclaration"] is False


# --- determinism, order and input checks --------------------------------------------------------


def test_same_input_same_fingerprint_and_arrival_order_does_not_matter():
    conds = _planted()
    first = result_fingerprint(_run(conds))
    assert first == result_fingerprint(_run(copy.deepcopy(conds)))
    shuffled = list(conds)
    random.Random(0).shuffle(shuffled)
    assert first == result_fingerprint(_run(shuffled))


def test_seed_changes_only_the_bootstrap_intervals():
    one = _run(_planted(), seed=1)["alternatives"]["A"]["comparison"]["difference"]
    two = _run(_planted(), seed=2)["alternatives"]["A"]["comparison"]["difference"]
    for stat in ("mean", "median", "p5", "p95"):
        assert one[stat]["value"] == two[stat]["value"]
    assert result_fingerprint(_run(_planted(), seed=1)) != result_fingerprint(
        _run(_planted(), seed=2)
    )


def test_replications_are_averaged_inside_a_condition():
    conds = [
        ConditionResult(i, {"f": i}, {"base": [50.0, 52.0], "A": [40.0, 44.0]})
        for i in range(30)
    ]
    out = _two_alt(conds)
    assert out["alternatives"]["base"]["meanOutcome"] == 51.0
    assert out["alternatives"]["A"]["meanOutcome"] == 42.0
    assert out["alternatives"]["A"]["comparison"]["difference"]["mean"]["value"] == -9.0


def test_bad_inputs_are_rejected():
    conds = _uniform_conditions(30)

    def call(**kw):
        body = {
            "alternatives": ["base", "A"],
            "baseline": "base",
            "replications": 2,
            "factor_ids": ["f"],
        }
        body.update(kw)
        return analyze(conds, **body)

    with pytest.raises(ValueError, match="baseline"):
        call(baseline="Z")
    with pytest.raises(ValueError, match="two alternatives"):
        call(alternatives=["base"])
    with pytest.raises(ValueError, match="unique"):
        call(alternatives=["base", "base"])
    with pytest.raises(ValueError, match="stratum"):
        call(factor_ids=["nope"])
    with pytest.raises(ValueError, match="0..N-1"):
        _two_alt(conds[1:])
    with pytest.raises(ValueError, match="no conditions"):
        _two_alt([])
