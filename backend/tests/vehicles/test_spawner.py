import pytest

from src.core.enums import Direction, TurnIntent
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
            "boundingRadius": 15.0,
        },
        "vehicleGeneration": {"arrivalRate": 0.5, "seed": 42},
    }
    spawner = VehicleSpawner(config, network)
    assert spawner.arrival_rate == 0.5
    assert spawner.spawned_count == 0


def test_vehicle_spawner_distributions_and_errors() -> None:
    network = RoadNetwork()
    network.setup_default_intersection(200.0, 3.5, 2)

    # 1. Zero directional split
    cfg_zero = {
        "traffic": {
            "arrivalRate": 0.5,
            "directionalSplit": {"north": 0.0, "south": 0.0, "east": 0.0, "west": 0.0},
        },
    }
    sp_zero = VehicleSpawner(cfg_zero, network)
    assert sp_zero._generate_next_arrival_time(Direction.NORTH) == float("inf")

    # 2. Uniform distribution
    cfg_uni = {
        "traffic": {
            "arrivalRate": 0.5,
            "arrivalDistribution": "uniform",
            "directionalSplit": {"north": 1.0},
        },
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
    lanes_3 = [
        Lane("l0", 0, 0, 10, 0),
        Lane("l1", 0, 0, 10, 0),
        Lane("l2", 0, 0, 10, 0),
    ]

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


def _single_lane_spawner() -> tuple[VehicleSpawner, RoadNetwork]:
    network = RoadNetwork()
    network.setup_default_intersection(200.0, 3.5, 1)
    config = {
        "simulation": {"randomSeed": 7},
        "traffic": {
            "arrivalRate": 0.5,
            "directionalSplit": {"north": 1.0, "south": 0.0, "east": 0.0, "west": 0.0},
            "turnProbabilities": {"left": 0.0, "straight": 1.0, "right": 0.0},
        },
    }
    return VehicleSpawner(config, network), network


def test_spawn_behind_stopped_vehicle_enters_slowly_enough_to_stop() -> None:
    """Regression: a vehicle inserted a few metres behind a stopped queue tail
    used to enter at its full desired speed (18-25 m/s), could not stop even at
    the IDM's hard braking limit, and drove through the vehicle ahead."""
    from src.vehicles.vehicle import Vehicle

    spawner, network = _single_lane_spawner()
    lane = network.get_incoming_approach(Direction.NORTH).get_lanes()[0]
    route = network.generate_route(Direction.NORTH, 0, TurnIntent.STRAIGHT)
    # Queue tail just far enough back for the entry to be "unblocked".
    tail = Vehicle("tail", 4.5, 2.0, 20.0, route, start_position=12.0)
    tail.speed = 0.0

    new = spawner._attempt_spawn(Direction.NORTH)
    assert new is not None
    gap = tail.position - tail.length / 2.0 - (new.position + new.length / 2.0)
    # Braking comfortably (3 m/s^2) it must stop with minimumGap to spare.
    stopping_distance = new.speed**2 / (2.0 * 3.0)
    assert stopping_distance <= gap - spawner.minimum_gap + 1e-9
    assert new.speed < new.desired_speed
    lane.remove_vehicle(tail)
    lane.remove_vehicle(new)


def test_spawn_on_empty_lane_still_enters_at_desired_speed() -> None:
    spawner, _ = _single_lane_spawner()
    new = spawner._attempt_spawn(Direction.NORTH)
    assert new is not None
    assert new.speed == new.desired_speed


def test_saturated_entry_never_produces_same_lane_overlap() -> None:
    """End to end: at a demand high enough for queues to reach the entry, no
    two vehicles on one lane may ever overlap (the collision audit skips
    same-lane pairs, so this would otherwise go unreported)."""
    from src.controllers.factory import create_controller
    from src.core.clock import Clock
    from src.core.engine import SimulationEngine

    config = {
        "simulation": {"duration": 40, "timeStep": 0.1, "randomSeed": 2},
        "geometry": {"intersectionType": "fixed_time_signal"},
        "roads": {"lanesPerApproach": 1},
        "traffic": {"arrivalRate": 1.2, "totalVehicles": 100000},
    }
    clock = Clock(time_step=0.1)
    engine = SimulationEngine(clock, duration=40, config=config)
    engine.controller = create_controller(config, engine.network)
    while engine.status.value.lower() != "completed":
        engine.step()
        by_lane: dict[str, list] = {}
        for v in engine.pool.active_vehicles:
            if v.lane is not None:
                by_lane.setdefault(v.lane.lane_id, []).append(v)
        for vehicles in by_lane.values():
            vehicles.sort(key=lambda v: v.position)
            for a, b in zip(vehicles, vehicles[1:]):
                gap = b.position - a.position - (a.length + b.length) / 2.0
                assert gap > -0.05, (
                    clock.get_elapsed_time(),
                    a.vehicle_id,
                    b.vehicle_id,
                    gap,
                )


def test_blocked_arrival_keeps_its_turn_intent_until_placed() -> None:
    """Regression: a blocked arrival used to re-draw its turn intent on every
    retry, so a left-turner confined to a full left lane was re-rolled into a
    straight-mover and admitted, distorting the configured turning mix."""
    from src.vehicles.vehicle import Vehicle

    network = RoadNetwork()
    network.setup_default_intersection(200.0, 3.5, 2)
    config = {
        "simulation": {"randomSeed": 3},
        "traffic": {
            "arrivalRate": 0.5,
            "turnProbabilities": {"left": 0.5, "straight": 0.5, "right": 0.0},
        },
    }
    spawner = VehicleSpawner(config, network)
    left_lane = network.get_incoming_approach(Direction.NORTH).get_lanes()[0]
    route = network.generate_route(Direction.NORTH, 0, TurnIntent.LEFT)
    blocker = Vehicle("blocker", 4.5, 2.0, 20.0, route, start_position=3.0)
    blocker.speed = 0.0

    # Draw arrivals until one is a (blocked) left-turner.
    for _ in range(50):
        placed = spawner._attempt_spawn(Direction.NORTH)
        if placed is None:
            break
        placed.lane.remove_vehicle(placed)
    else:
        pytest.fail("never drew a left-turner")

    # While its lane stays blocked, retries must keep failing — never
    # admitting a re-rolled straight-mover in its place.
    for _ in range(200):
        assert spawner._attempt_spawn(Direction.NORTH) is None

    left_lane.remove_vehicle(blocker)
    placed = spawner._attempt_spawn(Direction.NORTH)
    assert placed is not None and placed.turn_intent == TurnIntent.LEFT
