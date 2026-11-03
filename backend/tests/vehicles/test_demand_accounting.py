"""Demand accounting: offered, admitted and held arrivals (F-50, F-41).

When every permitted entry lane is full the spawner holds the due arrival and
suspends that approach's arrival process until it is placed; there is no
queue outside the network. These tests pin the accounting that makes that
visible (``VehicleSpawner.demand_accounting``, reported as the
``demandAccounting`` metric) and ``unfinishedShare``:

- the exact identities hold at every tick, light or saturated;
- the counters draw nothing from the random stream (runs are unchanged);
- blocked time and the suppressed-demand estimate appear only when entries
  are actually blocked;
- reset clears them.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

import pytest

from src.controllers.factory import create_controller
from src.core.clock import Clock
from src.core.enums import Direction
from src.engine.simulation_engine import SimulationEngine
from src.engine.tick_callback import build_tick_callback
from src.metrics.collector import MetricCollector
from src.roads.lane import Lane
from src.scenario.documents import compile_scenario, parse_scenario
from src.vehicles.vehicle import Vehicle


def _document(
    junction: str, vph: int, lanes: int, length: float, seed: int = 7
) -> Dict[str, Any]:
    return {
        "format": "urbanflow-scenario",
        "version": 1,
        "name": "demand",
        "junction": {"type": junction},
        "approaches": {
            d: {
                "lanes": lanes,
                "length": length,
                "vehiclesPerHour": vph,
                "turning": {"left": 0.25, "straight": 0.5, "right": 0.25},
                "vehicleMix": {"car": 0.7, "bus": 0.1, "truck": 0.1, "motorcycle": 0.1},
            }
            for d in ("north", "south", "east", "west")
        },
        "simulation": {"duration": 300.0, "warmup": 10.0, "seed": seed},
    }


def _build(
    document: Dict[str, Any], strategy: str
) -> Tuple[SimulationEngine, MetricCollector]:
    parsed, errors = parse_scenario(document)
    assert not errors, errors
    config = compile_scenario(parsed, strategy)
    clock = Clock(time_step=0.1)
    engine = SimulationEngine(clock, duration=300.0, config=config)
    controller = create_controller(config, engine.network)
    engine.controller = controller
    collector = MetricCollector(config)
    engine.register_tick_callback(
        build_tick_callback(controller, clock, engine, collector)
    )
    return engine, collector


def _metrics(engine: SimulationEngine, collector: MetricCollector) -> Dict[str, Any]:
    assert engine.spawner is not None
    return collector.get_metrics(
        engine.clock.get_elapsed_time(),
        engine.pool.active_vehicles,
        engine.pool.exited_vehicles,
        engine.spawner.spawned_count,
        engine.pool.collision_count,
        engine.spawner.demand_accounting(),
    )


def _check_identities(engine: SimulationEngine) -> Dict[str, Any]:
    assert engine.spawner is not None
    acc = engine.spawner.demand_accounting()
    assert acc["arrivals"] == acc["admitted"] + acc["waitingAtEntry"]
    assert acc["admitted"] == engine.spawner.spawned_count
    assert acc["admitted"] == len(engine.pool.active_vehicles) + len(
        engine.pool.exited_vehicles
    )
    assert 0 <= acc["waitingAtEntry"] <= len(acc["byApproach"])
    for row in acc["byApproach"].values():
        assert row["arrivals"] == row["admitted"] + row["waitingAtEntry"]
        assert row["entryBlockedSeconds"] >= 0.0
    assert sum(r["arrivals"] for r in acc["byApproach"].values()) == acc["arrivals"]
    return acc


SATURATED = _document("fixed_time_signal", vph=1400, lanes=1, length=80.0)
LIGHT = _document("fixed_time_signal", vph=150, lanes=2, length=150.0)


@pytest.fixture(autouse=True)
def _quiet() -> Any:
    logging.disable(logging.WARNING)  # deadlock and collision log lines
    yield
    logging.disable(logging.NOTSET)


@pytest.mark.parametrize(
    "document, strategy",
    [
        (SATURATED, "fixed_time"),
        (LIGHT, "fixed_time"),
        (_document("roundabout", vph=1000, lanes=1, length=80.0), "roundabout"),
    ],
    ids=["saturated-signal", "light-signal", "saturated-roundabout"],
)
def test_identities_hold_at_every_tick(document: Dict[str, Any], strategy: str) -> None:
    engine, _ = _build(document, strategy)
    for _ in range(1500):
        engine.step()
        _check_identities(engine)


def test_saturated_entry_reports_blocked_time_and_suppressed_demand() -> None:
    engine, collector = _build(SATURATED, "fixed_time")
    for _ in range(3000):
        engine.step()
    metrics = _metrics(engine, collector)
    acc = metrics["demandAccounting"]
    assert acc["entryBlockedSeconds"] > 60.0
    assert acc["estimatedSuppressedArrivals"] > 10.0
    # The configured demand is far beyond what one lane per arm admits.
    assert acc["admittedShareOfNominal"] < 0.8
    assert acc["demandFiguresAreEstimates"] is True
    assert metrics["totalVehiclesSpawned"] == acc["admitted"]
    # Expected value: generated + suppressed track the nominal demand. The
    # Poisson noise of a few hundred arrivals is well inside 25 %.
    expected = acc["arrivals"] + acc["estimatedSuppressedArrivals"]
    assert expected == pytest.approx(acc["nominalDemand"], rel=0.25)
    assert metrics["unfinishedShare"] is not None
    assert 0.0 < metrics["unfinishedShare"] < 1.0


def test_light_demand_is_barely_blocked() -> None:
    engine, collector = _build(LIGHT, "fixed_time")
    for _ in range(3000):
        engine.step()
    acc = _metrics(engine, collector)["demandAccounting"]
    # Not zero: two Poisson arrivals can come closer together than the entry
    # clearance (here once, for 1 s), but negligible against the run.
    assert acc["entryBlockedSeconds"] < 5.0
    assert acc["estimatedSuppressedArrivals"] < 1.0
    # 150 veh/h x 4 arms x 300 s = 50 expected arrivals; Poisson noise only.
    assert acc["nominalDemand"] == pytest.approx(50.0)
    assert 0.5 < acc["admittedShareOfNominal"] < 1.5


def _trace(document: Dict[str, Any], with_accounting: bool) -> List[Any]:
    engine, _ = _build(document, "fixed_time")
    trace: List[Any] = []
    for _ in range(1200):
        engine.step()
        if with_accounting:
            assert engine.spawner is not None
            engine.spawner.demand_accounting()
        trace.append(
            [(v.vehicle_id, v.position, v.speed) for v in engine.pool.active_vehicles]
        )
    assert engine.spawner is not None
    trace.append(engine.spawner.rng.getstate())
    return trace


def test_reading_the_accounting_does_not_change_the_run() -> None:
    assert _trace(SATURATED, True) == _trace(SATURATED, False)


def test_reset_clears_the_accounting() -> None:
    engine, _ = _build(SATURATED, "fixed_time")
    for _ in range(1500):
        engine.step()
    first = _check_identities(engine)
    assert first["entryBlockedSeconds"] > 0.0
    engine.reset()
    assert engine.spawner is not None
    cleared = engine.spawner.demand_accounting()
    assert cleared["arrivals"] == cleared["admitted"] == 0
    assert cleared["entryBlockedSeconds"] == 0.0
    assert cleared["nominalDemand"] == 0.0
    for _ in range(1500):
        engine.step()
    assert _check_identities(engine) == first


def test_generation_stops_at_the_vehicle_limit() -> None:
    document = _document("fixed_time_signal", vph=900, lanes=2, length=150.0)
    parsed, errors = parse_scenario(document)
    assert not errors, errors
    config = compile_scenario(parsed, "fixed_time")
    config["traffic"]["totalVehicles"] = 20
    engine = SimulationEngine(Clock(time_step=0.1), duration=300.0, config=config)
    engine.controller = create_controller(config, engine.network)
    for _ in range(1200):
        engine.step()
    assert engine.spawner is not None
    acc = engine.spawner.demand_accounting()
    assert acc["admitted"] == 20
    # The nominal demand covers only the time the source ran, so it stays
    # near the 20 generated, not 900 x 4 x 120 s / 3600 = 120.
    assert acc["nominalDemand"] < 60.0


def _vehicle(vid: str, spawn: float, exit_t: float | None) -> Vehicle:
    v = Vehicle(
        vehicle_id=vid,
        length=4.5,
        width=1.8,
        desired_speed=10.0,
        route=[Lane("in", 0.0, 0.0, 100.0, 0.0)],
        spawn_time=spawn,
    )
    v.exit_time = exit_t
    return v


def test_unfinished_share_counts_post_warmup_admissions_only() -> None:
    collector = MetricCollector({"simulation": {"warmupTime": 30.0}})
    # Admitted during warm-up (ignored either way), after warm-up and
    # exited, after warm-up and still inside.
    pre = _vehicle("veh_0", 5.0, None)
    done = [_vehicle(f"veh_{i}", 40.0 + i, 90.0 + i) for i in range(1, 4)]
    inside = _vehicle("veh_9", 80.0, None)
    metrics = collector.get_metrics(100.0, [pre, inside], done, 5)
    assert metrics["unfinishedShare"] == 0.25
    assert metrics["demandAccounting"] is None
    empty = collector.get_metrics(10.0, [pre], [], 1)
    assert empty["unfinishedShare"] is None


def test_suspended_approach_counts_one_arrival_until_placed() -> None:
    """Hand-checked: a blocked arrival is one arrival, however long it waits."""
    engine, _ = _build(SATURATED, "fixed_time")
    spawner = engine.spawner
    assert spawner is not None
    for _ in range(3000):
        engine.step()
        held = [d for d in Direction if d in spawner._held]
        for d in held:
            assert spawner.timers[d] == 0.0
            assert d in spawner._pending_turn
