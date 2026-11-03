"""The entry queue and demand accounting, end to end.

Unit tests pin the spawner; these follow the option and the new fields
through every layer a user reaches: scenario validation and compilation over
HTTP, engine-config validation on the versioned simulations endpoint, the
snapshot (validated against shared/schemas/snapshot.schema.json), persistence
of the engine configuration for reproduction, and the study results.
"""

from __future__ import annotations

import copy
import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterator

import jsonschema
import pytest
from fastapi.testclient import TestClient

from src.controllers.factory import create_controller
from src.core.clock import Clock
from src.core.schema import CONFIG_SCHEMA
from src.engine.simulation_engine import SimulationEngine
from src.engine.tick_callback import build_tick_callback
from src.main import app
from src.metrics.collector import MetricCollector
from src.scenario.documents import compile_scenario, parse_scenario
from src.snapshot.builder import SnapshotBuilder
from src.study.control_comparison import run_scenario_comparison

ROOT = Path(__file__).resolve().parents[3]
SNAPSHOT_SCHEMA = json.loads(
    (ROOT / "shared" / "schemas" / "snapshot.schema.json").read_text("utf-8")
)

SCENARIO: Dict[str, Any] = {
    "format": "urbanflow-scenario",
    "version": 1,
    "name": "Entry queue",
    "junction": {"type": "fixed_time_signal"},
    "approaches": {
        d: {"lanes": 1, "length": 80.0, "vehiclesPerHour": 1400}
        for d in ("north", "south", "east", "west")
    },
    "traffic": {"entryQueue": {"enabled": True, "capacity": 25}},
    "simulation": {"duration": 60, "warmup": 10, "seed": 5},
}

client = TestClient(app)


@pytest.fixture(autouse=True)
def _quiet() -> Iterator[None]:
    logging.disable(logging.WARNING)
    yield
    logging.disable(logging.NOTSET)


def test_the_api_validates_and_compiles_the_option() -> None:
    body = client.post(
        "/api/v1/scenarios/compile",
        json={"scenario": SCENARIO, "strategy": "fixed_time"},
    ).json()
    assert body["config"]["traffic"]["entryQueue"] == {"enabled": True, "capacity": 25}
    # The compiled engine configuration is valid against the shared schema.
    jsonschema.validate(body["config"], CONFIG_SCHEMA)

    bad = copy.deepcopy(SCENARIO)
    bad["traffic"]["entryQueue"]["capacity"] = 0
    response = client.post(
        "/api/v1/scenarios/compile", json={"scenario": bad, "strategy": "fixed_time"}
    )
    assert response.status_code == 400


def test_a_queued_scenario_runs_through_the_simulations_endpoint() -> None:
    response = client.post(
        "/api/v1/simulations", json={"scenario": SCENARIO, "strategy": "fixed_time"}
    )
    assert response.status_code == 201, response.text
    # The stored configuration (what a reproduction replays) keeps the option.
    assert response.json()["config"]["traffic"]["entryQueue"]["enabled"] is True
    client.delete(f"/api/v1/simulations/{response.json()['simulationId']}")


def test_snapshots_of_a_queued_run_match_the_snapshot_schema() -> None:
    parsed, errors = parse_scenario(SCENARIO)
    assert parsed is not None and not errors
    config = compile_scenario(parsed, "fixed_time")
    clock = Clock(time_step=0.1)
    engine = SimulationEngine(clock, duration=60.0, config=config)
    controller = create_controller(config, engine.network)
    engine.controller = controller
    collector = MetricCollector(config)
    engine.register_tick_callback(
        build_tick_callback(controller, clock, engine, collector)
    )
    builder = SnapshotBuilder("queue", "queue", engine, collector, controller)
    for tick in range(1, 601):
        engine.step()
        if tick % 100 == 0:
            snapshot = builder.build()
            jsonschema.validate(snapshot, SNAPSHOT_SCHEMA)
    acc = snapshot["metrics"]["demandAccounting"]
    assert acc["entryModel"] == "queue"
    assert acc["waitingAtEntry"] > 0
    assert acc["arrivals"] == acc["admitted"] + acc["waitingAtEntry"] + acc["rejected"]
    # Waiting demand is not in the network: every vehicle the snapshot lists
    # is an admitted one (active, or one of the recent exits it also
    # carries), and the in-network ones are exactly the active pool.
    pool_ids = {
        v.vehicle_id for v in engine.pool.active_vehicles + engine.pool.exited_vehicles
    }
    assert {v["id"] for v in snapshot["vehicles"]} <= pool_ids
    in_network = [v for v in snapshot["vehicles"] if v["state"] != "exited"]
    assert len(in_network) == len(engine.pool.active_vehicles)
    assert acc["admitted"] == len(pool_ids)


def test_a_study_of_a_queued_scenario_reports_the_queue_per_seed() -> None:
    parsed, errors = parse_scenario(SCENARIO)
    assert parsed is not None and not errors
    out = run_scenario_comparison(parsed, ["fixed_time", "roundabout"], num_seeds=2)
    for row in out["perSeed"]:
        for strategy in ("fixed_time", "roundabout"):
            acc = row[strategy]["demandAccounting"]
            assert acc["entryModel"] == "queue"
            assert (
                acc["arrivals"]
                == acc["admitted"] + acc["waitingAtEntry"] + acc["rejected"]
            )
    # Both strategies ran the same entry model (it comes from the document).
    assert (
        out["compiledConfigs"]["fixed_time"]["traffic"]["entryQueue"]
        == (out["compiledConfigs"]["roundabout"]["traffic"]["entryQueue"])
    )
