import math
from typing import TYPE_CHECKING, List, Optional, Tuple

from src.core.enums import TurnIntent, VehicleState
from src.roads.lane import Lane
from src.vehicles.body import LONG_VEHICLE_THRESHOLD, body_pose

if TYPE_CHECKING:
    from src.vehicles.vehicle_types import VehicleParams

# Class of a vehicle built without a profile (the V1.0 passenger car).
LEGACY_VEHICLE_TYPE: str = "car"
# Comfortable deceleration assumed for a vehicle with no profile; the value
# router.commits_through_yellow has always used for the dilemma zone.
LEGACY_COMFORT_DECELERATION: float = 3.0


class LaneChangeManeuver:
    """A lane change in progress: a gradual lateral move, never a jump.

    The vehicle's logical lane switches to the target lane the moment the
    manoeuvre starts (so it follows, and is followed in, the lane it is
    moving into), while it stays registered on the origin lane as well until
    the manoeuvre completes. Physically it straddles both, so followers in
    either lane must see it.

    Lateral progress is driven by *distance travelled*, not by time: a
    vehicle cannot move sideways without moving forward. The lateral offset
    from the target lane's centreline follows a smooth cosine profile over
    ``distance`` metres, so lateral speed and heading change continuously.
    Because the manoeuvre is only started when at least ``distance`` metres
    of lane remain (see vehicles/lane_change.py), it always completes before
    the vehicle can reach the end of the lane.
    """

    __slots__ = ("origin_lane", "start_position", "distance", "offset_x", "offset_y")

    def __init__(
        self,
        origin_lane: Lane,
        start_position: float,
        distance: float,
        offset: Tuple[float, float],
    ) -> None:
        if distance <= 0:
            raise ValueError("Lane-change distance must be positive")
        self.origin_lane = origin_lane
        self.start_position = start_position
        self.distance = distance
        # Origin-lane centreline minus target-lane centreline (constant for
        # the parallel lanes of one approach).
        self.offset_x, self.offset_y = offset

    def progress(self, position: float) -> float:
        travelled = position - self.start_position
        if travelled <= 0.0:
            return 0.0
        if travelled >= self.distance:
            return 1.0
        return travelled / self.distance

    def remaining_fraction(self, position: float) -> float:
        """Share of the original lateral offset still to cover (1 -> 0)."""
        t = self.progress(position)
        return 1.0 - (1.0 - math.cos(math.pi * t)) / 2.0

    def lateral_slope(self, position: float) -> float:
        """d(remaining_fraction)/d(position): how fast the offset shrinks."""
        t = self.progress(position)
        if t <= 0.0 or t >= 1.0:
            return 0.0
        return -(math.pi / 2.0) * math.sin(math.pi * t) / self.distance


class Vehicle:
    """Represents a single microscopic vehicle moving along a predefined route of lanes.

    Each vehicle carries its ``turn_intent`` so the conflict manager and signal
    controller can make priority / phase decisions.  Position is clamped during
    lane transitions to prevent overshoot artifacts.
    """

    def __init__(
        self,
        vehicle_id: str,
        length: float,
        width: float,
        desired_speed: float,
        route: List[Lane],
        start_position: float = 0.0,
        initial_speed: float = 0.0,
        turn_intent: Optional[TurnIntent] = None,
        spawn_time: float = 0.0,
        wait_speed_threshold: float = 0.5,
        params: Optional["VehicleParams"] = None,
    ) -> None:
        if not route:
            raise ValueError("Vehicle route cannot be empty")
        if length <= 0 or width <= 0:
            raise ValueError("Vehicle dimensions (length, width) must be positive")
        if desired_speed <= 0:
            raise ValueError("Desired speed must be positive")
        if initial_speed < 0:
            raise ValueError("Initial speed cannot be negative")

        self.vehicle_id: str = vehicle_id
        self.length: float = length
        self.width: float = width
        self.desired_speed: float = desired_speed
        self.route: List[Lane] = route
        # Per-class behaviour (vehicle_types.VehicleParams), shared by every
        # vehicle of the class. None for a legacy vehicle, which then uses the
        # engine-wide IDM and defaults exactly as in V1.0.
        self.params: Optional["VehicleParams"] = params
        # Lane change in progress (V1.2), or None.
        self.lane_change: Optional[LaneChangeManeuver] = None

        self.lane: Optional[Lane] = route[0]
        self.position: float = start_position
        self.speed: float = initial_speed
        self.acceleration: float = 0.0

        # Turn intent for priority arbitration & signal phase matching
        self.turn_intent: Optional[TurnIntent] = turn_intent

        # Timing metadata
        self.spawn_time: float = spawn_time
        self.exit_time: Optional[float] = None

        # Wait threshold speed — vehicles below this speed are considered
        # "waiting" for wait-time accounting. Matches the project-wide
        # configurable waitSpeedThreshold used by MetricCollector and the
        # queue_length/idle_loss metric definitions (default 0.5 m/s).
        self._wait_threshold: float = wait_speed_threshold

        # Register vehicle to the first lane
        self.lane.add_vehicle(self)

        # Tracking variables
        self.wait_time: float = 0.0
        if self.speed < self._wait_threshold:
            self.state: VehicleState = VehicleState.WAITING
            self.stop_count: int = 1
        else:
            self.state = VehicleState.APPROACHING
            self.stop_count = 0

        # Used by stop-count hysteresis in metrics/definitions/stop_count.py
        self._hysteresis_stopped: bool = self.speed < self._wait_threshold

    # Position and heading are pure functions of (lane, position) -- a lane's
    # geometry never changes -- yet every vehicle reads every other vehicle's
    # pose several times a tick while each pose changes only once. They are
    # memoised on exactly that key, so a changed lane or position (however it
    # was set) always recomputes.
    _pose_lane: Optional[Lane] = None
    _pose_position: float = math.nan
    _pose_coords: Tuple[float, float] = (0.0, 0.0)
    _heading_lane: Optional[Lane] = None
    _heading_position: float = math.nan
    _heading_value: float = 0.0
    # Same memo for a long vehicle's axle-chord body pose (vehicles/body.py),
    # which also depends on the route (the axles can be on adjacent lanes).
    _body_lane: Optional[Lane] = None
    _body_position: float = math.nan
    _body_route: Optional[List[Lane]] = None
    _body_value: Tuple[float, float, float] = (0.0, 0.0, 0.0)

    def _long_body_pose(self, lane: Lane) -> Tuple[float, float, float]:
        """Body pose of a vehicle longer than LONG_VEHICLE_THRESHOLD."""
        position = self.position
        if (
            lane is not self._body_lane
            or position != self._body_position
            or self.route is not self._body_route
        ):
            try:
                idx = self.route.index(lane)
            except ValueError:
                x, y = lane.get_point_at_distance(position)
                pose = (x, y, lane.get_heading_at_distance(position))
            else:
                pose = body_pose(self.route, idx, position, self.length)
            self._body_value = pose
            self._body_lane = lane
            self._body_position = position
            self._body_route = self.route
        return self._body_value

    @property
    def vehicle_type(self) -> str:
        return self.params.type_id if self.params is not None else LEGACY_VEHICLE_TYPE

    @property
    def comfort_deceleration(self) -> float:
        if self.params is not None:
            return self.params.comfort_deceleration
        return LEGACY_COMFORT_DECELERATION

    @property
    def coords(self) -> Tuple[float, float]:
        lane = self.lane
        if lane is None:
            return (0.0, 0.0)
        position = self.position
        maneuver = self.lane_change
        if self.length > LONG_VEHICLE_THRESHOLD or maneuver is not None:
            if self.length > LONG_VEHICLE_THRESHOLD:
                x, y, _ = self._long_body_pose(lane)
            else:
                x, y = lane.get_point_at_distance(position)
            if maneuver is None:
                return (x, y)
            f = maneuver.remaining_fraction(position)
            return (x + f * maneuver.offset_x, y + f * maneuver.offset_y)
        if lane is not self._pose_lane or position != self._pose_position:
            self._pose_coords = lane.get_point_at_distance(position)
            self._pose_lane = lane
            self._pose_position = position
        return self._pose_coords

    @property
    def heading(self) -> float:
        lane = self.lane
        if lane is None:
            return 0.0
        if not hasattr(lane, "get_heading_at_distance"):
            return lane.heading
        position = self.position
        maneuver = self.lane_change
        long_vehicle = self.length > LONG_VEHICLE_THRESHOLD
        if long_vehicle and maneuver is None:
            return self._long_body_pose(lane)[2]
        if maneuver is not None:
            # Yaw towards the target lane: the path's direction is the lane
            # direction plus the rate at which the lateral offset changes.
            base = math.radians(
                self._long_body_pose(lane)[2]
                if long_vehicle
                else lane.get_heading_at_distance(position)
            )
            slope = maneuver.lateral_slope(position)
            hx = math.sin(base) + slope * maneuver.offset_x
            hy = math.cos(base) + slope * maneuver.offset_y
            return (math.degrees(math.atan2(hx, hy)) + 360.0) % 360.0
        if lane is not self._heading_lane or position != self._heading_position:
            self._heading_value = lane.get_heading_at_distance(position)
            self._heading_lane = lane
            self._heading_position = position
        return self._heading_value

    @property
    def lane_id(self) -> str:
        if self.lane is None:
            return ""
        return self.lane.lane_id

    def begin_lane_change(
        self, target_lane: Lane, new_route: List[Lane], distance: float
    ) -> None:
        """Start a gradual move from the current lane into *target_lane*.

        *target_lane* must run parallel to the current lane (same length and
        direction), so ``position`` means the same place on both.
        """
        origin = self.lane
        if origin is None or self.lane_change is not None:
            raise ValueError("Vehicle cannot start a lane change now")
        ox, oy = origin.get_point_at_distance(self.position)
        tx, ty = target_lane.get_point_at_distance(self.position)
        self.lane_change = LaneChangeManeuver(
            origin, self.position, distance, (ox - tx, oy - ty)
        )
        # Stays registered on the origin lane (it still occupies it) and is
        # added to the target lane, which becomes its logical lane.
        self.lane = target_lane
        self.route = new_route
        target_lane.add_vehicle(self)

    def finish_lane_change(self) -> None:
        """Release the origin lane: the vehicle is wholly in its new lane."""
        maneuver = self.lane_change
        if maneuver is None:
            return
        self.lane_change = None
        if maneuver.origin_lane is not self.lane:
            maneuver.origin_lane.remove_vehicle(self)

    def detach(self) -> None:
        """Remove the vehicle from every lane it is registered on."""
        self.finish_lane_change()
        if self.lane is not None:
            self.lane.remove_vehicle(self)

    def update_state(self, acceleration: float, dt: float) -> None:
        if self.state == VehicleState.EXITED:
            return

        # Calculate new speed (cannot be negative)
        previous_speed = self.speed
        self.speed = max(0.0, self.speed + acceleration * dt)

        # Record the acceleration actually realised, not the one requested.
        # They differ only when the speed floor clips a deceleration: a vehicle
        # standing at a stop line keeps being commanded -9 m/s^2 by IDM (zero
        # gap), and snapshots used to report every queued, stationary vehicle
        # as braking at the hard limit.
        self.acceleration = (self.speed - previous_speed) / dt if dt > 0 else 0.0

        # Update position — clamp displacement so we never overshoot more
        # than one lane boundary per tick (prevents coordinate glitches)
        displacement = self.speed * dt
        self.position += displacement

        # Manage state transitions. Stop counting is handled exclusively by
        # update_vehicle_stops() in metrics/definitions/stop_count.py (which
        # applies hysteresis via vehicle._hysteresis_stopped) — do not
        # increment stop_count here as well, or stops get double-counted.
        is_stopped = self.speed < self._wait_threshold

        if is_stopped:
            self.state = VehicleState.WAITING
            self.wait_time += dt
        else:
            self.state = VehicleState.APPROACHING

        # A lane change completes once its distance has been driven. It is
        # only ever started with at least that much lane left, so this always
        # happens before the lane transition below.
        maneuver = self.lane_change
        if maneuver is not None and maneuver.progress(self.position) >= 1.0:
            self.finish_lane_change()

        # Handle lane transitions — process at most one transition per tick
        # to maintain deterministic ordering
        if self.lane is not None and self.position >= self.lane.length:
            self.finish_lane_change()
            try:
                curr_idx = self.route.index(self.lane)
                if curr_idx < len(self.route) - 1:
                    next_lane = self.route[curr_idx + 1]
                    overflow = self.position - self.lane.length
                    # Clamp overflow to avoid teleporting far into the next lane
                    overflow = min(overflow, next_lane.length * 0.5)
                    self.lane.remove_vehicle(self)
                    self.lane = next_lane
                    self.position = overflow
                    self.lane.add_vehicle(self)
                else:
                    # Traversed past the end of the last lane
                    self.lane.remove_vehicle(self)
                    self.lane = None
                    self.state = VehicleState.EXITED
                    self.speed = 0.0
            except ValueError:
                # Fallback if current lane is somehow not in the route
                self.finish_lane_change()
                if self.lane is not None:
                    self.lane.remove_vehicle(self)
                self.lane = None
                self.state = VehicleState.EXITED
                self.speed = 0.0

    def get_bounding_box(self) -> List[Tuple[float, float]]:

        cx, cy = self.coords
        heading_rad = math.radians(self.heading)

        h_x = math.sin(heading_rad)
        h_y = math.cos(heading_rad)

        r_x = h_y
        r_y = -h_x

        half_l = self.length / 2.0
        half_w = self.width / 2.0

        # Front-Left: center + L/2 * H - W/2 * R
        fl_x = cx + half_l * h_x - half_w * r_x
        fl_y = cy + half_l * h_y - half_w * r_y

        # Front-Right: center + L/2 * H + W/2 * R
        fr_x = cx + half_l * h_x + half_w * r_x
        fr_y = cy + half_l * h_y + half_w * r_y

        # Rear-Right: center - L/2 * H + W/2 * R
        rr_x = cx - half_l * h_x + half_w * r_x
        rr_y = cy - half_l * h_y + half_w * r_y

        # Rear-Left: center - L/2 * H - W/2 * R
        rl_x = cx - half_l * h_x - half_w * r_x
        rl_y = cy - half_l * h_y - half_w * r_y

        return [(fl_x, fl_y), (fr_x, fr_y), (rr_x, rr_y), (rl_x, rl_y)]
