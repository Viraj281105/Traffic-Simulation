"""Real-world junctions run end to end (V1.5).

Every scenario here is one document compiled for each control strategy, so
the comparison stays "same junction, same traffic, different control". The
fast tier runs each real-world shape once under every strategy; the slow
tier is the safety matrix (seeds x shapes x strategies, longer runs).
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict

import jsonschema
import pytest

from src.controllers.factory import build_tick_callback, create_controller
from src.core.clock import Clock
from src.core.engine import SimulationEngine
from src.core.enums import TurnIntent
from src.core.scenario import compile_scenario, parse_scenario, validate_scenario
from src.metrics.collector import MetricCollector
from src.snapshot.builder import SnapshotBuilder

STRATEGIES = ["fixed_time", "adaptive", "roundabout"]

SNAPSHOT_SCHEMA = json.loads(
    (
        Path(__file__).resolve().parents[3]
        / "shared"
        / "schemas"
        / "snapshot.schema.json"
    ).read_text(encoding="utf-8")
)


def _arm(
    lanes: int, vph: float, turning: Dict[str, float], **extra: Any
) -> Dict[str, Any]:
    return {"lanes": lanes, "vehiclesPerHour": vph, "turning": turning, **extra}


EVEN = {"left": 0.25, "straight": 0.5, "right": 0.25}

SHAPES: Dict[str, Dict[str, Any]] = {
    # T-junction: east-west main road, south stem, no north arm.
    "t-junction": {
        "approaches": {
            "north": None,
            "south": _arm(1, 350, {"left": 0.5, "straight": 0, "right": 0.5}),
            "east": _arm(1, 450, {"left": 0.3, "straight": 0.7, "right": 0}),
            "west": _arm(1, 450, {"left": 0, "straight": 0.7, "right": 0.3}),
        }
    },
    # Y-junction: three skewed arms.
    "y-junction": {
        "approaches": {
            "north": _arm(
                1, 400, {"left": 0.4, "straight": 0, "right": 0.6}, bearing=20.0
            ),
            "south": None,
            "east": _arm(
                1, 350, {"left": 0, "straight": 0.5, "right": 0.5}, bearing=115.0
            ),
            "west": _arm(
                1, 350, {"left": 0.5, "straight": 0.5, "right": 0}, bearing=250.0
            ),
        }
    },
    # Asymmetric four-arm: a two-lane skewed main road, a narrow side road,
    # unequal lengths, mixed vehicles and mixed turning.
    "skewed-asymmetric": {
        "approaches": {
            "north": _arm(
                2,
                600,
                {"left": 0.15, "straight": 0.7, "right": 0.15},
                bearing=15.0,
                length=300,
            ),
            "south": _arm(
                2,
                550,
                {"left": 0.2, "straight": 0.6, "right": 0.2},
                bearing=195.0,
                length=250,
            ),
            "east": _arm(
                1,
                250,
                {"left": 0.4, "straight": 0.3, "right": 0.3},
                bearing=80.0,
                laneWidth=3.0,
                length=120,
            ),
            "west": _arm(1, 200, EVEN, bearing=265.0, laneWidth=3.2),
        },
        "vehicles": {
            "mix": {
                "car": 0.75,
                "suv": 0.1,
                "bus": 0.05,
                "truck": 0.05,
                "motorcycle": 0.05,
            }
        },
    },
    # U-turns: three wide lanes at a signal (radius 6.75 m), the ring at a
    # roundabout.
    "uturn": {
        "approaches": {
            "north": _arm(
                3,
                500,
                {"left": 0.15, "straight": 0.6, "right": 0.15, "uturn": 0.1},
                laneWidth=4.5,
                laneUse=[["uturn", "left"], ["straight"], ["straight", "right"]],
                roundaboutLaneUse=[
                    ["uturn", "left"],
                    ["left", "straight"],
                    ["straight", "right"],
                ],
            ),
            "south": _arm(3, 450, EVEN),
            "east": _arm(1, 250, EVEN),
            "west": _arm(1, 250, EVEN),
        },
        "roundabout": {"circulatingLanes": 2, "innerRadius": 12, "outerRadius": 22},
    },
}


def _document(shape: str, seed: int = 3, duration: float = 120) -> Dict[str, Any]:
    doc = copy.deepcopy(SHAPES[shape])
    doc["junction"] = {"type": "fixed_time_signal"}
    doc["simulation"] = {"duration": duration, "warmup": 20, "seed": seed}
    return doc


class _Run:
    def __init__(self, doc: Dict[str, Any], strategy: str) -> None:
        document, errors = parse_scenario(doc)
        assert document is not None, errors
        self.config = compile_scenario(document, strategy)
        self.clock = Clock(time_step=0.1)
        self.engine = SimulationEngine(
            self.clock, self.config["simulation"]["duration"], self.config
        )
        self.controller = create_controller(self.config, self.engine.network)
        self.engine.controller = self.controller
        self.collector = MetricCollector(self.config)
        self.engine.register_tick_callback(
            build_tick_callback(
                self.controller, self.clock, self.engine, self.collector
            )
        )
        logging.getLogger("src.vehicles.pool").setLevel(logging.ERROR)

    def run(self) -> "_Run":
        while self.engine.status.value.lower() != "completed":
            self.engine.step()
        return self

    def metrics(self) -> Dict[str, Any]:
        pool = self.engine.pool
        return self.collector.get_metrics(
            self.clock.get_elapsed_time(),
            pool.active_vehicles,
            pool.exited_vehicles,
            self.engine.spawner.spawned_count if self.engine.spawner else 0,
            pool.collision_count,
        )

    def trace(self) -> str:
        digest = hashlib.sha256()
        for v in sorted(self.engine.pool.exited_vehicles, key=lambda v: v.vehicle_id):
            digest.update(
                repr((v.vehicle_id, v.turn_intent, round(v.exit_time or 0, 6))).encode()
            )
        return digest.hexdigest()


def _present(doc: Dict[str, Any]) -> set:
    return {d for d, arm in doc["approaches"].items() if arm is not None}


@pytest.mark.parametrize("shape", sorted(SHAPES))
def test_every_shape_is_valid_for_every_strategy(shape: str) -> None:
    result = validate_scenario(_document(shape), STRATEGIES)
    assert result["valid"], result["errors"]


@pytest.mark.parametrize("strategy", STRATEGIES)
@pytest.mark.parametrize("shape", sorted(SHAPES))
def test_real_world_junction_runs_safely(shape: str, strategy: str) -> None:
    doc = _document(shape)
    run = _Run(doc, strategy).run()
    pool = run.engine.pool
    present = _present(doc)
    assert pool.collision_count == 0
    assert len(pool.exited_vehicles) >= 10
    for vehicle in pool.exited_vehicles:
        origin = vehicle.route[0].approach.value
        exit_arm = vehicle.route[-1].approach.value
        assert origin in present and exit_arm in present
        if vehicle.turn_intent == TurnIntent.UTURN:
            assert exit_arm == origin
    metrics = run.metrics()
    assert metrics["collisionCount"] == 0
    assert set(metrics["approachBreakdown"]) == present


def test_uturns_are_made_under_every_strategy() -> None:
    for strategy in STRATEGIES:
        # Seed 4 draws six U-turners from the north in the first 400 s (seed
        # 3 happens to draw one); every strategy gets the same arrivals.
        run = _Run(_document("uturn", seed=4, duration=300), strategy).run()
        made = [
            v
            for v in run.engine.pool.exited_vehicles
            if v.turn_intent == TurnIntent.UTURN
        ]
        assert made, f"no U-turn completed under {strategy}"


def test_same_seed_reproduces_a_real_world_run() -> None:
    a = _Run(_document("skewed-asymmetric"), "fixed_time").run()
    b = _Run(_document("skewed-asymmetric"), "fixed_time").run()
    assert a.trace() == b.trace()
    c = _Run(_document("skewed-asymmetric", seed=4), "fixed_time").run()
    assert c.trace() != a.trace()


def test_all_strategies_receive_the_same_arrivals() -> None:
    spawned = {
        s: _Run(_document("t-junction"), s).run().engine.spawner.spawned_count
        for s in STRATEGIES
    }
    # The same document and seed: the same demand, whatever the control
    # (arrivals blocked at a full entry can make a few differ).
    assert max(spawned.values()) - min(spawned.values()) <= 3


@pytest.mark.parametrize("strategy", ["fixed_time", "roundabout"])
def test_real_world_snapshot_carries_arm_geometry(strategy: str) -> None:
    run = _Run(_document("y-junction", duration=30), strategy).run()
    snap = SnapshotBuilder(
        "sim", "cfg", run.engine, run.collector, run.controller
    ).build()
    jsonschema.validate(snap, SNAPSHOT_SCHEMA)
    approaches = {a["direction"]: a for a in snap["intersection"]["approaches"]}
    assert set(approaches) == {"north", "east", "west"}
    assert approaches["north"]["bearing"] == pytest.approx(20.0)
    assert approaches["east"]["stopLineDistance"] > 0
    if strategy == "fixed_time":
        signals = {s["direction"] for s in snap["controller"]["signals"]}
        assert signals == {"north", "east", "west"}


def test_standard_snapshot_is_unchanged_by_v15() -> None:
    doc = _document("t-junction", duration=10)
    doc["approaches"]["north"] = _arm(1, 300, EVEN)
    doc["approaches"]["south"]["turning"] = EVEN
    doc["approaches"]["east"]["turning"] = EVEN
    doc["approaches"]["west"]["turning"] = EVEN
    run = _Run(doc, "fixed_time").run()
    snap = SnapshotBuilder(
        "sim", "cfg", run.engine, run.collector, run.controller
    ).build()
    for approach in snap["intersection"]["approaches"]:
        assert set(approach) == {
            "direction",
            "queueLength",
            "laneCount",
            "lanePermittedTurns",
        }
    assert len(snap["controller"]["signals"]) == 4


@pytest.mark.slow
@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
@pytest.mark.parametrize("strategy", STRATEGIES)
@pytest.mark.parametrize("shape", sorted(SHAPES))
def test_real_world_safety_matrix(shape: str, strategy: str, seed: int) -> None:
    doc = _document(shape, seed=seed, duration=300)
    run = _Run(doc, strategy).run()
    assert run.engine.pool.collision_count == 0
    assert len(run.engine.pool.exited_vehicles) >= 60
