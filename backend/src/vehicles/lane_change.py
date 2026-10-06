"""Lane changing (V1.2): MOBIL decisions executed as gradual manoeuvres.

Decision — MOBIL (Kesting, Treiber & Helbing, 2007, "General lane-changing
model MOBIL for car-following models"), evaluated with each vehicle's own IDM
parameters, so a bus judges and is judged by bus dynamics:

* **Safety**: after the change, the new follower must not have to brake
  harder than ``safeDeceleration`` (b_safe), nor must the changing vehicle
  itself; both bumper-to-bumper gaps must be at least ``MIN_ACCEPTED_GAP``.
* **Incentive** (discretionary changes): the changing vehicle's acceleration
  gain plus ``politeness`` times the gain of the two affected followers (the
  new one and the old one) must exceed ``accelerationThreshold``.
* **Lane use**: a vehicle only ever moves into a lane its movement is
  permitted from (RoadNetwork.permitted_turns). A vehicle that is in a lane
  its movement is *not* permitted from must change (a mandatory change): the
  incentive test is waived but safety never is. If it reaches the point
  where a change can no longer be completed before the stop line, it takes a
  movement its lane does permit instead (a missed turn) — it never cuts in
  unsafely and never stops dead on the approach waiting for a gap.

Execution — :meth:`Vehicle.begin_lane_change`: the lateral move is spread
over ``max(laneChangeMinDistance, speed x laneChangeDuration)`` metres of
travel and only begun when that much lane remains, so it always completes
before the junction. While it is in progress the vehicle occupies both lanes.

Only incoming approach lanes are eligible: inside the junction and on the
roundabout ring vehicles keep to their path.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, FrozenSet, List, Mapping, Optional, Sequence, Tuple

from src.core.enums import Direction, TurnIntent
from src.roads.lane import Lane
from src.vehicles.idm import IntelligentDriverModel
from src.vehicles.vehicle import Vehicle
from src.vehicles.vehicle_types import (
    DEFAULT_LANE_CHANGE_DURATION,
    DEFAULT_LANE_CHANGE_MIN_DISTANCE,
    DEFAULT_POLITENESS,
)

logger = logging.getLogger(__name__)

# Smallest bumper-to-bumper gap (m), ahead and behind, a vehicle will merge
# into. The IDM safety test is what normally decides; this only rules out a
# merge into a gap that is physically closed.
MIN_ACCEPTED_GAP: float = 1.0

# Lane that must remain beyond the end of the manoeuvre (m), so a change is
# never still in progress as the vehicle reaches the stop line.
END_MARGIN: float = 10.0

# Minimum time between the starts of two changes by one vehicle (s). The
# value V1.0's lane change used.
COOLDOWN: float = 3.0

_TURN_PREFERENCE: Tuple[TurnIntent, ...] = (
    TurnIntent.STRAIGHT,
    TurnIntent.RIGHT,
    TurnIntent.LEFT,
)

# Incoming-lane id prefix -> approach Direction, for lanes that carry no
# explicit ``approach`` (hand-built lanes in tests).
_PREFIX_DIRECTIONS = {
    "n_in_": Direction.NORTH,
    "s_in_": Direction.SOUTH,
    "e_in_": Direction.EAST,
    "w_in_": Direction.WEST,
}


@dataclass(frozen=True)
class LaneChangeSettings:
    """``roads.laneChange`` — scenario-wide lane-changing settings."""

    enabled: bool = True
    acceleration_threshold: float = 0.2
    safe_deceleration: float = 4.0
    # When set, overrides every vehicle class's own politeness factor.
    politeness: Optional[float] = None


def resolve_lane_change_settings(config: Mapping[str, Any]) -> LaneChangeSettings:
    roads = config.get("roads") or {}
    section = roads.get("laneChange") if isinstance(roads, Mapping) else None
    if not isinstance(section, Mapping):
        return LaneChangeSettings()
    defaults = LaneChangeSettings()
    politeness = section.get("politeness")
    return LaneChangeSettings(
        enabled=bool(section.get("enabled", defaults.enabled)),
        acceleration_threshold=float(
            section.get("accelerationThreshold", defaults.acceleration_threshold)
        ),
        safe_deceleration=float(
            section.get("safeDeceleration", defaults.safe_deceleration)
        ),
        politeness=float(politeness) if politeness is not None else None,
    )


def incoming_direction(lane: Lane) -> Optional[Direction]:
    """Approach an incoming lane belongs to, or None if it is not one."""
    role = getattr(lane, "role", "")
    approach = getattr(lane, "approach", None)
    if role == "incoming" and isinstance(approach, Direction):
        return approach
    if role:
        return None
    lid = lane.lane_id.lower()
    for prefix, direction in _PREFIX_DIRECTIONS.items():
        if lid.startswith(prefix):
            return direction
    return None


class _Neighbour:
    """A vehicle (or stop-line obstacle) as seen from one lane."""

    __slots__ = ("vehicle", "position", "speed", "length")

    def __init__(
        self, vehicle: Optional[Vehicle], position: float, speed: float, length: float
    ) -> None:
        self.vehicle = vehicle
        self.position = position
        self.speed = speed
        self.length = length


class LaneChangeModel:
    """Decides and starts lane changes for one simulation."""

    def __init__(
        self, settings: LaneChangeSettings, default_idm: IntelligentDriverModel
    ) -> None:
        self.settings = settings
        self.default_idm = default_idm
        self.changes_started: int = 0
        self.missed_turns: int = 0

    def reset(self) -> None:
        self.changes_started = 0
        self.missed_turns = 0

    # -- per-vehicle parameters ------------------------------------------

    def _idm(self, vehicle: Vehicle) -> IntelligentDriverModel:
        params = vehicle.params
        return params.idm if params is not None else self.default_idm

    def _politeness(self, vehicle: Vehicle) -> float:
        if self.settings.politeness is not None:
            return self.settings.politeness
        params = vehicle.params
        return params.profile.politeness if params is not None else DEFAULT_POLITENESS

    @staticmethod
    def manoeuvre_distance(vehicle: Vehicle) -> float:
        params = vehicle.params
        if params is not None:
            duration = params.profile.lane_change_duration
            minimum = params.profile.lane_change_min_distance
        else:
            duration = DEFAULT_LANE_CHANGE_DURATION
            minimum = DEFAULT_LANE_CHANGE_MIN_DISTANCE
        return max(minimum, vehicle.speed * duration)

    # -- lane neighbourhood ----------------------------------------------

    @staticmethod
    def _neighbours(
        lane: Lane, subject: Vehicle, include_obstacle: bool = True
    ) -> Tuple[Optional[_Neighbour], Optional[_Neighbour]]:
        """Nearest leader and follower of *subject*'s position on *lane*.

        Vehicles straddling *lane* mid-manoeuvre are registered on it and so
        are included. A stop-line obstacle counts as a stationary leader.
        """
        leader: Optional[_Neighbour] = None
        follower: Optional[_Neighbour] = None
        pos = subject.position
        for v in lane.get_vehicles():
            if v is subject:
                continue
            if v.position >= pos:
                if leader is None or v.position < leader.position:
                    leader = _Neighbour(v, v.position, v.speed, v.length)
            elif follower is None or v.position > follower.position:
                follower = _Neighbour(v, v.position, v.speed, v.length)
        obstacle = getattr(lane, "virtual_obstacle", None) if include_obstacle else None
        if obstacle is not None and obstacle.position > pos:
            if leader is None or obstacle.position < leader.position:
                leader = _Neighbour(
                    None, obstacle.position, obstacle.speed, obstacle.length
                )
        return leader, follower

    def _acc(
        self,
        vehicle: Vehicle,
        position: float,
        leader: Optional[_Neighbour],
    ) -> float:
        """IDM acceleration of *vehicle* (placed at *position*) behind *leader*."""
        idm = self._idm(vehicle)
        desired = max(0.1, vehicle.desired_speed)
        if leader is None:
            return idm.calculate_acceleration(vehicle.speed, desired)
        gap = leader.position - position - (leader.length + vehicle.length) / 2.0
        return idm.calculate_acceleration(vehicle.speed, desired, leader.speed, gap)

    @staticmethod
    def _gap(front: _Neighbour, back_position: float, back_length: float) -> float:
        return front.position - back_position - (front.length + back_length) / 2.0

    # -- decision ----------------------------------------------------------

    def attempt(
        self,
        vehicle: Vehicle,
        network: Any,
        current_time: float,
        last_change_time: float,
    ) -> bool:
        """Consider a lane change for *vehicle* this tick; True if one began.

        May instead re-route a vehicle that can no longer reach a lane its
        movement is permitted from (a missed turn).
        """
        lane = vehicle.lane
        if (
            not self.settings.enabled
            or lane is None
            or vehicle.lane_change is not None
            or not vehicle.route
            or vehicle.route[0] is not lane
        ):
            return False
        direction = incoming_direction(lane)
        if direction is None:
            return False
        lanes: Sequence[Lane] = network.get_incoming_approach(direction).get_lanes()
        n_lanes = len(lanes)
        if n_lanes <= 1:
            return False
        idx = list(lanes).index(lane)

        turn = vehicle.turn_intent or TurnIntent.STRAIGHT
        permitted = [network.permitted_turns(direction, i) for i in range(n_lanes)]
        mandatory = turn not in permitted[idx]

        remaining = lane.length - vehicle.position
        distance = self.manoeuvre_distance(vehicle)
        if remaining < distance + END_MARGIN:
            if mandatory:
                self._miss_turn(vehicle, network, direction, idx, permitted[idx])
            return False
        if current_time - last_change_time < COOLDOWN:
            return False

        if mandatory:
            allowed = [i for i in range(n_lanes) if turn in permitted[i]]
            if not allowed:
                return False
            nearest = min(allowed, key=lambda i: (abs(i - idx), i))
            candidates = [idx + (1 if nearest > idx else -1)]
        else:
            candidates = [
                i
                for i in (idx - 1, idx + 1)
                if 0 <= i < n_lanes and turn in permitted[i]
            ]
        if not candidates:
            return False

        cur_leader, cur_follower = self._neighbours(lane, vehicle)
        a_self = self._acc(vehicle, vehicle.position, cur_leader)
        # Old follower: its acceleration now, and once we have left (it then
        # follows our current leader instead).
        old_gain = 0.0
        if cur_follower is not None and cur_follower.vehicle is not None:
            f = cur_follower.vehicle
            me = _Neighbour(vehicle, vehicle.position, vehicle.speed, vehicle.length)
            old_gain = self._acc(f, f.position, cur_leader) - self._acc(
                f, f.position, me
            )

        b_safe = self.settings.safe_deceleration
        best: Optional[Tuple[float, int]] = None
        for target_idx in candidates:
            target = lanes[target_idx]
            new_leader, new_follower = self._neighbours(target, vehicle)

            # Physical room, ahead and behind.
            if new_leader is not None and new_leader.vehicle is not None:
                if (
                    self._gap(new_leader, vehicle.position, vehicle.length)
                    < MIN_ACCEPTED_GAP
                ):
                    continue
            if new_follower is not None:
                me = _Neighbour(
                    vehicle, vehicle.position, vehicle.speed, vehicle.length
                )
                if self._gap(me, new_follower.position, new_follower.length) < (
                    MIN_ACCEPTED_GAP
                ):
                    continue

            # Safety criterion.
            a_self_new = self._acc(vehicle, vehicle.position, new_leader)
            if a_self_new < -b_safe:
                continue
            new_gain = 0.0
            if new_follower is not None and new_follower.vehicle is not None:
                f = new_follower.vehicle
                me = _Neighbour(
                    vehicle, vehicle.position, vehicle.speed, vehicle.length
                )
                a_f_new = self._acc(f, f.position, me)
                if a_f_new < -b_safe:
                    continue
                new_gain = a_f_new - self._acc(f, f.position, new_leader)

            incentive = (a_self_new - a_self) + self._politeness(vehicle) * (
                new_gain + old_gain
            )
            if not mandatory and incentive <= self.settings.acceleration_threshold:
                continue
            if best is None or incentive > best[0]:
                best = (incentive, target_idx)

        if best is None:
            return False
        target_idx = best[1]
        new_route = network.generate_route(direction, target_idx, turn)
        vehicle.begin_lane_change(lanes[target_idx], new_route, distance)
        self.changes_started += 1
        return True

    def _miss_turn(
        self,
        vehicle: Vehicle,
        network: Any,
        direction: Direction,
        idx: int,
        allowed: FrozenSet[TurnIntent],
    ) -> None:
        """Too late to reach a permitted lane: take a movement this lane allows."""
        new_turn = next(t for t in _TURN_PREFERENCE if t in allowed)
        logger.debug(
            "Vehicle %s missed its %s turn from %s lane %d; continuing %s",
            vehicle.vehicle_id,
            vehicle.turn_intent,
            direction.value,
            idx,
            new_turn.value,
        )
        vehicle.turn_intent = new_turn
        vehicle.route = network.generate_route(direction, idx, new_turn)
        self.missed_turns += 1


def origin_lane_leader(vehicle: Vehicle) -> Tuple[Optional[Vehicle], float]:
    """Nearest vehicle ahead on the lane a manoeuvring vehicle is leaving.

    During a lane change the vehicle still overlaps its origin lane, so it
    must keep its distance to what is ahead there too, not only in the lane
    it is moving into (which find_leader covers).
    """
    maneuver = vehicle.lane_change
    if maneuver is None:
        return None, float("inf")
    best: Optional[Vehicle] = None
    best_gap = float("inf")
    for v in maneuver.origin_lane.get_vehicles():
        if v is vehicle or v.position <= vehicle.position:
            continue
        gap = max(0.0, v.position - vehicle.position - (v.length + vehicle.length) / 2)
        if gap < best_gap:
            best, best_gap = v, gap
    return best, best_gap


def lane_index_of(vehicle: Vehicle) -> Optional[int]:
    """Index of the vehicle's current lane across its approach, if known."""
    lane = vehicle.lane
    return getattr(lane, "index", None) if lane is not None else None


__all__: List[str] = [
    "COOLDOWN",
    "END_MARGIN",
    "LaneChangeModel",
    "LaneChangeSettings",
    "MIN_ACCEPTED_GAP",
    "incoming_direction",
    "lane_index_of",
    "origin_lane_leader",
    "resolve_lane_change_settings",
]
