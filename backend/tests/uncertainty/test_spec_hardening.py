"""Spec hardening (W1 WP1): parameters must match the distribution kind, bounds must hold probability,
the primary indicator is a known delay, the fingerprint ignores the label, sampled values are rounded."""

import pytest
from pydantic import ValidationError

from src.uncertainty import UncertaintySpec, fingerprint, run_counts, sample_conditions


def _factor(fid="demand", kind="demand_scale", dist=None, bounds=(0.7, 1.3), **kw):
    kw.setdefault("rationale", "assumed planning range")
    return {
        "id": fid,
        "kind": kind,
        "distribution": dist or {"kind": "uniform"},
        "bounds": list(bounds),
        **kw,
    }


def _spec(**kw):
    body = {"conditions": 30, "seed": 5, "factors": [_factor()]}
    body.update(kw)
    return UncertaintySpec.model_validate(body)


@pytest.mark.parametrize(
    "dist",
    [
        {"kind": "uniform", "mode": 1.0},  # a parameter the kind does not use
        {"kind": "triangular", "mode": 1.0, "sd": 0.1},
        {"kind": "truncated_normal", "mean": 1.0, "sd": 0.1, "mode": 1.0},
        {"kind": "lognormal", "mu": 0.0, "sigma": 0.2, "mean": 1.0},
        {"kind": "triangular"},  # mode missing
    ],
)
def test_distribution_parameters_must_match_the_kind(dist):
    with pytest.raises(ValidationError):
        _spec(factors=[_factor(dist=dist)])


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_non_finite_numbers_are_rejected(bad):
    with pytest.raises(ValidationError):
        _spec(factors=[_factor(bounds=(0.7, bad))])
    with pytest.raises(ValidationError):
        _spec(
            factors=[_factor(dist={"kind": "truncated_normal", "mean": bad, "sd": 0.1})]
        )
    with pytest.raises(ValidationError):
        _spec(tieTolerance=bad)


def test_bounds_that_hold_no_probability_are_rejected():
    # a normal centred at 1.0 with sd 0.01 has essentially no mass in [1.5, 1.6]
    with pytest.raises(ValidationError, match="probability"):
        _spec(
            factors=[
                _factor(
                    dist={"kind": "truncated_normal", "mean": 1.0, "sd": 0.01},
                    bounds=(1.5, 1.6),
                )
            ]
        )
    with pytest.raises(ValidationError, match="probability"):
        _spec(
            factors=[
                _factor(
                    dist={"kind": "lognormal", "mu": 0.0, "sigma": 0.01},
                    bounds=(2.0, 3.0),
                )
            ]
        )


def test_primary_indicator_is_a_known_delay():
    assert _spec().primaryIndicator == "averageDelay"
    assert _spec(primaryIndicator="p95Delay").primaryIndicator == "p95Delay"
    with pytest.raises(ValidationError):
        _spec(primaryIndicator="throughput")  # higher is better: not a v1 primary


def test_negative_tie_tolerance_is_rejected():
    with pytest.raises(ValidationError):
        _spec(tieTolerance=-0.5)


def test_fingerprint_ignores_the_label_but_not_the_content():
    assert fingerprint(_spec(name="A")) == fingerprint(_spec(name="B"))
    assert fingerprint(_spec(tieTolerance=2.0)) != fingerprint(_spec())
    assert fingerprint(_spec(primaryIndicator="medianDelay")) != fingerprint(_spec())
    assert fingerprint(_spec(replications=3)) != fingerprint(_spec())


def test_run_counts_are_reported_separately():
    spec = _spec(conditions=100, replications=2)
    assert run_counts(spec, 3) == {
        "conditions": 100,
        "alternatives": 3,
        "replications": 2,
        "totalRuns": 600,
    }
    with pytest.raises(ValueError):
        run_counts(spec, 0)


def test_sampled_values_are_rounded_and_inside_the_bounds():
    spec = _spec(
        conditions=200,
        factors=[
            _factor(
                "h",
                "headway_scale",
                {"kind": "lognormal", "mu": 0.0, "sigma": 0.2},
                (0.7, 1.4),
            )
        ],
    )
    for c in sample_conditions(spec):
        value = c.values["h"]
        assert value == round(value, 6)
        assert 0.7 <= value <= 1.4
