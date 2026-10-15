"""run_simulation_tasks_isolated: one failing simulation is reported, the others still return."""

from typing import Any, Dict, List

import jsonschema
import pytest

from src.core.limits import demand_vehicle_limit
from src.core.scenario import _validate_against_config_schema
from src.core.schema import CONFIG_SCHEMA
from src.study import runner
from src.study.runner import (
    Progress,
    SimTask,
    run_simulation_tasks,
    run_simulation_tasks_isolated,
)


def _config(seed: int) -> Dict[str, Any]:
    rate = 0.3
    return {
        "simulation": {
            "timeStep": 0.1,
            "duration": 8.0,
            "warmupTime": 2.0,
            "randomSeed": seed,
        },
        "roads": {
            "approachLength": 200.0,
            "laneWidth": 3.5,
            "lanesPerApproach": {d: 1 for d in ("north", "south", "east", "west")},
        },
        "traffic": {
            "arrivalRate": rate,
            "arrivalDistribution": "poisson",
            "totalVehicles": demand_vehicle_limit(rate, 8.0),
        },
    }


def _tasks() -> List[SimTask]:
    broken = _config(2)
    broken["simulation"]["timeStep"] = (
        "not a number"  # raises while the engine is built
    )
    return [
        SimTask(_config(1), "signal", 8.0, "good 1"),
        SimTask(broken, "signal", 8.0, "broken"),
        SimTask(_config(3), "roundabout", 8.0, "good 3"),
    ]


def _check(results: List[Any]) -> None:
    assert isinstance(results[1], Exception)
    for good in (results[0], results[2]):
        assert isinstance(good, dict) and "metrics" in good


def test_inline_isolation_returns_the_exception_and_keeps_the_others() -> None:
    progress = Progress()
    results = run_simulation_tasks_isolated(_tasks(), progress)
    _check(results)
    snap = progress.snapshot()
    assert snap["total"] == 3 and snap["completed"] == 3


def test_the_all_or_nothing_runner_still_raises() -> None:
    with pytest.raises(Exception):  # noqa: B017 - the contract being pinned is "raises"
        run_simulation_tasks(_tasks())


def test_process_pool_isolation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STUDY_WORKERS", "2")
    try:
        results = run_simulation_tasks_isolated(_tasks())
    finally:
        runner.shutdown_pool()
    _check(results)


def test_isolated_results_equal_the_plain_runner_when_nothing_fails() -> None:
    good = [
        SimTask(_config(5), "signal", 8.0, "a"),
        SimTask(_config(6), "signal", 8.0, "b"),
    ]
    assert run_simulation_tasks_isolated(good) == run_simulation_tasks(good)


def test_cached_config_validator_matches_jsonschema_validate() -> None:
    """The cached validator raises the same best-match error as jsonschema.validate."""
    valid = {
        "simulation": {"timeStep": 0.1, "duration": 10.0, "randomSeed": 1},
        "traffic": {
            "arrivalRate": 0.2,
            "arrivalDistribution": "poisson",
            "totalVehicles": 50,
        },
    }
    bad = {"simulation": {"timeStep": 0.1, "duration": -5.0, "randomSeed": 1}}
    for payload in (valid, bad):
        try:
            jsonschema.validate(instance=payload, schema=CONFIG_SCHEMA)
            expected = None
        except jsonschema.ValidationError as err:
            expected = (err.message, list(err.absolute_path))
        try:
            _validate_against_config_schema(payload)
            got = None
        except jsonschema.ValidationError as err:
            got = (err.message, list(err.absolute_path))
        assert got == expected
        if payload is bad:
            assert expected is not None  # the comparison is not vacuous
