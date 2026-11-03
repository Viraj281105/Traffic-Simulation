"""Demand-accounting invariants under both entry models (checkpoint 10).

test_entry_queue.py and test_demand_accounting.py pin conservation per tick,
capacity, FIFO, reset and determinism. These add the cases the stabilization
brief names that were not yet pinned:

- the point queue's arrival clock is exact (F-57): it generates the
  configured demand even at the highest supported rate, where restarting the
  clock at each tick boundary lost about 11 % of arrivals;
- zero-length steps generate nothing and keep every identity;
- the queue never exceeds the run's vehicle limit at the maximum supported
  rate, so its memory is bounded by ``totalVehicles`` (at most 5,000);
- vehicles waiting outside are never counted as vehicles in the network;
- a run to completion leaves every arrival accounted for.
"""

from __future__ import annotations

import logging
import sys
from typing import Any, Dict, Iterator, Optional

import pytest

from src.controllers.factory import create_controller
from src.core.clock import Clock
from src.engine.simulation_engine import SimulationEngine
from src.scenario.documents import compile_scenario, parse_scenario


@pytest.fixture(autouse=True)
def _quiet() -> Iterator[None]:
    logging.disable(logging.WARNING)
    yield
    logging.disable(logging.NOTSET)


def _config(
    queue: Optional[Dict[str, Any]],
    *,
    rate: float = 1.6,
    distribution: str = "poisson",
    total: int = 5000,
    duration: float = 300.0,
) -> Dict[str, Any]:
    doc: Dict[str, Any] = {
        "format": "urbanflow-scenario",
        "version": 1,
        "name": "invariants",
        "junction": {"type": "fixed_time_signal"},
        "approaches": {
            d: {
                "lanes": 1,
                "length": 80.0,
                "vehiclesPerHour": 1000,
                "turning": {"left": 0.25, "straight": 0.5, "right": 0.25},
            }
            for d in ("north", "south", "east", "west")
        },
        "simulation": {"duration": duration, "warmup": 10.0, "seed": 5},
    }
    if queue is not None:
        doc["traffic"] = {"entryQueue": queue}
    parsed, errors = parse_scenario(doc)
    assert parsed is not None and not errors, errors
    config = compile_scenario(parsed, "fixed_time")
    # A known rate and an even split, so the expected demand is exact.
    config["traffic"]["arrivalRate"] = rate
    config["traffic"]["arrivalDistribution"] = distribution
    config["traffic"]["directionalSplit"] = {
        d: 0.25 for d in ("north", "south", "east", "west")
    }
    config["traffic"]["totalVehicles"] = total
    return config


def _engine(config: Dict[str, Any]) -> SimulationEngine:
    engine = SimulationEngine(
        Clock(time_step=0.1),
        duration=float(config["simulation"]["duration"]),
        config=config,
    )
    engine.controller = create_controller(config, engine.network)
    return engine


def _identities(engine: SimulationEngine) -> Dict[str, Any]:
    assert engine.spawner is not None
    acc = engine.spawner.demand_accounting()
    assert acc["arrivals"] == acc["admitted"] + acc["waitingAtEntry"] + acc["rejected"]
    # Waiting vehicles are outside the network: only admitted vehicles are in
    # the pool, active or exited, and nothing is counted twice.
    assert acc["admitted"] == engine.spawner.spawned_count
    assert acc["admitted"] == len(engine.pool.active_vehicles) + len(
        engine.pool.exited_vehicles
    )
    ids = [v.vehicle_id for v in engine.pool.active_vehicles] + [
        v.vehicle_id for v in engine.pool.exited_vehicles
    ]
    assert len(ids) == len(set(ids))
    return acc


QUEUED = {"enabled": True}


def test_queue_clock_generates_the_configured_uniform_demand_exactly() -> None:
    # 7 veh/s, a quarter per approach: one arrival every 4/7 s = 0.571 s,
    # which a 0.1 s tick cannot divide. Over 60 s each approach is due
    # floor(60 x 1.75) = 105 arrivals. Restarting the clock at the tick
    # boundary made every gap 0.6 s: 100.
    engine = _engine(_config(QUEUED, rate=7.0, distribution="uniform", duration=60))
    for _ in range(600):
        engine.step()
    acc = _identities(engine)
    for row in acc["byApproach"].values():
        assert row["arrivals"] == pytest.approx(105, abs=1)
    assert acc["arrivals"] == pytest.approx(acc["nominalDemand"], abs=4)


def test_queue_clock_matches_poisson_demand_at_the_maximum_rate() -> None:
    # 10 veh/s is the largest arrivalRate the schema accepts. 200 s gives
    # 2,000 expected arrivals (Poisson s.d. about 45, 2.2 %); the restarted
    # clock fell about 11 % short.
    engine = _engine(_config(QUEUED, rate=10.0, duration=200))
    for _ in range(2000):
        engine.step()
    acc = _identities(engine)
    assert acc["nominalDemand"] == pytest.approx(2000.0, abs=0.5)
    assert acc["arrivals"] == pytest.approx(acc["nominalDemand"], rel=0.07)
    assert acc["estimatedSuppressedArrivals"] == 0.0


def test_queued_arrivals_record_when_they_fell_due() -> None:
    engine = _engine(_config(QUEUED, rate=7.0, distribution="uniform", duration=30))
    for _ in range(300):
        engine.step()
    assert engine.spawner is not None
    # Arrival times are the exact due moments, not tick ends: with a 4/7 s
    # gap almost none falls on a tick boundary.
    times = [a.arrival_time for q in engine.spawner._backlog.values() for a in q]
    assert times
    off_tick = [t for t in times if abs(t * 10 - round(t * 10)) > 1e-6]
    assert len(off_tick) > len(times) // 2
    for q in engine.spawner._backlog.values():
        due = [a.arrival_time for a in q]
        assert due == sorted(due)
        assert all(t <= engine.clock.get_elapsed_time() + 1e-9 for t in due)


@pytest.mark.parametrize("queue", [None, QUEUED, {"enabled": True, "capacity": 2}])
def test_zero_length_steps_generate_nothing(queue: Optional[Dict[str, Any]]) -> None:
    engine = _engine(_config(queue, rate=4.0, duration=60))
    for _ in range(200):
        engine.step()
    assert engine.spawner is not None
    before = _identities(engine)
    for _ in range(50):
        engine.spawner.step(0.0)
    after = engine.spawner.demand_accounting()
    assert after["arrivals"] == before["arrivals"]
    assert after["nominalDemand"] == before["nominalDemand"]
    assert after["entryBlockedSeconds"] == before["entryBlockedSeconds"]
    assert after["rejected"] == before["rejected"]
    assert after["arrivals"] == (
        after["admitted"] + after["waitingAtEntry"] + after["rejected"]
    )


def test_queue_memory_is_bounded_by_the_vehicle_limit_at_maximum_load() -> None:
    # Maximum rate, no queue capacity, a small vehicle limit so it is reached
    # quickly: generation stops at the limit and the backlog can never hold
    # more than it (at most totalVehicles = 5,000 entries in any run).
    engine = _engine(_config(QUEUED, rate=10.0, total=400, duration=120))
    assert engine.spawner is not None
    peak = 0
    for _ in range(1200):
        engine.step()
        waiting = sum(len(q) for q in engine.spawner._backlog.values())
        peak = max(peak, waiting)
        assert engine.spawner.demand_accounting()["arrivals"] <= 400
    acc = _identities(engine)
    assert acc["arrivals"] == 400
    assert peak <= 400
    # Each waiting arrival is one three-field record (arrival time, turn,
    # class), not a Vehicle: a full 5,000-entry backlog stays well under 1 MB.
    entries = [a for q in engine.spawner._backlog.values() for a in q]
    if entries:
        assert len(entries[0]) == 3
        assert sys.getsizeof(entries[0]) < 200


@pytest.mark.parametrize("queue", [None, QUEUED, {"enabled": True, "capacity": 3}])
def test_a_completed_run_accounts_for_every_arrival(
    queue: Optional[Dict[str, Any]],
) -> None:
    engine = _engine(_config(queue, rate=2.0, duration=90))
    while not engine.clock.get_elapsed_time() >= 90.0 - 1e-9:
        engine.step()
    acc = _identities(engine)
    still_in = len(engine.pool.active_vehicles)
    exited = len(engine.pool.exited_vehicles)
    assert acc["admitted"] == still_in + exited
    assert (
        acc["arrivals"] == exited + still_in + acc["waitingAtEntry"] + acc["rejected"]
    )
    if queue is None:
        assert acc["rejected"] == 0
        assert acc["waitingAtEntry"] <= len(acc["byApproach"])
    else:
        assert acc["estimatedSuppressedArrivals"] == 0.0


def test_reset_mid_run_reproduces_a_fresh_queued_run() -> None:
    config = _config(QUEUED, rate=6.0, duration=60)
    fresh = _engine(config)
    for _ in range(400):
        fresh.step()
    assert fresh.spawner is not None
    expected = fresh.spawner.demand_accounting()

    reused = _engine(config)
    for _ in range(250):
        reused.step()
    reused.reset()
    for _ in range(400):
        reused.step()
    assert reused.spawner is not None
    assert reused.spawner.demand_accounting() == expected
