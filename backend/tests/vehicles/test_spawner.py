import pytest

from src.core.enums import Direction
from src.roads.approach import Approach
from src.roads.network import RoadNetwork
from src.vehicles.spawner import VehicleSpawner


def test_vehicle_spawner_init() -> None:
    network = RoadNetwork()
    network.setup_default_intersection(200.0, 3.5, 2)
    config = {
        "simulation": {"timeStep": 0.1},
        "geometry": {
            "intersectionType": "fixed_time_signal",
            "intersectionCenter": {"x": 0.0, "y": 0.0},
            "boundingRadius": 15.0
        },
        "vehicleGeneration": {
            "arrivalRate": 0.5,
            "seed": 42
        }
    }
    spawner = VehicleSpawner(config, network)
    assert spawner.arrival_rate == 0.5
    assert spawner.spawned_count == 0


def test_vehicle_spawner_distributions_and_errors() -> None:
    network = RoadNetwork()
    network.setup_default_intersection(200.0, 3.5, 2)

    # 1. Zero directional split
    cfg_zero = {
        "traffic": {"arrivalRate": 0.5, "directionalSplit": {"north": 0.0, "south": 0.0, "east": 0.0, "west": 0.0}},
    }
    sp_zero = VehicleSpawner(cfg_zero, network)
    assert sp_zero._generate_next_arrival_time(Direction.NORTH) == float("inf")

    # 2. Uniform distribution
    cfg_uni = {
        "traffic": {"arrivalRate": 0.5, "arrivalDistribution": "uniform", "directionalSplit": {"north": 1.0}},
    }
    sp_uni = VehicleSpawner(cfg_uni, network)
    assert sp_uni._generate_next_arrival_time(Direction.NORTH) == 2.0

    # 3. Burst distribution (NotImplementedError)
    cfg_burst = {
        "traffic": {"arrivalRate": 0.5, "arrivalDistribution": "burst"},
    }
    with pytest.raises(NotImplementedError):
        VehicleSpawner(cfg_burst, network)

    # 4. Invalid distribution
    cfg_inv = {
        "traffic": {"arrivalRate": 0.5, "arrivalDistribution": "unknown_dist"},
    }
    with pytest.raises(ValueError):
        VehicleSpawner(cfg_inv, network)


def test_vehicle_spawner_blocked_and_spacing() -> None:
    network = RoadNetwork()
    network.setup_default_intersection(200.0, 3.5, 1)
    config = {
        "traffic": {"arrivalRate": 10.0, "totalVehicles": 10},
    }
    spawner = VehicleSpawner(config, network)

    # 1. First vehicle spawned
    v1 = spawner._attempt_spawn(Direction.NORTH)
    assert v1 is not None

    # 2. Block the lane by putting v1 at start position (pos=5.0)
    # Target lane has vehicle too close to spawn another
    v_blocked = spawner._attempt_spawn(Direction.NORTH)
    assert v_blocked is None

    # 3. If v1 moves far down the lane (pos=100.0), spawning should succeed
    v1.position = 100.0
    v2 = spawner._attempt_spawn(Direction.NORTH)
    assert v2 is not None

    # 4. Step spawner when blocked sets timer to 0.0
    # Create network with 0-lane approach to force block
    empty_net = RoadNetwork()
    for d in Direction:
        empty_net.add_incoming_approach(Approach(d))
    sp_blocked = VehicleSpawner(config, empty_net)
    sp_blocked.timers[Direction.NORTH] = 0.0
    sp_blocked.step(0.1)
    assert sp_blocked.timers[Direction.NORTH] == 0.0



def test_vehicle_spawner_lane_selection_and_spawn_loop() -> None:
    from src.core.enums import TurnIntent
    from src.roads.lane import Lane

    network = RoadNetwork()
    network.setup_default_intersection(200.0, 3.5, 3)
    config = {
        "traffic": {"arrivalRate": 10.0, "totalVehicles": 2},
    }
    spawner = VehicleSpawner(config, network)

    # Test _select_lane_for_turn
    lanes_1 = [Lane("l0", 0, 0, 10, 0)]
    lanes_2 = [Lane("l0", 0, 0, 10, 0), Lane("l1", 0, 0, 10, 0)]
    lanes_3 = [Lane("l0", 0, 0, 10, 0), Lane("l1", 0, 0, 10, 0), Lane("l2", 0, 0, 10, 0)]

    assert spawner._select_lane_for_turn(lanes_1, TurnIntent.LEFT) == 0
    assert spawner._select_lane_for_turn(lanes_2, TurnIntent.LEFT) == 0
    assert spawner._select_lane_for_turn(lanes_2, TurnIntent.STRAIGHT) == 1
    assert spawner._select_lane_for_turn(lanes_3, TurnIntent.LEFT) == 0
    assert spawner._select_lane_for_turn(lanes_3, TurnIntent.RIGHT) == 2
    assert spawner._select_lane_for_turn(lanes_3, TurnIntent.STRAIGHT) == 1

    # Step simulation to spawn up to limit
    vehs = []
    for _ in range(100):
        vehs.extend(spawner.step(0.1))
    assert spawner.spawned_count == 2

    # Attempt spawn when approach has no lanes
    empty_net = RoadNetwork()
    for d in Direction:
        empty_net.add_incoming_approach(Approach(d))
    sp_empty = VehicleSpawner(config, empty_net)
    assert sp_empty._attempt_spawn(Direction.NORTH) is None


def test_random_traffic_variation_across_runs() -> None:
    """Verifies that separate runs without fixed seeds or with different seeds produce distinct traffic streams."""
    network = RoadNetwork()
    network.setup_default_intersection(200.0, 3.5, 2)

    config_run1 = {
        "simulation": {"timeStep": 0.1, "randomSeed": 1001},
        "traffic": {"arrivalRate": 2.0, "totalVehicles": 50},
    }
    config_run2 = {
        "simulation": {"timeStep": 0.1, "randomSeed": 2002},
        "traffic": {"arrivalRate": 2.0, "totalVehicles": 50},
    }

    spawner1 = VehicleSpawner(config_run1, network)
    spawner2 = VehicleSpawner(config_run2, network)

    # Directional splits should be different
    assert spawner1.directional_split != spawner2.directional_split

    vehs1 = []
    vehs2 = []
    for _ in range(200):
        vehs1.extend(spawner1.step(0.1))
        vehs2.extend(spawner2.step(0.1))

    # Spawning sequences should differ across runs
    assert len(vehs1) > 0 and len(vehs2) > 0
    speeds1 = [v.desired_speed for v in vehs1]
    speeds2 = [v.desired_speed for v in vehs2]
    assert speeds1 != speeds2


def test_directional_split_asymmetry() -> None:
    """Verifies that default randomized traffic has non-uniform distribution across approaches."""
    network = RoadNetwork()
    network.setup_default_intersection(200.0, 3.5, 2)

    config = {
        "simulation": {"timeStep": 0.1, "randomSeed": 777},
        "traffic": {"arrivalRate": 1.0, "totalVehicles": 20},
    }
    spawner = VehicleSpawner(config, network)

    # Weights across directions should not be identical 0.25 everywhere
    splits = list(spawner.directional_split.values())
    assert not all(s == 0.25 for s in splits)
    # Total sum of directional splits should still equal 1.0
    assert pytest.approx(sum(splits), rel=1e-3) == 1.0


