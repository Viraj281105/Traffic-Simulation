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
