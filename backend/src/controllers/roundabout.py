import math
from typing import Any, Dict, List, Set, Tuple

from src.controllers.base import BaseController
from src.controllers.virtual_obstacle import VirtualObstacle
from src.core.enums import Direction, TurnIntent
from src.roads.network import ROUNDABOUT_ENTRY_SETBACK, RoadNetwork
from src.vehicles.vehicle import Vehicle

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

        for d in Direction:
            try:
                approach = self.network.get_incoming_approach(d)
                total_in_lanes = len(approach.get_lanes())
                for lane in approach.get_lanes():
                    # Calculate if there is an oncoming circulating vehicle that blocks entry.
                    # We check circulating vehicles approaching this direction's entry node.
                    # The entry point of this lane is lane.end_coords.
                    entry_pt = lane.end_coords
                    theta_entry = math.atan2(entry_pt[1], entry_pt[0])

                    entering_lane_idx = int(lane.lane_id.split("_")[-1])
                    w_ring = self.outer_radius - self.inner_radius
                    lane_radius = self.inner_radius + (entering_lane_idx + 0.5) * (
                        w_ring / total_in_lanes
                    )

                    should_yield = False

                    # Widest distance any circulating vehicle could cover in
                    # one critical gap, used only to prune obviously-distant
                    # traffic before the exact per-vehicle test below. The
                    # real decision is made on each vehicle's own speed, so
                    # this is deliberately generous rather than exact.
                    scan_radius = max(
                        15.0, self.critical_gap * self.circulating_speed * 2.0
                    )

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
                                    cv_lane_idx = int(cv_parts[2])
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
                                    cv_ring_radius = self.inner_radius + (
                                        cv_lane_idx + 0.5
                                    ) * (w_ring / total_in_lanes)

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
                                if time_gap < self.critical_gap:
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
        }

    def update_active_vehicles_ref(self, active_vehicles: List[Vehicle]) -> None:
        self._active_vehicles = active_vehicles
