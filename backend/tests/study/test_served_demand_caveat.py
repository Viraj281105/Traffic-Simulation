"""A delay comparison says when the strategies served different populations.

Mean delay averages only vehicles that finished their trip. A strategy that
admits less of the offered demand (F-50) or leaves more of it in the network
at the end (F-41) can show a lower mean delay for that reason alone, so every
paired delay comparison reports how far the two served populations differ,
and a planning study flags it in its validity block and findings. The delay
``reading`` itself is unchanged.
"""

from __future__ import annotations

from typing import Any, Dict, List

from src.planning.findings import generate_findings
from src.planning.runner import _served_demand, _served_demand_differs
from src.scenario.documents import parse_scenario
from src.study import control_comparison as cc


def test_shares_within_tolerance_are_comparable() -> None:
    a = {
        "averageDelay": [40.0, 42.0],
        "admittedShareOfNominal": [0.98, 1.0],
        "unfinishedShare": [0.10, 0.12],
    }
    b = {
        "averageDelay": [50.0, 52.0],
        "admittedShareOfNominal": [0.97, 0.99],
        "unfinishedShare": [0.13, 0.12],
    }
    out = cc._served_demand(a, b)
    assert out["comparable"] is True
    assert out["lowerDelayServedLess"] is False
    assert out["admittedShareOfNominalDifference"] == 0.01
    assert out["unfinishedShareDifference"] == -0.015


def test_lower_delay_from_admitting_less_is_flagged() -> None:
    # a has the lower delay but admitted far less of the demand.
    a = {
        "averageDelay": [60.0, 62.0],
        "admittedShareOfNominal": [0.52, 0.55],
        "unfinishedShare": [0.30, 0.34],
    }
    b = {
        "averageDelay": [80.0, 84.0],
        "admittedShareOfNominal": [0.97, 0.99],
        "unfinishedShare": [0.30, 0.33],
    }
    out = cc._served_demand(a, b)
    assert out["comparable"] is False
    assert out["lowerDelayServedLess"] is True
    assert out["admittedShareOfNominalDifference"] == -0.445
    # Same populations, delays swapped: b (now lower) served more. The
    # difference strengthens the reading, so it is not flagged.
    a["averageDelay"], b["averageDelay"] = b["averageDelay"], a["averageDelay"]
    out = cc._served_demand(a, b)
    assert out["comparable"] is False
    assert out["lowerDelayServedLess"] is False


def test_lower_delay_from_leaving_more_unfinished_is_flagged() -> None:
    a = {"averageDelay": [30.0], "unfinishedShare": [0.32]}
    b = {"averageDelay": [55.0], "unfinishedShare": [0.21]}
    assert cc._served_demand(a, b)["lowerDelayServedLess"] is True


def test_measured_study_shape_is_not_flagged() -> None:
    """Measured (600 s, 5 seeds, 300 veh/h per arm): the roundabout's lower
    delay came with a lower unfinished share, i.e. it served more."""
    fixed = {
        "averageDelay": [56.0],
        "admittedShareOfNominal": [1.02],
        "unfinishedShare": [0.21],
    }
    roundabout = {
        "averageDelay": [31.0],
        "admittedShareOfNominal": [1.02],
        "unfinishedShare": [0.11],
    }
    out = cc._served_demand(fixed, roundabout)
    assert out["comparable"] is False
    assert out["lowerDelayServedLess"] is False


def test_missing_measures_do_not_flag() -> None:
    out = cc._served_demand({}, {"unfinishedShare": [0.2]})
    assert out == {
        "admittedShareOfNominalDifference": None,
        "unfinishedShareDifference": None,
        "comparable": True,
        "lowerDelayServedLess": False,
        # Checkpoint 10: the entry-wait reading, absent measures included.
        "averageEntryWaitDifference": None,
        "entryWaitReversesDelay": False,
    }


def test_admitted_share_is_read_from_the_demand_accounting() -> None:
    m = {"unfinishedShare": 0.2, "demandAccounting": {"admittedShareOfNominal": 0.6}}
    assert cc._measure(m, "admittedShareOfNominal") == 0.6
    assert cc._measure(m, "unfinishedShare") == 0.2
    assert cc._measure({"demandAccounting": None}, "admittedShareOfNominal") is None


def _row(
    alt: str, scale: float, delay: float, admitted: float, unfinished: float
) -> Dict[str, Any]:
    row = {
        "controls": {
            "s": {
                "averageDelay": {"mean": delay},
                "admittedShareOfNominal": {"mean": admitted},
                "unfinishedShare": {"mean": unfinished},
            }
        }
    }
    return {
        "alternativeId": alt,
        "demandScale": scale,
        "servedDemand": _served_demand(row, "s"),
    }


def test_planning_flags_a_delay_advantage_from_serving_less() -> None:
    rows: List[Dict[str, Any]] = [
        _row("base", 1.0, 50.0, 0.95, 0.20),
        _row("alt", 1.0, 40.0, 0.94, 0.21),  # similar populations
        _row("base", 1.5, 90.0, 0.90, 0.25),
        _row("alt", 1.5, 70.0, 0.60, 0.26),  # better delay, admitted 30 pts less
        _row("base", 2.0, 90.0, 0.70, 0.25),
        _row("alt", 2.0, 120.0, 0.60, 0.26),  # worse delay and served less: fine
    ]
    flagged = _served_demand_differs(rows, "base")
    assert [(f["alternativeId"], f["demandScale"]) for f in flagged] == [("alt", 1.5)]
    validity = {"servedDemandDiffers": flagged}
    findings = generate_findings([], [], [], [1, 2, 3, 4, 5], validity, [])
    flagged_findings = [
        f for f in findings if {"path": "validity.servedDemandDiffers"} in f["evidence"]
    ]
    assert len(flagged_findings) == 1, findings
    assert flagged_findings[0]["kind"] == "reliability"
    none = generate_findings(
        [], [], [], [1, 2, 3, 4, 5], {"servedDemandDiffers": []}, []
    )
    assert not any(
        {"path": "validity.servedDemandDiffers"} in f["evidence"] for f in none
    )


def test_scenario_comparison_reports_served_demand_per_pair() -> None:
    document, errors = parse_scenario(
        {
            "format": "urbanflow-scenario",
            "version": 1,
            "name": "served",
            "junction": {"type": "fixed_time_signal"},
            "approaches": {
                d: {"lanes": 1, "length": 80.0, "vehiclesPerHour": 900}
                for d in ("north", "south", "east", "west")
            },
            "simulation": {"duration": 60.0, "warmup": 10.0, "seed": 3},
        }
    )
    assert document is not None and not errors, errors
    out = cc.run_scenario_comparison(
        document, ["fixed_time", "roundabout"], num_seeds=2
    )
    row = out["results"][0]
    pair = row["delayComparisons"]["fixed_time_vs_roundabout"]
    assert set(pair["servedDemand"]) == {
        "admittedShareOfNominalDifference",
        "unfinishedShareDifference",
        "comparable",
        "lowerDelayServedLess",
        "averageEntryWaitDifference",
        "entryWaitReversesDelay",
    }
    for strategy in ("fixed_time", "roundabout"):
        assert "admittedShareOfNominal" in row["controls"][strategy]
        assert "unfinishedShare" in row["controls"][strategy]
    assert "servedDemand" in out["method"]
    seed_row = out["perSeed"][0]["roundabout"]
    acc = seed_row["demandAccounting"]
    assert acc["arrivals"] == acc["admitted"] + acc["waitingAtEntry"]
