import json

from src.controllers.fixed_time_signal import FixedTimeSignalController
from src.core.clock import Clock
from src.core.engine import SimulationEngine
from src.core.enums import TurnIntent, VehicleState
from src.metrics.collector import MetricCollector
from src.roads.lane import Lane
from src.snapshot.buffer import SnapshotBuffer
from src.snapshot.builder import SnapshotBuilder
from src.snapshot.dual_orchestrator import DualSimulationOrchestrator
from src.vehicles.vehicle import Vehicle


def test_snapshot_buffer(tmp_path) -> None:
    buf = SnapshotBuffer(max_frames=2)
    assert buf.get_all() == []

    buf.append({"tick": 1, "data": "f1"})
    buf.append({"tick": 2, "data": "f2"})
    assert len(buf.get_all()) == 2

    # Overflow capacity
    buf.append({"tick": 3, "data": "f3"})
    assert len(buf.get_all()) == 2
    assert buf.get_frame(1) is None
    assert buf.get_frame(2) == {"tick": 2, "data": "f2"}

    # Export to file
    out_file = str(tmp_path / "snapshots.json")
    buf.export_to_file(out_file)
    with open(out_file, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert len(loaded) == 2

    # Clear
    buf.clear()
    assert len(buf.get_all()) == 0


def test_snapshot_builder_active_and_exited_vehicles() -> None:
    config = {
        "simulation": {"warmupTime": 5.0, "timeStep": 0.1},
        "geometry": {"intersectionType": "fixed_time_signal", "intersectionCenter": {"x": 0.0, "y": 0.0}},
        "roads": {"approachLength": 100.0, "laneWidth": 3.5, "lanesPerApproach": 2},
    }
    clock = Clock(0.1)
    engine = SimulationEngine(clock, duration=10.0, config=config)
    collector = MetricCollector(config)
    controller = FixedTimeSignalController(config, engine.network)
    builder = SnapshotBuilder("sim_1", "cfg_1", engine, collector, controller)

    lane_conn = Lane("conn_north_0_straight", 0.0, 10.0, 0.0, -10.0)
    lane_round = Lane("roundabout_circ", 0.0, 10.0, 10.0, 0.0)
    lane_in = Lane("north_in_0", 0.0, 100.0, 0.0, 10.0)

    # 1. Crossing vehicle on conn lane
    v_crossing = Vehicle("v_cross", 4.0, 2.0, 10.0, route=[lane_in, lane_conn], start_position=5.0, initial_speed=10.0, turn_intent=TurnIntent.STRAIGHT)
    v_crossing.lane = lane_conn

    # 2. In-roundabout vehicle
    v_round = Vehicle("v_round", 4.0, 2.0, 10.0, route=[lane_round], start_position=5.0, initial_speed=8.0, turn_intent=TurnIntent.LEFT)

    # 3. Approaching & waiting vehicles
    v_app = Vehicle("v_app", 4.0, 2.0, 10.0, route=[lane_in], start_position=5.0, initial_speed=10.0, turn_intent=TurnIntent.RIGHT)
    v_wait = Vehicle("v_wait", 4.0, 2.0, 10.0, route=[lane_in], start_position=50.0, initial_speed=0.0, turn_intent=TurnIntent.STRAIGHT)
    v_wait.state = VehicleState.WAITING

    engine.pool.active_vehicles.extend([v_crossing, v_round, v_app, v_wait])

    # 4. Exited vehicle
    v_exit = Vehicle("v_exit", 4.0, 2.0, 10.0, route=[lane_in], start_position=100.0, initial_speed=10.0, turn_intent=TurnIntent.STRAIGHT)
    v_exit.state = VehicleState.EXITED
    v_exit.exit_time = 8.5
    engine.pool.exited_vehicles.append(v_exit)

    snapshot = builder.build()
    assert snapshot["schemaVersion"] == "1.0.0"
    assert snapshot["vehicleCounts"]["active"] == 4
    assert snapshot["vehicleCounts"]["exited"] == 1
    assert len(snapshot["vehicles"]) == 5

    # Test KeyError on missing approach in network
    empty_engine = SimulationEngine(clock, duration=10.0)
    builder_empty = SnapshotBuilder("sim_empty", "cfg_empty", empty_engine, collector, controller)
    snap_empty = builder_empty.build()
    assert len(snap_empty["intersection"]["approaches"]) == 4


def test_dual_simulation_orchestrator() -> None:
    config = {
        "roads": {"approachLength": 100.0, "laneWidth": 3.5, "lanesPerApproach": 2},
        "traffic": {"arrivalRate": 2.0},
    }
    orchestrator = DualSimulationOrchestrator(config)
    assert orchestrator.get_status() == "initialized"

    # Step engines to invoke tick callbacks
    orchestrator.engine_signal.step()
    orchestrator.engine_roundabout.step()

    orchestrator.start()
    assert orchestrator.get_status() == "running"

    orchestrator.pause()
    assert orchestrator.get_status() == "paused"

    orchestrator.stop()
    assert orchestrator.get_status() == "completed"

    snap = orchestrator.get_dual_snapshot()
    assert "signal" in snap
    assert "roundabout" in snap


