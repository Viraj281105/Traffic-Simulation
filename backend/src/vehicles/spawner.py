import math
import random
from typing import Any, Dict, List, Optional

from src.core.enums import Direction, TurnIntent
from src.roads.lane import Lane
from src.roads.network import RoadNetwork
from src.vehicles.vehicle import Vehicle


class VehicleSpawner:
    """Spawns vehicles onto the road network using arrival processes (Poisson or Uniform)."""

    def __init__(self, config: Dict[str, Any], network: RoadNetwork) -> None:
        self.config: Dict[str, Any] = config
        self.network: RoadNetwork = network

        traffic_cfg = config.get("traffic", {})
        sim_cfg = config.get("simulation", {})
        veh_gen_cfg = config.get("vehicleGeneration", {})

        self.random_seed: int = sim_cfg.get("randomSeed", 42)
        self.rng: random.Random = random.Random(self.random_seed)

        self.total_vehicles_limit: int = traffic_cfg.get("totalVehicles", 200)
        self.arrival_rate: float = traffic_cfg.get("arrivalRate", 0.5)
        self.arrival_distribution: str = traffic_cfg.get(
            "arrivalDistribution", "poisson"
        )

        self.directional_split: Dict[str, float] = traffic_cfg.get(
            "directionalSplit",
            {"north": 0.25, "south": 0.25, "east": 0.25, "west": 0.25},
        )

        self.turn_probabilities: Dict[str, float] = traffic_cfg.get(
            "turnProbabilities", {"left": 0.2, "straight": 0.6, "right": 0.2}
        )

        # Vehicle physical parameter bounds
        self.len_min: float = veh_gen_cfg.get("vehicleLength", {}).get("min", 4.0)
        self.len_max: float = veh_gen_cfg.get("vehicleLength", {}).get("max", 5.0)
        self.width_min: float = veh_gen_cfg.get("vehicleWidth", {}).get("min", 1.8)
        self.width_max: float = veh_gen_cfg.get("vehicleWidth", {}).get("max", 2.2)
        self.speed_min: float = veh_gen_cfg.get("desiredSpeed", {}).get("min", 11.0)
        self.speed_max: float = veh_gen_cfg.get("desiredSpeed", {}).get("max", 15.0)

        # Safety distance
        self.minimum_gap: float = veh_gen_cfg.get("minimumGap", 2.0)

        # Vehicles spawned count
        self.spawned_count: int = 0

        # Spawn timers for each direction
        self.timers: Dict[Direction, float] = {}
        self.reset()

    def reset(self) -> None:
        self.rng = random.Random(self.random_seed)
        self.spawned_count = 0
        self.timers.clear()
        for d in Direction:
            self.timers[d] = self._generate_next_arrival_time(d)

    def _generate_next_arrival_time(self, direction: Direction) -> float:
        split = self.directional_split.get(direction.value, 0.25)
        dir_rate = self.arrival_rate * split
        if dir_rate <= 0:
            return float("inf")

        if self.arrival_distribution == "poisson":
            u = self.rng.random()
            # Prevent log(0)
            u = max(1e-9, u)
            return -math.log(u) / dir_rate
        if self.arrival_distribution == "uniform":
            return 1.0 / dir_rate
        if self.arrival_distribution == "burst":
            raise NotImplementedError(
                "arrivalDistribution='burst' is not implemented in VehicleSpawner"
            )
        raise ValueError(
            f"Unsupported arrivalDistribution: {self.arrival_distribution!r}"
        )

    def step(self, dt: float) -> List[Vehicle]:
        """Ticks spawner and returns a list of newly spawned vehicles."""
        new_vehicles: List[Vehicle] = []

        # Check total vehicle limit
        if self.spawned_count >= self.total_vehicles_limit:
            return new_vehicles

        for d in Direction:
            if self.timers[d] != float("inf"):
                self.timers[d] -= dt
                if self.timers[d] <= 0:
                    # Attempt spawning
                    vehicle = self._attempt_spawn(d)
                    if vehicle is not None:
                        new_vehicles.append(vehicle)
                        self.spawned_count += 1
                        self.timers[d] = self._generate_next_arrival_time(d)
                        if self.spawned_count >= self.total_vehicles_limit:
                            break
                    else:
                        # If blocked, try again next tick
                        self.timers[d] = 0.0

        return new_vehicles

    def _attempt_spawn(self, direction: Direction) -> Optional[Vehicle]:
        incoming_approach = self.network.get_incoming_approach(direction)
        lanes = incoming_approach.get_lanes()
        if not lanes:
            return None

        # Choose lane with the largest spacing from the entrance (first vehicle is furthest down the lane)
        # Or choose randomly/sequentially. To prevent blockages, let's select a lane that has enough space.
        # Let's check which lane has the best space at the entrance.
        available_lanes: List[Lane] = []
        for lane in lanes:
            vehicles = lane.get_vehicles()
            if not vehicles:
                available_lanes.append(lane)
            else:
                # Find vehicle with the minimum position in the lane
                preceding = min(vehicles, key=lambda v: v.position)
                # Tail of preceding vehicle: preceding.position - preceding.length / 2
                # We need it to be >= minimum_gap + new_vehicle_length
                # Let's assume max length for check
                if (
                    preceding.position - preceding.length / 2.0
                    >= self.minimum_gap + self.len_max
                ):
                    available_lanes.append(lane)

        if not available_lanes:
            return None

        # Pick one lane from the available ones
        lane = self.rng.choice(available_lanes)
        lane_idx = lanes.index(lane)

        # Generate vehicle parameters
        v_len = self.rng.uniform(self.len_min, self.len_max)
        v_width = self.rng.uniform(self.width_min, self.width_max)
        v_desired_speed = self.rng.uniform(self.speed_min, self.speed_max)

        # Decide Turn Intent based on turn probabilities
        turns = [TurnIntent.LEFT, TurnIntent.STRAIGHT, TurnIntent.RIGHT]
        weights = [
            self.turn_probabilities.get("left", 0.2),
            self.turn_probabilities.get("straight", 0.6),
            self.turn_probabilities.get("right", 0.2),
        ]
        turn = self.rng.choices(turns, weights=weights)[0]

        # Generate Route
        route = self.network.generate_route(direction, lane_idx, turn)

        # Create Vehicle
        vehicle_id = f"veh_{self.spawned_count}"

        # Vehicle starts at position L/2 so that its rear bumper is at 0.0
        start_pos = v_len / 2.0

        vehicle = Vehicle(
            vehicle_id=vehicle_id,
            length=v_len,
            width=v_width,
            desired_speed=v_desired_speed,
            route=route,
            start_position=start_pos,
            initial_speed=v_desired_speed,  # starts moving at free-flow speed
        )

        return vehicle
