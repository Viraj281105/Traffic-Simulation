"""The Layer 4 proximity index returns every vehicle the full scan could act on.

find_leader's emergency check (Layer 4) acts on a vehicle only within
_EMERGENCY_DIST + _LATERAL_MARGIN + (L_a + L_b + W_a + W_b) / 2 of the one it
checks. These tests run busy scenarios with the index live, and at every
call compare it against a brute-force scan of the active list: every vehicle
within that distance must be returned, in active-list order, so the scan sees
exactly the vehicles (and the tie order) it saw before. The leader-trace pins
(test_leader_trace_pins.py) and the golden fingerprints check the end result.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, Iterator, List

import pytest

from src.controllers.factory import create_controller
from src.core.clock import Clock
from src.engine.simulation_engine import SimulationEngine
from src.scenario.documents import compile_scenario, parse_scenario
from src.vehicles import proximity as prox
from src.vehicles.router import _EMERGENCY_DIST, _LATERAL_MARGIN


@pytest.fixture(autouse=True)
def _quiet() -> Iterator[None]:
    logging.disable(logging.WARNING)
    yield
    logging.disable(logging.NOTSET)


def _config(junction: str, lanes: int, vph: int, strategy: str) -> Dict[str, Any]:
    doc = {
        "format": "urbanflow-scenario",
        "version": 1,
        "name": "proximity",
        "junction": {"type": junction},
        "approaches": {
            d: {
                "lanes": lanes,
                "length": 120.0,
                "vehiclesPerHour": vph,
                "turning": {"left": 0.25, "straight": 0.5, "right": 0.25},
                "vehicleMix": {
                    "car": 0.6,
                    "bus": 0.15,
                    "truck": 0.15,
                    "motorcycle": 0.1,
                },
            }
            for d in ("north", "south", "east", "west")
        },
        "simulation": {"duration": 120.0, "warmup": 10.0, "seed": 4},
    }
    parsed, errors = parse_scenario(doc)
    assert parsed is not None and not errors, errors
    return compile_scenario(parsed, strategy)


class Checking(prox.ProximityGrid):
    """The real index, checked against a brute-force scan on every query."""

    calls = 0

    def __init__(self, vehicles: List[Any]) -> None:
        super().__init__(vehicles)
        self._all = vehicles

    def near(self, v: Any) -> List[Any]:
        got = super().near(v)
        vx, vy = v.coords
        must = []
        for o in self._all:
            if o is v or o.lane is None:
                continue
            reach = (
                _EMERGENCY_DIST
                + _LATERAL_MARGIN
                + (v.length + o.length + v.width + o.width) / 2.0
            )
            ox, oy = o.coords
            if math.hypot(ox - vx, oy - vy) <= reach:
                must.append(o)
        ids = [id(o) for o in got]
        assert all(id(o) in ids for o in must), "a vehicle in reach was missed"
        positions = [ids.index(id(o)) for o in must]
        assert positions == sorted(positions), "order differs from the active list"
        order = [self._all.index(o) for o in got]
        assert order == sorted(order)
        Checking.calls += 1
        return got


@pytest.mark.parametrize(
    "junction, lanes, vph, strategy",
    [
        ("fixed_time_signal", 2, 900, "fixed_time"),
        ("fixed_time_signal", 3, 700, "adaptive"),
        ("roundabout", 2, 800, "roundabout"),
    ],
    ids=["signal-2-lane", "adaptive-3-lane", "roundabout-2-lane"],
)
def test_index_covers_every_vehicle_in_reach(
    monkeypatch: pytest.MonkeyPatch,
    junction: str,
    lanes: int,
    vph: int,
    strategy: str,
) -> None:
    import src.engine.vehicle_pool as pool

    monkeypatch.setattr(pool, "ProximityGrid", Checking)
    Checking.calls = 0
    config = _config(junction, lanes, vph, strategy)
    engine = SimulationEngine(Clock(time_step=0.1), duration=120.0, config=config)
    engine.controller = create_controller(config, engine.network)
    peak = 0
    for _ in range(900):
        engine.step()
        peak = max(peak, len(engine.pool.active_vehicles))
    assert Checking.calls > 10_000
    assert peak > 40, "the scenario must be busy enough to test the index"


def test_index_follows_a_vehicle_that_moves_and_drops_one_that_leaves() -> None:
    class Lane:
        lane_id = "n_in_0"

    class Car:
        def __init__(self, x: float, y: float) -> None:
            self.lane: Any = Lane()
            self.length = 4.5
            self.width = 1.8
            self.coords = (x, y)

    a, b, c = Car(0.0, 0.0), Car(3.0, 0.0), Car(500.0, 0.0)
    grid = prox.ProximityGrid([a, b, c])
    assert grid.near(a) == [a, b]
    c.coords = (2.0, 1.0)
    grid.move(c)
    assert grid.near(a) == [a, b, c]
    b.lane = None
    grid.move(b)
    assert grid.near(a) == [a, c]
