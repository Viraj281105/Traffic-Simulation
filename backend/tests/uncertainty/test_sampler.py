"""Unit tests for the uncertainty specification and Latin-hypercube sampler (B0-5 skeleton)."""

import statistics

import pytest
from pydantic import ValidationError

from src.uncertainty import (
    Distribution,
    Factor,
    UncertaintySpec,
    derive_seed,
    fingerprint,
    inverse_cdf,
    sample_conditions,
)


def _factor(fid="demand", kind="demand_scale", dist=None, bounds=(0.7, 1.3), **kw):
    dist = dist or {"kind": "uniform"}
    kw.setdefault("rationale", "assumed planning range")
    return {"id": fid, "kind": kind, "distribution": dist, "bounds": list(bounds), **kw}


def _spec(n=50, seed=7, factors=None, **kw):
    factors = factors or [
        _factor("demand"),
        _factor(
            "headway", "headway_scale", {"kind": "triangular", "mode": 1.0}, (0.8, 1.2)
        ),
        _factor(
            "speed",
            "desired_speed_scale",
            {"kind": "truncated_normal", "mean": 1.0, "sd": 0.1},
            (0.8, 1.2),
        ),
        _factor(
            "accel",
            "max_acceleration_scale",
            {"kind": "lognormal", "mu": 0.0, "sigma": 0.2},
            (0.7, 1.4),
        ),
    ]
    return UncertaintySpec.model_validate(
        {"conditions": n, "seed": seed, "factors": factors, **kw}
    )


# --- specification -----------------------------------------------------------------------------


def test_extra_fields_are_rejected():
    with pytest.raises(ValidationError):
        UncertaintySpec.model_validate(
            {"conditions": 5, "seed": 1, "factors": [_factor()], "surprise": 1}
        )
    with pytest.raises(ValidationError):
        Factor.model_validate({**_factor(), "surprise": 1})


def test_assumed_factor_needs_a_rationale():
    with pytest.raises(ValidationError, match="rationale"):
        Factor.model_validate(_factor(rationale=""))
    # an observed factor may omit it
    Factor.model_validate(_factor(rationale="", basis="observed"))


@pytest.mark.parametrize(
    "bad",
    [
        _factor(bounds=(1.3, 0.7)),  # low >= high
        _factor(bounds=(0.0, 1.3)),  # scale factor must be positive
        _factor("shift", "turning_shift", bounds=(-1.5, 0.5)),  # shift outside [-1, 1]
        _factor(dist={"kind": "triangular", "mode": 2.0}),  # mode outside bounds
        _factor(dist={"kind": "truncated_normal", "mean": 1.0}),  # sd missing
        _factor(dist={"kind": "lognormal", "mu": 0.0}),  # sigma missing
    ],
)
def test_invalid_factor_definitions_are_rejected(bad):
    with pytest.raises(ValidationError):
        Factor.model_validate(bad)


def test_duplicate_factor_ids_and_limits_are_rejected():
    with pytest.raises(ValidationError, match="unique"):
        _spec(factors=[_factor("a"), _factor("a")])
    with pytest.raises(ValidationError):
        _spec(n=0)
    with pytest.raises(ValidationError):
        _spec(n=100000)


def test_fingerprint_is_stable_and_sensitive():
    a, b = _spec(), _spec()
    assert fingerprint(a) == fingerprint(b)
    assert len(fingerprint(a)) == 16
    assert fingerprint(_spec(seed=8)) != fingerprint(a)
    assert fingerprint(_spec(n=51)) != fingerprint(a)


# --- sampler -----------------------------------------------------------------------------------


def test_same_spec_gives_identical_conditions():
    first, second = sample_conditions(_spec()), sample_conditions(_spec())
    assert first == second


def test_different_seed_changes_conditions():
    assert sample_conditions(_spec(seed=7)) != sample_conditions(_spec(seed=8))


def test_condition_count_and_indices():
    conditions = sample_conditions(_spec(n=40))
    assert len(conditions) == 40
    assert [c.index for c in conditions] == list(range(40))


def test_latin_hypercube_stratification_one_point_per_stratum():
    spec = _spec(n=60)
    conditions = sample_conditions(spec)
    for factor in spec.factors:
        assert sorted(c.strata[factor.id] for c in conditions) == list(range(60))


def test_values_respect_bounds():
    spec = _spec(n=200)
    for c in sample_conditions(spec):
        for factor in spec.factors:
            low, high = factor.bounds
            assert low <= c.values[factor.id] <= high


def test_uniform_stratified_sample_covers_the_range_evenly():
    # a shift factor, so the unit interval [0, 1] is a legal range (scale factors start at 0.05)
    spec = _spec(
        n=100,
        factors=[_factor("shift", "turning_shift", bounds=(0.0, 1.0))],
    )
    values = sorted(c.values["shift"] for c in sample_conditions(spec))
    # one point per 1% stratum: the k-th smallest value lies in its own stratum
    for k, v in enumerate(values):
        assert k / 100 <= v <= (k + 1) / 100 + 1e-6


def test_triangular_mode_shifts_the_sample_towards_the_mode():
    spec = _spec(
        n=400,
        factors=[
            _factor(
                "h", "headway_scale", {"kind": "triangular", "mode": 0.9}, (0.8, 1.2)
            )
        ],
    )
    mean = statistics.fmean(c.values["h"] for c in sample_conditions(spec))
    # triangular mean = (low + mode + high) / 3
    assert mean == pytest.approx((0.8 + 0.9 + 1.2) / 3, abs=0.01)


def test_truncated_normal_is_centred_when_symmetric():
    spec = _spec(
        n=400,
        factors=[
            _factor(
                "s",
                "desired_speed_scale",
                {"kind": "truncated_normal", "mean": 1.0, "sd": 0.1},
                (0.8, 1.2),
            )
        ],
    )
    mean = statistics.fmean(c.values["s"] for c in sample_conditions(spec))
    assert mean == pytest.approx(1.0, abs=0.01)


def test_inverse_cdf_is_monotone_and_hits_the_bounds_for_every_distribution():
    cases = [
        (Distribution(kind="uniform"), 0.7, 1.3),
        (Distribution(kind="triangular", mode=1.0), 0.7, 1.3),
        (Distribution(kind="truncated_normal", mean=1.0, sd=0.2), 0.7, 1.3),
        (Distribution(kind="lognormal", mu=0.0, sigma=0.3), 0.7, 1.3),
    ]
    for dist, low, high in cases:
        grid = [inverse_cdf(dist, low, high, p / 100) for p in range(1, 100)]
        assert grid == sorted(grid)
        assert low <= grid[0] and grid[-1] <= high
        assert inverse_cdf(dist, low, high, 0.0) == pytest.approx(low, abs=1e-6)
        assert inverse_cdf(dist, low, high, 1.0) == pytest.approx(high, abs=1e-6)


# --- seed derivation ---------------------------------------------------------------------------


def test_seed_derivation_is_deterministic_and_distinct():
    assert derive_seed(7, 3, 1) == derive_seed(7, 3, 1)
    seeds = {derive_seed(7, i, r) for i in range(200) for r in range(3)}
    assert len(seeds) == 600  # no collisions in a realistic grid
    assert all(0 <= s <= 0x7FFFFFFF for s in seeds)
    assert derive_seed(7, 0, 0) != derive_seed(8, 0, 0)


def test_replication_seeds_match_the_spec():
    spec = _spec(n=10, replications=3)
    for c in sample_conditions(spec):
        assert c.seeds == [derive_seed(spec.seed, c.index, r) for r in range(3)]


def test_common_random_numbers_seeds_do_not_depend_on_factors():
    # The same (seed, condition, replication) gives the same engine seed whatever the factors are,
    # so every alternative can share it.
    a = sample_conditions(_spec(n=5))
    b = sample_conditions(_spec(n=5, factors=[_factor("only")]))
    assert [c.seeds for c in a] == [c.seeds for c in b]
