"""Ensemble runner (W1 WP3): common random numbers, exclusion accounting and the pre-run refusals.

Most tests drive the runner with a fake executor that returns canned metrics, so the rules are checked
without simulating; one small real ensemble at the end proves the pieces fit the real engine."""

import math
from typing import Any, Dict, List

import pytest

from src.core.scenario import ScenarioDocument
from src.uncertainty import UncertaintySpec, result_fingerprint, sample_conditions
from src.uncertainty.runner import (
    EnsembleRefusedError,
    RunAlternative,
    run_ensemble,
    run_experiment,
)


def _doc(vph=300.0, mix=None, advanced=None, duration=60, warmup=5):
    body: Dict[str, Any] = {
        "format": "urbanflow-scenario",
        "version": 1,
        "name": "runner test",
        "junction": {"type": "fixed_time_signal"},
        "approaches": {
            d: {
                "lanes": 1,
                "vehiclesPerHour": vph,
                "turning": {"left": 0.2, "straight": 0.6, "right": 0.2},
            }
            for d in ("north", "south", "east", "west")
        },
        "simulation": {"duration": duration, "warmup": warmup, "seed": 3},
    }
    if mix:
        body["vehicles"] = {"mix": mix}
    if advanced:
        body["advanced"] = advanced
    return ScenarioDocument.model_validate(body)


def _spec(n=12, reps=2, factors=None, **kw):
    factors = factors or [
        {
            "id": "demand",
            "kind": "demand_scale",
            "distribution": {"kind": "uniform"},
            "bounds": [0.7, 1.3],
            "rationale": "test",
        },
        {
            "id": "headway",
            "kind": "headway_scale",
            "distribution": {"kind": "uniform"},
            "bounds": [0.8, 1.2],
            "rationale": "test",
        },
    ]
    return UncertaintySpec.model_validate(
        {"conditions": n, "replications": reps, "seed": 21, "factors": factors, **kw}
    )


def _alts(doc=None):
    doc = doc or _doc()
    return [
        RunAlternative("fixed", "fixed_time", doc),
        RunAlternative("adaptive", "adaptive", doc),
        RunAlternative("round", "roundabout", doc),
    ]


class FakeExecutor:
    """Returns canned metrics and records the tasks it was given."""

    def __init__(self, delay=None, fail=(), limit=(), missing=(), empty=()):
        self.delay = delay or (lambda cfg: 40.0 + 100.0 * cfg["traffic"]["arrivalRate"])
        self.fail, self.limit, self.missing = set(fail), set(limit), set(missing)
        self.empty = set(empty)  # runs in which no vehicle finished its trip
        self.tasks: List[Any] = []

    def __call__(self, tasks, progress=None):
        self.tasks = list(tasks)
        out: List[Any] = []
        for task in tasks:
            if any(tag in task.label for tag in self.fail):
                out.append(RuntimeError("simulated crash"))
                continue
            strategy = task.config["scenario"]["strategy"]
            delay = self.delay(task.config) - (5.0 if strategy == "adaptive" else 0.0)
            metrics: Dict[str, Any] = {
                "averageDelay": delay,
                "vehicleLimitReached": any(tag in task.label for tag in self.limit),
                "throughput": 0 if any(tag in task.label for tag in self.empty) else 25,
            }
            if any(tag in task.label for tag in self.empty):
                metrics["averageDelay"] = (
                    0.0  # what the collector reports for an empty sample
                )
            if any(tag in task.label for tag in self.missing):
                metrics["averageDelay"] = None
            out.append({"metrics": metrics})
        return out


# --- common random numbers ------------------------------------------------------------------------


def test_alternatives_share_the_seed_and_the_traffic_inside_every_condition():
    fake = FakeExecutor()
    spec = _spec()
    run_ensemble(spec, _alts(), executor=fake)
    by_cell: Dict[tuple, List[Any]] = {}
    for task in fake.tasks:
        parts = task.label.split(" · ")
        cell = (parts[0], parts[1])  # (condition, replication)
        by_cell.setdefault(cell, []).append(task)
    assert len(by_cell) == spec.conditions * spec.replications
    sampled = {c.index: c for c in sample_conditions(spec)}
    for (condition_label, rep_label), tasks in by_cell.items():
        assert len(tasks) == 3
        index = int(condition_label.split()[1])
        rep = int(rep_label.split()[1])
        expected_seed = sampled[index].seeds[rep]
        for task in tasks:
            assert task.config["simulation"]["randomSeed"] == expected_seed
        first = tasks[0].config
        for other in tasks[1:]:
            # same perturbed scenario: traffic, vehicle population and simulation settings are equal
            for section in ("simulation", "traffic", "vehicleGeneration"):
                assert other.config[section] == first[section], section


def test_two_alternatives_differ_only_in_their_control():
    fake = FakeExecutor()
    run_ensemble(_spec(n=4, reps=1), _alts()[:2], executor=fake)
    fixed, adaptive = fake.tasks[0].config, fake.tasks[1].config
    differing = {k for k in fixed if fixed[k] != adaptive[k]}
    assert differing == {"controller", "scenario"}


def test_replications_and_conditions_use_different_seeds():
    fake = FakeExecutor()
    run_ensemble(_spec(n=10, reps=3), _alts()[:2], executor=fake)
    seeds = {t.config["simulation"]["randomSeed"] for t in fake.tasks}
    assert len(seeds) == 30


def test_sampled_values_reach_the_scenario():
    fake = FakeExecutor()
    spec = _spec(n=8, reps=1)
    run_ensemble(spec, _alts()[:2], executor=fake)
    sampled = sample_conditions(spec)
    for task in fake.tasks:
        index = int(task.label.split()[1])
        rate = task.config["traffic"]["arrivalRate"]
        assert rate == pytest.approx(
            4 * 300.0 * sampled[index].values["demand"] / 3600.0, rel=1e-5
        )
        assert task.config["vehicleGeneration"]["desiredTimeHeadway"] == pytest.approx(
            1.5 * sampled[index].values["headway"], abs=1e-5
        )


# --- exclusion accounting -------------------------------------------------------------------------


def _reasons(run):
    return {c.index: c.exclusion for c in run.conditions if c.exclusion}


def test_a_crashing_run_excludes_its_condition_for_every_alternative():
    fake = FakeExecutor(fail=("condition 3 · rep 1 · adaptive",))
    run = run_ensemble(_spec(), _alts(), executor=fake)
    assert _reasons(run) == {3: "run_failed"}
    assert (
        run.conditions[3].outcomes == {}
    )  # nothing of it is analysed, for any alternative
    assert len(run.conditions[4].outcomes["fixed"]) == 2


def test_vehicle_limit_and_missing_indicator_are_excluded_with_their_reasons():
    fake = FakeExecutor(
        limit=("condition 2 · rep 0 · round",), missing=("condition 5 · rep 1 · fixed",)
    )
    run = run_ensemble(_spec(), _alts(), executor=fake)
    assert _reasons(run) == {2: "vehicle_limit", 5: "non_finite"}


def test_a_run_in_which_no_vehicle_finished_is_excluded_not_scored_as_zero_delay():
    fake = FakeExecutor(empty=("condition 4 · rep 1 · round",))
    run = run_ensemble(_spec(), _alts(), executor=fake)
    assert _reasons(run) == {4: "no_completed_vehicles"}
    assert (
        run.conditions[4].outcomes == {}
    )  # excluded for every alternative, pairing preserved


def test_a_stub_without_a_throughput_figure_is_not_treated_as_empty():
    class NoThroughput(FakeExecutor):
        def __call__(self, tasks, progress=None):
            out = super().__call__(tasks, progress)
            for r in out:
                r["metrics"].pop("throughput")
            return out

    assert _reasons(run_ensemble(_spec(n=4), _alts(), executor=NoThroughput())) == {}


def test_when_a_condition_has_several_problems_the_most_fundamental_is_reported():
    fake = FakeExecutor(
        fail=("condition 1 · rep 0 · fixed",), limit=("condition 1 · rep 1 · round",)
    )
    assert _reasons(run_ensemble(_spec(), _alts(), executor=fake)) == {1: "run_failed"}


def test_an_invalid_perturbed_scenario_is_excluded_not_run_and_not_repaired():
    # 4 arms x 3000 vph: any demand scale above 2.4 pushes an arm past the 7200 vph limit
    spec = _spec(
        factors=[
            {
                "id": "demand",
                "kind": "demand_scale",
                "distribution": {"kind": "uniform"},
                "bounds": [1.0, 3.0],
                "rationale": "test",
            }
        ],
        n=30,
        reps=2,
    )
    fake = FakeExecutor()
    run = run_ensemble(spec, _alts(_doc(vph=3000.0)), executor=fake)
    too_high = {
        c.index for c in sample_conditions(spec) if c.values["demand"] * 3000.0 > 7200.0
    }
    assert too_high  # the scenario is only meaningful if some conditions overshoot
    assert set(_reasons(run)) == too_high
    assert set(_reasons(run).values()) == {"validation_failed"}
    assert (
        len(fake.tasks) == (30 - len(too_high)) * 3 * 2
    )  # excluded conditions are never queued
    assert run.runs_planned == 30 * 3 * 2 and run.runs_executed == len(fake.tasks)


def test_every_condition_is_reported_valid_or_not():
    run = run_ensemble(_spec(), _alts(), executor=FakeExecutor(fail=("condition 0 ",)))
    assert [c.index for c in run.conditions] == list(range(12))
    assert all(set(c.strata) == {"demand", "headway"} for c in run.conditions)


# --- refusals before any run ----------------------------------------------------------------------


def test_refusals_happen_before_any_simulation():
    fake = FakeExecutor()
    with pytest.raises(EnsembleRefusedError, match="at least two"):
        run_ensemble(_spec(), _alts()[:1], executor=fake)
    dup = [_alts()[0], RunAlternative("fixed", "adaptive", _doc())]
    with pytest.raises(EnsembleRefusedError, match="unique"):
        run_ensemble(_spec(), dup, executor=fake)
    bad = [_alts()[0], RunAlternative("x", "teleport", _doc())]
    with pytest.raises(EnsembleRefusedError, match="unknown strategy"):
        run_ensemble(_spec(), bad, executor=fake)
    mix_spec = _spec(
        factors=[
            {
                "id": "mix",
                "kind": "mix_shift",
                "distribution": {"kind": "uniform"},
                "bounds": [-0.5, 0.5],
                "rationale": "test",
            }
        ]
    )
    with pytest.raises(EnsembleRefusedError, match="declare a vehicle mix"):
        run_ensemble(
            mix_spec, _alts(), executor=fake
        )  # the base scenarios declare no mix
    shadowed = _doc(advanced={"traffic": {"arrivalRate": 0.2}})
    with pytest.raises(EnsembleRefusedError, match="advanced.traffic"):
        run_ensemble(_spec(), _alts(shadowed), executor=fake)
    assert fake.tasks == []


def test_executor_returning_the_wrong_number_of_results_is_an_error():
    with pytest.raises(RuntimeError, match="different number"):
        run_ensemble(_spec(n=3), _alts(), executor=lambda tasks, progress=None: [])


# --- run_experiment -------------------------------------------------------------------------------


def test_experiment_result_is_deterministic_and_carries_the_contract_fields():
    spec = _spec(n=40, reps=2)
    first = run_experiment(spec, _alts(), "fixed", executor=FakeExecutor())
    second = run_experiment(spec, _alts(), "fixed", executor=FakeExecutor())
    assert first["resultFingerprint"] == second["resultFingerprint"]
    assert first["resultFingerprint"] == result_fingerprint(first["analysis"])
    assert len(first["specFingerprint"]) == 16
    counts = first["analysis"]["counts"]
    assert counts == {
        "conditions": 40,
        "validConditions": 40,
        "alternatives": 3,
        "replications": 2,
        "totalRuns": 240,
    }
    # the fake makes adaptive exactly 5 s better than fixed everywhere
    comparison = first["analysis"]["alternatives"]["adaptive"]["comparison"]
    assert comparison["win"]["count"] == 40
    assert comparison["difference"]["mean"]["value"] == pytest.approx(-5.0)
    assert (
        first["analysis"]["eligibility"]["criteria"][-1]["passed"] is True
    )  # pre-declared
    assert first["execution"]["runsExecuted"] == 240
    assert (
        "execution" not in first["analysis"]
    )  # machine details stay out of the fingerprinted result


def test_wall_time_does_not_change_the_result_fingerprint():
    spec = _spec(n=10, reps=1)
    one = run_experiment(spec, _alts(), "fixed", executor=FakeExecutor())
    two = run_experiment(spec, _alts(), "fixed", executor=FakeExecutor())
    assert one["execution"]["wallSeconds"] is not None
    assert one["resultFingerprint"] == two["resultFingerprint"]


def test_nan_never_reaches_the_analysis():
    spec = _spec(n=10, reps=1)
    out = run_experiment(
        spec,
        _alts(),
        "fixed",
        executor=FakeExecutor(missing=("condition 4 · rep 0 · adaptive",)),
    )
    assert out["analysis"]["exclusions"]["byReason"] == {"non_finite": 1}
    assert out["analysis"]["counts"]["validConditions"] == 9
    assert not math.isnan(out["analysis"]["alternatives"]["adaptive"]["meanOutcome"])


# --- one small real ensemble ----------------------------------------------------------------------


def test_real_ensemble_two_identical_alternatives_tie_exactly_and_repeat_exactly():
    """Same strategy twice under common random numbers must give identical outcomes in every condition,
    so every comparison is a tie with difference exactly 0; and rerunning gives the same fingerprint."""
    doc = _doc(vph=600.0, duration=60, warmup=5)
    alts = [
        RunAlternative("first", "fixed_time", doc),
        RunAlternative("second", "fixed_time", doc),
    ]
    spec = _spec(n=3, reps=1)
    one = run_experiment(spec, alts, "first")
    two = run_experiment(spec, alts, "first")
    assert one["resultFingerprint"] == two["resultFingerprint"]
    analysis = one["analysis"]
    assert analysis["counts"]["validConditions"] == 3
    comparison = analysis["alternatives"]["second"]["comparison"]
    assert comparison["tie"]["count"] == 3
    assert comparison["difference"]["mean"]["value"] == 0.0
    assert (
        analysis["alternatives"]["first"]["meanOutcome"] > 0
    )  # real delays, not an empty sample
    assert one["execution"]["runsExecuted"] == 6


def test_real_ensemble_compares_a_signal_with_a_roundabout():
    doc = _doc(vph=600.0, duration=60, warmup=5)
    alts = [
        RunAlternative("signal", "fixed_time", doc),
        RunAlternative("round", "roundabout", doc),
    ]
    out = run_experiment(_spec(n=3, reps=1), alts, "signal")
    assert out["analysis"]["counts"]["validConditions"] == 3
    block = out["analysis"]["alternatives"]["round"]["comparison"]
    assert sum(block[k]["count"] for k in ("win", "tie", "loss")) == 3


def test_real_ensemble_too_short_for_any_vehicle_to_finish_is_excluded_and_says_so():
    """30 s at 200 veh/h per arm: nothing completes after warm-up, and the engine reports delay 0.0. That
    is not a measurement; every condition must be excluded with its reason, never compared as a tie."""
    doc = _doc(vph=200.0, duration=30, warmup=5)
    alts = [
        RunAlternative("signal", "fixed_time", doc),
        RunAlternative("round", "roundabout", doc),
    ]
    out = run_experiment(_spec(n=3, reps=1), alts, "signal")
    analysis = out["analysis"]
    assert analysis["counts"]["validConditions"] == 0
    assert analysis["exclusions"]["byReason"] == {"no_completed_vehicles": 3}
    assert analysis["eligibility"]["class"] == "exploratory"
    assert analysis["alternatives"]["round"]["comparison"] is None
