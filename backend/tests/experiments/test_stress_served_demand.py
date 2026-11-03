"""Stress breakpoints say when the preferred strategy served less (F-54).

``run_breakpoints`` prefers, at each level, the strategy with the lowest mean
delay. Delay averages only vehicles that finished, so a strategy that admits
less of the demand can be preferred for that reason alone. Each level row now
reports the strategies' served shares and ``preferredServedLess``; which
strategy is preferred is unchanged.
"""

from __future__ import annotations

from typing import Any, Dict, List

from src.stress.lab import run_breakpoints
from tests.experiments.test_stress import default_scenario


def _executor(admitted: Dict[str, float]) -> Any:
    def run(tasks: List[Any], progress: Any = None) -> List[Any]:
        out = []
        for t in tasks:
            strategy = "roundabout" if "roundabout" in t.label else "fixed_time"
            out.append(
                {
                    "metrics": {
                        # The roundabout always has the lower delay.
                        "averageDelay": 30.0 if strategy == "roundabout" else 50.0,
                        "unfinishedShare": 0.2,
                        "demandAccounting": {
                            "admittedShareOfNominal": admitted[strategy]
                        },
                    }
                }
            )
        return out

    return run


def _rows(admitted: Dict[str, float]) -> List[Dict[str, Any]]:
    result = run_breakpoints(
        default_scenario(),
        "demand_scale",
        [0.5, 1.0, 1.5],
        ["fixed_time", "roundabout"],
        1,
        2,
        _executor(admitted),
    )
    rows: List[Dict[str, Any]] = result["table"]
    return rows


def test_a_preference_bought_by_serving_less_is_flagged() -> None:
    rows = _rows({"roundabout": 0.55, "fixed_time": 0.95})
    assert all(r["preferred"] == "roundabout" for r in rows)
    assert all(r["preferredServedLess"] is True for r in rows)
    assert rows[0]["servedDemand"]["roundabout"]["admittedShareOfNominal"] == 0.55


def test_a_preference_that_served_as_much_is_not_flagged() -> None:
    rows = _rows({"roundabout": 0.95, "fixed_time": 0.93})
    assert all(r["preferred"] == "roundabout" for r in rows)
    assert not any(r["preferredServedLess"] for r in rows)


def test_results_without_the_measures_are_not_flagged() -> None:
    def run(tasks: List[Any], progress: Any = None) -> List[Any]:
        return [
            {"metrics": {"averageDelay": 30.0 if "roundabout" in t.label else 50.0}}
            for t in tasks
        ]

    result = run_breakpoints(
        default_scenario(),
        "demand_scale",
        [0.5, 1.0, 1.5],
        ["fixed_time", "roundabout"],
        1,
        2,
        run,
    )
    assert not any(r["preferredServedLess"] for r in result["table"])
    assert result["table"][0]["servedDemand"]["roundabout"] == {
        "averageDelay": 30.0,
        "admittedShareOfNominal": None,
        "unfinishedShare": None,
    }
