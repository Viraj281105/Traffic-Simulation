import time
from typing import Any, Dict

from src.controllers.fixed_time_signal import FixedTimeSignalController
from src.core.clock import Clock
from src.core.engine import SimulationEngine
from src.core.enums import VehicleState
from src.metrics.collector import MetricCollector
from src.roads.lane import Lane
from src.snapshot.builder import SnapshotBuilder
from src.snapshot.serializer import Serializer
from src.vehicles.vehicle import Vehicle


def generate_benchmark_config() -> Dict[str, Any]:
    return {
        "simulation": {
            "timeStep": 0.1,
            "duration": 300,
            "warmupTime": 30.0,
        },
        "geometry": {
            "intersectionType": "fixed_time_signal",
            "intersectionCenter": {"x": 0.0, "y": 0.0},
            "boundingRadius": 15.0,
        },
        "controller": {
            "greenDuration": 30,
            "yellowDuration": 5,
            "allRedDuration": 2,
        },
        "vehicleGeneration": {
            "stopSpeedThreshold": 0.1,
            "waitSpeedThreshold": 0.5,
        },
    }


def run_benchmark() -> None:
    print("=== Traffic Simulation Serialization Benchmark ===")

    # Initialize basic elements
    config = generate_benchmark_config()
    clock = Clock(time_step=0.1)
    engine = SimulationEngine(clock, duration=300, config=config)
    controller = FixedTimeSignalController(config, engine.network)
    collector = MetricCollector(config)

    # Setup a mock lane and route
    lane = Lane("w_in_0", -100.0, -3.5, 0.0, -3.5)
    route = [lane]

    # Populate pool with 200 active vehicles
    print("Spawning 200 active mock vehicles...")
    for i in range(200):
        v = Vehicle(
            vehicle_id=f"veh_bench_{i}",
            length=4.5,
            width=2.0,
            desired_speed=12.0,
            route=route,
            start_position=10.0 + (i * 0.1),
            initial_speed=8.0,
        )
        # Set state
        v.state = VehicleState.APPROACHING
        v.spawn_time = 10.0
        engine.pool.add_vehicle(v)

    # Initialize builder
    builder = SnapshotBuilder("bench_sim", "bench_cfg", engine, collector, controller)

    # Warmup runs
    print("Warming up JIT and caches...")
    for _ in range(10):
        snap = builder.build()
        Serializer.serialize(snap)

    # Benchmark builder
    print("Benchmarking SnapshotBuilder.build()...")
    start_build = time.perf_counter()
    runs = 100
    for _ in range(runs):
        snap = builder.build()
    end_build = time.perf_counter()

    avg_build_ms = ((end_build - start_build) / runs) * 1000.0
    print(f"Average build() time: {avg_build_ms:.2f} ms")

    # Benchmark serialization
    print("Benchmarking Serializer.serialize()...")
    snap = builder.build()
    start_serialize = time.perf_counter()
    for _ in range(runs):
        Serializer.serialize(snap)
    end_serialize = time.perf_counter()

    avg_serialize_ms = ((end_serialize - start_serialize) / runs) * 1000.0
    print(f"Average serialize() time: {avg_serialize_ms:.2f} ms")

    total_ms = avg_build_ms + avg_serialize_ms
    print(f"Total Snapshot cycle time: {total_ms:.2f} ms")

    # Exit check
    if total_ms < 5.0:
        print("\033[92mSUCCESS: Serialization cycle is under 5ms target!\033[0m")
    else:
        print("\033[91mFAILURE: Serialization cycle exceeded 5ms target!\033[0m")


if __name__ == "__main__":
    run_benchmark()
