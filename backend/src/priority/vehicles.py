"""Emergency vehicle model and injection of scheduled vehicles into a run.

The existing spawner draws background traffic from a random stream and is not
touched. Emergency and transit vehicles are instead *injected* by the priority
controller on a fixed schedule, with no random draws, so adding them never
shifts the background arrivals of a seed.

An emergency vehicle is an ordinary :class:`~src.vehicles.vehicle.Vehicle` with
its own class profile (a higher desired speed, stronger acceleration and
braking, a shorter headway), so the engine's car-following, curve-speed and
conflict logic apply to it unchanged. What makes it an emergency vehicle is the
``priority`` flag and the behaviour other components give it (pre-emption,
yielding).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from src.core.enums import Direction, TurnIntent
from src.roads.lane import Lane
from src.roads.network import RoadNetwork
from src.vehicles.vehicle import Vehicle
from src.vehicles.vehicle_types import (
    DEFAULT_PROFILES,
    VehicleParams,
    VehicleTypeProfile,
)

# Vehicle lengths stay within the 7 m the junction geometry is sized for
# (see engine/vehicle_pool.py): a longer vehicle needs a mixed-population
# junction layout this package does not alter.
MAX_INJECTED_LENGTH: float = 7.0


@dataclass(frozen=True)
class EmergencyKind:
    """Parameters of one emergency vehicle class. Model inputs, not findings."""

    kind_id: str
    label: str
    length: float
    width: float
    #: Desired speed as a multiple of the road's speed limit.
    speed_factor: float
    max_acceleration: float
    comfort_deceleration: float
    desired_time_headway: float
    minimum_gap: float
    max_lateral_acceleration: float

    def profile(self) -> VehicleTypeProfile:
        base = DEFAULT_PROFILES["car"]
        return VehicleTypeProfile(
            type_id=self.kind_id,
            label=self.label,
            length=(self.length, self.length),
            width=(self.width, self.width),
            desired_speed_factor=(self.speed_factor, self.speed_factor),
            max_acceleration=self.max_acceleration,
            comfort_deceleration=self.comfort_deceleration,
            desired_time_headway=self.desired_time_headway,
            minimum_gap=self.minimum_gap,
            idm_delta=base.idm_delta,
            max_lateral_acceleration=self.max_lateral_acceleration,
            lane_change_duration=base.lane_change_duration,
            lane_change_min_distance=base.lane_change_min_distance,
            politeness=0.0,
        )

    def params(self, speed_limit: float) -> VehicleParams:
        desired = speed_limit * self.speed_factor
        return VehicleParams(self.profile(), (desired, desired))

    def describe(self) -> Dict[str, object]:
        return {
            "id": self.kind_id,
            "label": self.label,
            "length": self.length,
            "width": self.width,
            "speedFactor": self.speed_factor,
            "maxAcceleration": self.max_acceleration,
            "comfortDeceleration": self.comfort_deceleration,
            "desiredTimeHeadway": self.desired_time_headway,
            "minimumGap": self.minimum_gap,
            "maxLateralAcceleration": self.max_lateral_acceleration,
            "priority": True,
        }


EMERGENCY_KINDS: Dict[str, EmergencyKind] = {
    "ambulance": EmergencyKind(
        kind_id="ambulance",
        label="Ambulance",
        length=5.5,
        width=2.1,
        speed_factor=1.4,
        max_acceleration=3.0,
        comfort_deceleration=4.0,
        desired_time_headway=1.0,
        minimum_gap=1.5,
        max_lateral_acceleration=4.0,
    ),
    "fire_truck": EmergencyKind(
        kind_id="fire_truck",
        label="Fire truck",
        length=7.0,
        width=2.5,
        speed_factor=1.2,
        max_acceleration=1.6,
        comfort_deceleration=3.0,
        desired_time_headway=1.2,
        minimum_gap=2.5,
        max_lateral_acceleration=2.8,
    ),
}


class EmergencyVehicle(Vehicle):
    """A vehicle with right of way. ``priority`` is what other components read."""

    priority: bool = True

    def __init__(
        self,
        base: "VehicleBase",
        kind: str,
        approach: str,
        turn_name: str,
        scheduled_time: float,
    ) -> None:
        super().__init__(**base.as_kwargs())
        self.kind = kind
        self.approach = approach
        self.turn_name = turn_name
        self.scheduled_time = scheduled_time
        # Set by the controller as the vehicle is observed.
        self.stop_line_time: Optional[float] = None
        self.free_flow_time: float = 0.0


class TransitVehicle(Vehicle):
    """A scheduled bus. Dwell state is driven by ``transit.TransitStops``."""

    priority: bool = False

    def __init__(
        self,
        base: "VehicleBase",
        line_id: str,
        trip_index: int,
        approach: str,
        turn_name: str,
        dwell_s: float,
        stop_position: float,
    ) -> None:
        super().__init__(**base.as_kwargs())
        self.line_id = line_id
        self.trip_index = trip_index
        self.approach = approach
        self.turn_name = turn_name
        self.dwell_s = dwell_s
        self.stop_position = stop_position
        # "approach" -> "dwelling" -> "done"
        self.dwell_state = "approach"
        self.dwell_started: float = 0.0
        self.dwell_total: float = 0.0
        self.hold_position: float = stop_position
        self.stop_line_time: Optional[float] = None
        # Time of day the timetable expects the bus at its stop line.
        self.planned_arrival: float = 0.0
        self.free_flow_to_stop: float = 0.0
        self.priority_extension_s: float = 0.0
        self.priority_early_green: bool = False


@dataclass(frozen=True)
class VehicleBase:
    """The constructor arguments every injected vehicle shares."""

    vehicle_id: str
    length: float
    width: float
    desired_speed: float
    route: List[Lane]
    start_position: float
    initial_speed: float
    turn_intent: TurnIntent
    spawn_time: float
    wait_speed_threshold: float
    params: VehicleParams

    def as_kwargs(self) -> Dict[str, Any]:
        return {
            "vehicle_id": self.vehicle_id,
            "length": self.length,
            "width": self.width,
            "desired_speed": self.desired_speed,
            "route": self.route,
            "start_position": self.start_position,
            "initial_speed": self.initial_speed,
            "turn_intent": self.turn_intent,
            "spawn_time": self.spawn_time,
            "wait_speed_threshold": self.wait_speed_threshold,
            "params": self.params,
        }


# Incoming-lane id prefix per approach (RoadNetwork's naming).
LANE_PREFIX: Dict[str, str] = {
    "north": "n_in_",
    "south": "s_in_",
    "east": "e_in_",
    "west": "w_in_",
}


def lane_preferred_index(lane_count: int, turn: str) -> int:
    """The lane a turn uses under the network's default lane policy."""
    if lane_count <= 1:
        return 0
    if lane_count == 2:
        return 0 if turn == "left" else 1
    if turn == "left":
        return 0
    if turn == "right":
        return lane_count - 1
    return lane_count // 2


def candidate_lanes(
    network: RoadNetwork, direction: Direction, turn: str, requested: Optional[int]
) -> List[int]:
    """Entry lanes to try, best first; raises ValueError if none permits the turn."""
    lanes = network.get_incoming_approach(direction).get_lanes()
    n = len(lanes)
    intent = TurnIntent(turn)
    permitted = [i for i in range(n) if intent in network.permitted_turns(direction, i)]
    if requested is not None:
        if requested >= n:
            raise ValueError(
                f"lane {requested} does not exist on the {direction.value} approach"
            )
        if requested not in permitted:
            raise ValueError(f"lane {requested} does not permit a {turn} turn")
        return [requested]
    if not permitted:
        raise ValueError(f"no {direction.value} lane permits a {turn} turn")
    preferred = lane_preferred_index(n, turn)
    if preferred not in permitted:
        preferred = min(permitted, key=lambda i: (abs(i - preferred), i))
    return [preferred] + [i for i in permitted if i != preferred]


def find_entry(
    network: RoadNetwork,
    direction: Direction,
    turn: str,
    requested: Optional[int],
    length: float,
    minimum_gap: float,
    comfort_deceleration: float,
    desired_speed: float,
) -> Optional[Tuple[int, float]]:
    """(lane index, initial speed) of a free entry for a vehicle, or None.

    The same clearance rule and safe-insertion speed the background spawner
    uses (``VehicleSpawner._attempt_spawn``): the vehicle's tail must clear the
    one ahead by the minimum gap, and it enters no faster than it could stop.
    """
    lanes = network.get_incoming_approach(direction).get_lanes()
    for idx in candidate_lanes(network, direction, turn, requested):
        vehicles = lanes[idx].get_vehicles()
        if not vehicles:
            return idx, desired_speed
        preceding = min(vehicles, key=lambda v: v.position)
        tail_gap = preceding.position - preceding.length / 2.0
        if tail_gap >= minimum_gap + length:
            usable = max(0.0, tail_gap - length - minimum_gap)
            safe = math.sqrt(
                preceding.speed * preceding.speed + 2.0 * comfort_deceleration * usable
            )
            return idx, min(desired_speed, safe)
    return None


def route_free_flow_time(vehicle: Vehicle) -> float:
    """Seconds to drive the vehicle's whole route at its desired speed, from its
    start position (a lower bound: curves and acceleration add to it)."""
    total = sum(lane.length for lane in vehicle.route) - vehicle.length / 2.0
    return max(0.0, total) / vehicle.desired_speed


def distance_driven(vehicle: Vehicle) -> float:
    """Metres driven along the route since the vehicle was placed (placement
    is at ``length / 2`` on the first lane, as the spawner does)."""
    route = vehicle.route
    if vehicle.lane is None:
        return max(0.0, sum(lane.length for lane in route) - vehicle.length / 2.0)
    done = 0.0
    for lane in route:
        if lane is vehicle.lane:
            return max(0.0, done + vehicle.position - vehicle.length / 2.0)
        done += lane.length
    return max(0.0, done - vehicle.length / 2.0)
