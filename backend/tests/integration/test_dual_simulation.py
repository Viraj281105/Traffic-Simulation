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


def test_dual_simulation_different_runs() -> None:
    """Verifies that separate dual runs produce different traffic across runs, but each dual run is internally synchronized."""
    config_run1 = {
        "simulation": {"timeStep": 0.1, "duration": 5.0, "randomSeed": 111},
        "traffic": {"arrivalRate": 1.5, "totalVehicles": 30},
    }
    config_run2 = {
        "simulation": {"timeStep": 0.1, "duration": 5.0, "randomSeed": 222},
        "traffic": {"arrivalRate": 1.5, "totalVehicles": 30},
    }

    orch1 = DualSimulationOrchestrator(config_run1)
    orch2 = DualSimulationOrchestrator(config_run2)

    for _ in range(25):
        orch1.engine_signal.step()
        orch1.engine_roundabout.step()
        orch2.engine_signal.step()
        orch2.engine_roundabout.step()

    # In Run 1: signal and roundabout match 1:1
    sig1 = sorted(orch1.engine_signal.pool.active_vehicles, key=lambda v: v.vehicle_id)
    rnd1 = sorted(
        orch1.engine_roundabout.pool.active_vehicles, key=lambda v: v.vehicle_id
    )
    assert len(sig1) == len(rnd1)
    for vs, vr in zip(sig1, rnd1):
        assert vs.desired_speed == vr.desired_speed
        assert vs.route[0].lane_id == vr.route[0].lane_id

    # In Run 2: signal and roundabout match 1:1
    sig2 = sorted(orch2.engine_signal.pool.active_vehicles, key=lambda v: v.vehicle_id)
    rnd2 = sorted(
        orch2.engine_roundabout.pool.active_vehicles, key=lambda v: v.vehicle_id
    )
    assert len(sig2) == len(rnd2)
    for vs, vr in zip(sig2, rnd2):
        assert vs.desired_speed == vr.desired_speed
        assert vs.route[0].lane_id == vr.route[0].lane_id

    # Across runs: Run 1 and Run 2 are completely different
    speeds1 = [v.desired_speed for v in sig1]
    speeds2 = [v.desired_speed for v in sig2]
    assert speeds1 != speeds2
