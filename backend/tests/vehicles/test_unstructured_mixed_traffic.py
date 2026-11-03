"""unstructuredTraffic with a vehicle mix (F-38).

The flag promises chaotic driving ("hesitation, variable reaction,
blocking"). It used to replace only the engine-wide driver model, which
vehicles with a class never use, so with any vehicle mix it changed no
trajectory at all. Every class now drives the stochastic model around its own
parameters, on the spawner's random stream.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Tuple

import pytest

from src.engine.simulation_engine import SimulationEngine
from src.vehicles.idm import IntelligentDriverModel
from src.vehicles.stochastic_idm import StochasticIDM
from tests.engine.test_reset_matches_fresh_run import _build, _cars_only, _document

TICKS = 600


@pytest.fixture(autouse=True)
def _quiet() -> Any:
    logging.disable(logging.WARNING)  # deadlock insight log lines
    yield
    logging.disable(logging.NOTSET)


def _mixed(seed: int = 21, junction: str = "fixed_time_signal") -> Dict[str, Any]:
    doc = _document(
        junction, {"circulatingLanes": 2} if junction == "roundabout" else None
    )
    doc["simulation"]["seed"] = seed
    return doc


def _strategy(junction: str) -> str:
    return "roundabout" if junction == "roundabout" else "fixed_time"


def _run(doc: Dict[str, Any], unstructured: bool) -> Tuple[SimulationEngine, List[Any]]:
    junction = doc["junction"]["type"]
    engine, _, _ = _build(doc, _strategy(junction), unstructured)
    for _ in range(TICKS):
        engine.step()
    state = [(v.vehicle_id, v.position, v.speed) for v in engine.pool.active_vehicles]
    return engine, state


def _class_params(engine: SimulationEngine) -> List[Any]:
    assert engine.spawner is not None
    populations = [engine.spawner.population]
    populations += list(engine.spawner.approach_populations.values())
    return [p for pop in populations if pop is not None for p, _ in pop.entries]


def test_every_class_drives_the_stochastic_model_with_its_own_parameters() -> None:
    engine, _ = _run(_mixed(), unstructured=True)
    params = _class_params(engine)
    assert {p.type_id for p in params} == {"car", "bus", "truck", "motorcycle"}
    assert engine.spawner is not None
    for p in params:
        assert isinstance(p.idm, StochasticIDM), p.type_id
        assert p.idm.rng is engine.spawner.rng
        # The class keeps its own baseline: a bus is still a bus.
        assert p.idm._desired_time_headway == p.profile.desired_time_headway
        assert p.idm._minimum_gap == p.profile.minimum_gap
        assert p.idm._max_acceleration == p.profile.max_acceleration
    headways = {p.type_id: p.idm._desired_time_headway for p in params}
    assert (
        headways["truck"] > headways["bus"] > headways["car"] > headways["motorcycle"]
    )


def test_structured_traffic_keeps_the_deterministic_class_models() -> None:
    engine, _ = _run(_mixed(), unstructured=False)
    for p in _class_params(engine):
        assert type(p.idm) is IntelligentDriverModel, p.type_id


@pytest.mark.parametrize("junction", ["fixed_time_signal", "roundabout"])
def test_unstructured_changes_mixed_traffic_trajectories(junction: str) -> None:
    _, structured = _run(_mixed(junction=junction), unstructured=False)
    _, chaotic = _run(_mixed(junction=junction), unstructured=True)
    assert chaotic != structured


def test_the_same_seed_reproduces_and_other_seeds_differ() -> None:
    _, first = _run(_mixed(seed=5), unstructured=True)
    _, again = _run(_mixed(seed=5), unstructured=True)
    _, other = _run(_mixed(seed=6), unstructured=True)
    assert first == again
    assert first != other


def test_cars_only_unstructured_traffic_is_unchanged_by_the_fix() -> None:
    """Without a mix every vehicle still drives the engine-wide model alone."""
    engine, _ = _run(_cars_only(_mixed()), unstructured=True)
    assert isinstance(engine.idm, StochasticIDM)
    assert _class_params(engine) == []


@pytest.mark.parametrize("junction", ["fixed_time_signal", "roundabout"])
@pytest.mark.parametrize("seed", [1, 2])
def test_chaotic_mixed_traffic_stays_physically_plausible(
    junction: str, seed: int
) -> None:
    doc = _mixed(seed=seed, junction=junction)
    for approach in doc["approaches"].values():
        approach["vehiclesPerHour"] = 900
    engine, _, _ = _build(doc, _strategy(junction), True)
    for _ in range(1200):
        engine.step()
        for v in engine.pool.active_vehicles:
            assert math.isfinite(v.position) and math.isfinite(v.speed)
            assert v.speed >= 0.0
            idm = v.params.idm if v.params is not None else engine.idm
            # The model's reaction jitter adds up to 0.5 m/s^2 either side of
            # the IDM's own limits (9 m/s^2 braking).
            assert v.acceleration <= idm._max_acceleration + 0.5 + 1e-9
            assert v.acceleration >= -9.5 - 1e-9
    assert engine.pool.collision_count == 0
