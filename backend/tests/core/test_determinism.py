"""Phase 4: Determinism Audit and Fix.

Verifies that the entire simulation is deterministic when run twice with the same
random seed, including for unstructured traffic (StochasticIDM and LaneChangeModel).
"""

import pytest

from src.snapshot.dual_orchestrator import DualSimulationOrchestrator


def run_simulation_and_get_snapshot(seed: int, unstructured: bool = False):
    """Runs a short simulation and returns the final metrics and active vehicles."""
    config_dict = {
        "geometry": {
            "intersectionType": "fixed_time_signal",
            "laneWidth": 3.0,
        },
        "simulation": {
            "randomSeed": seed,
            "warmupTime": 5.0,
            "timeStep": 0.1,
            "metricsCollectionInterval": 1.0,
            "duration": 15.0,
        },
        "traffic": {
            "totalVehicles": 50,
            "unstructuredTraffic": unstructured,
        },
    }
    
    # Run the engine for exactly 15 seconds (150 ticks)
    orch = DualSimulationOrchestrator(config_dict)
    engine = orch.engine_signal
    clock = orch.clock_signal
    collector = orch.collector_signal
    
    for _ in range(150):
        engine.step()
        
    return {
        "metrics": collector.get_metrics(
            clock.get_elapsed_time(), 
            engine.pool.active_vehicles, 
            [], 
            engine.spawner.spawned_count
        ),
        "active_vehicle_count": len(engine.pool.active_vehicles),
        # Extract vehicle coordinates and speeds to verify exact positional determinism
        "vehicle_states": {
            v.vehicle_id: (round(v.coords[0], 4), round(v.coords[1], 4), round(v.speed, 4))
            for v in engine.pool.active_vehicles
        }
    }


def test_structured_traffic_is_deterministic():
    """Two identical runs with standard IDM should produce identical results."""
    run1 = run_simulation_and_get_snapshot(seed=42, unstructured=False)
    run2 = run_simulation_and_get_snapshot(seed=42, unstructured=False)
    
    assert run1["active_vehicle_count"] == run2["active_vehicle_count"]
    assert run1["vehicle_states"] == run2["vehicle_states"]


def test_unstructured_traffic_is_deterministic():
    """Two identical runs with StochasticIDM should produce identical results.
    This failed before Phase 4 because StochasticIDM used the global `random` module.
    """
    run1 = run_simulation_and_get_snapshot(seed=1337, unstructured=True)
    run2 = run_simulation_and_get_snapshot(seed=1337, unstructured=True)
    
    assert run1["active_vehicle_count"] == run2["active_vehicle_count"]
    assert run1["vehicle_states"] == run2["vehicle_states"]


def test_different_seeds_produce_different_results_unstructured():
    """Sanity check: different seeds should perturb StochasticIDM/spawner."""
    run1 = run_simulation_and_get_snapshot(seed=100, unstructured=True)
    run2 = run_simulation_and_get_snapshot(seed=200, unstructured=True)
    
    # It's highly probable the states diverge after 15s
    assert run1["vehicle_states"] != run2["vehicle_states"]
