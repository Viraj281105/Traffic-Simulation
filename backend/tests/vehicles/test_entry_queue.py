"""The opt-in entry queue (traffic.entryQueue).

By default a full entry holds one arrival and suspends that approach's
arrival process (test_demand_accounting.py). With ``entryQueue.enabled`` the
arrival process keeps running and arrivals wait in a first-in-first-out point
queue outside the network, entering as space allows; beyond an optional
per-approach capacity they are rejected and counted. These tests pin:

- exact conservation at every tick (arrivals = admitted + waiting + rejected);
- all demand is generated (arrivals track the nominal demand, nothing
  suppressed), and the entry wait is measured;
- the default model is untouched (``enabled: false`` runs bit-identically);
- capacity, the vehicle limit, FIFO order, reset and determinism;
- scenario documents compile it and fingerprint it only when enabled.
"""

from __future__ import annotations

import copy
import logging
from typing import Any, Dict, Iterator, List, Optional, Tuple

import pytest

from src.controllers.factory import create_controller
from src.core.clock import Clock
from src.core.config_models import ScenarioConfiguration
from src.engine.simulation_engine import SimulationEngine
from src.metrics.collector import MetricCollector
from src.scenario.documents import (
    compile_scenario,
    parse_scenario,
    scenario_fingerprint,
)
from src.vehicles.vehicle import Vehicle


def _document(
    junction: str = "fixed_time_signal",
    vph: int = 1400,
    lanes: int = 1,
    queue: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    doc: Dict[str, Any] = {
        "format": "urbanflow-scenario",
        "version": 1,
        "name": "queue",
        "junction": {"type": junction},
        "approaches": {
            d: {
                "lanes": lanes,
                "length": 80.0,
                "vehiclesPerHour": vph,
                "turning": {"left": 0.25, "straight": 0.5, "right": 0.25},
                "vehicleMix": {"car": 0.7, "bus": 0.1, "truck": 0.1, "motorcycle": 0.1},
            }
            for d in ("north", "south", "east", "west")
        },
        "simulation": {"duration": 300.0, "warmup": 10.0, "seed": 11},
    }
    if queue is not None:
        doc["traffic"] = {"entryQueue": queue}
    return doc


def _config(document: Dict[str, Any], strategy: str = "fixed_time") -> Dict[str, Any]:
    parsed, errors = parse_scenario(document)
    assert parsed is not None and not errors, errors
    return compile_scenario(parsed, strategy)


def _engine(config: Dict[str, Any]) -> SimulationEngine:
    engine = SimulationEngine(Clock(time_step=0.1), duration=300.0, config=config)
    engine.controller = create_controller(config, engine.network)
    return engine


@pytest.fixture(autouse=True)
def _quiet() -> Iterator[None]:
    logging.disable(logging.WARNING)
    yield
    logging.disable(logging.NOTSET)


def _identities(engine: SimulationEngine) -> Dict[str, Any]:
    assert engine.spawner is not None
    acc = engine.spawner.demand_accounting()
    assert acc["arrivals"] == acc["admitted"] + acc["waitingAtEntry"] + acc["rejected"]
    assert acc["admitted"] == engine.spawner.spawned_count
    assert acc["admitted"] == len(engine.pool.active_vehicles) + len(
        engine.pool.exited_vehicles
    )
    for row in acc["byApproach"].values():
        assert (
            row["arrivals"] == row["admitted"] + row["waitingAtEntry"] + row["rejected"]
        )
    return acc


QUEUED = {"enabled": True}


@pytest.mark.parametrize(
    "document, strategy",
    [
        (_document(queue=QUEUED), "fixed_time"),
        (_document("roundabout", 1000, queue=QUEUED), "roundabout"),
        (_document(queue={"enabled": True, "capacity": 3}), "fixed_time"),
    ],
    ids=["signal", "roundabout", "signal-capacity-3"],
)
def test_conservation_holds_at_every_tick(
    document: Dict[str, Any], strategy: str
) -> None:
    engine = _engine(_config(document, strategy))
    for _ in range(1500):
        engine.step()
        _identities(engine)


def test_all_demand_is_generated_and_waits_outside() -> None:
    engine = _engine(_config(_document(queue=QUEUED)))
    for _ in range(3000):
        engine.step()
    acc = _identities(engine)
    assert acc["entryModel"] == "queue"
    assert acc["estimatedSuppressedArrivals"] == 0.0
    assert acc["rejected"] == 0
    # 1,400 veh/h x 4 arms x 300 s = 466.7 expected; Poisson noise only.
    assert acc["nominalDemand"] == pytest.approx(466.67, abs=0.01)
    assert acc["arrivals"] == pytest.approx(acc["nominalDemand"], rel=0.1)
    # The entries cannot take that, so a backlog builds and waits grow.
    assert acc["waitingAtEntry"] > 50
    assert acc["meanEntryWaitSeconds"] > 10.0
    assert acc["oldestWaitingSeconds"] > acc["meanEntryWaitSeconds"]
    assert acc["admittedShareOfNominal"] < 0.8


def test_capacity_rejects_and_counts_the_excess() -> None:
    engine = _engine(_config(_document(queue={"enabled": True, "capacity": 2})))
    assert engine.spawner is not None
    for _ in range(3000):
        engine.step()
        assert all(len(q) <= 2 for q in engine.spawner._backlog.values())
    acc = _identities(engine)
    assert acc["rejected"] > 0
    assert acc["waitingAtEntry"] <= 2 * len(acc["byApproach"])


def test_disabled_queue_is_the_default_model_bit_for_bit() -> None:
    def trace(queue: Optional[Dict[str, Any]]) -> List[Any]:
        config = _config(_document())
        if queue is not None:
            config["traffic"]["entryQueue"] = queue
        engine = _engine(config)
        out: List[Any] = []
        for _ in range(1200):
            engine.step()
            out.append(
                [
                    (v.vehicle_id, v.position.hex(), v.speed.hex())
                    for v in engine.pool.active_vehicles
                ]
            )
        assert engine.spawner is not None
        out.append(engine.spawner.rng.getstate())
        out.append(engine.spawner.demand_accounting())
        return out

    assert trace({"enabled": False}) == trace(None)


def _admissions(engine: SimulationEngine, ticks: int) -> List[Vehicle]:
    seen: List[Vehicle] = []
    known = set()
    for _ in range(ticks):
        engine.step()
        for v in engine.pool.active_vehicles:
            if v.vehicle_id not in known:
                known.add(v.vehicle_id)
                seen.append(v)
    return seen


def test_entry_waits_are_recorded_first_in_first_out() -> None:
    engine = _engine(_config(_document(queue=QUEUED)))
    vehicles = _admissions(engine, 2000)
    assert engine.spawner is not None
    acc = engine.spawner.demand_accounting()
    waits = [v.entry_wait for v in vehicles]
    assert all(w >= 0.0 for w in waits)
    assert max(waits) == pytest.approx(acc["maxEntryWaitSeconds"], abs=0.01)
    # FIFO per approach: arrival time (entry time minus wait) never
    # decreases in admission order.
    by_approach: Dict[str, List[float]] = {}
    for v in vehicles:
        # One lane per approach here, so the entry lane is the approach.
        by_approach.setdefault(v.route[0].lane_id, []).append(
            v.spawn_time - v.entry_wait
        )
    for arrivals in by_approach.values():
        assert all(b >= a - 1e-9 for a, b in zip(arrivals, arrivals[1:]))


def test_vehicle_limit_caps_arrivals_and_is_reported() -> None:
    config = _config(_document(queue=QUEUED))
    config["traffic"]["totalVehicles"] = 60
    engine = _engine(config)
    for _ in range(2000):
        engine.step()
    assert engine.spawner is not None
    acc = _identities(engine)
    assert acc["arrivals"] == 60
    collector = MetricCollector(config)
    metrics = collector.get_metrics(
        engine.clock.get_elapsed_time(),
        engine.pool.active_vehicles,
        engine.pool.exited_vehicles,
        engine.spawner.spawned_count,
        0,
        acc,
    )
    assert metrics["vehicleLimitReached"] is True


def _run(config: Dict[str, Any], ticks: int) -> Tuple[Any, ...]:
    engine = _engine(config)
    for _ in range(ticks):
        engine.step()
    assert engine.spawner is not None
    return (
        [(v.vehicle_id, v.position, v.entry_wait) for v in engine.pool.active_vehicles],
        engine.spawner.demand_accounting(),
    )


def test_queued_runs_reproduce_and_reset_clears_the_queue() -> None:
    config = _config(_document(queue=QUEUED))
    first = _run(copy.deepcopy(config), 1500)
    assert first == _run(copy.deepcopy(config), 1500)
    engine = _engine(copy.deepcopy(config))
    for _ in range(1500):
        engine.step()
    engine.reset()
    assert engine.spawner is not None
    assert all(not q for q in engine.spawner._backlog.values())
    assert engine.spawner.demand_accounting()["arrivals"] == 0
    for _ in range(1500):
        engine.step()
    assert (
        [(v.vehicle_id, v.position, v.entry_wait) for v in engine.pool.active_vehicles],
        engine.spawner.demand_accounting(),
    ) == first


def test_scenario_document_compiles_and_fingerprints_the_queue() -> None:
    plain, _ = parse_scenario(_document())
    disabled, _ = parse_scenario(_document(queue={"enabled": False}))
    enabled, _ = parse_scenario(_document(queue={"enabled": True, "capacity": 40}))
    assert plain is not None and disabled is not None and enabled is not None
    assert scenario_fingerprint(disabled) == scenario_fingerprint(plain)
    assert scenario_fingerprint(enabled) != scenario_fingerprint(plain)
    assert "entryQueue" not in compile_scenario(disabled, "fixed_time")["traffic"]
    assert compile_scenario(enabled, "fixed_time")["traffic"]["entryQueue"] == {
        "enabled": True,
        "capacity": 40,
    }
    _, errors = parse_scenario(_document(queue={"enabled": True, "capacity": 0}))
    assert errors


def test_engine_config_validation_accepts_the_queue() -> None:
    config = _config(_document(queue={"enabled": True, "capacity": 5}))
    model = ScenarioConfiguration.model_validate(config)
    assert model.traffic.entryQueue is not None
    assert model.traffic.entryQueue.capacity == 5


def test_average_entry_wait_covers_the_exited_population() -> None:
    from src.engine.tick_callback import build_tick_callback

    for queue, saturated in ((QUEUED, True), (None, False)):
        config = _config(_document(vph=1400 if saturated else 200, queue=queue))
        clock = Clock(time_step=0.1)
        engine = SimulationEngine(clock, duration=300.0, config=config)
        controller = create_controller(config, engine.network)
        engine.controller = controller
        collector = MetricCollector(config)
        engine.register_tick_callback(
            build_tick_callback(controller, clock, engine, collector)
        )
        for _ in range(3000):
            engine.step()
        assert engine.spawner is not None
        metrics = collector.get_metrics(
            clock.get_elapsed_time(),
            engine.pool.active_vehicles,
            engine.pool.exited_vehicles,
            engine.spawner.spawned_count,
            engine.pool.collision_count,
            engine.spawner.demand_accounting(),
        )
        exited = [
            v
            for v in engine.pool.exited_vehicles
            if v.exit_time is not None and v.exit_time >= collector.warmup_time
        ]
        expected = sum(v.entry_wait for v in exited) / len(exited)
        assert metrics["averageEntryWait"] == pytest.approx(expected, abs=0.005)
        if saturated:
            assert metrics["averageEntryWait"] > 5.0
        else:
            assert metrics["averageEntryWait"] < 1.0
