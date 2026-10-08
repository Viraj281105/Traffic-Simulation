import math
from typing import Any, Dict, List, NamedTuple, Optional, Set, Tuple

from src.controllers.base import BaseController
from src.controllers.virtual_obstacle import VirtualObstacle
from src.core.enums import Direction, TurnIntent
from src.roads.lane_config import (
    MAX_CIRCULATING_LANES,
    entry_home_ring_lane,
    merging_entry_groups,
    ring_lane_radius,
)
from src.roads.network import (
    ROUNDABOUT_ENTRY_SETBACK,
    ROUNDABOUT_TRANSITION_ARC,
    RoadNetwork,
)
from src.vehicles.body import LONG_VEHICLE_THRESHOLD
from src.vehicles.vehicle import Vehicle
from src.vehicles.vehicle_types import long_vehicle_allowance

# Distance from the entry point (lane end) within which a vehicle is
# considered "at the roundabout entry" for follow-up-time bookkeeping below.
_ENTRY_ZONE: float = 5.0

# Distance from the entry point over which the ``entrySpeed`` cap is applied.
#
# This used to be _ENTRY_ZONE (5 m). A vehicle approaching at its free-flow
# desired speed (VehicleSpawner's desiredSpeed max defaults to 25 m/s) cannot
# physically shed that much speed in 5 m: at the default comfortDeceleration
# of 3 m/s^2 it needs v^2/(2a) ~ 100 m. The cap was therefore applied far too
# late to have any effect, and vehicles entered the ring at full approach
# speed — which is what made circulating gap acceptance meaningless and
# produced high-closing-speed conflicts inside the roundabout. Applying it
# over a realistic braking distance instead lets IDM's free-road term bring
# the vehicle down to entrySpeed *before* it reaches the give-way line,
# which is what a real roundabout approach taper does.
#
# 2026-09-25: 60 m -> 10 m. The continuous braking taper outside the zone (see
# _approach_speed_limit) now does the slowing, and desired speeds follow the
# 50 km/h speed limit rather than 18-25 m/s (vehicles/speed_profile.py), so the
# zone only has to cover the last two vehicle lengths before the give-way line.
# At 60 m every vehicle crawled at entrySpeed for 60 m of straight road, which
# alone added about 6 s of delay per vehicle at an empty roundabout (free-flow
# delay 13.4 s -> 7.7 s at 180 veh/h, seed 1; peak braking and collisions
# unchanged). That was the largest part of why roundabout traffic looked so
# much slower than signal traffic.
_ENTRY_APPROACH_ZONE: float = 10.0

# Comfortable deceleration (m/s^2) used to shape the spillback speed limit
# while an approach is congested (see _approach_speed_limit).
_APPROACH_DECEL: float = 3.0

# Spillback detection. A queue is "propagating" once its tail is further from
# the give-way line than _QUEUE_TRIGGER_DIST (a short standing queue at a
# give-way line is normal and must not slow anything), and the approach is
# only treated as congested when the ring is also not discharging it — a queue
# that is moving is just traffic. The congestion state is released at the
# smaller _QUEUE_RELEASE_DIST (hysteresis) so it cannot chatter around one
# threshold.
_QUEUE_TRIGGER_DIST: float = 20.0
_QUEUE_RELEASE_DIST: float = 10.0
_QUEUE_STOPPED_SPEED: float = 0.5
# A vehicle at the give-way line heads the queue if within this distance of it.
_QUEUE_HEAD_WINDOW: float = 10.0
# Extra bumper-to-bumper distance (beyond vehicle length) still counted as
# the same standing queue.
_QUEUE_LINK_SLACK: float = 6.0
# The approach must have gone this long without discharging a vehicle onto
# the ring before the queue counts as stalled, and must have discharged this
# recently for the state to be released early.
_STALL_ON_TIME: float = 6.0
_STALL_OFF_TIME: float = 1.5
# Minimum time the congested state is held once entered.
_CONGESTION_MIN_HOLD: float = 3.0

# Length of a multi-lane entry's shared mouth, along a connection lane: the
# straight stub to the ring plus the radial transition onto the vehicle's own
# ring (see RoadNetwork._get_or_create_connection_lane). Beyond it the paths
# from adjacent entry lanes have separated.
_MOUTH_LENGTH: float = ROUNDABOUT_ENTRY_SETBACK + ROUNDABOUT_TRANSITION_ARC

# A vehicle whose front is within this distance of its give-way line is "at
# the line" for the first-come-first-served rule between adjacent entry lanes
# (see RoundaboutController._yields_to_earlier_neighbour): close enough for a
# long vehicle's tail swinging out of the next lane to reach it.
_AT_LINE_DISTANCE: float = 6.0

# Exit convergence zones (V1.4, see RoundaboutController._update_exit_yields).
# A vehicle this close beyond its comfortable stopping distance from the start
# of its exit curve, with no conflict in sight, is committed to leaving.
_EXIT_COMMIT_MARGIN: float = 1.0
# Time (s) a convergence zone stays reserved after the vehicle in it has left
# it, before a vehicle from the other ring lane may arrive. A modelling choice,
# not a calibrated value; see the methodology assumptions register.
_EXIT_SAFETY_HEADWAY: float = 1.0
# Distance (m) before its zone within which an approaching vehicle is taken
# into account.
_EXIT_ZONE_HORIZON: float = 40.0
# Sampling step (m) along ring paths for zone and crossing geometry.
_ZONE_SAMPLE_STEP: float = 0.5
# Arc (m, on the outer lane) added before and after an inner-lane exit curve
# to make the zone an outer-lane vehicle shares with it.
_ZONE_ANGULAR_MARGIN: float = 2.0
# Keep-clear entry (RoundaboutController._entry_blocked_downstream): free
# ring beyond the entering vehicle's own length (m), and the speed (m/s)
# below which a ring vehicle counts as standing there.
_KEEP_CLEAR_MARGIN: float = 2.0
_KEEP_CLEAR_SPEED: float = 2.0


class _ZoneVehicle(NamedTuple):
    """A vehicle located relative to the exit convergence zone of its ring
    path: distances along that path (negative before the path begins)."""

    vehicle: Vehicle
    conn: Any
    ring: int
    exit_dir: Any
    front: float
    rear: float
    start: float
    zone_end: float


# Connection-lane ids are built as "conn_{direction.value}_{index}_{turn.value}"
# (see RoadNetwork._get_or_create_connection_lane), so the tokens are the full
# enum values — "east", not "e".
#
# These lookups were previously keyed by single letters, so every id lookup
# raised KeyError. That escaped the inner handler (which caught only
# ValueError/IndexError) and was swallowed by the outer `except KeyError` that
# guards the whole per-direction block — silently abandoning entry-yield
# evaluation for that entire approach as soon as any vehicle was circulating.
# Entry yielding therefore almost never engaged when it mattered most.
_DIRECTION_BY_NAME: Dict[str, Direction] = {d.value: d for d in Direction}
_TURN_BY_NAME: Dict[str, TurnIntent] = {t.value: t for t in TurnIntent}


class RoundaboutController(BaseController):
    """Manages entry yielding logic and circulating traffic flow inside a roundabout intersection."""

    def __init__(self, config: Dict[str, Any], network: RoadNetwork) -> None:
        self.config: Dict[str, Any] = config
        self.network: RoadNetwork = network

        ctrl_cfg = config.get("controller", {})
        self.inner_radius: float = ctrl_cfg.get("innerRadius", 10.0)
        self.outer_radius: float = ctrl_cfg.get("outerRadius", 20.0)
        # Reserved / future-only, and deliberately not read anywhere: the
        # circulating ring count is derived from the approach lane count (see
        # RoadNetwork's connection-lane radii). Kept so the accepted config
        # value is still visible on the controller, and because asymmetric
        # lanesPerApproach will need a genuine ring-lane count. See
        # docs/architecture/06-scenario-configuration-contract.md section 2.6.2.
        self.circulating_lanes: int = ctrl_cfg.get("circulatingLanes", 1)
        self.critical_gap: float = ctrl_cfg.get("criticalGap", 4.0)
        self.follow_up_time: float = ctrl_cfg.get("followUpTime", 2.5)
        self.entry_speed: float = ctrl_cfg.get("entrySpeed", 5.0)
        self.circulating_speed: float = ctrl_cfg.get("circulatingSpeed", 8.0)

        self.time_in_current_state: float = 0.0
        # Per-lane timestamp (in self.time_in_current_state units) of the
        # most recent tick a vehicle was observed completing its entry from
        # that lane — used to enforce follow_up_time spacing between
        # consecutive entries (see update()).
        self._last_entry_time: Dict[str, float] = {}
        # Per-lane set of vehicle_ids that were within _ENTRY_ZONE as of
        # the previous tick, so a "completed entry" can be detected as a
        # vehicle that was in the zone and has now left the lane entirely
        # (rather than merely still sitting in the zone).
        self._prev_zone_occupants: Dict[str, Set[str]] = {}
        # Per-vehicle-id desired_speed as it was before the entrySpeed cap
        # was first applied, so it can be restored once the vehicle starts
        # circulating (see update()).
        self._pre_entry_desired_speed: Dict[str, float] = {}
        # Per-approach spillback state (keyed by Direction.value): whether the
        # approach is latched congested, when it was latched, and since when
        # its head vehicle has been waiting. See _update_congestion().
        self._congested: Dict[str, bool] = {}
        self._congested_since: Dict[str, float] = {}
        self._queue_since: Dict[str, float] = {}
        # lane_id -> (approach congested, distance from give-way line to the
        # queue tail), rebuilt every tick for the approach speed limit.
        self._approach_ctx: Dict[str, Tuple[bool, float]] = {}
        # lane_id -> id of a long vehicle that has begun entering the ring
        # from that lane (see _committed_long_entry).
        self._committed_entry: Dict[str, str] = {}
        # vehicle_id -> time it reached the front of its entry lane at the
        # give-way line (see _yields_to_earlier_neighbour).
        self._at_line_since: Dict[str, float] = {}
        # V1.4 exit convergence zones (see _update_exit_yields): this tick's
        # per-vehicle stopping limits (read by VehiclePool), the (vehicle,
        # exit) pairs committed to a zone, the vehicles held this tick, and
        # two run counters — zone give-ways started, and vehicles that had to
        # continue because a conflict appeared inside their stopping distance.
        self.vehicle_stop_limits: Dict[str, float] = {}
        self._committed_zone: Set[Tuple[str, Any]] = set()
        self._zone_waiting: Set[str] = set()
        self.exit_yielding_count: int = 0
        self.exit_yield_events: int = 0
        self.forced_exit_commitments: int = 0
        # Geometry caches (the network does not change during a run).
        self._angle_cache: Dict[str, List[Tuple[float, float]]] = {}
        self._zone_cache: Dict[str, List[Tuple[Any, float, float]]] = {}
        self._crossing_cache: Dict[str, List[Tuple[int, float]]] = {}
        self._windows: Optional[Dict[Any, Tuple[float, float]]] = None
        self.reset()

    def reset(self) -> None:
        self.time_in_current_state = 0.0
        self._last_entry_time = {}
        self._prev_zone_occupants = {}
        self._pre_entry_desired_speed = {}
        self._congested = {}
        self._congested_since = {}
        self._queue_since = {}
        self._approach_ctx = {}
        self._committed_entry = {}
        self._at_line_since = {}
        self.vehicle_stop_limits = {}
        self._committed_zone = set()
        self._zone_waiting = set()
        self.exit_yielding_count = 0
        self.exit_yield_events = 0
        self.forced_exit_commitments = 0
        for conn in self.network.get_all_connection_lanes():
            conn.virtual_obstacle = None
        # Clear all entry obstacles initially
        for d in Direction:
            try:
                approach = self.network.get_incoming_approach(d)
                for lane in approach.get_lanes():
                    lane.virtual_obstacle = None
            except KeyError:
                pass

    def _remember_desired_speed(self, vehicle: Vehicle) -> float:
        """Return the vehicle's own desired speed, recording it on first sight.

        The caps applied through the roundabout overwrite ``desired_speed``, so
        the pre-roundabout value has to be stashed the first time a vehicle is
        capped and restored on the way out.
        """
        original = self._pre_entry_desired_speed.get(vehicle.vehicle_id)
        if original is None:
            original = vehicle.desired_speed
            self._pre_entry_desired_speed[vehicle.vehicle_id] = original
        return original

    @staticmethod
    def _queue_tail_distance(lane: Any) -> float:
        """Distance from the give-way line back to the tail of the standing queue.

        A queue is the chain of stopped vehicles that starts at the line and
        runs upstream with no gap larger than a vehicle length plus a little
        slack. Returns 0.0 when nothing is queued at the line.
        """
        vehicles = sorted(lane.get_vehicles(), key=lambda v: v.position, reverse=True)
        tail_dist = 0.0
        prev = None
        for v in vehicles:
            if v.speed >= _QUEUE_STOPPED_SPEED:
                break
            if prev is None:
                if (lane.length - v.position) > _QUEUE_HEAD_WINDOW:
                    break
            elif (prev.position - v.position) > prev.length + _QUEUE_LINK_SLACK:
                break
            tail_dist = lane.length - v.position
            prev = v
        return tail_dist

    def _update_congestion(self) -> None:
        """Refresh per-approach spillback state and the per-lane speed context.

        An approach is congested when its standing queue has propagated past
        _QUEUE_TRIGGER_DIST AND the ring has not discharged it for
        _STALL_ON_TIME. Once latched it is held for _CONGESTION_MIN_HOLD and
        released when the queue recedes inside _QUEUE_RELEASE_DIST or the ring
        starts discharging again. The asymmetric thresholds and the minimum
        hold are what keep the state from chattering.
        """
        now = self.time_in_current_state
        self._approach_ctx = {}
        for d in Direction:
            try:
                lanes = self.network.get_incoming_approach(d).get_lanes()
            except KeyError:
                continue
            key = d.value

            tail_dist = max(
                (self._queue_tail_distance(ln) for ln in lanes), default=0.0
            )
            if tail_dist > 0.0:
                self._queue_since.setdefault(key, now)
            else:
                self._queue_since.pop(key, None)

            last_discharge = max(
                (self._last_entry_time.get(ln.lane_id, -math.inf) for ln in lanes),
                default=-math.inf,
            )
            waiting_since = max(self._queue_since.get(key, now), last_discharge)
            stalled_for = now - waiting_since

            congested = self._congested.get(key, False)
            if not congested:
                if tail_dist > _QUEUE_TRIGGER_DIST and stalled_for >= _STALL_ON_TIME:
                    congested = True
                    self._congested_since[key] = now
            else:
                held = now - self._congested_since.get(key, now)
                discharging = (now - last_discharge) < _STALL_OFF_TIME
                if held >= _CONGESTION_MIN_HOLD and (
                    tail_dist <= _QUEUE_RELEASE_DIST or discharging
                ):
                    congested = False
                    self._congested_since.pop(key, None)
            self._congested[key] = congested

            for ln in lanes:
                self._approach_ctx[ln.lane_id] = (congested, tail_dist)

    def _approach_speed_limit(self, lane: Any, position: float) -> float:
        """Desired-speed ceiling for a vehicle on an approach lane.

        Normally: entrySpeed within _ENTRY_APPROACH_ZONE of the give-way line
        and no limit beyond it. While the approach is congested, additionally
        the speed from which the vehicle can still brake at _APPROACH_DECEL
        down to entrySpeed by the queue tail, so spillback is met at
        entrySpeed rather than at free-flow speed. The result is the tighter
        of the two.
        """
        dist_to_line = max(0.0, lane.length - position)
        # Outside the zone the ceiling is the speed from which the vehicle can
        # still brake at _APPROACH_DECEL down to entrySpeed by the time it
        # reaches the zone. It used to be a step — unlimited, then entrySpeed
        # the instant a vehicle crossed the 60 m mark — which dropped the
        # desired speed of a 20-25 m/s vehicle to 5 m/s in one tick. IDM's
        # free-road term answers that with -a(v/v0)^4, i.e. the 9 m/s^2 hard
        # limit: 55 of 56 vehicles at a lightly loaded roundabout were doing
        # emergency stops on every approach. The taper is continuous with the
        # zone's own cap and with the congested taper below, and changes
        # nothing inside the zone.
        if dist_to_line <= _ENTRY_APPROACH_ZONE:
            limit = self.entry_speed
        else:
            limit = math.sqrt(
                self.entry_speed**2
                + 2.0 * _APPROACH_DECEL * (dist_to_line - _ENTRY_APPROACH_ZONE)
            )
        congested, tail_dist = self._approach_ctx.get(lane.lane_id, (False, 0.0))
        if congested:
            dist_to_tail = max(0.0, dist_to_line - tail_dist)
            limit = min(
                limit,
                math.sqrt(self.entry_speed**2 + 2.0 * _APPROACH_DECEL * dist_to_tail),
            )
        return limit

    def update(self, delta_time: float, active_vehicles: List[Vehicle]) -> None:
        self.update_active_vehicles_ref(active_vehicles)
        self.time_in_current_state += delta_time

        # Identify all circulating vehicles (those on connection/circulating lanes)
        circulating_vehicles = [
            v
            for v in active_vehicles
            if v.lane is not None and v.lane.lane_id.startswith("conn")
        ]

        self._update_congestion()

        # Speed regime through the roundabout, in three stages:
        #
        #   approach  -> capped to entrySpeed over the last
        #                _ENTRY_APPROACH_ZONE; while the approach is congested
        #                also tapered to entrySpeed at the queue tail (see
        #                _approach_speed_limit)
        #   circulating -> capped to circulatingSpeed
        #   exit      -> original desired speed restored
        #
        # The circulating cap is the important one, and it used to be missing
        # entirely: reaching a connection lane *restored* the vehicle's full
        # desired speed, so `circulatingSpeed` was accepted, documented and
        # never applied. Vehicles circulated with a desired speed averaging
        # ~22 m/s and actually reached ~17 m/s on a 12.5-20 m radius ring —
        # a lateral acceleration of nearly 2 g, which no car can do.
        #
        # That single omission is what made the ring unsafe: gap acceptance at
        # the give-way line is calibrated against circulatingSpeed, so traffic
        # moving at twice that speed arrives sooner than any accepted gap
        # allowed for, and no achievable deceleration could recover it.
        # Enforcing the cap is strictly more realistic than not, and is what
        # makes the entry gap test mean what it says.
        for v in active_vehicles:
            if v.lane is None:
                continue
            lane_id = v.lane.lane_id.lower()
            if lane_id.startswith("conn"):
                v.desired_speed = min(
                    self._remember_desired_speed(v), self.circulating_speed
                )
            elif "_in_" in lane_id:
                original = self._pre_entry_desired_speed.get(
                    v.vehicle_id, v.desired_speed
                )
                limit = self._approach_speed_limit(v.lane, v.position)
                if limit < original:
                    v.desired_speed = min(self._remember_desired_speed(v), limit)
                elif v.vehicle_id in self._pre_entry_desired_speed:
                    # Limit has lifted (congestion cleared): hand the
                    # vehicle its own speed back.
                    v.desired_speed = original
            elif "_out_" in lane_id:
                # Clear of the roundabout: give the vehicle its own speed back.
                original_speed = self._pre_entry_desired_speed.pop(v.vehicle_id, None)
                if original_speed is not None:
                    v.desired_speed = original_speed

        self._note_heads_at_line()

        for d in Direction:
            try:
                approach = self.network.get_incoming_approach(d)
                total_in_lanes = len(approach.get_lanes())
                for lane in approach.get_lanes():
                    # Uses last tick's decision (still on the lane): a long
                    # vehicle that crossed an open line is committed.
                    self._note_long_entries(lane)

                    # Calculate if there is an oncoming circulating vehicle that blocks entry.
                    # We check circulating vehicles approaching this direction's entry node.
                    # The entry point of this lane is lane.end_coords.
                    entry_pt = lane.end_coords
                    theta_entry = math.atan2(entry_pt[1], entry_pt[0])

                    should_yield = False

                    # Gap the vehicle at the head of this entry needs. The
                    # critical gap is a passenger-car value; a longer vehicle
                    # (V1.1: bus, truck) occupies the conflict point for as
                    # much longer as its extra length takes to pass it at
                    # entry speed, so it needs that much more gap. Zero for
                    # every vehicle up to the 5 m reference car.
                    head = max(
                        lane.get_vehicles(), key=lambda hv: hv.position, default=None
                    )

                    # Ring lane this entry joins (V1.4): the head vehicle's
                    # own, since one entry lane may feed several ring lanes;
                    # the lane's home ring lane when nobody is waiting. With
                    # as many ring lanes as entry lanes both are the entry
                    # lane itself, exactly as in V1.0-V1.3.
                    entering_lane_idx = self._entry_ring_lane(
                        lane, head, total_in_lanes
                    )
                    lane_radius = self._ring_radius(entering_lane_idx)
                    required_gap = self.critical_gap
                    if head is not None:
                        required_gap += long_vehicle_allowance(head.length) / max(
                            self.entry_speed, 1.0
                        )

                    # Widest distance any circulating vehicle could cover in
                    # one critical gap, used only to prune obviously-distant
                    # traffic before the exact per-vehicle test below. The
                    # real decision is made on each vehicle's own speed, so
                    # this is deliberately generous rather than exact.
                    scan_radius = max(15.0, required_gap * self.circulating_speed * 2.0)

                    for cv in circulating_vehicles:
                        # Ring the circulating vehicle is on; defaults to the
                        # entering lane's own ring for hand-built lanes whose
                        # id doesn't carry an index (see the except below).
                        cv_ring_radius = lane_radius

                        # Match circulating lane index and ignore downstream/exiting vehicles
                        if cv.lane is not None:
                            try:
                                cv_parts = cv.lane.lane_id.split("_")
                                if len(cv_parts) >= 4 and cv_parts[0] == "conn":
                                    cv_origin_dir_str = cv_parts[1]
                                    cv_ring = getattr(cv.lane, "ring_lane", None)
                                    cv_lane_idx = (
                                        int(cv_ring)
                                        if cv_ring is not None
                                        else int(cv_parts[2])
                                    )
                                    cv_turn_str = cv_parts[3]

                                    # 1. Skip if the vehicle entered from the same approach (it is downstream)
                                    if cv_origin_dir_str == d.value:
                                        continue

                                    # 2. Skip only circulating lanes this
                                    #    entry path does NOT cross.
                                    #
                                    #    Ring radius grows with lane index
                                    #    (see lane_radius above), so a
                                    #    vehicle entering towards ring
                                    #    `entering_lane_idx` comes from
                                    #    outside and must cut across every
                                    #    ring with an index >= its own.
                                    #    Rings further in (a lower index)
                                    #    are never crossed and are correctly
                                    #    ignored.
                                    #
                                    #    This previously required an exact
                                    #    index match, so a vehicle entering
                                    #    towards an inner ring ignored the
                                    #    outer ring(s) it had to drive
                                    #    straight through, and pulled out in
                                    #    front of circulating traffic.
                                    if cv_lane_idx < entering_lane_idx:
                                        continue

                                    # The gap must be judged on the ring the
                                    # circulating vehicle is actually on, not
                                    # on the entering vehicle's destination
                                    # ring.
                                    cv_ring_radius = self._ring_radius(cv_lane_idx)

                                    # 3. Skip if the vehicle is exiting at this approach
                                    cv_origin = _DIRECTION_BY_NAME[cv_origin_dir_str]
                                    cv_turn = _TURN_BY_NAME[cv_turn_str]
                                    cv_target = self.network._resolve_target_direction(
                                        cv_origin, cv_turn
                                    )
                                    if cv_target == d:
                                        continue
                            except (ValueError, IndexError, KeyError):
                                # An unrecognised connection-lane id means we
                                # cannot tell where this vehicle is heading, so
                                # fall through and treat it as conflicting
                                # traffic rather than ignoring it.
                                pass

                        cv_x, cv_y = cv.coords
                        dist_to_entry_euclidean = (
                            (cv_x - entry_pt[0]) ** 2 + (cv_y - entry_pt[1]) ** 2
                        ) ** 0.5

                        if dist_to_entry_euclidean < scan_radius:
                            theta_cv = math.atan2(cv_y, cv_x)
                            # Angular distance from circulating vehicle to entry point (counter-clockwise)
                            angular_gap = (theta_entry - theta_cv) % (2 * math.pi)

                            # A vehicle that leaves the ring before it gets
                            # here is not conflicting traffic. Only the exit
                            # at this entry's own arm used to be excluded
                            # (check 3 above), so an entering driver also gave
                            # way to vehicles about to turn off at an earlier
                            # exit — at low demand roughly one first stop in
                            # four was for a vehicle that never arrived, at a
                            # junction that looked empty. The exit angle is
                            # read from the vehicle's own path, so this holds
                            # for every ring and turn.
                            if cv.lane is not None and cv.lane.lane_id.startswith(
                                "conn"
                            ):
                                ex, ey = cv.lane.end_coords
                                angle_to_exit = (math.atan2(ey, ex) - theta_cv) % (
                                    2 * math.pi
                                )
                                past_ring = (
                                    cv.lane.length - cv.position
                                    <= ROUNDABOUT_ENTRY_SETBACK
                                )
                                if angle_to_exit < angular_gap or past_ring:
                                    continue

                            # If angular_gap < pi, it is upstream / approaching the entry point
                            if angular_gap < math.pi:
                                dist_along_circle = cv_ring_radius * angular_gap

                                # Judge the gap purely on how long THIS vehicle
                                # will take to arrive.
                                #
                                # A fixed distance window derived from the
                                # nominal circulatingSpeed used to gate this
                                # test, so a vehicle travelling faster than
                                # nominal was simply not seen: it sat outside
                                # the window yet still arrived inside the
                                # critical gap. Time-to-arrival is the quantity
                                # the critical gap is actually defined against,
                                # so comparing it directly removes the
                                # inconsistency rather than papering over it.
                                eff_speed = max(cv.speed, self.circulating_speed)
                                time_gap = dist_along_circle / eff_speed
                                if time_gap < required_gap:
                                    should_yield = True
                                    break

                    # followUpTime: "Time between consecutive entering
                    # vehicles" — even once a circulating gap is accepted,
                    # hold the lane for follow_up_time after the previous
                    # entry from it, modeling the minimum headway queued
                    # vehicles need between each other (HCM roundabout
                    # capacity: critical gap + follow-up time).
                    last_entry = self._last_entry_time.get(lane.lane_id)
                    if last_entry is not None and (
                        self.time_in_current_state - last_entry < self.follow_up_time
                    ):
                        should_yield = True

                    if not should_yield and (
                        self._mouth_shared_with_long_vehicle(d, lane, active_vehicles)
                        or self._yields_to_earlier_neighbour(approach, lane)
                        or self._merging_entry_must_wait(
                            d, approach, lane, active_vehicles
                        )
                        or self._keep_clear(lane, head, circulating_vehicles)
                    ):
                        should_yield = True

                    if should_yield and self._committed_long_entry(lane):
                        should_yield = False

                    if should_yield:
                        lane.virtual_obstacle = VirtualObstacle(position=lane.length)
                    else:
                        lane.virtual_obstacle = None

                    # Detect a completed entry: a vehicle that was within
                    # _ENTRY_ZONE last tick and has now left this lane
                    # entirely (crossed into the roundabout). Using actual
                    # departure from the lane — rather than mere continued
                    # presence in the zone — avoids a vehicle re-arming its
                    # own follow-up timer every tick it is held waiting
                    # right at the entry, which would otherwise deadlock it.
                    current_lane_vehicle_ids = {
                        v.vehicle_id for v in lane.get_vehicles()
                    }
                    prev_zone_occupants = self._prev_zone_occupants.get(
                        lane.lane_id, set()
                    )
                    if prev_zone_occupants - current_lane_vehicle_ids:
                        self._last_entry_time[lane.lane_id] = self.time_in_current_state
                    self._prev_zone_occupants[lane.lane_id] = {
                        v.vehicle_id
                        for v in lane.get_vehicles()
                        if (lane.length - v.position) <= _ENTRY_ZONE
                    }
            except KeyError:
                pass

        self._update_exit_yields(circulating_vehicles, active_vehicles)

    # ------------------------------------------------------------------
    # V1.4: ring lanes, exit spiral-out and merging entries
    # ------------------------------------------------------------------

    @property
    def ring_lanes(self) -> int:
        """Circulating lanes: the network's (V1.4), else the widest approach."""
        rings = int(getattr(self.network, "circulating_lanes", 0) or 0)
        if rings:
            return rings
        widest = 1
        for d in Direction:
            try:
                widest = max(
                    widest, len(self.network.get_incoming_approach(d).get_lanes())
                )
            except KeyError:
                continue
        return min(widest, MAX_CIRCULATING_LANES)

    def _ring_radius(self, ring_lane: int) -> float:
        return ring_lane_radius(
            self.inner_radius, self.outer_radius, self.ring_lanes, ring_lane
        )

    def _entry_ring_lane(self, lane: Any, head: Any, entry_lanes: int) -> int:
        """Ring lane the vehicle at the head of an entry lane will join."""
        if head is not None and head.route:
            try:
                nxt = head.route[head.route.index(lane) + 1]
            except (ValueError, IndexError):
                nxt = None
            ring = getattr(nxt, "ring_lane", None) if nxt is not None else None
            if ring is not None:
                return int(ring)
        index = getattr(lane, "index", None)
        if index is None:
            index = int(lane.lane_id.split("_")[-1])
        return entry_home_ring_lane(int(index), entry_lanes, self.ring_lanes)

    def _merging_entry_must_wait(
        self,
        direction: Direction,
        approach: Any,
        lane: Any,
        active_vehicles: List[Vehicle],
    ) -> bool:
        """Entry lanes that feed the same ring lane take turns.

        Only where an approach has more lanes than the ring (a merging
        entry): the surplus left-hand lanes all join the innermost ring lane
        and their paths converge in the mouth. While a vehicle from another
        lane of the group is still in the mouth this lane waits, and among
        heads waiting at the line the first to arrive goes first — the same
        total order as _yields_to_earlier_neighbour, so no cycle can form.
        """
        lanes = approach.get_lanes()
        my_index = getattr(lane, "index", None)
        if my_index is None:
            return False
        group = next(
            (
                g
                for g in merging_entry_groups(len(lanes), self.ring_lanes)
                if my_index in g
            ),
            None,
        )
        if group is None:
            return False
        head = self._head_at_line(lane)
        if head is None:
            return False
        for v in active_vehicles:
            other = v.lane
            if (
                other is None
                or getattr(other, "role", "") != "connection"
                or getattr(other, "approach", None) != direction
            ):
                continue
            other_index = getattr(other, "index", None)
            if other_index == my_index or other_index not in group:
                continue
            if v.position - v.length / 2.0 < _MOUTH_LENGTH:
                return True
        mine = self._at_line_since.get(head.vehicle_id)
        if mine is None:
            return False
        for other_index in group:
            if other_index == my_index or other_index >= len(lanes):
                continue
            other_head = self._head_at_line(lanes[other_index])
            if other_head is None:
                continue
            theirs = self._at_line_since.get(other_head.vehicle_id)
            if theirs is None:
                continue
            if theirs < mine or (theirs == mine and other_index < my_index):
                return True
        return False

    def _time_to_cover(self, vehicle: Vehicle, distance: float) -> float:
        """Seconds for *vehicle* to travel *distance* from its current speed,
        accelerating at its own maximum up to the circulating speed."""
        if distance <= 0.0:
            return 0.0
        params = vehicle.params
        accel = params.profile.max_acceleration if params is not None else 2.0
        accel = max(accel, 0.1)
        v0 = min(vehicle.speed, self.circulating_speed)
        vmax = max(self.circulating_speed, v0, 0.1)
        ramp = (vmax * vmax - v0 * v0) / (2.0 * accel)
        if distance <= ramp:
            return (math.sqrt(v0 * v0 + 2.0 * accel * distance) - v0) / accel
        return (vmax - v0) / accel + (distance - ramp) / vmax

    # -- exit convergence zones -------------------------------------------

    def _path_angles(self, conn: Any) -> List[Tuple[float, float]]:
        """(distance along path, unwrapped counter-clockwise angle) samples."""
        cached = self._angle_cache.get(conn.lane_id)
        if cached is not None:
            return cached
        x0, y0 = conn.get_point_at_distance(0.0)
        a0 = math.atan2(y0, x0)
        samples: List[Tuple[float, float]] = []
        s = 0.0
        while s <= conn.length:
            x, y = conn.get_point_at_distance(s)
            samples.append((s, a0 + (math.atan2(y, x) - a0) % (2 * math.pi)))
            s += _ZONE_SAMPLE_STEP
        self._angle_cache[conn.lane_id] = samples
        return samples

    def _zones_of(self, conn: Any) -> List[Tuple[Any, float, float]]:
        """The exit convergence zones a ring path runs through, in order:
        (exit, distance along the path where the zone starts, where it ends).

        For an inner-lane path: its own exit, from where it starts to spiral
        out to the throat of the exit. For an outer-lane path: every exit
        whose inner-lane exit curve it passes alongside — from just before
        that curve starts to climb towards the outer lane to just after the
        curve has crossed it — and its own exit, through to its throat.
        """
        cached = self._zone_cache.get(conn.lane_id)
        if cached is not None:
            return cached
        zones: List[Tuple[Any, float, float]] = []
        ring = getattr(conn, "ring_lane", None)
        exit_dir = getattr(conn, "exit_direction", None)
        throat = conn.length - ROUNDABOUT_ENTRY_SETBACK
        if ring == 0 and exit_dir is not None:
            zones.append((exit_dir, float(conn.exit_transition_start), throat))
        elif ring is not None and ring > 0:
            samples = self._path_angles(conn)
            for target, (lo, hi) in self._exit_windows().items():
                a0 = samples[0][1]
                lo_rel = a0 + (lo - a0) % (2 * math.pi)
                hi_rel = lo_rel + (hi - lo) % (2 * math.pi)
                inside = [s for s, ang in samples if lo_rel <= ang <= hi_rel]
                if target == exit_dir:
                    start = inside[0] if inside else float(conn.exit_transition_start)
                    zones.append(
                        (target, min(start, float(conn.exit_transition_start)), throat)
                    )
                elif inside and inside[0] > _ZONE_SAMPLE_STEP:
                    zones.append((target, inside[0], inside[-1]))
            zones.sort(key=lambda z: z[1])
        self._zone_cache[conn.lane_id] = zones
        return zones

    def _exit_windows(self) -> Dict[Any, Tuple[float, float]]:
        """Angular window of each exit's inner-lane exit curve: from where it
        leaves the inner lane (less a margin) to its throat (plus a margin),
        within which outer-lane traffic shares the zone."""
        if self._windows is not None:
            return self._windows
        windows: Dict[Any, Tuple[float, float]] = {}
        r_outer = self._ring_radius(self.ring_lanes - 1)
        margin = _ZONE_ANGULAR_MARGIN / r_outer
        for conn in self.network.get_all_connection_lanes():
            if getattr(conn, "ring_lane", None) != 0:
                continue
            exit_dir = getattr(conn, "exit_direction", None)
            spiral = getattr(conn, "exit_transition_start", None)
            if exit_dir is None or spiral is None or exit_dir in windows:
                continue
            sx, sy = conn.get_point_at_distance(float(spiral))
            tx, ty = conn.get_point_at_distance(conn.length - ROUNDABOUT_ENTRY_SETBACK)
            windows[exit_dir] = (
                math.atan2(sy, sx) - margin,
                math.atan2(ty, tx) + margin,
            )
        self._windows = windows
        return windows

    def _zone_traffic(self, active_vehicles: List[Vehicle]) -> List[_ZoneVehicle]:
        """Every vehicle on, or about to join, a ring path, located relative to
        the next exit convergence zone on that path."""
        found: List[_ZoneVehicle] = []
        for v in active_vehicles:
            route = v.route
            lane = v.lane
            if lane is None or not route or len(route) < 2:
                continue
            conn = route[1]
            ring = getattr(conn, "ring_lane", None)
            if ring is None:
                continue
            half = v.length / 2.0
            if lane is route[0]:
                front = v.position + half - lane.length
            elif lane is conn:
                front = v.position + half
            elif len(route) > 2 and lane is route[2]:
                front = conn.length + v.position + half
            else:
                continue
            rear = front - v.length
            for exit_dir, start, end in self._zones_of(conn):
                if rear >= end:
                    continue  # past this zone
                if start - front <= _EXIT_ZONE_HORIZON:
                    found.append(
                        _ZoneVehicle(
                            v, conn, int(ring), exit_dir, front, rear, start, end
                        )
                    )
                break  # only the next zone on its path
        return found

    def _zone_exit_time(self, zv: _ZoneVehicle) -> float:
        """Seconds until *zv*'s rear has left its zone."""
        return self._time_to_cover(zv.vehicle, zv.zone_end - zv.rear)

    @staticmethod
    def _zone_eta(zv: _ZoneVehicle) -> float:
        """Seconds until *zv*'s front reaches its zone (0 once inside)."""
        return max(0.0, zv.start - zv.front) / max(zv.vehicle.speed, 1.0)

    def _zone_conflict(self, mine: _ZoneVehicle, others: List[_ZoneVehicle]) -> bool:
        """True when a vehicle from the other ring lane will still be in the
        zone when *mine* reaches it, and gets there first.

        A vehicle already inside is simply first (arrival time 0). It used to
        conflict whatever the timing, which held every vehicle within the
        40 m horizon: a car 20-36 m out braked for a zone the vehicle inside
        would leave seconds before it arrived. That was ~85 % of all zone
        waiting and cost a two-lane ring a third of its capacity gain over
        one lane (2,880 veh/h: x1.15 instead of x1.4).
        """
        my_eta = self._zone_eta(mine)
        for other in others:
            if other.ring == mine.ring or other.vehicle is mine.vehicle:
                continue
            their_eta = self._zone_eta(other)
            if (their_eta, other.ring) < (my_eta, mine.ring) or (
                other.front >= other.start
            ):
                if my_eta < self._zone_exit_time(other) + _EXIT_SAFETY_HEADWAY:
                    return True
        return False

    def _update_exit_yields(
        self, circulating: List[Vehicle], active_vehicles: List[Vehicle]
    ) -> None:
        """Exit convergence zones of a two-lane ring (V1.4).

        Around each exit the two ring lanes interact: a vehicle leaving from
        the inner lane spirals out across the outer lane, where outer-lane
        traffic either continues past the exit or leaves by it too, into the
        exit lane alongside. No geometry keeps two 12 m vehicles clear there
        whatever their timing (measured: their bodies, posed along both
        curves, overlap for every inner exit arc tried), and an unarbitrated
        weave was the cause of every contact on multi-lane rings in
        V1.0-V1.3 (known limitation K1).

        So that stretch is a zone that vehicles from the two ring lanes take
        in strict arrival order: a vehicle may enter it only if no vehicle
        from the other ring lane is inside it, and none that reaches it first
        would still be there when this one arrives ("first": the earlier
        arrival time, ties to the inner lane). A vehicle that must wait is
        held with its front at the zone start, where its body is still clear
        of the other lane's path; the limit is applied to that vehicle alone
        (``vehicle_stop_limits``), since one ring path can need two different
        vehicles held at two different exits at once.

        Deadlock-freedom: arrival order is total, so two vehicles never wait
        for each other; every wait is for a vehicle inside a zone, or ahead
        of this one in that order. A vehicle inside a zone is not held by the
        zone rule, and can only be stopped there by traffic on its own lane
        ahead, which leads to a free exit lane or on to the next zone. The
        keep-clear entry rule (_entry_blocked_downstream) means no entering
        vehicle stops across the outer lane, which is what closed the cycle
        in an earlier version (see roads/lane_config.py). Safeguards as at an
        entry: a vehicle already inside its comfortable stopping distance
        when a conflict appears continues (``forced_exit_commitments``), and
        that decision is latched for that zone.
        """
        self.vehicle_stop_limits = {}
        if self.ring_lanes < 2:
            return
        traffic = self._zone_traffic(active_vehicles)
        by_exit: Dict[Any, List[_ZoneVehicle]] = {}
        for zv in traffic:
            by_exit.setdefault(zv.exit_dir, []).append(zv)
        live = {(zv.vehicle.vehicle_id, zv.exit_dir) for zv in traffic}
        self._committed_zone = {key for key in self._committed_zone if key in live}
        waiting = 0
        for zv in traffic:
            if zv.front >= zv.start:
                continue  # inside: never held here
            key = (zv.vehicle.vehicle_id, zv.exit_dir)
            if key in self._committed_zone:
                continue
            v = zv.vehicle
            to_start = zv.start - zv.front
            params = v.params
            decel = params.comfort_deceleration if params is not None else 3.0
            stopping = v.speed * v.speed / (2.0 * max(decel, 0.1))
            can_stop = to_start >= stopping or v.speed < _QUEUE_STOPPED_SPEED
            if self._zone_conflict(zv, by_exit.get(zv.exit_dir, [])):
                if can_stop:
                    self.vehicle_stop_limits[v.vehicle_id] = max(0.0, to_start)
                    waiting += 1
                    if v.vehicle_id not in self._zone_waiting:
                        self.exit_yield_events += 1
                    continue
                self.forced_exit_commitments += 1
                self._committed_zone.add(key)
                continue
            if to_start <= stopping + _EXIT_COMMIT_MARGIN:
                self._committed_zone.add(key)
        self._zone_waiting = set(self.vehicle_stop_limits)
        self.exit_yielding_count = waiting

    # -- keep-clear entry ---------------------------------------------------

    def _keep_clear(self, lane: Any, head: Any, circulating: List[Vehicle]) -> bool:
        """Keep-clear check for the vehicle at the head of an entry lane of a
        multi-lane ring (one-lane rings are left exactly as before)."""
        if self.ring_lanes < 2 or head is None or not head.route:
            return False
        if self._head_at_line(lane) is None:
            return False
        try:
            conn = head.route[head.route.index(lane) + 1]
        except (ValueError, IndexError):
            return False
        if getattr(conn, "ring_lane", None) is None:
            return False
        return self._entry_blocked_downstream(conn, head, circulating)

    def _crossing_points(self, conn: Any) -> List[Tuple[int, float]]:
        """(ring lane, polar angle) where an entry path reaches each ring
        lane's centre radius on its way in, outermost first."""
        cached = self._crossing_cache.get(conn.lane_id)
        if cached is not None:
            return cached
        ring = int(conn.ring_lane)
        found: List[Tuple[int, float]] = []
        for m in range(self.ring_lanes - 1, ring - 1, -1):
            radius = self._ring_radius(m)
            s = 0.0
            while s <= conn.length:
                x, y = conn.get_point_at_distance(s)
                if math.hypot(x, y) <= radius + 1e-6:
                    found.append((m, math.atan2(y, x)))
                    break
                s += _ZONE_SAMPLE_STEP
        self._crossing_cache[conn.lane_id] = found
        return found

    def _entry_blocked_downstream(
        self, conn: Any, head: Vehicle, circulating: List[Vehicle]
    ) -> bool:
        """Keep clear: would entering mean stopping across a ring lane?

        An entering vehicle bound for the inner lane crosses the outer lane
        first. It used to enter whenever no circulating vehicle was coming,
        even if the inner lane just beyond was standing still; it then
        stopped half-way, across the outer lane, and outer-lane traffic was
        held behind it. So it only enters when, on every ring lane it will
        cross or join, nothing is standing within its own length (plus a
        margin) beyond the point where it gets there — the "do not enter
        unless you can clear" rule drivers apply at a busy junction.
        """
        reach = head.length + _KEEP_CLEAR_MARGIN
        for m, angle in self._crossing_points(conn):
            radius = self._ring_radius(m)
            for cv in circulating:
                lane = cv.lane
                if lane is None or getattr(lane, "ring_lane", None) != m:
                    continue
                if cv.speed >= _KEEP_CLEAR_SPEED:
                    continue
                cx, cy = cv.coords
                ahead = (math.atan2(cy, cx) - angle) % (2 * math.pi) * radius
                behind = (angle - math.atan2(cy, cx)) % (2 * math.pi) * radius
                if ahead - cv.length / 2.0 < reach or behind < cv.length / 2.0 + 1.0:
                    return True
        return False

    def _committed_long_entry(self, lane: Any) -> bool:
        """True while a long vehicle is part-way across this give-way line.

        A vehicle moves onto its ring path when its *centre* reaches the
        give-way line, but its front crosses half a length earlier. For a car
        that window is short and ROUNDABOUT_ENTRY_SETBACK absorbs it: a car
        stopped there protrudes at most 2.5 m, inside the 4 m setback. A
        12 m bus protrudes up to 6 m — into the circulating lane. Re-judging
        the gap every tick while its front was already in the ring made the
        bus emergency-stop across the circulating lane whenever traffic came
        into view, and the ring locked solid (30% heavy vehicles, 1.0 veh/s,
        seed 13: one vehicle served in 240 s).

        So, like a real driver, a long vehicle that has started to enter on
        an accepted gap completes its entry: once its front is across the
        line while the entry is open, the decision holds until it has left
        the approach lane. Vehicles up to LONG_VEHICLE_THRESHOLD keep the
        V1.0 behaviour exactly.
        """
        committed_id = self._committed_entry.get(lane.lane_id)
        vehicles = lane.get_vehicles()
        if committed_id is not None:
            if any(v.vehicle_id == committed_id for v in vehicles):
                return True
            del self._committed_entry[lane.lane_id]
        return False

    @staticmethod
    def _mouth_shared_with_long_vehicle(
        direction: Direction, lane: Any, active_vehicles: List[Vehicle]
    ) -> bool:
        """True while this entry must wait for a long vehicle in its mouth.

        A multi-lane entry's lanes share one mouth: the paths fan out to their
        rings over the first ROUNDABOUT_ENTRY_SETBACK + ROUNDABOUT_TRANSITION_ARC
        metres. Two cars fit through it side by side. A bus or truck does not:
        a car turning onto the outer ring swung its tail across the nose of a
        truck entering beside it for the inner ring, after which each was
        blocking the other and the approach locked (30% heavy vehicles, two
        lanes). Real long vehicles take the whole mouth while they swing in.

        So while a vehicle from another lane of this approach is still in the
        mouth, this lane waits if either that vehicle or the one at the head
        of this lane is longer than the reference car. A vehicle already in
        the mouth is never held by this, so it cannot form a cycle; pairs of
        cars enter side by side exactly as in V1.0.
        """
        vehicles = lane.get_vehicles()
        head = max(vehicles, key=lambda hv: hv.position, default=None)
        if head is None:
            return False
        head_long = head.length > LONG_VEHICLE_THRESHOLD
        lane_index = getattr(lane, "index", None)
        for v in active_vehicles:
            other = v.lane
            if other is None or getattr(other, "approach", None) != direction:
                continue
            if getattr(other, "index", None) == lane_index:
                continue
            if not (head_long or v.length > LONG_VEHICLE_THRESHOLD):
                continue
            role = getattr(other, "role", "")
            if role == "connection":
                rear = v.position - v.length / 2.0
                if rear < _MOUTH_LENGTH:
                    return True
            elif role == "incoming" and v.length > LONG_VEHICLE_THRESHOLD:
                # A long vehicle already part-way across its give-way line.
                if v.position + v.length / 2.0 >= other.length:
                    return True
        return False

    @staticmethod
    def _head_at_line(lane: Any) -> Any:
        """The vehicle at the front of an entry lane if it is at the line."""
        head = max(lane.get_vehicles(), key=lambda hv: hv.position, default=None)
        if head is None:
            return None
        if lane.length - (head.position + head.length / 2.0) > _AT_LINE_DISTANCE:
            return None
        return head

    def _note_heads_at_line(self) -> None:
        """Record when each entry lane's front vehicle reached the line."""
        now = self.time_in_current_state
        present: Set[str] = set()
        for d in Direction:
            try:
                lanes = self.network.get_incoming_approach(d).get_lanes()
            except KeyError:
                continue
            for ln in lanes:
                head = self._head_at_line(ln)
                if head is not None:
                    present.add(head.vehicle_id)
                    self._at_line_since.setdefault(head.vehicle_id, now)
        self._at_line_since = {
            vid: t for vid, t in self._at_line_since.items() if vid in present
        }

    def _yields_to_earlier_neighbour(self, approach: Any, lane: Any) -> bool:
        """True when a long vehicle is involved and another lane of this
        approach has a vehicle that reached the line first.

        A long vehicle swings its tail as it turns out of its lane: a bus
        pulling out for the outer ring swept its rear across the next lane's
        stop position and struck the bus waiting there. Holding the bus back
        until the neighbour has gone would deadlock against
        _mouth_shared_with_long_vehicle, which holds the neighbour while the
        bus is in the mouth. Taking turns in the order the vehicles reached
        the line resolves both: when a long vehicle is among the front
        vehicles of an approach, they enter one at a time, first come first
        served — no cycle can form and nobody is passed over indefinitely.
        Pairs of cars are unaffected and enter side by side as in V1.0.
        """
        head = self._head_at_line(lane)
        if head is None:
            return False
        mine = self._at_line_since.get(head.vehicle_id)
        if mine is None:
            return False
        my_index = getattr(lane, "index", 0) or 0
        for other_lane in approach.get_lanes():
            if other_lane is lane:
                continue
            other = self._head_at_line(other_lane)
            if other is None:
                continue
            if not (
                head.length > LONG_VEHICLE_THRESHOLD
                or other.length > LONG_VEHICLE_THRESHOLD
            ):
                continue
            theirs = self._at_line_since.get(other.vehicle_id)
            if theirs is None:
                continue
            other_index = getattr(other_lane, "index", 0) or 0
            if theirs < mine or (theirs == mine and other_index < my_index):
                return True
        return False

    def _note_long_entries(self, lane: Any) -> None:
        """Latch a long vehicle whose front has crossed an open give-way line."""
        if lane.virtual_obstacle is not None or lane.lane_id in self._committed_entry:
            return
        for v in lane.get_vehicles():
            if (
                v.length > LONG_VEHICLE_THRESHOLD
                and v.position + v.length / 2.0 >= lane.length
            ):
                self._committed_entry[lane.lane_id] = v.vehicle_id
                return

    def get_state(self) -> Dict[str, Any]:
        # Count circulating vehicles
        circulating_count = 0
        yielding_count = 0

        # Count yielding vehicles (near stop line on incoming approaches with low speed)
        for d in Direction:
            try:
                approach = self.network.get_incoming_approach(d)
                for lane in approach.get_lanes():
                    for v in lane.get_vehicles():
                        if v.position >= lane.length - 5.0 and v.speed < 0.5:
                            yielding_count += 1
            except KeyError:
                pass

        active_vehs = getattr(self, "_active_vehicles", [])
        circulating_count = sum(
            1
            for v in active_vehs
            if v.lane is not None and v.lane.lane_id.startswith("conn")
        )

        return {
            "type": "roundabout",
            "timeInCurrentState": round(self.time_in_current_state, 2),
            "innerRadius": self.inner_radius,
            "outerRadius": self.outer_radius,
            "circulatingCount": circulating_count,
            "yieldingCount": yielding_count,
            "gapAcceptance": self.critical_gap,
            # V1.4 (additive): ring lanes, vehicles currently held at an exit
            # convergence zone, and run totals of zone give-ways and of
            # vehicles that had to continue through a late conflict.
            "circulatingLanes": self.ring_lanes,
            "exitYieldingCount": self.exit_yielding_count,
            "exitYieldEvents": self.exit_yield_events,
            "forcedExitCommitments": self.forced_exit_commitments,
        }

    def update_active_vehicles_ref(self, active_vehicles: List[Vehicle]) -> None:
        self._active_vehicles = active_vehicles
