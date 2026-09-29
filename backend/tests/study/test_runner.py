"""Parallel study execution (src/study/runner.py) must not change results.

The volume sweep and Monte Carlo study used to step both geometries of a
DualSimulationOrchestrator in lockstep, in one process. They now run each
geometry on its own, in a pool of worker processes. These tests pin that
the two give identical numbers.
"""

import json
import random
import re
from typing import Any, Dict

import pytest

from src.core.limits import demand_vehicle_limit
from src.snapshot.dual_orchestrator import DualSimulationOrchestrator
from src.study import runner
from src.study.runner import Progress, simulate_geometry, study_workers
from src.study.validation import run_statistical_validation
from src.study.volume_sweep import run_volume_sweep_experiment


def _config(rate: float, lanes: int, duration: float, seed: int) -> Dict[str, Any]:
    return {
        "simulation": {
            "timeStep": 0.1,
            "duration": duration,
            "warmupTime": 5.0,
            "randomSeed": seed,
        },
        "roads": {
            "approachLength": 200.0,
            "laneWidth": 3.5,
            "lanesPerApproach": {d: lanes for d in ("north", "south", "east", "west")},
        },
        "traffic": {
            "arrivalRate": rate,
            "arrivalDistribution": "poisson",
            "totalVehicles": demand_vehicle_limit(rate, duration),
        },
    }


def _lockstep_metrics(config: Dict[str, Any], duration: float) -> Dict[str, Any]:
    """The pre-runner study loop, verbatim in effect."""
    orch = DualSimulationOrchestrator(config)
    for _ in range(orch.clock_signal.ticks_for_duration(duration)):
        orch.engine_signal.step()
        orch.engine_roundabout.step()
    out = {}
    for geometry in ("signal", "roundabout"):
        engine = getattr(orch, f"engine_{geometry}")
        out[geometry] = getattr(orch, f"collector_{geometry}").get_metrics(
            getattr(orch, f"clock_{geometry}").get_elapsed_time(),
            engine.pool.active_vehicles,
            engine.pool.exited_vehicles,
            engine.spawner.spawned_count if engine.spawner else 0,
            engine.pool.collision_count,
        )
    return out


@pytest.mark.parametrize(
    "rate,lanes,seed", [(0.5, 1, 42), (0.8, 2, 7)], ids=["1-lane", "2-lane"]
)
def test_one_geometry_alone_matches_the_lockstep_pair(
    rate: float, lanes: int, seed: int
) -> None:
    duration = 40.0
    lockstep = _lockstep_metrics(_config(rate, lanes, duration, seed), duration)
    for geometry in ("signal", "roundabout"):
        alone = simulate_geometry(
            _config(rate, lanes, duration, seed), geometry, duration
        )
        assert alone["metrics"] == lockstep[geometry]
        assert alone["steps"] == 400
        assert alone["config"]["geometry"]["intersectionType"] == (
            "fixed_time_signal" if geometry == "signal" else "roundabout"
        )


def _normalise_sweep(result: Dict[str, Any]) -> str:
    text = json.dumps(result, sort_keys=True)
    text = text.replace(result["sessionId"], "SESSION")
    return re.sub(r"sweep_[0-9a-f]{8}_", "sweep_X_", text)


def test_process_pool_gives_the_inline_results(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.database import db

    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "runner.db"))
    kwargs: Dict[str, Any] = {
        "arrival_rates": [0.2, 0.6],
        "duration": 15.0,
        "random_seed": 11,
    }

    inline_sweep = run_volume_sweep_experiment(**kwargs)
    random.seed(5)
    inline_mc = run_statistical_validation(num_seeds=3, duration=10.0)

    monkeypatch.setenv("STUDY_WORKERS", "2")
    try:
        progress = Progress()
        pooled_sweep = run_volume_sweep_experiment(**kwargs, progress=progress)
        random.seed(5)
        pooled_mc = run_statistical_validation(num_seeds=3, duration=10.0)
    finally:
        runner.shutdown_pool()

    assert _normalise_sweep(pooled_sweep) == _normalise_sweep(inline_sweep)
    assert pooled_mc == inline_mc

    snap = progress.snapshot()
    assert snap["total"] == 4
    assert snap["completed"] == 4
    assert snap["fraction"] == 1.0
    assert snap["running"] == []
    assert snap["phase"] == "saving"


def test_progress_reports_real_state_and_withholds_early_eta() -> None:
    progress = Progress()
    assert progress.snapshot()["phase"] == "queued"
    progress.begin(["a", "b", "c", "d"])
    progress.advance(0, 0.5)
    progress.advance(1, 0.0)
    snap = progress.snapshot()
    assert snap["running"] == ["a", "b"]
    assert snap["completed"] == 0
    assert snap["fraction"] == pytest.approx(0.125)
    assert snap["etaSeconds"] is None  # too little done to extrapolate

    progress.finish(0)
    progress.advance(0, 0.3)  # a late message never moves a task backwards
    snap = progress.snapshot()
    assert snap["completed"] == 1
    assert snap["running"] == ["b"]
    assert snap["fraction"] == pytest.approx(0.25)


@pytest.mark.parametrize("value,expected", [("0", 0), ("3", 3), ("999", 32), ("-4", 0)])
def test_study_workers_setting(
    monkeypatch: pytest.MonkeyPatch, value: str, expected: int
) -> None:
    monkeypatch.setenv("STUDY_WORKERS", value)
    assert study_workers() == expected


def test_study_workers_default_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STUDY_WORKERS", raising=False)
    monkeypatch.setattr(runner.os, "cpu_count", lambda: 64)
    assert study_workers() == runner.MAX_AUTO_WORKERS
    monkeypatch.setattr(runner.os, "cpu_count", lambda: 2)
    assert study_workers() == 2
    monkeypatch.setattr(runner.os, "cpu_count", lambda: None)
    assert study_workers() == 1
    monkeypatch.setenv("STUDY_WORKERS", "not-a-number")
    assert study_workers() == 1
