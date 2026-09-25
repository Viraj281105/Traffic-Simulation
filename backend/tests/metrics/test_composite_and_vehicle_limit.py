"""Composite validity and the vehicle-generation limit flag.

Regression for: the fixed-weight composite scored best-case placeholders
(fairness 1.0, no waiting) before any vehicle had exited, and the silent
200-vehicle spawn cap could truncate demand without any signal in the metrics.
"""

from typing import Any, Dict

from src.core.limits import DEFAULT_TOTAL_VEHICLES
from src.metrics.collector import MetricCollector
from src.metrics.efficiency import calculate_master_efficiency_score


def _base(**overrides: Any) -> Dict[str, Any]:
    metrics: Dict[str, Any] = {
        "throughput": 10,
        "throughputRate": 30.0,
        "averageWaitTime": 5.0,
        "averageStopsPerVehicle": 1.0,
        "directionalFairnessIndex": 0.9,
        "idleOpportunityLoss": 0.0,
    }
    metrics.update(overrides)
    return metrics


def test_composite_is_not_computed_before_anything_was_measured() -> None:
    assert calculate_master_efficiency_score(_base(throughput=0)) is None
    assert calculate_master_efficiency_score({}) is None
    assert calculate_master_efficiency_score(_base()) is not None


def test_collector_reports_no_composite_until_a_vehicle_exits() -> None:
    collector = MetricCollector({"simulation": {"warmupTime": 30.0}})
    metrics = collector.get_metrics(5.0, [], [], 0)
    assert metrics["throughput"] == 0
    assert metrics["masterEfficiencyScore"] is None


def test_composite_gives_a_roundabout_the_full_idle_term_by_construction() -> None:
    """Documents (and pins) why the composite must never rank a signal against
    a roundabout: idleOpportunityLoss is 0.0 for a roundabout, so its idle term
    is always the full 10 points, whatever else happens."""
    signal = calculate_master_efficiency_score(_base(idleOpportunityLoss=0.3))
    roundabout = calculate_master_efficiency_score(_base(idleOpportunityLoss=0.0))
    assert signal is not None and roundabout is not None
    assert round(roundabout - signal, 1) == 3.0  # 10 * 0.3, from geometry alone


def test_vehicle_limit_defaults_to_the_spawners_default() -> None:
    collector = MetricCollector({})
    metrics = collector.get_metrics(1.0, [], [], 0)
    assert metrics["vehicleLimit"] == DEFAULT_TOTAL_VEHICLES == 200
    assert metrics["vehicleLimitReached"] is False


def test_vehicle_limit_flag_follows_the_configured_cap() -> None:
    collector = MetricCollector({"traffic": {"totalVehicles": 50}})
    below = collector.get_metrics(1.0, [], [], 49)
    at_cap = collector.get_metrics(1.0, [], [], 50)
    assert below["vehicleLimit"] == 50
    assert below["vehicleLimitReached"] is False
    assert at_cap["vehicleLimitReached"] is True


def test_a_truncated_run_is_flagged_end_to_end() -> None:
    """High demand x a small cap: the spawner stops at the cap and the metrics
    say so, on both geometries, instead of reading as full demand."""
    from src.snapshot.dual_orchestrator import DualSimulationOrchestrator

    orch = DualSimulationOrchestrator(
        {
            "simulation": {
                "timeStep": 0.1,
                "duration": 30.0,
                "warmupTime": 1.0,
                "randomSeed": 3,
            },
            "roads": {"lanesPerApproach": 1},
            "traffic": {"arrivalRate": 1.0, "totalVehicles": 5},
        }
    )
    for _ in range(orch.clock_signal.ticks_for_duration(30.0)):
        orch.engine_signal.step()
        orch.engine_roundabout.step()
    for engine, collector, clock in (
        (orch.engine_signal, orch.collector_signal, orch.clock_signal),
        (orch.engine_roundabout, orch.collector_roundabout, orch.clock_roundabout),
    ):
        assert engine.spawner is not None and engine.spawner.spawned_count == 5
        metrics = collector.get_metrics(
            clock.get_elapsed_time(),
            engine.pool.active_vehicles,
            engine.pool.exited_vehicles,
            engine.spawner.spawned_count,
            engine.pool.collision_count,
        )
        assert metrics["vehicleLimit"] == 5
        assert metrics["vehicleLimitReached"] is True


# ── the limit is sized to the scenario, so it cannot silently truncate demand ─


def test_demand_vehicle_limit_is_sized_from_the_scenario() -> None:
    from src.core.limits import MAX_TOTAL_VEHICLES, demand_vehicle_limit

    # Small scenarios keep the historical default.
    assert demand_vehicle_limit(0.2, 60.0) == DEFAULT_TOTAL_VEHICLES
    assert demand_vehicle_limit(0.0, 300.0) == DEFAULT_TOTAL_VEHICLES
    # 0.7 veh/s x 300 s = 210 expected: the old default (200) truncated this;
    # the derived limit is ceil(210 x 1.5) + 50 = 365.
    assert demand_vehicle_limit(0.7, 300.0) == 365
    # Never above the schema maximum.
    assert demand_vehicle_limit(10.0, 3600.0) == MAX_TOTAL_VEHICLES == 5000


def test_dashboard_scenarios_no_longer_inherit_the_silent_cap() -> None:
    from src.main import _compile_dashboard_config

    config = _compile_dashboard_config(
        {
            "intersectionType": "fixed_time_signal",
            "arrivalRate": 0.8,
            "duration": 300,
            "lanesNorth": 2,
            "lanesSouth": 2,
            "lanesEast": 2,
            "lanesWest": 2,
        },
        seed_val=1,
    )
    assert config["traffic"]["totalVehicles"] == 410  # ceil(240 x 1.5) + 50 > 200


def test_sweep_and_validation_size_the_limit_but_respect_an_explicit_one(
    tmp_path: object, monkeypatch: object
) -> None:
    import src.database.db as db
    from src.core.limits import demand_vehicle_limit
    from src.study.validation import run_statistical_validation
    from src.study.volume_sweep import run_volume_sweep_experiment

    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "s.db"))  # type: ignore[attr-defined,operator]
    sweep = run_volume_sweep_experiment(arrival_rates=[0.3], duration=3.0)
    assert sweep["runs"][0]["signal"]["metrics"]["vehicleLimit"] == (
        demand_vehicle_limit(0.3, 3.0)
    )
    explicit = run_volume_sweep_experiment(
        arrival_rates=[0.3],
        duration=3.0,
        custom_config={"traffic": {"totalVehicles": 7}},
    )
    assert explicit["runs"][0]["signal"]["metrics"]["vehicleLimit"] == 7

    # Validation: the per-seed run config gets a sized limit too.
    seen: list = []
    from src.snapshot.dual_orchestrator import DualSimulationOrchestrator

    original = DualSimulationOrchestrator.__init__

    def spy(self, config):  # type: ignore[no-untyped-def]
        seen.append(config["traffic"]["totalVehicles"])
        original(self, config)

    monkeypatch.setattr(DualSimulationOrchestrator, "__init__", spy)  # type: ignore[attr-defined]
    run_statistical_validation(num_seeds=1, duration=3.0)
    assert seen == [demand_vehicle_limit(0.35, 3.0)]


# ── fairness uses the same warm-up window as averageWaitTime ────────────────


def test_fairness_subtracts_the_warmup_baseline_like_average_wait_time() -> None:
    """A vehicle already waiting when warm-up ended must not carry that
    pre-warm-up waiting into the post-warm-up fairness index."""
    from src.metrics.definitions.fairness import calculate_directional_fairness

    class _Lane:
        def __init__(self, lane_id: str) -> None:
            self.lane_id = lane_id

    class _V:
        def __init__(self, vid: str, lane_id: str, wait: float) -> None:
            self.vehicle_id = vid
            self.route = [_Lane(lane_id)]
            self.wait_time = wait

    vehicles = [_V("a", "n_in_0", 30.0), _V("b", "s_in_0", 10.0)]
    # Unclipped: mean waits 30 vs 10 -> J = (40^2) / (2 * 1000) = 0.8
    assert abs(calculate_directional_fairness(vehicles) - 0.8) < 1e-9
    # "a" had already waited 20 s before warm-up ended: 10 vs 10 -> J = 1.0
    assert calculate_directional_fairness(vehicles, {"a": 20.0}) == 1.0
    # A baseline larger than the wait never produces a negative wait.
    assert calculate_directional_fairness(vehicles, {"a": 99.0, "b": 99.0}) == 1.0
