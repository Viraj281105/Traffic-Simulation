"""The roundabout skips a missing arm, and nothing else, silently (F-45).

``RoundaboutController.update`` used to wrap each approach's whole entry
evaluation in ``except KeyError: pass``, meant for a slot with no arm. Any
other ``KeyError`` raised while judging an entry was swallowed too, and that
approach kept last tick's give-way decisions without a trace (the file records
one real bug hidden that way). Only the approach lookup is guarded now.
"""

from __future__ import annotations

from typing import Any, Dict

import pytest

from src.controllers.entry_gate import GateDecision
from src.controllers.roundabout import RoundaboutController
from src.core.clock import Clock
from src.core.enums import Direction
from src.engine.simulation_engine import SimulationEngine
from src.roads.lane import Lane
from src.scenario.documents import compile_scenario, parse_scenario


def _config(missing: str | None = None) -> Dict[str, Any]:
    approach = {
        "lanes": 1,
        "length": 150.0,
        "vehiclesPerHour": 400,
        "turning": {"left": 0.25, "straight": 0.5, "right": 0.25},
    }
    approaches: Dict[str, Any] = {
        d: dict(approach) for d in ("north", "south", "east", "west")
    }
    if missing is not None:
        approaches[missing] = None
        # No traffic may be sent into the missing slot.
        approaches["north"]["turning"] = {"left": 0.5, "straight": 0.5, "right": 0.0}
        approaches["south"]["turning"] = {"left": 0.0, "straight": 0.5, "right": 0.5}
        approaches["east"]["turning"] = {"left": 0.5, "straight": 0.0, "right": 0.5}
    document = {
        "format": "urbanflow-scenario",
        "version": 1,
        "name": "entry errors",
        "junction": {"type": "roundabout"},
        "approaches": approaches,
        "simulation": {"duration": 60.0, "warmup": 5.0, "seed": 4},
    }
    parsed, errors = parse_scenario(document)
    assert not errors, errors
    return compile_scenario(parsed, "roundabout")


class _BrokenGate:
    """An entry gate with a bug: it raises KeyError on every call."""

    def allows(self, approach: Direction, lane: Lane, now: float) -> GateDecision:
        raise KeyError("lookup inside the gate")


def test_an_error_while_judging_an_entry_is_not_swallowed() -> None:
    config = _config()
    engine = SimulationEngine(Clock(time_step=0.1), duration=60.0, config=config)
    controller = RoundaboutController(config, engine.network, entry_gate=_BrokenGate())

    with pytest.raises(KeyError, match="lookup inside the gate"):
        controller.update(0.1, [])


def test_a_missing_arm_is_still_skipped() -> None:
    config = _config(missing="west")
    clock = Clock(time_step=0.1)
    engine = SimulationEngine(clock, duration=60.0, config=config)
    controller = RoundaboutController(config, engine.network)
    engine.controller = controller

    for _ in range(300):
        engine.step()

    assert engine.spawner is not None and engine.spawner.spawned_count > 10
    for d in (Direction.NORTH, Direction.SOUTH, Direction.EAST):
        assert controller._prev_zone_occupants is not None
        lane_ids = [
            lane.lane_id for lane in engine.network.get_incoming_approach(d).get_lanes()
        ]
        assert all(lane_id in controller._prev_zone_occupants for lane_id in lane_ids)
