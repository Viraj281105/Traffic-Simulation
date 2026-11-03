"""Seed derivation and the reproducibility of the multi-seed Monte Carlo study."""

import random
from typing import Any, Dict

import pytest

from src.study.seeds import MAX_SEED, SEED_SCHEME, derive_run_seeds
from src.study.validation import run_statistical_validation


def test_derivation_is_deterministic() -> None:
    assert derive_run_seeds(42, 8) == derive_run_seeds(42, 8)


def test_a_longer_study_extends_a_shorter_one() -> None:
    assert derive_run_seeds(9, 10)[:4] == derive_run_seeds(9, 4)


def test_different_base_seeds_give_different_seeds() -> None:
    assert derive_run_seeds(1, 5) != derive_run_seeds(2, 5)


def test_seeds_are_distinct_and_in_range() -> None:
    seeds = derive_run_seeds(0, 500)
    assert len(set(seeds)) == 500
    assert all(0 <= s <= MAX_SEED for s in seeds)


def test_boundary_base_seeds_are_accepted() -> None:
    assert len(derive_run_seeds(0, 3)) == 3
    assert len(derive_run_seeds(MAX_SEED, 3)) == 3
    assert derive_run_seeds(5, 0) == []


@pytest.mark.parametrize("bad", [-1, MAX_SEED + 1])
def test_out_of_range_base_seed_is_rejected(bad: int) -> None:
    with pytest.raises(ValueError):
        derive_run_seeds(bad, 3)


def test_negative_count_is_rejected() -> None:
    with pytest.raises(ValueError):
        derive_run_seeds(1, -1)


def test_pinned_values() -> None:
    # Pins the scheme: changing the label or width changes every study's seeds.
    assert SEED_SCHEME == "sha256-v1"
    assert derive_run_seeds(42, 3) == [1656207632, 512058240, 954463373]


def _study(**kwargs: Any) -> Dict[str, Any]:
    return run_statistical_validation(num_seeds=2, duration=4.0, **kwargs)


def test_same_base_seed_repeats_the_study_exactly() -> None:
    first = _study(base_seed=11)
    second = _study(base_seed=11)
    assert first == second
    assert first["baseSeed"] == 11
    assert first["seedScheme"] == SEED_SCHEME
    assert first["seeds"] == derive_run_seeds(11, 2)


def test_different_base_seed_changes_the_seeds() -> None:
    assert _study(base_seed=11)["seeds"] != _study(base_seed=12)["seeds"]


def test_omitted_base_seed_is_drawn_and_reported() -> None:
    random.seed(5)
    result = _study()
    assert result["seeds"] == derive_run_seeds(result["baseSeed"], 2)
    # Repeating from the reported base seed reproduces the study.
    assert _study(base_seed=result["baseSeed"]) == result


def test_legacy_result_fields_are_unchanged() -> None:
    result = _study(base_seed=3)
    for key in ("numSeeds", "seeds", "seedRuns", "individualRuns", "signal"):
        assert key in result
    assert result["seedRuns"][0]["seed"] == result["seeds"][0]
