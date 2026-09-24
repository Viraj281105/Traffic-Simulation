from src.study.report_generator import (
    _summarize_sweep_verdict,
    generate_study_report_csv,
    generate_study_report_json,
)
from src.study.validation import run_statistical_validation
from src.study.volume_sweep import run_volume_sweep_experiment


def test_study_report_generation(tmp_path, monkeypatch) -> None:
    test_db = str(tmp_path / "test_report.db")
    monkeypatch.setattr("src.database.db.DB_PATH", test_db)
    monkeypatch.setattr("src.study.volume_sweep.DB_PATH", test_db)

    sweep = run_volume_sweep_experiment(arrival_rates=[0.2, 0.5], duration=4.0)
    val = run_statistical_validation(num_seeds=2, duration=4.0)

    # JSON report
    report_json = generate_study_report_json(
        sweep_results=sweep, validation_results=val
    )
    assert report_json["version"] == "1.0.0"
    assert "summary" in report_json
    assert "volumeSweep" in report_json
    assert "statisticalValidation" in report_json

    # CSV report
    report_csv = generate_study_report_csv(sweep_results=sweep, validation_results=val)
    assert "=== COMPREHENSIVE TRAFFIC STUDY REPORT ===" in report_csv
    assert "=== VOLUME SWEEP RESULTS ===" in report_csv
    assert "=== STATISTICAL MONTE CARLO VALIDATION ===" in report_csv


# ── _summarize_sweep_verdict / recommendation text: data-driven, not fixed ──
#
# Regression coverage for the executive recommendation no longer being a
# hard-coded "roundabouts are superior below X / signals above X" template
# (see docs/future-scope audit). Synthetic sweep dicts are used instead of
# running real simulations, since _summarize_sweep_verdict only consumes the
# already-computed `winner`/`curves` fields that run_volume_sweep_experiment
# produces -- it does not re-derive them.


def _run(winner: str, arrival_rate: float = 0.3) -> dict:
    return {"arrivalRate": arrival_rate, "winner": winner}


def test_verdict_signal_better_never_claims_roundabout_superior() -> None:
    sweep = {
        "runs": [_run("signal"), _run("signal"), _run("signal")],
        "curves": {"crossoverArrivalRate": None, "crossoverHourlyVolume": None},
    }
    verdict = _summarize_sweep_verdict(sweep)

    assert verdict["status"] == "measured"
    assert verdict["signalWins"] == 3
    assert verdict["roundaboutWins"] == 0
    assert "fixed-time signal had the lower measured delay" in verdict["text"]
    # Must not contradict the supplied measurements by claiming the loser won.
    assert "roundabout had the lower measured delay" not in verdict["text"]
    assert "roundabout: 0" in verdict["text"]


def test_verdict_roundabout_better_never_claims_signal_superior() -> None:
    sweep = {
        "runs": [_run("roundabout"), _run("roundabout"), _run("roundabout")],
        "curves": {"crossoverArrivalRate": None, "crossoverHourlyVolume": None},
    }
    verdict = _summarize_sweep_verdict(sweep)

    assert verdict["status"] == "measured"
    assert verdict["roundaboutWins"] == 3
    assert verdict["signalWins"] == 0
    assert "roundabout had the lower measured delay" in verdict["text"]
    assert "no delay-direction reversal was observed" in verdict["text"]


def test_verdict_tie_does_not_pick_a_winner() -> None:
    sweep = {
        "runs": [_run("tie"), _run("tie"), _run("tie")],
        "curves": {"crossoverArrivalRate": None, "crossoverHourlyVolume": None},
    }
    verdict = _summarize_sweep_verdict(sweep)

    assert verdict["status"] == "measured"
    assert verdict["roundaboutWins"] == 0
    assert verdict["signalWins"] == 0
    assert verdict["ties"] == 3
    assert "does not show either geometry as consistently better" in verdict["text"]


def test_verdict_mixed_without_crossover_reports_measured_counts_only() -> None:
    # 2 signal wins, 1 roundabout win, no reversal point was detected by the
    # sweep's own crossover-detection logic (curves.crossoverArrivalRate is
    # None) -- the verdict must still be strictly proportional to counts,
    # not assert a reversal that wasn't measured.
    sweep = {
        "runs": [_run("signal"), _run("signal"), _run("roundabout")],
        "curves": {"crossoverArrivalRate": None, "crossoverHourlyVolume": None},
    }
    verdict = _summarize_sweep_verdict(sweep)

    assert verdict["signalWins"] == 2
    assert verdict["roundaboutWins"] == 1
    assert "fixed-time signal had the lower measured delay at 2" in verdict["text"]
    assert "reversed direction" not in verdict["text"]


def test_verdict_crossover_reversal_uses_measured_crossover_value() -> None:
    sweep = {
        "runs": [_run("roundabout", 0.1), _run("roundabout", 0.2), _run("signal", 0.4)],
        "curves": {"crossoverArrivalRate": 0.3, "crossoverHourlyVolume": 1080},
    }
    verdict = _summarize_sweep_verdict(sweep)

    assert verdict["crossoverArrivalRate"] == 0.3
    # 0.3 veh/s <-> 1080 veh/h: the rate is the whole junction's, not per approach.
    assert "0.300 veh/s (whole junction)" in verdict["text"]
    assert "1,080" in verdict["text"] or "1080" in verdict["text"]
    assert "roundabout had the lower measured delay (2 of 3" in verdict["text"]
    assert "signal did (1 of 3" in verdict["text"]


def test_verdict_insufficient_data_is_handled_safely() -> None:
    sweep: dict = {"runs": [], "curves": {}}
    verdict = _summarize_sweep_verdict(sweep)

    assert verdict["status"] == "insufficient_data"
    assert verdict["totalPoints"] == 0
    assert "No volume-sweep data points" in verdict["text"]


def test_verdict_missing_runs_key_is_handled_safely() -> None:
    # A malformed/partial sweep dict (e.g. an aborted run) must not raise.
    verdict = _summarize_sweep_verdict({})
    assert verdict["status"] == "insufficient_data"


def test_recommendation_is_never_the_old_fixed_template() -> None:
    """Regression guard for the specific hard-coded phrasing this fix
    removed: the recommendation must not unconditionally assert roundabout
    superiority regardless of what was measured."""
    sweep = {
        "runs": [_run("signal"), _run("signal"), _run("signal")],
        "curves": {"crossoverArrivalRate": None, "crossoverHourlyVolume": None},
    }
    report = generate_study_report_json(
        sweep_results=sweep,
        validation_results={"signal": {}, "roundabout": {}, "comparison": {}},
    )
    recommendation = report["summary"]["recommendation"]
    assert "exhibit significantly superior performance" not in recommendation
    assert "Modern roundabouts" not in recommendation
    assert report["summary"]["signalOptimalCount"] == 3
    assert report["summary"]["roundaboutOptimalCount"] == 0


def test_report_labels_match_the_reported_quantities() -> None:
    """Regression: the CSV labelled the sweep's vehicle-count throughput as
    veh/h, and the verdict called the whole-junction arrival rate
    "veh/s/approach"."""
    from src.study.report_generator import (
        _summarize_sweep_verdict,
        generate_study_report_csv,
    )

    sweep = {
        "runs": [
            {
                "arrivalRate": 0.2,
                "winner": "roundabout",
                "signal": {},
                "roundabout": {},
            },
            {"arrivalRate": 0.6, "winner": "signal", "signal": {}, "roundabout": {}},
        ],
        "curves": {"crossoverArrivalRate": 0.6, "crossoverHourlyVolume": 2160},
    }
    assert "veh/s/approach" not in _summarize_sweep_verdict(sweep)["text"]
    csv_text = generate_study_report_csv(sweep, {"signal": {}, "roundabout": {}})
    assert "Throughput (veh/h)" not in csv_text
    assert "Throughput (vehicles served)" in csv_text
