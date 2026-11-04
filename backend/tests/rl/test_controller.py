"""ExternalPhaseController: external green choice with enforced clearance."""

import pytest

from src.core.clock import Clock
from src.engine.simulation_engine import SimulationEngine
from src.rl.controller import ExternalPhaseController
from src.rl.scenario import junction_config


def _rig(min_green: float = 5.0):
    config = junction_config(vehicles_per_hour=100, seed=3, duration=120.0)
    engine = SimulationEngine(
        Clock(time_step=float(config["simulation"]["timeStep"])),
        duration=120.0,
        config=config,
    )
    controller = ExternalPhaseController(config, engine.network, min_green=min_green)
    engine.controller = controller
    return engine, controller


def _run(engine, seconds):
    for _ in range(int(round(seconds / engine.clock.time_step))):
        engine.step()


def test_starts_on_north_south_green_and_holds_without_a_request():
    engine, controller = _rig()
    _run(engine, 30)
    assert controller.current_phase.name == "ns_green"
    assert controller.switches == 0


def test_min_green_then_yellow_then_all_red_then_other_green():
    engine, controller = _rig(min_green=5.0)
    controller.request_green(1)
    _run(engine, 4.0)
    assert controller.current_phase.name == "ns_green"  # min green not yet served
    _run(engine, 1.5)
    assert controller.current_phase.name == "ns_yellow"
    assert controller.in_transition
    _run(engine, controller.yellow_duration)
    assert controller.current_phase.name == "all_red"
    _run(engine, controller.all_red_duration + 0.2)
    assert controller.current_phase.name == "ew_green"
    assert controller.active_green == 1
    assert controller.switches == 1


def test_invalid_request_is_rejected():
    _, controller = _rig()
    with pytest.raises(ValueError):
        controller.request_green(2)
