"""The sweep verdict is read from the measured data, never assumed.

Regression for: the verdict used to say "below the crossover the roundabout
had the lower delay; at or above it the signal did" whenever a crossover
existed, whichever way the data actually went; the crossover was found from
raw delay differences that ignored the tie band; and points with too few
vehicles (or truncated demand) were still awarded a winner.
"""

from typing import Any, Dict, List

from src.study.report_generator import (
    _summarize_sweep_verdict,
    _summarize_validation_evidence,
    generate_study_report_csv,
    generate_study_report_json,
)
from src.study.tolerances import delays_are_tied, tie_tolerance
from src.study.volume_sweep import find_delay_crossover


def _run(winner: str, rate: float) -> Dict[str, Any]:
    return {"arrivalRate": rate, "winner": winner}


def _sweep(winners: List[str], crossover: Any = None) -> Dict[str, Any]:
    rates = [round(0.1 * (i + 1), 1) for i in range(len(winners))]
    runs = [_run(w, r) for w, r in zip(winners, rates)]
    found = find_delay_crossover(runs) if crossover == "auto" else None
    return {
        "runs": runs,
        "curves": {
            "crossoverArrivalRate": found["upperRate"] if found else None,
            "crossoverHourlyVolume": int(found["upperRate"] * 3600) if found else None,
        },
    }


# ── direction is read from the data ─────────────────────────────────────────


def test_reversal_roundabout_then_signal() -> None:
    verdict = _summarize_sweep_verdict(
        _sweep(["roundabout", "roundabout", "signal"], "auto")
    )
    assert verdict["directional"] == "reversal"
    text = verdict["text"]
    assert (
        "Below that point the roundabout had the lower measured delay (2 of 3" in text
    )
    assert "at or above it the fixed-time signal did (1 of 3" in text


def test_reversal_signal_then_roundabout_is_not_described_the_other_way_round() -> None:
    """The bug: this data used to be reported as 'roundabout better below'."""
    verdict = _summarize_sweep_verdict(
        _sweep(["signal", "signal", "roundabout"], "auto")
    )
    assert verdict["directional"] == "reversal"
    text = verdict["text"]
    assert (
        "Below that point the fixed-time signal had the lower measured delay (2 of 3"
        in text
    )
    assert "at or above it the roundabout did (1 of 3" in text
    assert "Below that point the roundabout" not in text


def test_signal_only_direction() -> None:
    verdict = _summarize_sweep_verdict(_sweep(["signal", "signal", "signal"]))
    assert verdict["directional"] == "signal"
    assert "fixed-time signal had the lower measured delay at 3 of 3" in verdict["text"]
    assert "roundabout had the lower" not in verdict["text"]


def test_roundabout_only_direction() -> None:
    verdict = _summarize_sweep_verdict(_sweep(["roundabout", "roundabout"]))
    assert verdict["directional"] == "roundabout"
    assert "roundabout had the lower measured delay at 2 of 2" in verdict["text"]
    assert "signal had the lower" not in verdict["text"]


def test_all_ties_do_not_pick_a_winner() -> None:
    verdict = _summarize_sweep_verdict(_sweep(["tie", "tie", "tie"]))
    assert verdict["directional"] == "none"
    assert verdict["ties"] == 3
    assert "does not show either geometry as consistently better" in verdict["text"]


def test_insufficient_or_inconclusive_evidence_says_so() -> None:
    empty = _summarize_sweep_verdict({"runs": [], "curves": {}})
    assert empty["status"] == "insufficient_data"

    verdict = _summarize_sweep_verdict(_sweep(["inconclusive", "inconclusive"]))
    assert verdict["directional"] == "none"
    assert verdict["inconclusive"] == 2
    assert verdict["roundaboutWins"] == verdict["signalWins"] == 0
    assert "None of the 2 measured volume point(s) could be decided" in verdict["text"]
    assert "no direction is reported" in verdict["text"]


def test_inconclusive_points_are_counted_but_never_win() -> None:
    verdict = _summarize_sweep_verdict(_sweep(["inconclusive", "signal", "tie"]))
    assert verdict["inconclusive"] == 1
    assert verdict["ties"] == 1
    assert verdict["signalWins"] == 1
    assert "1 inconclusive" in verdict["text"]


def test_multiple_changes_report_no_single_crossover() -> None:
    verdict = _summarize_sweep_verdict(
        _sweep(["roundabout", "signal", "roundabout", "signal"], "auto")
    )
    assert verdict["directional"] == "multiple_changes"
    assert "no single crossover" in verdict["text"]
    assert "reversed direction" not in verdict["text"]


def test_mixed_without_a_recorded_crossover_asserts_no_reversal() -> None:
    verdict = _summarize_sweep_verdict(_sweep(["signal", "signal", "roundabout"]))
    assert verdict["directional"] == "mixed"
    assert "fixed-time signal had the lower measured delay at 2" in verdict["text"]
    assert "reversed direction" not in verdict["text"]
    assert "no single direction is supported" in verdict["text"]


def test_every_verdict_states_it_is_one_random_pattern_per_point() -> None:
    for winners in (["signal"], ["roundabout"], ["tie"], ["signal", "roundabout"]):
        text = _summarize_sweep_verdict(_sweep(winners, "auto"))["text"]
        assert "one random traffic pattern" in text


def test_non_calibrated_sweep_says_so() -> None:
    sweep = _sweep(["signal", "signal"])
    sweep["calibration"] = {
        "calibrated": False,
        "note": "Exploratory, not calibrated: X",
    }
    assert "Exploratory, not calibrated" in _summarize_sweep_verdict(sweep)["text"]


# ── the crossover ───────────────────────────────────────────────────────────


def test_crossover_is_a_bracket_between_decided_tiers() -> None:
    runs = [_run("roundabout", 0.1), _run("roundabout", 0.2), _run("signal", 0.4)]
    assert find_delay_crossover(runs) == {"lowerRate": 0.2, "upperRate": 0.4}


def test_ties_and_inconclusive_tiers_cannot_create_a_crossover() -> None:
    runs = [
        _run("roundabout", 0.1),
        _run("tie", 0.2),
        _run("inconclusive", 0.3),
        _run("roundabout", 0.4),
    ]
    assert find_delay_crossover(runs) is None
    # ...but a real change across them is still found, bracketing the decided tiers.
    runs[3] = _run("signal", 0.4)
    assert find_delay_crossover(runs) == {"lowerRate": 0.1, "upperRate": 0.4}


def test_crossover_is_independent_of_run_order() -> None:
    runs = [_run("signal", 0.4), _run("roundabout", 0.1), _run("roundabout", 0.2)]
    assert find_delay_crossover(runs) == {"lowerRate": 0.2, "upperRate": 0.4}


# ── the shared tie rule ─────────────────────────────────────────────────────


def test_tie_rule_absolute_and_relative() -> None:
    tol = tie_tolerance()
    assert tol == {"absSeconds": 1.0, "relative": 0.05}
    assert delays_are_tied(5.0, 5.9)  # within 1 s
    assert not delays_are_tied(5.0, 6.5)  # 1.5 s and 23 %
    assert delays_are_tied(100.0, 104.9)  # 4.9 s but < 5 % of the larger
    assert not delays_are_tied(100.0, 106.0)
    assert delays_are_tied(3.0, 3.0)
    assert delays_are_tied(0.0, 0.0)
    # Exactly at the tolerance is a tie (no floating-point tip-over).
    assert delays_are_tied(10.0, 11.0)


# ── validation evidence ─────────────────────────────────────────────────────


def _validation(
    p: Any, significant: bool, s_mean: float = 10.0, r_mean: float = 14.0
) -> Dict[str, Any]:
    def stat(m: float) -> Dict[str, float]:
        return {"mean": m, "std": 1.0, "ci95": 1.0}

    cmp = {"pValue": p, "significant": significant, "cohensD": -2.0}
    return {
        "numSeeds": 5,
        "alpha": 0.05,
        "signal": {"delay": stat(s_mean), "throughput": stat(100), "queue": stat(2)},
        "roundabout": {"delay": stat(r_mean), "throughput": stat(90), "queue": stat(3)},
        "comparison": {"delay": cmp, "throughput": cmp, "queue": cmp},
    }


def test_validation_evidence_supported_difference_names_the_lower_mean() -> None:
    evidence = _summarize_validation_evidence(_validation(0.01, True))
    assert evidence["status"] == "available"
    text = evidence["text"]
    assert "statistically supported at alpha = 0.05" in text
    assert "lower mean at the fixed-time signal" in text


def test_validation_evidence_not_significant_is_not_called_equal() -> None:
    evidence = _summarize_validation_evidence(_validation(0.4, False))
    text = evidence["text"]
    assert "not statistically supported" in text
    assert "not the same as showing they are equal" in text
    # Every "supported" mention is the negated form.
    assert text.count("statistically supported at alpha") == text.count(
        "not statistically supported at alpha"
    )


def test_validation_evidence_without_a_test_makes_no_statement() -> None:
    assert _summarize_validation_evidence({})["status"] == "unavailable"
    evidence = _summarize_validation_evidence(_validation(None, False))
    assert "no test was possible" in evidence["text"]


def test_report_combines_sweep_and_validation_evidence_without_recommending() -> None:
    sweep = _sweep(["signal", "signal", "signal"])
    report = generate_study_report_json(sweep, _validation(0.4, False))
    summary = report["summary"]
    assert summary["evidenceSummary"] == summary["recommendation"]
    assert "not statistically supported" in summary["evidenceSummary"]
    assert "one random traffic pattern" in summary["evidenceSummary"]
    assert summary["signalOptimalCount"] == 3
    assert summary["directional"] == "signal"
    csv_text = generate_study_report_csv(sweep, _validation(0.4, False))
    assert "Evidence summary" in csv_text
    assert "Executive Recommendation" not in csv_text
    assert "Welch p-value" in csv_text
    assert "Cohen's d" in csv_text
