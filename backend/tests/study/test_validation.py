from src.study.validation import run_invariant_checks, run_statistical_validation


def test_statistical_validation() -> None:
    res = run_statistical_validation(num_seeds=3, duration=4.0, time_step=0.1)

    assert res["numSeeds"] == 3
    assert len(res["seeds"]) == 3
    assert len(res["individualRuns"]) == 3

    # Check that statistics dictionary is properly calculated
    for strategy in ["signal", "roundabout"]:
        assert "delay" in res[strategy]
        assert "throughput" in res[strategy]
        assert "queue" in res[strategy]
        assert "mean" in res[strategy]["delay"]
        assert "std" in res[strategy]["delay"]
        assert "ci95" in res[strategy]["delay"]


def test_invariant_and_repeatability_checks() -> None:
    res = run_invariant_checks(duration=4.0, time_step=0.1, random_seed=4242)

    assert res["valid"] is True
    assert res["isDeterministic"] is True
    assert res["massConservationValid"] is True
    assert res["ticksTested"] == 40
    assert len(res["violations"]) == 0
