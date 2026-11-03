"""run_multi_seed: one scenario, one geometry, N derived seeds."""

import math
from typing import Any, Dict

import pytest

from src.study import runner
from src.study.multiseed import (
    default_study_config,
    describe,
    run_multi_seed,
    seeded_run_config,
)
from src.study.runner import simulate_geometry
from src.study.seeds import derive_run_seeds

DURATION = 4.0


def _run(**kwargs: Any) -> Dict[str, Any]:
    return run_multi_seed(num_seeds=2, duration=DURATION, **kwargs)


def test_same_base_seed_repeats_exactly() -> None:
    assert _run(base_seed=5) == _run(base_seed=5)


def test_reports_seeds_and_scheme() -> None:
    result = _run(base_seed=5, geometry="roundabout")
    assert result["geometry"] == "roundabout"
    assert result["baseSeed"] == 5
    assert result["seeds"] == derive_run_seeds(5, 2)
    assert [row["seed"] for row in result["seedRuns"]] == result["seeds"]
    assert result["summary"]["delay"]["n"] == 2


@pytest.mark.parametrize("geometry", ["signal", "roundabout"])
def test_each_seed_equals_that_seed_run_alone(geometry: str) -> None:
    result = _run(base_seed=8, geometry=geometry)
    for row in result["seedRuns"]:
        cfg = seeded_run_config(default_study_config(DURATION), row["seed"], DURATION)
        alone = simulate_geometry(cfg, geometry, DURATION)["metrics"]
        assert row["throughput"] == alone["throughput"]
        assert row["queue"] == alone["averageQueueLength"]


def test_result_does_not_depend_on_worker_count(monkeypatch) -> None:
    monkeypatch.setenv("STUDY_WORKERS", "0")
    inline = _run(base_seed=3)
    monkeypatch.setenv("STUDY_WORKERS", "2")
    try:
        pooled = _run(base_seed=3)
    finally:
        runner.shutdown_pool()
    assert pooled == inline


def test_omitted_base_seed_is_drawn_and_reported() -> None:
    result = _run()
    assert result["seeds"] == derive_run_seeds(result["baseSeed"], 2)


def test_rejects_unknown_geometry_and_bad_count() -> None:
    with pytest.raises(ValueError):
        run_multi_seed(geometry="bridge")
    with pytest.raises(ValueError):
        run_multi_seed(num_seeds=0)


def test_describe() -> None:
    d = describe([1.0, 2.0, 3.0, 4.0])
    assert d["n"] == 4 and d["mean"] == 2.5 and d["min"] == 1.0 and d["max"] == 4.0
    assert d["sd"] == pytest.approx(math.sqrt(5 / 3))
    assert describe([7.0])["sd"] is None
    assert describe([]) == {"n": 0, "mean": None, "sd": None, "min": None, "max": None}


def test_seeded_run_config_leaves_base_untouched() -> None:
    base = default_study_config(DURATION)
    cfg = seeded_run_config(base, 99, DURATION)
    assert cfg["simulation"]["randomSeed"] == 99
    assert "randomSeed" not in base["simulation"]
    assert "totalVehicles" not in base["traffic"]
