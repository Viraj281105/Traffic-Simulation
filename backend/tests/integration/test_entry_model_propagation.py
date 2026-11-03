"""The entry model (traffic.entryQueue) reaches every place a run is set up,
reported or exported (F-50, checkpoint 10).

Checkpoint 9 made the point queue available in engine configs and scenario
documents. These tests pin the remaining paths: the dashboard's flat payload
(the guided comparison, the live session and the reliability check all send
it), the built-in three-way study, the study outputs that label which model
ran, the entry-wait caution on paired comparisons, and the experiment
package, whose request member carries the scenario document.
"""

from __future__ import annotations

import copy
import io
import json
import zipfile
from typing import Any, Dict, List

import pytest
from fastapi import HTTPException

from src.live.dashboard_config import compile_dashboard_config
from src.study import control_comparison as cc
from src.study.router import ControlComparisonRequest
from src.study.tolerances import entry_wait_reverses_delay
from tests.experiments.conftest import (
    SCENARIO,
    FakeExecutor,
    as_user,
    build_client,
    submit,
    wait_for,
)

BASE_PAYLOAD: Dict[str, Any] = {
    "intersectionType": "fixed_time_signal",
    "lanesNorth": 1,
    "lanesSouth": 1,
    "lanesEast": 1,
    "lanesWest": 1,
    "arrivalRate": 0.5,
    "duration": 120,
    "randomSeed": 7,
}


# ---- dashboard payload ------------------------------------------------------------------------------


def test_dashboard_payload_without_the_option_is_unchanged() -> None:
    plain = compile_dashboard_config(dict(BASE_PAYLOAD), 7)
    assert "entryQueue" not in plain["traffic"]
    for off in (None, {"enabled": False}, {"enabled": False, "capacity": 4}):
        cfg = compile_dashboard_config({**BASE_PAYLOAD, "entryQueue": off}, 7)
        assert cfg == plain


@pytest.mark.parametrize("capacity", [None, 1, 40, 5000])
def test_dashboard_payload_enables_the_point_queue(capacity: Any) -> None:
    cfg = compile_dashboard_config(
        {**BASE_PAYLOAD, "entryQueue": {"enabled": True, "capacity": capacity}}, 7
    )
    assert cfg["traffic"]["entryQueue"] == {"enabled": True, "capacity": capacity}


@pytest.mark.parametrize(
    "bad",
    [
        True,
        "queue",
        {"enabled": "yes"},
        {"enabled": True, "capacity": 0},
        {"enabled": True, "capacity": 5001},
        {"enabled": True, "capacity": 2.5},
    ],
)
def test_dashboard_payload_rejects_a_malformed_queue(bad: Any) -> None:
    with pytest.raises(HTTPException) as err:
        compile_dashboard_config({**BASE_PAYLOAD, "entryQueue": bad}, 7)
    assert err.value.status_code == 400


def test_dashboard_scenario_document_carries_its_own_queue() -> None:
    doc = copy.deepcopy(SCENARIO)
    doc["traffic"] = {"entryQueue": {"enabled": True, "capacity": 9}}
    cfg = compile_dashboard_config({**BASE_PAYLOAD, "scenario": doc}, 7)
    assert cfg["traffic"]["entryQueue"] == {"enabled": True, "capacity": 9}


def test_live_session_runs_the_queue_it_was_given() -> None:
    from src.core.clock import Clock
    from src.engine.simulation_engine import SimulationEngine

    cfg = compile_dashboard_config(
        {**BASE_PAYLOAD, "entryQueue": {"enabled": True, "capacity": 3}}, 7
    )
    engine = SimulationEngine(Clock(time_step=0.1), duration=120.0, config=cfg)
    assert engine.spawner is not None
    assert engine.spawner.entry_queue is True
    assert engine.spawner.entry_queue_capacity == 3
    assert engine.spawner.demand_accounting()["entryModel"] == "queue"


# ---- studies ----------------------------------------------------------------------------------------


def _capture_tasks(monkeypatch: pytest.MonkeyPatch) -> List[Any]:
    seen: List[Any] = []

    def fake_run(tasks: List[Any], progress: Any = None) -> List[Any]:
        seen.extend(tasks)
        return [
            {
                "metrics": {
                    "averageDelay": 30.0 + i % 3,
                    "averageEntryWait": 2.0,
                    "unfinishedShare": 0.1,
                    "demandAccounting": {"admittedShareOfNominal": 0.95},
                }
            }
            for i, _ in enumerate(tasks)
        ]

    monkeypatch.setattr(cc, "run_simulation_tasks", fake_run)
    return seen


def test_three_way_study_runs_every_control_under_the_chosen_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = _capture_tasks(monkeypatch)
    out = cc.run_control_comparison(
        levels=["busy"],
        num_seeds=2,
        duration=60.0,
        entry_queue={"enabled": True, "capacity": 12},
    )
    assert seen and all(
        t.config["traffic"]["entryQueue"] == {"enabled": True, "capacity": 12}
        for t in seen
    )
    assert out["entryModel"] == {"model": "queue", "capacity": 12}
    assert "entryModel" in out["method"]


def test_three_way_study_default_is_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = _capture_tasks(monkeypatch)
    out = cc.run_control_comparison(levels=["busy"], num_seeds=2, duration=60.0)
    assert all("entryQueue" not in t.config["traffic"] for t in seen)
    assert out["entryModel"] == {"model": "suspend", "capacity": None}


def test_scenario_study_labels_the_documents_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.scenario.documents import parse_scenario

    _capture_tasks(monkeypatch)
    doc = copy.deepcopy(SCENARIO)
    doc["traffic"] = {"entryQueue": {"enabled": True}}
    document, errors = parse_scenario(doc)
    assert not errors
    out = cc.run_scenario_comparison(document, ["fixed_time", "roundabout"], 2)
    assert out["entryModel"] == {"model": "queue", "capacity": None}
    for cfg in out["compiledConfigs"].values():
        assert cfg["traffic"]["entryQueue"]["enabled"] is True


def test_request_accepts_the_queue_for_the_built_in_junction_only() -> None:
    req = ControlComparisonRequest(entryQueue={"enabled": True, "capacity": 5})
    assert req.entryQueue is not None and req.entryQueue.capacity == 5
    with pytest.raises(ValueError, match="entryQueue"):
        ControlComparisonRequest(
            scenario=copy.deepcopy(SCENARIO), entryQueue={"enabled": True}
        )
    with pytest.raises(ValueError):
        ControlComparisonRequest(entryQueue={"enabled": True, "capcity": 5})


# ---- the entry-wait caution -------------------------------------------------------------------------


def test_entry_wait_reversal_matches_the_checkpoint_9_case() -> None:
    # Fixed-time vs roundabout at 900 veh/h per arm, point queue (F-50 table):
    # fixed-time has the lower in-network delay, the roundabout the lower
    # delay from arrival.
    fixed = {"averageDelay": [153.8], "averageEntryWait": [80.1]}
    roundabout = {"averageDelay": [157.1], "averageEntryWait": [62.7]}
    assert entry_wait_reverses_delay(fixed, roundabout) is True
    assert entry_wait_reverses_delay(roundabout, fixed) is True


@pytest.mark.parametrize(
    "a, b",
    [
        # Same order with and without the wait.
        (
            {"averageDelay": [10.0], "averageEntryWait": [1.0]},
            {"averageDelay": [20.0], "averageEntryWait": [5.0]},
        ),
        # Equal delays: nothing to reverse.
        (
            {"averageDelay": [10.0], "averageEntryWait": [9.0]},
            {"averageDelay": [10.0], "averageEntryWait": [1.0]},
        ),
        # Saved before the measure existed.
        ({"averageDelay": [10.0]}, {"averageDelay": [20.0]}),
        # Sums tied.
        (
            {"averageDelay": [10.0], "averageEntryWait": [5.0]},
            {"averageDelay": [12.0], "averageEntryWait": [3.0]},
        ),
    ],
)
def test_entry_wait_reversal_is_not_flagged_otherwise(a: Any, b: Any) -> None:
    assert entry_wait_reverses_delay(a, b) is False


def test_paired_comparison_reports_the_entry_wait() -> None:
    served = cc._served_demand(
        {
            "averageDelay": [150.0, 157.6],
            "averageEntryWait": [80.0, 80.2],
            "admittedShareOfNominal": [0.5, 0.5],
            "unfinishedShare": [0.4, 0.4],
        },
        {
            "averageDelay": [157.0, 157.2],
            "averageEntryWait": [62.0, 63.4],
            "admittedShareOfNominal": [0.55, 0.55],
            "unfinishedShare": [0.4, 0.4],
        },
    )
    assert served["averageEntryWaitDifference"] == pytest.approx(17.4)
    assert served["entryWaitReversesDelay"] is True
    # The served-demand reading is independent of the entry-wait one.
    assert served["lowerDelayServedLess"] is False


# ---- export -----------------------------------------------------------------------------------------


def test_experiment_package_carries_the_entry_model(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.experiments.service import ExperimentService
    from src.experiments.store import ExperimentStore

    monkeypatch.setattr("src.database.db.DB_PATH", str(tmp_path / "experiments.db"))
    service = ExperimentService(
        store=ExperimentStore(persist=False), executor=FakeExecutor()
    )
    client = build_client(service)
    queued = copy.deepcopy(SCENARIO)
    queued["traffic"] = {"entryQueue": {"enabled": True, "capacity": 20}}
    fingerprints = {}
    for label, scenario in (("plain", copy.deepcopy(SCENARIO)), ("queued", queued)):
        eid = submit(client, "alice", scenario=scenario)["id"]
        assert wait_for(client, eid)["status"] == "completed"
        res = client.get(f"/api/v3/experiments/{eid}/package", headers=as_user("alice"))
        assert res.status_code == 200
        with zipfile.ZipFile(io.BytesIO(res.content)) as zf:
            request = json.loads(zf.read("experiment.json"))
            manifest = json.loads(zf.read("manifest.json"))
        traffic = request["scenario"].get("traffic") or {}
        if label == "queued":
            assert traffic["entryQueue"] == {"enabled": True, "capacity": 20}
        else:
            assert "entryQueue" not in traffic
        fingerprints[label] = manifest["scenarioFingerprint"]
    # The model is part of the scenario's identity, so the two runs can never
    # be mistaken for the same experiment.
    assert fingerprints["plain"] != fingerprints["queued"]


# ---- stored-run comparison --------------------------------------------------------------------------


def _stored(config: Dict[str, Any], delay: float) -> Dict[str, Any]:
    return {
        "intersection_type": "fixed_time_signal",
        "random_seed": 7,
        "arrival_rate": 0.5,
        "config": config,
        "summary_metrics": {"averageDelay": delay, "throughput": 100},
    }


def test_run_comparison_warns_when_entry_models_differ() -> None:
    from src.history.router import compare_runs

    plain = {"traffic": {"arrivalRate": 0.5}}
    queued = {"traffic": {"arrivalRate": 0.5, "entryQueue": {"enabled": True}}}
    in_doc = {"scenario": {"traffic": {"entryQueue": {"enabled": True}}}}

    same = compare_runs(_stored(plain, 30), _stored(plain, 40), "a", "b")
    assert same["warnings"] == []
    assert same["entryModels"] == {"runA": "suspend", "runB": "suspend"}

    mixed = compare_runs(_stored(plain, 30), _stored(queued, 40), "a", "b")
    assert mixed["entryModels"] == {"runA": "suspend", "runB": "queue"}
    assert len(mixed["warnings"]) == 1
    assert "different entry models" in mixed["warnings"][0]
    # The deltas are kept for existing clients, now beside the warning.
    assert mixed["comparison"]["delayDelta"] == 10.0

    both = compare_runs(_stored(queued, 30), _stored(in_doc, 40), "a", "b")
    assert both["warnings"] == []

    # A run that stored no configuration cannot be judged either way.
    unknown = compare_runs(_stored({}, 30), _stored(queued, 40), "a", "b")
    assert unknown["entryModels"]["runA"] is None
    assert unknown["warnings"] == []
