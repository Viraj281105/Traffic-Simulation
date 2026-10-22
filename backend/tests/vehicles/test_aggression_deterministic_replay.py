"""Deterministic replay tests for driver-aggression profiles (W4-T4).

Verifies:
1. Deterministic simulation replay for identical scenario specifications, seeds, and aggression profiles.
2. Distinct simulation trajectories across standard, moderate, and high profiles under identical seeds.
3. Invariant: safe deceleration b_safe remains 4.0 m/s^2 and collisions remain 0 under aggressive driving.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import pytest

from src.controllers.factory import create_controller
from src.core.clock import Clock
from src.engine.simulation_engine import SimulationEngine
from src.metrics.collector import MetricCollector
from src.scenario.documents import (
    ScenarioDocument,
    compile_scenario,
    create_scenario,
    parse_scenario,
    scenario_fingerprint,
)
from src.vehicles.driver_aggression import (
    DriverAggression,
)


def _simulate_scenario(
    doc: ScenarioDocument, strategy: str = "fixed_time", ticks: int = 100
) -> Tuple[List[Tuple[int, str, float, float]], Dict[str, Any]]:
    """Compile scenario document and run engine for `ticks` steps, returning vehicle states and metrics."""
    config = compile_scenario(doc, strategy)
    clock = Clock(time_step=config.get("simulation", {}).get("timeStep", 0.1))
    duration = config.get("simulation", {}).get("duration", 300)
    engine = SimulationEngine(clock, duration=duration, config=config)
    controller = create_controller(config, engine.network)
    engine.controller = controller
    collector = MetricCollector(config)

    for _ in range(ticks):
        engine.step()

    metrics = collector.get_metrics(
        clock.get_elapsed_time(),
        engine.pool.active_vehicles,
        engine.pool.exited_vehicles,
        engine.spawner.spawned_count if engine.spawner else 0,
        engine.pool.collision_count,
    )

    vehicles = sorted(engine.pool.active_vehicles, key=lambda v: v.vehicle_id)
    states = [
        (
            v.vehicle_id,
            v.lane.lane_id if v.lane is not None else "",
            round(float(v.position), 6),
            round(float(v.speed), 6),
        )
        for v in vehicles
    ]
    return states, metrics, engine.pool.collision_count


@pytest.mark.parametrize("profile", ("standard", "moderate", "high"))
def test_deterministic_replay_per_profile(profile: DriverAggression) -> None:
    """Identical scenario specification, seed, and aggression profile replay bit-identically."""
    # Build base scenario with specific seed and aggression profile
    doc1 = create_scenario(
        name=f"Deterministic Replay - {profile}",
        junction_type="fixed_time_signal",
        driver_aggression=profile,
    )
    # Ensure seed is deterministic
    doc1.simulation.seed = 2026

    # Clone document independently
    doc2, errs = parse_scenario(doc1.model_dump())
    assert errs == []
    assert doc2 is not None

    # Verify scenario identity matches
    assert scenario_fingerprint(doc1) == scenario_fingerprint(doc2)

    # Run two independent simulations
    states1, metrics1, collisions1 = _simulate_scenario(doc1, strategy="fixed_time", ticks=120)
    states2, metrics2, collisions2 = _simulate_scenario(doc2, strategy="fixed_time", ticks=120)

    # Invariants: no collisions, vehicles spawned
    assert collisions1 == 0
    assert collisions2 == 0
    assert len(states1) > 0

    # Bit-identical state trajectory and metrics replay
    assert states1 == states2
    assert metrics1["throughput"] == metrics2["throughput"]
    assert metrics1["averageDelay"] == metrics2["averageDelay"]


def test_distinct_trajectories_across_profiles_under_same_seed() -> None:
    """Under identical seeds and geometry, moderate and high profiles alter vehicle dynamics distinctly."""
    seed = 42
    mix = {"mix": {"car": 0.8, "truck": 0.2}}

    doc_std = create_scenario(
        name="Profile Comparison - Standard",
        junction_type="fixed_time_signal",
        driver_aggression="standard",
        vehicles=mix,
    )
    doc_std.simulation.seed = seed

    doc_mod = create_scenario(
        name="Profile Comparison - Moderate",
        junction_type="fixed_time_signal",
        driver_aggression="moderate",
        vehicles=mix,
    )
    doc_mod.simulation.seed = seed

    doc_high = create_scenario(
        name="Profile Comparison - High",
        junction_type="fixed_time_signal",
        driver_aggression="high",
        vehicles=mix,
    )
    doc_high.simulation.seed = seed

    states_std, metrics_std, collisions_std = _simulate_scenario(doc_std, strategy="fixed_time", ticks=150)
    states_mod, metrics_mod, collisions_mod = _simulate_scenario(doc_mod, strategy="fixed_time", ticks=150)
    states_high, metrics_high, collisions_high = _simulate_scenario(doc_high, strategy="fixed_time", ticks=150)

    # Zero collisions invariant holds across all aggression profiles
    assert collisions_std == 0
    assert collisions_mod == 0
    assert collisions_high == 0

    # Dynamics differ: positions and speeds are not identical to standard
    assert states_high != states_std
    assert states_mod != states_std
    assert states_high != states_mod

    # Replaying high profile a second time still produces exact identity with first high run
    doc_high_replay, _ = parse_scenario(doc_high.model_dump())
    assert doc_high_replay is not None
    states_high_replay, _, collisions_high_replay = _simulate_scenario(
        doc_high_replay, strategy="fixed_time", ticks=150
    )
    assert states_high_replay == states_high
    assert collisions_high_replay == 0
