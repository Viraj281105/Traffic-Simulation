"""SimulationEngine.reset() must return every subsystem to its initial state.

reset() used to clear only the clock, the spawner and the two vehicle lists.
Everything else carried straight over: the signal controller stayed mid-cycle,
the metric collector kept the previous run's queue history and post-warmup tick
counts, and the pool's collision tally stayed on the board. The first metrics
read after a reset therefore described a run that no longer existed.
"""

from typing import Any, Dict

from src.controllers.factory import build_tick_callback, create_controller
from src.core.clock import Clock
from src.core.engine import SimulationEngine
from src.core.enums import SimulationStatus
from src.metrics.collector import MetricCollector


def _config(**overrides: Any) -> Dict[str, Any]:
    config: Dict[str, Any] = {
        "simulation": {
            "duration": 120,
            "timeStep": 0.1,
            "warmupTime": 2.0,
            "randomSeed": 4242,
        },
        "geometry": {"intersectionType": "fixed_time_signal"},
        "roads": {"approachLength": 200.0, "laneWidth": 3.5, "lanesPerApproach": 2},
        "traffic": {"arrivalRate": 0.8, "arrivalDistribution": "poisson"},
        "controller": {"greenTime": 30.0, "yellowTime": 4.0, "allRedTime": 2.0},
    }
    config.update(overrides)
    return config


def _build(config: Dict[str, Any]) -> tuple[SimulationEngine, Any, MetricCollector]:
    clock = Clock(time_step=config["simulation"]["timeStep"])
    engine = SimulationEngine(
        clock, duration=config["simulation"]["duration"], config=config
    )
    controller = create_controller(config, engine.network)
    engine.controller = controller
    collector = MetricCollector(config)
    engine.register_tick_callback(
        build_tick_callback(controller, clock, engine, collector)
    )
    return engine, controller, collector


def _run(engine: SimulationEngine, steps: int) -> None:
    for _ in range(steps):
        engine.step()


def test_reset_restores_clock_and_status() -> None:
    engine, _, _ = _build(_config())
    _run(engine, 300)

    engine.reset()

    assert engine.clock.get_tick_count() == 0
    assert engine.clock.get_elapsed_time() == 0.0
    assert engine.status == SimulationStatus.INITIALIZED


def test_reset_clears_controller_phase_state() -> None:
    """The controller used to stay wherever it was in its cycle."""
    engine, controller, _ = _build(_config())
    _run(engine, 300)
    assert (controller.current_phase_idx, controller.time_in_current_state) != (0, 0.0)

    engine.reset()

    assert controller.current_phase_idx == 0
    assert controller.time_in_current_state == 0.0
    assert controller.cycle_number == 0


def test_reset_clears_collector_accumulated_state() -> None:
    """The collector used to keep the previous run's history and tick counts."""
    engine, _, collector = _build(_config())
    _run(engine, 300)
    assert collector.queue_history
    assert collector.total_ticks_post_warmup > 0

    engine.reset()

    assert collector.queue_history == []
    assert collector.total_ticks_post_warmup == 0
    assert collector.speed_cv_history == []
    assert collector.congestion_recovery_time == 0.0
    assert collector._warmup_baseline_captured is False


def test_reset_clears_vehicles_and_collision_tally() -> None:
    engine, _, _ = _build(_config())
    _run(engine, 300)
    engine.pool._collision_count = 7
    engine.pool._colliding_pairs.add(frozenset({"veh_1", "veh_2"}))

    engine.reset()

    assert engine.pool.active_vehicles == []
    assert engine.pool.exited_vehicles == []
    assert engine.pool.collision_count == 0
    assert engine.pool._colliding_pairs == set()
    assert engine.pool._last_lane_change == {}


def test_reset_clears_conflict_reservations() -> None:
    engine, _, _ = _build(_config())
    _run(engine, 300)
    engine.conflict_manager._reservations.clear()
    lane_ids = list(engine.conflict_manager._conflict_points.keys())
    assert lane_ids, "expected pre-computed conflict points for a signal junction"

    from src.intersection.conflict_manager import Reservation

    engine.conflict_manager._reservations[lane_ids[0]] = Reservation("veh_x", 99.0)

    engine.reset()

    assert engine.conflict_manager.get_reservation_count() == 0
    # Geometry is not run state and must survive.
    assert engine.conflict_manager._conflict_points


def test_reset_detaches_vehicles_from_their_lanes() -> None:
    """A stale vehicle left on a lane would be seen by the new run's followers."""
    engine, _, _ = _build(_config())
    _run(engine, 300)
    occupied = [
        lane
        for lane in engine.network.get_all_connection_lanes()
        if lane.get_vehicles()
    ]

    engine.reset()

    for lane in occupied:
        assert lane.get_vehicles() == []


def test_run_after_reset_reproduces_the_original_run() -> None:
    """The real point of a complete reset: a rerun is a genuine rerun.

    Also guards determinism — identical seed, identical results.
    """
    engine, _, collector = _build(_config())
    _run(engine, 400)
    first = collector.get_metrics(
        engine.clock.get_elapsed_time(),
        engine.pool.active_vehicles,
        engine.pool.exited_vehicles,
        engine.spawner.spawned_count if engine.spawner else 0,
        engine.pool.collision_count,
    )

    engine.reset()
    _run(engine, 400)
    second = collector.get_metrics(
        engine.clock.get_elapsed_time(),
        engine.pool.active_vehicles,
        engine.pool.exited_vehicles,
        engine.spawner.spawned_count if engine.spawner else 0,
        engine.pool.collision_count,
    )

    assert first == second


def test_reset_is_idempotent() -> None:
    engine, _, _ = _build(_config())
    _run(engine, 100)

    engine.reset()
    engine.reset()

    assert engine.status == SimulationStatus.INITIALIZED
    assert engine.clock.get_tick_count() == 0


def test_reset_on_a_roundabout_clears_controller_state() -> None:
    config = _config(geometry={"intersectionType": "roundabout"})
    config["controller"] = {"innerRadius": 10.0, "outerRadius": 20.0}
    engine, controller, _ = _build(config)
    _run(engine, 300)
    assert controller.time_in_current_state > 0.0

    engine.reset()

    assert controller.time_in_current_state == 0.0
    assert controller._last_entry_time == {}
    assert controller._prev_zone_occupants == {}
    assert controller._pre_entry_desired_speed == {}


def test_engine_can_start_again_after_reset() -> None:
    """reset() must leave the engine genuinely startable, not just look reset."""
    engine, _, _ = _build(_config())
    _run(engine, 50)

    engine.reset()
    engine.step()

    assert engine.clock.get_tick_count() == 1
