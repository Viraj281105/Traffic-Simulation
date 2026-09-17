"""The emitted snapshot must satisfy the published snapshot schema.

`shared/schemas/snapshot.schema.json` is a cross-team contract: the frontend
types are written against it. Nothing previously checked a real snapshot
against it, and the two had drifted — the schema listed only the paired-green
phase names (`ns_green` etc.), so every snapshot produced by the controller's
default one-direction-at-a-time cycle (`north_straight_right`, `north_left`,
...) violated the contract the frontend was typed from.

These tests validate genuinely produced snapshots, and enumerate every phase
name the controller can emit, so that vocabulary and schema cannot drift apart
again.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List

import jsonschema
import pytest

from src.controllers.fixed_time_signal import FixedTimeSignalController
from src.controllers.roundabout import RoundaboutController
from src.core.clock import Clock
from src.core.engine import SimulationEngine
from src.metrics.collector import MetricCollector
from src.roads.network import RoadNetwork
from src.snapshot.builder import SnapshotBuilder

SNAPSHOT_SCHEMA_PATH = (
    Path(__file__).resolve().parents[3] / "shared" / "schemas" / "snapshot.schema.json"
)

with open(SNAPSHOT_SCHEMA_PATH, "r", encoding="utf-8") as _f:
    SNAPSHOT_SCHEMA: Dict[str, Any] = json.load(_f)

_CURRENT_PHASE_PATTERN: str = SNAPSHOT_SCHEMA["properties"]["controller"]["properties"][
    "currentPhase"
]["pattern"]


def _base_config(**overrides: Any) -> Dict[str, Any]:
    config: Dict[str, Any] = {
        "simulation": {
            "duration": 60,
            "timeStep": 0.1,
            "warmupTime": 0.0,
            "randomSeed": 11,
        },
        "geometry": {"intersectionType": "fixed_time_signal"},
        "roads": {"approachLength": 200.0, "laneWidth": 3.5, "lanesPerApproach": 2},
        "traffic": {"arrivalRate": 0.5, "arrivalDistribution": "poisson"},
    }
    config.update(overrides)
    return config


def _build_snapshot(config: Dict[str, Any], steps: int = 40) -> Dict[str, Any]:
    clock = Clock(time_step=config["simulation"]["timeStep"])
    engine = SimulationEngine(
        clock, duration=config["simulation"]["duration"], config=config
    )
    if config["geometry"]["intersectionType"] == "roundabout":
        controller: Any = RoundaboutController(config, engine.network)
    else:
        controller = FixedTimeSignalController(config, engine.network)
    engine.controller = controller
    collector = MetricCollector(config)
    builder = SnapshotBuilder("sim", "cfg", engine, collector, controller)

    for _ in range(steps):
        engine.step()
    return builder.build()


def test_default_cycle_snapshot_matches_schema() -> None:
    """The no-phaseSequence cycle is what previously violated the contract."""
    config = _base_config()
    config["controller"] = {"greenTime": 30.0, "yellowTime": 4.0, "allRedTime": 2.0}
    snapshot = _build_snapshot(config)

    jsonschema.validate(snapshot, SNAPSHOT_SCHEMA)
    assert snapshot["controller"]["currentPhase"].startswith("north")


def test_configured_phase_sequence_snapshot_matches_schema() -> None:
    config = _base_config()
    config["controller"] = {
        "greenTime": 30.0,
        "yellowTime": 4.0,
        "allRedTime": 2.0,
        "phaseSequence": [
            "ns_green",
            "ns_yellow",
            "all_red",
            "ew_green",
            "ew_yellow",
            "all_red",
        ],
    }
    snapshot = _build_snapshot(config)

    jsonschema.validate(snapshot, SNAPSHOT_SCHEMA)
    assert snapshot["controller"]["currentPhase"] == "ns_green"


def test_roundabout_snapshot_matches_schema() -> None:
    config = _base_config()
    config["geometry"] = {"intersectionType": "roundabout"}
    config["controller"] = {"innerRadius": 10.0, "outerRadius": 20.0}
    snapshot = _build_snapshot(config)

    jsonschema.validate(snapshot, SNAPSHOT_SCHEMA)
    assert snapshot["controller"]["type"] == "roundabout"


def _all_default_cycle_phase_names() -> List[str]:
    network = RoadNetwork()
    network.setup_default_intersection()
    controller = FixedTimeSignalController(
        {"controller": {"greenTime": 30.0, "yellowTime": 4.0, "allRedTime": 2.0}},
        network,
    )
    return [phase.name for phase in controller.phases]


def _all_configured_phase_names() -> List[str]:
    """Every token the phaseSequence vocabulary admits."""
    groups = ["n", "s", "e", "w", "ns", "sn", "ew", "we"]
    return ["all_red"] + [
        f"{group}_{color}" for group in groups for color in ("green", "yellow")
    ]


@pytest.mark.parametrize(
    "phase_name", _all_default_cycle_phase_names() + _all_configured_phase_names()
)
def test_every_emittable_phase_name_matches_schema_pattern(phase_name: str) -> None:
    """Pin the full vocabulary, not just the phases a sample run happened to hit."""
    assert re.match(_CURRENT_PHASE_PATTERN, phase_name), (
        f"{phase_name!r} is emitted by the controller but rejected by the "
        "snapshot schema's currentPhase pattern"
    )


@pytest.mark.parametrize(
    "bogus", ["", "ns_blue", "north_green", "all_green", "xy_green", "ns_green_extra"]
)
def test_schema_pattern_rejects_names_outside_the_vocabulary(bogus: str) -> None:
    """The pattern must still be a real constraint, not a rubber stamp."""
    assert not re.match(_CURRENT_PHASE_PATTERN, bogus)


def test_configured_phase_sequence_names_round_trip_into_the_snapshot() -> None:
    """Single-approach groups are emitted verbatim and stay schema-valid."""
    config = _base_config()
    config["controller"] = {
        "greenTime": 30.0,
        "yellowTime": 4.0,
        "allRedTime": 2.0,
        "phaseSequence": ["w_green", "w_yellow", "all_red"],
    }
    snapshot = _build_snapshot(config)

    assert snapshot["controller"]["currentPhase"] == "w_green"
    jsonschema.validate(snapshot, SNAPSHOT_SCHEMA)
