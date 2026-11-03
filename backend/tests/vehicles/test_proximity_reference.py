"""find_leader with the proximity index against the exhaustive reference (checkpoint 12).

test_proximity_index.py checks that the index returns every vehicle within
Layer 4's reach on every query of live runs. This file checks the end result
and the index's own invariants:

- **Reference comparison.** At sampled ticks of runs across densities, lane
  counts and junction types (up to the maximum supported demand), every
  vehicle's ``find_leader`` result with the index equals the result of the
  full scan (``proximity=None``): the same leader object, or a virtual
  obstacle with the same fields, and the same gap to the bit. The conflict
  manager is left out of both calls (it reserves zones as a side effect, and
  the index only changes Layer 4).
- **No stale entries.** During real pool updates, every filed vehicle is in
  the cell of its current position, and no vehicle is filed twice.
- **Determinism.** Two seeded runs with the index give identical
  trajectories.
- **Unit cases.** Cell boundaries, negative coordinates, overlapping
  vehicles, empty and single-vehicle scenes, many-cell moves, non-finite
  positions.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, Iterator, List, Tuple

import pytest

from src.controllers.factory import create_controller
from src.core.clock import Clock
from src.engine.simulation_engine import SimulationEngine
from src.scenario.documents import compile_scenario, parse_scenario
from src.vehicles import proximity as prox
from src.vehicles.router import find_leader
from src.vehicles.virtual_obstacle import VirtualObstacle


@pytest.fixture(autouse=True)
def _quiet() -> Iterator[None]:
    logging.disable(logging.WARNING)
    yield
    logging.disable(logging.NOTSET)


def _config(
    junction: str,
    lanes: int,
    vph: int,
    strategy: str,
    mix: bool = True,
    ring_lanes: int | None = None,
    seed: int = 7,
) -> Dict[str, Any]:
    arm: Dict[str, Any] = {
        "lanes": lanes,
        "length": 120.0,
        "vehiclesPerHour": vph,
        "turning": {"left": 0.25, "straight": 0.5, "right": 0.25},
    }
    if mix:
        arm["vehicleMix"] = {"car": 0.6, "bus": 0.15, "truck": 0.15, "motorcycle": 0.1}
    doc: Dict[str, Any] = {
        "format": "urbanflow-scenario",
        "version": 1,
        "name": "reference",
        "junction": {"type": junction},
        "approaches": {d: dict(arm) for d in ("north", "south", "east", "west")},
        "simulation": {"duration": 150.0, "warmup": 10.0, "seed": seed},
    }
    if ring_lanes is not None:
        doc["roundabout"] = {"circulatingLanes": ring_lanes}
    parsed, errors = parse_scenario(doc)
    assert parsed is not None and not errors, errors
    return compile_scenario(parsed, strategy)


def _engine(config: Dict[str, Any]) -> SimulationEngine:
    engine = SimulationEngine(Clock(time_step=0.1), duration=150.0, config=config)
    engine.controller = create_controller(config, engine.network)
    return engine


def _signature(leader: Any, gap: float) -> Tuple[Any, ...]:
    """A comparable form of a find_leader result: real vehicles by identity,
    virtual obstacles (created per call) by their fields."""
    if leader is None:
        return (None, gap)
    # VirtualObstacle also has a vehicle_id slot, so test the type, not the
    # attribute: obstacles are built per call and compared field by field.
    if isinstance(leader, VirtualObstacle):
        return (
            "virtual",
            leader.position,
            leader.speed,
            leader.length,
            leader.vehicle_id,
            leader.is_yellow,
            leader.stop_line,
            gap,
        )
    return ("vehicle", leader.vehicle_id, id(leader), gap)


SCENARIOS = [
    ("light-1-lane", ("fixed_time_signal", 1, 150, "fixed_time"), {}),
    ("saturated-2-lane", ("fixed_time_signal", 2, 900, "fixed_time"), {}),
    ("adaptive-3-lane", ("fixed_time_signal", 3, 1000, "adaptive"), {}),
    ("cars-only-1-lane", ("fixed_time_signal", 1, 700, "fixed_time"), {"mix": False}),
    ("roundabout-1-ring", ("roundabout", 1, 600, "roundabout"), {}),
    ("roundabout-2-ring", ("roundabout", 2, 900, "roundabout"), {"ring_lanes": 2}),
    # The highest per-arm demand the scenario schema accepts on three lanes:
    # the entries saturate and the network holds as many vehicles as it can.
    ("maximum-3-lane", ("fixed_time_signal", 3, 7200, "fixed_time"), {}),
]


@pytest.mark.parametrize(
    "args, kwargs", [s[1:] for s in SCENARIOS], ids=[s[0] for s in SCENARIOS]
)
def test_indexed_find_leader_equals_the_full_scan(
    args: Tuple[Any, ...], kwargs: Dict[str, Any]
) -> None:
    engine = _engine(_config(*args, **kwargs))
    compared = 0
    peak = 0
    for tick in range(1, 1201):
        engine.step()
        if tick % 40:
            continue
        active = list(engine.pool.active_vehicles)
        peak = max(peak, len(active))
        grid = prox.ProximityGrid(active)
        now = engine.clock.get_elapsed_time()
        for v in active:
            reference = find_leader(v, engine.network, active, None, now)
            indexed = find_leader(v, engine.network, active, None, now, grid)
            assert _signature(*indexed) == _signature(*reference), (
                f"tick {tick}, vehicle {v.vehicle_id}"
            )
            compared += 1
    assert compared > 100
    if args[2] >= 900:
        assert peak > 40, "a busy scenario must actually be busy"


class _InvariantGrid(prox.ProximityGrid):
    """The real index, checking its own bookkeeping on every query."""

    checks = 0

    def near(self, v: Any) -> List[Any]:
        filed = [o for cell in self._cells.values() for o in cell]
        assert len(filed) == len({id(o) for o in filed}), "a vehicle is filed twice"
        for o in filed:
            assert self._where[id(o)] == self._cell(o), "stale cell"
            assert o.lane is not None
        _InvariantGrid.checks += 1
        return super().near(v)


@pytest.mark.parametrize(
    "args, kwargs",
    [SCENARIOS[1][1:], SCENARIOS[5][1:]],
    ids=["saturated-2-lane", "roundabout-2-ring"],
)
def test_no_stale_or_duplicate_entries_during_updates(
    monkeypatch: pytest.MonkeyPatch, args: Tuple[Any, ...], kwargs: Dict[str, Any]
) -> None:
    import src.engine.vehicle_pool as pool

    monkeypatch.setattr(pool, "ProximityGrid", _InvariantGrid)
    _InvariantGrid.checks = 0
    engine = _engine(_config(*args, **kwargs))
    for _ in range(600):
        engine.step()
    assert _InvariantGrid.checks > 5_000


def _trajectory(seed: int) -> List[Any]:
    engine = _engine(_config("fixed_time_signal", 2, 900, "fixed_time", seed=seed))
    out: List[Any] = []
    for _ in range(900):
        engine.step()
        out.append(
            [
                (v.vehicle_id, v.position.hex(), v.speed.hex())
                for v in engine.pool.active_vehicles
            ]
        )
    return out


def test_seeded_runs_reproduce_with_the_index() -> None:
    first = _trajectory(11)
    assert first == _trajectory(11)
    assert first != _trajectory(12)


class _Lane:
    lane_id = "n_in_0"


class _Car:
    def __init__(self, x: float, y: float, length: float = 4.5) -> None:
        self.lane: Any = _Lane()
        self.length = length
        self.width = 1.8
        self.coords = (x, y)


def test_empty_and_single_vehicle_scenes() -> None:
    assert prox.ProximityGrid([]).near(_Car(0.0, 0.0)) == []
    solo = _Car(10.0, -3.0)
    assert prox.ProximityGrid([solo]).near(solo) == [solo]


def test_cell_boundaries_and_negative_coordinates() -> None:
    a = _Car(0.0, 0.0)
    grid = prox.ProximityGrid([a])
    size = grid.cell_size
    # Within reach but on the other side of a boundary, in every direction
    # including negative coordinates (floor, not truncation).
    reach = 2.5 + 0.3 + (4.5 + 4.5 + 1.8 + 1.8) / 2.0
    for x, y in (
        (size - 1e-9, 0.0),
        (size, 0.0),
        (-1e-9, -1e-9),
        (-reach, 0.0),
        (0.0, -reach),
        (reach * math.cos(2.4), reach * math.sin(2.4)),
    ):
        b = _Car(x, y)
        grid = prox.ProximityGrid([a, b])
        if math.hypot(x, y) <= reach:
            assert b in grid.near(a), (x, y)
            assert a in grid.near(b), (x, y)


def test_overlapping_vehicles_are_all_returned_in_list_order() -> None:
    cars = [_Car(5.0, 5.0) for _ in range(6)]
    grid = prox.ProximityGrid(cars)
    assert grid.near(cars[3]) == cars


def test_a_vehicle_moving_across_many_cells_is_refiled_once() -> None:
    a, b = _Car(0.0, 0.0), _Car(1.0, 0.0)
    grid = prox.ProximityGrid([a, b])
    for x in range(0, 400, 7):
        b.coords = (float(x), 0.0)
        grid.move(b)
        filed = [o for cell in grid._cells.values() for o in cell]
        assert filed.count(b) == 1
    assert b not in grid.near(a)


def test_non_finite_positions_are_ignored_like_the_full_scan() -> None:
    a, b = _Car(0.0, 0.0), _Car(float("nan"), 0.0)
    grid = prox.ProximityGrid([a, b])
    assert grid.near(a) == [a]
    assert grid.near(b) == []
    b.coords = (1.0, 0.0)
    grid.move(b)
    assert grid.near(a) == [a, b]
