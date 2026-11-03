"""The entry model through the Discovery Lab, the Stress Lab and experiment
results (checkpoint 11).

Checkpoint 10 left Discovery and the stress generator on the default model:
neither request could carry ``entryQueue``, and both built fresh scenario
documents. These tests drive the real search and suite code with an executor
that records the compiled engine configs, so they show the option reaching
every simulation (candidates, baselines, held-out and unseen-grid runs,
every generated scenario and strategy), and that leaving it out changes
nothing, fingerprints included. One test runs the real engine.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List

import pytest

from src.discovery.evaluator import SimulationEvaluator, objectives_of, run_task
from src.discovery.models import SearchSpec
from src.discovery.search import Search
from src.discovery.space import candidate_document, regime_scenario
from src.scenario.documents import parse_scenario, scenario_entry_model
from src.stress import lab
from src.stress.service import BreakpointRequest, SuiteRequest, default_scenario
from src.study.runner import run_simulation_tasks

QUEUE = {"enabled": True, "capacity": 25}


def _metrics(i: int) -> Dict[str, Any]:
    return {
        "metrics": {
            "averageDelay": 30.0 + (i % 5),
            "averageEntryWait": 4.0,
            "throughput": 50,
            "maxQueueLength": 6,
            "nearMissCount": 0,
            "collisionCount": 0,
            "unfinishedShare": 0.1,
            "demandAccounting": {"admittedShareOfNominal": 0.9},
        }
    }


class Recorder:
    """Stands in for the worker pool; keeps every compiled config it is given."""

    def __init__(self) -> None:
        self.configs: List[Dict[str, Any]] = []

    def __call__(self, tasks: List[Any], progress: Any = None) -> List[Any]:
        self.configs.extend(t.config for t in tasks)
        return [_metrics(i) for i, _ in enumerate(tasks)]


def _spec(queue: Any = None, unseen: bool = False) -> SearchSpec:
    regime: Dict[str, Any] = {"vehiclesPerHour": 500, "duration": 60, "warmup": 10}
    if queue is not None:
        regime["entryQueue"] = queue
    return SearchSpec.model_validate(
        {
            "regime": regime,
            "budget": {
                "population": 4,
                "generations": 1,
                "tuningSeeds": 1,
                "selectionSeeds": 2,
                "heldOutSeeds": 10,
                "paretoCap": 2,
                "shortlist": 1,
                "unseenGrid": unseen,
            },
            "strategies": ["fixed_time", "roundabout"],
        }
    )


# ---- Discovery ----------------------------------------------------------------------------------


def test_discovery_fingerprint_is_unchanged_without_the_queue() -> None:
    plain = _spec()
    assert _spec({"enabled": False}).fingerprint() == plain.fingerprint()
    assert _spec({"enabled": False, "capacity": 9}).fingerprint() == plain.fingerprint()
    assert _spec(QUEUE).fingerprint() != plain.fingerprint()
    assert "traffic" not in regime_scenario(plain.regime)


def test_discovery_regime_keeps_aggression_and_queue_together() -> None:
    spec = SearchSpec.model_validate(
        {"regime": {"aggression": "high", "entryQueue": QUEUE}}
    )
    doc = regime_scenario(spec.regime)
    assert doc["traffic"] == {
        "driverAggression": "high",
        "entryQueue": {"enabled": True, "capacity": 25},
    }
    parsed, errors = parse_scenario(doc)
    assert parsed is not None and not errors
    assert scenario_entry_model(parsed) == {"model": "queue", "capacity": 25}


@pytest.mark.parametrize("unseen", [False, True])
def test_every_discovery_run_uses_the_requested_model(unseen: bool) -> None:
    recorder = Recorder()
    result = Search(_spec(QUEUE, unseen), SimulationEvaluator(executor=recorder)).run()
    assert recorder.configs, "no simulation was compiled"
    assert all(
        c["traffic"].get("entryQueue") == {"enabled": True, "capacity": 25}
        for c in recorder.configs
    )
    assert result["entryModel"] == {"model": "queue", "capacity": 25}
    held = result["heldOut"]
    assert held is not None
    for row in list(held["candidates"].values()) + list(held["baselines"].values()):
        served = row["servedDemand"]
        assert served["averageEntryWait"] == 4.0
        assert served["admittedShareOfNominal"] == 0.9
        # The objective is the delay from arrival; the in-network part is kept.
        assert row["objectives"]["averageDelay"] == pytest.approx(
            served["inNetworkDelay"] + 4.0
        )
    for row in held["candidates"].values():
        assert all("lowerDelayServedLess" in v for v in row["versusBaselines"].values())


def test_default_discovery_is_unchanged() -> None:
    recorder = Recorder()
    result = Search(_spec(), SimulationEvaluator(executor=recorder)).run()
    assert all("entryQueue" not in c["traffic"] for c in recorder.configs)
    assert result["entryModel"] == {"model": "suspend", "capacity": None}
    for row in result["heldOut"]["baselines"].values():
        # In-network delay only, as before; no inNetworkDelay beside it.
        assert "inNetworkDelay" not in (row["servedDemand"] or {})


def test_discovery_delay_objective_counts_entry_wait_only_under_the_queue() -> None:
    runs = [_metrics(0), _metrics(1)]
    plain, plain_metrics, _, _ = objectives_of(runs)
    queued, queued_metrics, _, _ = objectives_of(runs, delay_from_arrival=True)
    assert plain is not None and queued is not None
    assert plain[0] == pytest.approx(30.5)
    assert queued[0] == pytest.approx(34.5)
    assert queued_metrics["inNetworkDelay"] == pytest.approx(30.5)
    assert plain[1:] == queued[1:]


def test_discovery_candidates_keep_the_model_through_the_genome_patch() -> None:
    spec = _spec(QUEUE)
    genome = {
        "strategy": "fixed_time",
        "nsGreen": 30.0,
        "ewGreen": 25.0,
        "yellow": 4.0,
        "allRed": 2.0,
    }
    doc = candidate_document(spec.regime, genome, "fixed_time")
    assert doc["traffic"]["entryQueue"]["enabled"] is True
    task = run_task(doc, "fixed_time", 3, "t")
    assert task.config["traffic"]["entryQueue"] == {"enabled": True, "capacity": 25}


def test_a_discovery_task_runs_the_queue_in_the_real_engine() -> None:
    spec = _spec({"enabled": True})
    doc = regime_scenario(spec.regime)
    [result] = run_simulation_tasks([run_task(doc, "fixed_time", 1, "real")])
    accounting = result["metrics"]["demandAccounting"]
    assert accounting["entryModel"] == "queue"
    assert accounting["arrivals"] == (
        accounting["admitted"] + accounting["waitingAtEntry"] + accounting["rejected"]
    )


# ---- Stress Lab ---------------------------------------------------------------------------------


def test_stress_suite_runs_every_scenario_and_strategy_with_the_queue() -> None:
    recorder = Recorder()
    out = lab.run_suite(
        3, 4, ["fixed_time", "roundabout"], 1, 60.0, recorder, None, QUEUE
    )
    assert len(recorder.configs) >= 4
    assert all(
        c["traffic"].get("entryQueue") == {"enabled": True, "capacity": 25}
        for c in recorder.configs
    )
    assert out["entryModel"] == {"model": "queue", "capacity": 25}
    for row in out["scenarios"]:
        assert "lowestDelayServedLess" in row
        for cell in row["results"].values():
            if "skipped" not in cell:
                assert cell["admittedShareOfNominal"] == 0.9


def test_default_stress_suite_and_its_fingerprint_are_unchanged() -> None:
    recorder = Recorder()
    plain = lab.run_suite(3, 4, ["fixed_time"], 1, 60.0, recorder)
    again = lab.run_suite(3, 4, ["fixed_time"], 1, 60.0, Recorder(), None, None)
    off = lab.run_suite(
        3, 4, ["fixed_time"], 1, 60.0, Recorder(), None, {"enabled": False}
    )
    queued = lab.run_suite(3, 4, ["fixed_time"], 1, 60.0, Recorder(), None, QUEUE)
    assert all("entryQueue" not in c["traffic"] for c in recorder.configs)
    assert plain["suiteFingerprint"] == again["suiteFingerprint"]
    assert plain["suiteFingerprint"] == off["suiteFingerprint"]
    assert plain["suiteFingerprint"] != queued["suiteFingerprint"]
    assert plain["entryModel"] == {"model": "suspend", "capacity": None}


def test_stress_queue_keeps_the_generated_aggression() -> None:
    generated = [
        item for item in lab.generate(3, 8, 60.0) if item["scenario"].get("traffic")
    ]
    assert generated, "the generator draws an aggression for some scenarios"
    item = generated[0]
    queued = lab.with_entry_queue(item["scenario"], QUEUE)
    assert (
        queued["traffic"]["driverAggression"]
        == item["scenario"]["traffic"]["driverAggression"]
    )
    assert queued["traffic"]["entryQueue"]["enabled"] is True
    # The generator's own document is untouched.
    assert "entryQueue" not in item["scenario"]["traffic"]


def test_breakpoints_keep_the_queue_at_every_level() -> None:
    recorder = Recorder()
    scenario = lab.with_entry_queue(default_scenario(60.0), QUEUE)
    for factor, levels in (
        ("demand_scale", [0.5, 1.0]),
        ("aggression", ["standard", "high"]),
    ):
        out = lab.run_breakpoints(
            scenario, factor, levels, ["fixed_time", "roundabout"], 1, 1, recorder
        )
        assert out["entryModel"] == {"model": "queue", "capacity": 25}
    assert recorder.configs and all(
        c["traffic"]["entryQueue"]["enabled"] for c in recorder.configs
    )


def test_breakpoint_request_takes_the_queue_for_the_default_junction_only() -> None:
    assert BreakpointRequest(entryQueue={"enabled": True}).entryQueue is not None
    with pytest.raises(ValueError, match="entryQueue"):
        BreakpointRequest(scenario=default_scenario(), entryQueue={"enabled": True})
    with pytest.raises(ValueError):
        SuiteRequest(entryQueue={"enabled": True, "capcity": 3})


def test_entry_model_label_follows_an_advanced_override() -> None:
    doc = copy.deepcopy(default_scenario(60.0))
    doc["advanced"] = {"traffic": {"entryQueue": {"enabled": True, "capacity": 4}}}
    assert lab._entry_model(doc) == {"model": "queue", "capacity": 4}


# ---- experiment results and packages ------------------------------------------------------------


def test_experiment_result_and_package_report_the_entry_model(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.experiments.package import inspect_package
    from src.experiments.service import ExperimentService
    from src.experiments.store import ExperimentStore
    from tests.experiments.conftest import (
        SCENARIO,
        FakeExecutor,
        as_user,
        build_client,
        submit,
        wait_for,
    )

    monkeypatch.setattr("src.database.db.DB_PATH", str(tmp_path / "experiments.db"))
    client = build_client(
        ExperimentService(store=ExperimentStore(persist=False), executor=FakeExecutor())
    )
    for queue, expected in ((None, "suspend"), ({"enabled": True}, "queue")):
        scenario = copy.deepcopy(SCENARIO)
        if queue:
            scenario["traffic"] = {"entryQueue": queue}
        eid = submit(client, "alice", scenario=scenario)["id"]
        assert wait_for(client, eid)["status"] == "completed"
        result = client.get(
            f"/api/v3/experiments/{eid}/result", headers=as_user("alice")
        ).json()
        assert result["provenance"]["entryModel"]["model"] == expected
        package = client.get(
            f"/api/v3/experiments/{eid}/package", headers=as_user("alice")
        ).content
        summary = inspect_package(package).manifestSummary
        assert summary is not None
        assert summary["entryModel"]["model"] == expected
