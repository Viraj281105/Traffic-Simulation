from src.snapshot.dual_orchestrator import DualSimulationOrchestrator


def test_dual_simulation_seed_determinism() -> None:
    """Verifies that under the same random seed, dual parallel instances spawn vehicles in identical intervals, routes, and properties."""
    config = {
        "simulation": {
            "timeStep": 0.1,
            "duration": 5.0,
            "warmupTime": 0.0,
            "randomSeed": 100,  # identical seed
        },
        "traffic": {
            "arrivalRate": 0.8,
            "totalVehicles": 20,
        },
        "geometry": {
            "intersectionCenter": {"x": 0.0, "y": 0.0},
            "boundingRadius": 15.0,
        },
        "controller": {
            "greenDuration": 10,
            "yellowDuration": 3,
            "allRedDuration": 2,
        },
        "vehicleGeneration": {
            "stopSpeedThreshold": 0.1,
            "waitSpeedThreshold": 0.5,
        },
    }

    orchestrator = DualSimulationOrchestrator(config)

    # Step both engines concurrently for 30 ticks (3.0s)
    for _ in range(30):
        orchestrator.engine_signal.step()
        orchestrator.engine_roundabout.step()

    # Compare vehicle lists spawned so far
    signal_vehs = sorted(
        orchestrator.engine_signal.pool.active_vehicles,
        key=lambda v: v.vehicle_id,
    )
    roundabout_vehs = sorted(
        orchestrator.engine_roundabout.pool.active_vehicles,
        key=lambda v: v.vehicle_id,
    )

    # The number of spawned vehicles must be identical
    assert len(signal_vehs) == len(roundabout_vehs)

    # For each vehicle, properties and starting lanes/routes should be identical
    for vs, vr in zip(signal_vehs, roundabout_vehs):
        assert vs.length == vr.length
        assert vs.width == vr.width
        assert vs.desired_speed == vr.desired_speed
        assert vs.route[0].lane_id == vr.route[0].lane_id
