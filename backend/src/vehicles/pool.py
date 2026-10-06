"""Vehicle pool — manages all active and exited vehicles.

Integrates with the :class:`ConflictManager` by passing it through to
:func:`find_leader`, and runs a post-update collision audit to catch (and
log) any remaining overlaps as a safety net.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple

from src.core.enums import Direction, VehicleState
from src.intersection.predictive_conflicts import (
    PredictiveConflictResolver,
    apply_predictive_constraint,
)
from src.roads.network import SIGNAL_STOP_LINE_SETBACK
from src.vehicles.idm import IntelligentDriverModel
from src.vehicles.lane_change import (
    LaneChangeModel,
    origin_lane_leader,
    resolve_lane_change_settings,
)
from src.vehicles.router import _conn_lane_index, find_leader
from src.vehicles.speed_profile import (
    curve_speed_ceiling,
    resolve_max_lateral_acceleration,
)
from src.vehicles.vehicle import Vehicle

logger = logging.getLogger(__name__)

# Minimum centre-to-centre distance before we flag a collision.
_COLLISION_THRESHOLD: float = 0.5  # meters

# Incoming-lane id prefix -> approach Direction. RoadNetwork always names
# incoming lanes "{n,s,e,w}_in_{index}" (see RoadNetwork's lane
# construction), so this single table is shared by every call site here
# that needs to recover a Direction from a route's origin lane id.
_INCOMING_LANE_DIRECTIONS: Dict[str, Direction] = {
    "n_in_": Direction.NORTH,
    "s_in_": Direction.SOUTH,
    "e_in_": Direction.EAST,
    "w_in_": Direction.WEST,
}


def _direction_from_incoming_lane_id(lane_id: str) -> Optional[Direction]:
    """Maps an incoming-lane id (e.g. "n_in_0") to its approach Direction."""
    lid = lane_id.lower()
    for prefix, direction in _INCOMING_LANE_DIRECTIONS.items():
        if lid.startswith(prefix):
            return direction
    return None


def _check_sat_overlap(
    poly_a: List[Tuple[float, float]], poly_b: List[Tuple[float, float]]
) -> bool:
    """Check if two convex polygons (oriented bounding boxes) overlap using the Separating Axis Theorem."""
    for poly in (poly_a, poly_b):
        for i in range(len(poly)):
            p1 = poly[i]
            p2 = poly[(i + 1) % len(poly)]
            edge_x = p2[0] - p1[0]
            edge_y = p2[1] - p1[1]
            axis_x = -edge_y
            axis_y = edge_x
            axis_len = math.hypot(axis_x, axis_y)
            if axis_len < 1e-6:
                continue
            axis_x /= axis_len
            axis_y /= axis_len

            min_a = max_a = poly_a[0][0] * axis_x + poly_a[0][1] * axis_y
            for p in poly_a[1:]:
                proj = p[0] * axis_x + p[1] * axis_y
                if proj < min_a:
                    min_a = proj
                if proj > max_a:
                    max_a = proj

            min_b = max_b = poly_b[0][0] * axis_x + poly_b[0][1] * axis_y
            for p in poly_b[1:]:
                proj = p[0] * axis_x + p[1] * axis_y
                if proj < min_b:
                    min_b = proj
                if proj > max_b:
                    max_b = proj

            if max_a < min_b or max_b < min_a:
                return False
    return True


def _audit_group(lane_id: str) -> str:
    """The collision audit's "same street" key: pairs with equal keys are
    parallel lanes of one street and are not audited against each other.

    Roundabout connection lanes group by (origin, circulating lane index),
    not origin alone: two conn_ lanes from the same origin but a different
    lane index (e.g. conn_n_0_straight vs conn_n_1_left) are a real
    cross-lane-index weave conflict — exactly what router.find_leader's
    Layer 4 is responsible for catching — and must remain eligible for the
    audit. Same origin *and* same lane index (regardless of turn intent) are
    one continuous physical path (see Layer 1's same-lane-index following),
    so those still group together.
    """
    lid = lane_id.lower()
    if lid.startswith("conn_"):
        origin = lid.split("_")[1][0] if "_" in lid else lid
        return f"{origin}{_conn_lane_index(lid)}"
    if lid and lid[0] in ("n", "s", "e", "w"):
        return lid[0]
    return lid


class VehiclePool:
    """Manages active and exited vehicles, coordinating their movement and lifecycle."""

    def __init__(self) -> None:
        self.active_vehicles: List[Vehicle] = []
        self.exited_vehicles: List[Vehicle] = []
        self._collision_count: int = 0
        self._last_lane_change: Dict[str, float] = {}
        # Vehicle-id pairs currently overlapping, as of the last audit —
        # used to count each physical collision once (on the tick it
        # starts) rather than once per tick the overlap persists.
        self._colliding_pairs: Set[FrozenSet[str]] = set()
        # Predictive (trajectory-projection) conflict avoidance. Remembers who
        # was told to give way to whom, keyed by vehicle id, so it must be
        # reset with the pool (see reset() below).
        self._predictive: PredictiveConflictResolver = PredictiveConflictResolver()
        # Lane changing (V1.2), built from the engine's config on first use.
        self._lane_changes: Optional[LaneChangeModel] = None
        self._lane_changes_config_id: Optional[int] = None

    def reset(self) -> None:
        """Clear every trace of the previous run.

        Beyond the two vehicle lists, this drops the collision tally and the
        debounce/lane-change bookkeeping keyed by vehicle id. Leaving those
        behind meant a reset simulation started with the previous run's
        collision count already on the board, and could mis-debounce a new
        vehicle that happened to reuse an id from the old run.
        """
        for vehicle in self.active_vehicles:
            # Also drops a mid-manoeuvre vehicle from the lane it was leaving.
            vehicle.detach()
        self.active_vehicles.clear()
        self.exited_vehicles.clear()
        self._collision_count = 0
        self._colliding_pairs.clear()
        self._last_lane_change.clear()
        self._predictive.reset()
        if self._lane_changes is not None:
            self._lane_changes.reset()

    @property
    def lane_change_count(self) -> int:
        """Lane changes started this run (each one runs to completion)."""
        return self._lane_changes.changes_started if self._lane_changes else 0

    @property
    def missed_turn_count(self) -> int:
        """Vehicles that could not reach a lane permitting their turn in time."""
        return self._lane_changes.missed_turns if self._lane_changes else 0

    def _lane_change_model(self, engine: Any) -> LaneChangeModel:
        config = getattr(engine, "config", None) or {}
        if self._lane_changes is None or self._lane_changes_config_id != id(config):
            default_idm = getattr(engine, "idm", None)
            if default_idm is None:
                default_idm = _idm_from_config(config)
            previous = self._lane_changes
            self._lane_changes = LaneChangeModel(
                resolve_lane_change_settings(config), default_idm
            )
            if previous is not None:
                self._lane_changes.changes_started = previous.changes_started
                self._lane_changes.missed_turns = previous.missed_turns
            self._lane_changes_config_id = id(config)
        return self._lane_changes

    def add_vehicle(self, vehicle: Vehicle) -> None:
        if vehicle not in self.active_vehicles:
            self.active_vehicles.append(vehicle)

    def get_active_vehicles(self) -> List[Vehicle]:
        return self.active_vehicles

    def get_exited_vehicles(self) -> List[Vehicle]:
        return self.exited_vehicles

    @property
    def collision_count(self) -> int:
        return self._collision_count

    def update(self, dt: float, engine: Any) -> None:
        """Tick all active vehicles, find leaders, update states, and cleanup exited vehicles."""
        # Get IDM physics from engine or configuration
        idm = getattr(engine, "idm", None)
        config = getattr(engine, "config", {})
        if idm is None:
            idm = _idm_from_config(config)

        # ConflictManager pre-computes conflict/crossing points from straight
        # chords between each connection lane's start/end coordinates (see
        # ConflictManager.compute_conflict_points). That approximation holds
        # for fixed-time-signal connection lanes (short straight or gently
        # curved turn paths near the intersection box), so it is enabled
        # there — it is what makes permissive lefts (e.g. an "ns_green"
        # phase where NORTH/SOUTH share a green and left-turners cross
        # opposing straight traffic) safe once phaseSequence-driven paired
        # phases are used (see FixedTimeSignalController).
        #
        # For roundabouts, connection lanes are long curved circulating arcs
        # (see RoadNetwork._get_or_create_connection_lane) that can span most
        # of the circle; a straight chord between their endpoints cuts
        # across the roundabout and would produce geometrically incorrect
        # conflict points (spurious crossings with lanes that never actually
        # meet, and missed real crossings). Rather than force an
        # incompatible model onto curved geometry, multi-lane roundabout
        # cross-conflicts (vehicles in different circulating lane indices,
        # e.g. weaving between inner/outer rings near entries and exits) are
        # instead caught by the emergency-proximity check in
        # router.find_leader (Layer 4), which works on live Euclidean
        # positions and needs no lane-geometry assumptions.
        geom_type = config.get("geometry", {}).get(
            "intersectionType", "fixed_time_signal"
        )
        if geom_type == "roundabout":
            conflict_manager = None
        else:
            conflict_manager = getattr(engine, "conflict_manager", None)

        current_time = 0.0
        clock = getattr(engine, "clock", None)
        if clock is not None:
            current_time = clock.get_elapsed_time()

        # Update conflict manager reservations if active
        if conflict_manager is not None:
            conflict_manager.update_reservations(current_time)

        # Predictive conflict avoidance (see predictive_conflicts.py). Runs
        # for every geometry, not just roundabouts: it is what actually
        # prevents crossing/merging conflicts, whereas find_leader's Layer 4
        # only reacts once vehicles are already within 2.5 m — too late to
        # stop. Computed once per tick from the pre-update state so every
        # vehicle in this tick sees the same, order-independent picture.
        # On a SINGLE-ring roundabout the controller's gap acceptance at the
        # give-way line is a complete account of entry: the entering vehicle
        # crosses no ring other than the one it is joining. Re-deciding that
        # here only rejects gaps the controller already accepted — measured at
        # roughly a 75% throughput loss for no real safety gain.
        #
        # With two or more rings, entry means cutting across ring(s) the
        # vehicle is not joining, and the predictive layer catches conflicts
        # there that the controller's single give-way test does not, so it
        # keeps arbitrating entry. A signalised junction has no gap logic at
        # all, so it always arbitrates in full.
        net = getattr(engine, "network", None)
        single_ring_roundabout = (
            geom_type == "roundabout"
            and net is not None
            and all(
                len(approach.get_lanes()) <= 1
                for approach in getattr(net, "_incoming", {}).values()
            )
        )
        predictive_limits = self._predictive.compute_braking_distances(
            self.active_vehicles,
            entry_gated_by_controller=single_ring_roundabout,
            junction_arbitrated_elsewhere=conflict_manager is not None,
        )

        stop_line_setback = float(
            getattr(net, "stop_line_setback", SIGNAL_STOP_LINE_SETBACK)
        )

        # Curve speed (see speed_profile.py): the same lateral-acceleration
        # limit on every curved path, at the signal and at the roundabout.
        max_lateral_accel = resolve_max_lateral_acceleration(config)
        curve_decel = float(
            (config.get("vehicleGeneration") or {}).get("comfortDeceleration", 3.0)
        )

        # Update each vehicle
        to_remove: List[Vehicle] = []

        for vehicle in self.active_vehicles:
            if vehicle.state == VehicleState.EXITED:
                to_remove.append(vehicle)
                continue

            self._attempt_lane_change(vehicle, current_time, engine)

            # Leader detection with all safety layers
            leader, gap = find_leader(
                vehicle,
                getattr(engine, "network", None),
                self.active_vehicles,
                conflict_manager=conflict_manager,
                current_time=current_time,
            )

            # Fold in the predictive constraint, keeping whichever of the two
            # is tighter. Expressed as an ordinary stationary obstacle so IDM
            # brakes smoothly rather than clamping the speed directly.
            leader, gap = apply_predictive_constraint(
                gap, leader, predictive_limits.get(vehicle.vehicle_id)
            )

            # Mid lane change the vehicle still overlaps the lane it is
            # leaving, so whatever is ahead there constrains it too.
            if vehicle.lane_change is not None:
                origin_leader, origin_gap = origin_lane_leader(vehicle)
                if origin_leader is not None and origin_gap < gap:
                    leader, gap = origin_leader, origin_gap

            # Per-class behaviour (V1.1): a vehicle with a profile brings its
            # own IDM, curve limit and braking; a legacy one uses the
            # engine-wide values exactly as before.
            params = vehicle.params
            if params is not None:
                vehicle_idm = params.idm
                vehicle_lat = params.max_lateral_acceleration
                vehicle_decel = params.comfort_deceleration
            else:
                vehicle_idm = idm
                vehicle_lat = max_lateral_accel
                vehicle_decel = curve_decel

            # The vehicle's own desired speed, lowered where a curve ahead
            # requires it. vehicle.desired_speed itself is left untouched: it
            # is also the free-flow reference for delay.
            desired = min(
                vehicle.desired_speed,
                curve_speed_ceiling(vehicle, vehicle_lat, vehicle_decel),
            )

            # Calculate acceleration using IDM
            acc = vehicle_idm.calculate_acceleration(
                speed=vehicle.speed,
                desired_speed=max(0.1, desired),
                lead_speed=leader.speed if leader is not None else None,
                gap=gap if leader is not None else None,
            )

            # Update kinematics
            vehicle.update_state(acc, dt)

            if vehicle.state == VehicleState.EXITED:  # type: ignore[comparison-overlap]
                vehicle.exit_time = current_time
                # Release any conflict zone reservations
                if conflict_manager is not None:
                    conflict_manager.release_vehicle(vehicle.vehicle_id)
                to_remove.append(vehicle)
            elif conflict_manager is not None and vehicle.lane is not None:
                # Release the moment the vehicle reaches its outgoing lane: it
                # is physically clear of the junction and its conflict zones,
                # whatever the reservation's nominal clearance timer says.
                #
                # Reservations previously survived until that timer expired,
                # which is CLEARANCE_TIME (2 s) after the vehicle passed the
                # conflict point. But the vehicle then drives 200 m down the
                # outgoing approach, so for most of those 2 s it holds zones it
                # left long ago, and the next vehicle in the queue is blocked
                # behind a junction that is visibly empty.
                #
                # "Clear" means the whole body, not just the centre: a 12 m
                # bus whose centre has reached the outgoing lane can still
                # have its rear in the junction box. The outgoing lane starts
                # the stop-line setback beyond the box, so the rear is out
                # once position >= length/2 - that setback — immediately for
                # every vehicle up to 7 m (all V1.0 cars).
                if "_out_" in vehicle.lane.lane_id and vehicle.position >= (
                    vehicle.length / 2.0 - stop_line_setback
                ):
                    conflict_manager.release_vehicle(vehicle.vehicle_id)

        # Move exited vehicles from active to exited list
        for vehicle in to_remove:
            if vehicle in self.active_vehicles:
                self.active_vehicles.remove(vehicle)
            if vehicle not in self.exited_vehicles:
                self.exited_vehicles.append(vehicle)

        # ── Post-update collision audit ────────────────────────────────
        self._collision_audit()

    def _collision_audit(self) -> None:
        """Scan for overlapping vehicles using Separating Axis Theorem on bounding boxes.

        Debounced: a given pair of vehicles overlapping across multiple
        consecutive ticks is one collision event, counted once (on the tick
        the overlap begins), not once per tick the overlap persists.
        """
        # What each pair test needs from one vehicle, computed once per audit
        # rather than once per pair. Positions do not change during the
        # audit; speeds do (the slower vehicle of a collision is stopped
        # below), and are read live.
        entries = [
            (
                v,
                v.lane,
                _audit_group(v.lane.lane_id),
                {lane_obj.lane_id for lane_obj in v.route} if v.route else set(),
                v.coords,
                v.lane_change is not None,
            )
            for v in self.active_vehicles
            if v.lane is not None
        ]
        still_colliding: Set[FrozenSet[str]] = set()
        for i, (va, lane_a, group_a, va_lane_ids, (ax, ay), chg_a) in enumerate(
            entries
        ):
            for vb, lane_b, group_b, vb_lane_ids, (bx, by), chg_b in entries[i + 1 :]:
                # The three exemptions below assume both vehicles keep to
                # their lanes. A vehicle part-way through a lane change does
                # not: it straddles two lanes, so it is audited against
                # everything near it, including the vehicles it is merging
                # between.
                if not (chg_a or chg_b):
                    # Skip vehicles on the same lane — close following is normal
                    if lane_a is lane_b:
                        continue

                    # Skip parallel lanes of the same street (see _audit_group)
                    if group_a == group_b:
                        continue

                    # Skip vehicles that share any lane in their routes (same path)
                    if va_lane_ids & vb_lane_ids:
                        continue

                # Quick bounding radius check before running full SAT
                dx = bx - ax
                dy = by - ay
                dist_sq = dx * dx + dy * dy
                max_radius = (va.length + vb.length) * 0.6

                if dist_sq > max_radius * max_radius:
                    continue

                pair_key = frozenset((va.vehicle_id, vb.vehicle_id))
                was_colliding = pair_key in self._colliding_pairs

                # Exact SAT collision check on Oriented Bounding Boxes
                box_a = va.get_bounding_box()
                box_b = vb.get_bounding_box()
                if _check_sat_overlap(box_a, box_b):
                    still_colliding.add(pair_key)

                    if not was_colliding:
                        self._collision_count += 1
                        logger.warning(
                            "Collision detected: %s ↔ %s (lanes: %s ↔ %s)",
                            va.vehicle_id,
                            vb.vehicle_id,
                            lane_a.lane_id,
                            lane_b.lane_id,
                        )

                    slower = va if va.speed <= vb.speed else vb
                    slower.speed = 0.0
                    slower.acceleration = 0.0
                elif was_colliding:
                    # Contact hysteresis. The boxes have parted, but the
                    # vehicles are still inside the contact radius, so this is
                    # the same ongoing contact rather than a fresh event.
                    #
                    # Two vehicles resting against each other used to recount
                    # as a brand-new collision every time SAT flickered. They
                    # rock by centimetres as they creep and their box headings
                    # swing as they follow a curve, so the overlap test
                    # alternates while the vehicles never actually separate —
                    # one stalled pair logged eight "collisions" in three
                    # seconds. Releasing on distance rather than on the
                    # overlap test is what makes the existing debounce do what
                    # it always said it did: count each physical collision
                    # once, on the tick it begins.
                    #
                    # Detection is unchanged. A new collision still requires a
                    # real SAT overlap between vehicles not already in
                    # contact, and a pair that moves beyond the contact radius
                    # is released by the check above, so a genuine second
                    # impact is still counted separately.
                    still_colliding.add(pair_key)

        self._colliding_pairs = still_colliding

    def get_active_counts(self) -> Dict[Direction, Dict[VehicleState, int]]:
        """Returns active count summaries categorized by direction and current vehicle state."""
        summary = {d: {s: 0 for s in VehicleState} for d in Direction}

        for v in self.active_vehicles:
            if not v.route or v.state == VehicleState.EXITED:
                continue

            # Infer origin direction from route start lane ID
            direction = _direction_from_incoming_lane_id(v.route[0].lane_id)

            if direction is not None:
                summary[direction][v.state] += 1

        return summary

    def _attempt_lane_change(
        self, vehicle: Vehicle, current_time: float, engine: Any
    ) -> None:
        """Consider a lane change for *vehicle* (see vehicles/lane_change.py).

        V1.0 moved the vehicle into the adjacent lane in a single tick — a
        3.5 m sideways jump, never checked by the collision audit. Changes are
        now MOBIL decisions carried out as gradual, distance-based manoeuvres.
        """
        network = getattr(engine, "network", None)
        if network is None or vehicle.lane is None:
            return
        try:
            started = self._lane_change_model(engine).attempt(
                vehicle,
                network,
                current_time,
                self._last_lane_change.get(vehicle.vehicle_id, -999.0),
            )
        except (KeyError, ValueError, IndexError) as e:
            # KeyError: network.get_incoming_approach() for an unregistered
            # direction (matches the pattern used throughout roundabout.py/
            # router.py). ValueError: the vehicle's lane isn't in this
            # approach's lane list. IndexError: a malformed lane/route lookup
            # inside generate_route(). These are the same "lane data
            # unavailable, skip this attempt" conditions every other
            # lane-lookup site in this codebase narrows to; genuine
            # programming errors (e.g. AttributeError) still surface.
            logger.error(f"Error changing lane for vehicle {vehicle.vehicle_id}: {e}")
            return
        if started:
            self._last_lane_change[vehicle.vehicle_id] = current_time


def _idm_from_config(config: Dict[str, Any]) -> IntelligentDriverModel:
    """The engine-wide IDM a legacy vehicle uses, from vehicleGeneration."""
    veh_gen = config.get("vehicleGeneration", {}) or {}
    return IntelligentDriverModel(
        max_acceleration=veh_gen.get("maxAcceleration", 2.0),
        comfort_deceleration=veh_gen.get("comfortDeceleration", 3.0),
        desired_time_headway=veh_gen.get("desiredTimeHeadway", 1.5),
        minimum_gap=veh_gen.get("minimumGap", 2.0),
        idm_delta=veh_gen.get("idmDelta", 4.0),
    )
