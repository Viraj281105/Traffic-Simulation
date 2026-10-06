"""Layered leader-detection and collision avoidance for vehicles.

Safety layers (checked in order):
    1. **Same-lane following** — vehicles ahead on the current / upcoming route
       lanes (including shared connection lanes).
    2. **Virtual obstacles** — signal stop-line barriers placed by the traffic
       controller.
    3. **Conflict zone reservation** — queries the :class:`ConflictManager` for
       blocked intersection zones and inserts virtual obstacles before them.
    4. **Emergency proximity check** — bounding-box proximity scan; if any
       vehicle is dangerously close, returns an emergency braking obstacle.
"""

from __future__ import annotations

import math
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

from src.controllers.virtual_obstacle import VirtualObstacle
from src.core.enums import TurnIntent
from src.roads.network import RoadNetwork
from src.vehicles.body import (
    LONG_VEHICLE_THRESHOLD,
    body_pose,
    forward_probe,
    polygons_overlap,
)
from src.vehicles.vehicle import Vehicle

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_EMERGENCY_DIST: float = 2.5  # meters — triggers emergency braking
_LATERAL_MARGIN: float = 0.3  # meters — added to the two half-widths
# Distances ahead (m) at which a long vehicle's body is posed along its route
# for the Layer 4 check (see _long_vehicle_probe_gap).
_PROBE_STEPS: Tuple[float, ...] = (0.5, 1.0, 1.5, 2.0, 2.5)
_SENSOR_RANGE: float = 30.0  # meters — max 360° sensor reach
_LOOK_AHEAD_LANES: int = 3  # how many route lanes to scan forward


@lru_cache(maxsize=4096)
def _conn_lane_index(lane_id: str) -> Optional[int]:
    """Extract the circulating lane index from a roundabout connection lane id.

    Connection lane ids follow ``conn_{origin}_{lane_idx}_{turn}`` (see
    RoadNetwork._get_or_create_connection_lane). Returns ``None`` if the id
    doesn't match that shape. Cached: it runs for every vehicle pair on the
    hot path, and a lane id always parses the same way.
    """
    parts = lane_id.split("_")
    if len(parts) >= 3:
        try:
            return int(parts[2])
        except ValueError:
            return None
    return None


@lru_cache(maxsize=4096)
def _proximity_lane_key(lane_id: str) -> Tuple[str, bool, Optional[int]]:
    """(lower-cased id, is a connection lane, circulating lane index) — what
    the emergency proximity check (Layer 4) tests about a lane, cached per id
    because that check runs for every pair of vehicles every tick."""
    lower = lane_id.lower()
    is_conn = lower.startswith("conn")
    return lower, is_conn, _conn_lane_index(lower) if is_conn else None


def _long_vehicle_probe_gap(
    vehicle: Vehicle,
    my_x: float,
    my_y: float,
    fwd_x: float,
    fwd_y: float,
    other: Vehicle,
) -> Optional[float]:
    """Layer 4 for a pair involving a long vehicle (V1.1): the gap to *other*
    if *vehicle*'s body, moved a little further along its own route, would
    touch *other*'s body; None if the next _EMERGENCY_DIST metres are clear.

    The car test (below, in find_leader) compares centre points along a
    straight line from the centre: lateral offset against the two
    half-widths, forward distance against the two half-lengths. That is
    exact for vehicles in line and close enough for cars, but for an 11 m
    vehicle it reaches 14 m out along a straight line — off the outside of
    any curve. A bus leaving the roundabout braked to a stop for a truck
    queued on the entry lane across the splitter island, and a truck
    finishing a right turn did the same for a bus held at the next
    approach's stop line. Here the vehicle's body is posed where it will
    actually be (vehicles/body.py) at a few points along its route.
    """
    route = vehicle.route
    lane = vehicle.lane
    other_box = other.get_bounding_box()
    try:
        idx = route.index(lane) if lane is not None else -1
    except ValueError:
        idx = -1
    if idx < 0:
        probe = forward_probe(
            my_x,
            my_y,
            vehicle.heading,
            vehicle.length,
            vehicle.width,
            _EMERGENCY_DIST,
            _LATERAL_MARGIN / 2.0,
        )
        if not polygons_overlap(probe, other_box):
            return None
        nearest = min((px - my_x) * fwd_x + (py - my_y) * fwd_y for px, py in other_box)
        return max(0.0, nearest - vehicle.length / 2.0)

    clear = 0.0
    for step in _PROBE_STEPS:
        x, y, heading = body_pose(route, idx, vehicle.position + step, vehicle.length)
        box = forward_probe(
            x,
            y,
            heading,
            vehicle.length,
            vehicle.width,
            0.0,
            _LATERAL_MARGIN / 2.0,
        )
        if polygons_overlap(box, other_box):
            return clear
        clear = step
    return None


def _remaining_ring_angle(lane: Any, theta_from: float) -> float:
    """Counter-clockwise angle from ``theta_from`` to where ``lane`` ends
    (its exit from the ring)."""
    ex, ey = lane.end_coords
    return (math.atan2(ey, ex) - theta_from) % (2 * math.pi)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def commits_through_yellow(vehicle: Vehicle, virtual_obs: Any) -> bool:
    """True when *vehicle* may run the yellow obstacle *virtual_obs* on its lane.

    The dilemma-zone rule: a vehicle that cannot stop comfortably before the
    line is allowed to clear the junction on yellow. Shared by find_leader's
    Layer 2 (which then ignores the obstacle) and is_blocked_before_lane (which
    must ignore it too — see there).
    """
    if not getattr(virtual_obs, "is_yellow", False):
        return False
    stopping_dist = (vehicle.speed**2) / (
        2.0 * max(getattr(vehicle, "comfort_deceleration", 3.0), 1.0)
    )
    dist_to_line = max(0.0, virtual_obs.position - vehicle.position)
    return bool(dist_to_line <= stopping_dist + vehicle.length)


def is_blocked_before_lane(vehicle: Vehicle, target_lane: Any) -> bool:
    """Check if there is a vehicle or virtual obstacle on the route before target_lane."""
    if vehicle.lane is None:
        return True
    try:
        curr_idx = vehicle.route.index(vehicle.lane)
        target_idx = vehicle.route.index(target_lane)
    except ValueError:
        return True

    accumulated_dist = -vehicle.position
    for i in range(curr_idx, target_idx):
        lane = vehicle.route[i]
        # Check for virtual obstacle on this intermediate lane.
        #
        # Except a yellow the vehicle is committed to running. Layer 2 of
        # find_leader waives that obstacle and the vehicle drives on into the
        # junction — but this check still called it "blocked", so Layer 3
        # skipped the vehicle's conflict-zone admission entirely. Every
        # yellow-runner (and every permissive left-turner released from the
        # stop line at yellow onset) therefore entered the box holding no
        # reservations and stopped inside it on top of crossings others held.
        # At saturation that circular wait froze the whole junction for the
        # rest of the run (1-lane signal, 1.5 veh/s, seed 1: nothing left
        # after t = 178 s).
        virtual_obs = getattr(lane, "virtual_obstacle", None)
        if virtual_obs is not None and not (
            i == curr_idx and commits_through_yellow(vehicle, virtual_obs)
        ):
            return True
        # Check for any vehicles ahead of us on this intermediate lane
        for v in lane.get_vehicles():
            if v is vehicle:
                continue
            v_dist = accumulated_dist + v.position
            if v_dist > 0:
                # There is a vehicle ahead of us before the target lane
                return True
        accumulated_dist += lane.length
    return False


def find_leader(
    vehicle: Vehicle,
    network: Optional[RoadNetwork] = None,
    active_vehicles: Optional[List[Vehicle]] = None,
    conflict_manager: Any = None,
    current_time: float = 0.0,
) -> Tuple[Optional[Any], float]:
    """Find the effective leader (or virtual obstacle) for *vehicle*.

    Returns ``(leader_object, gap)`` where *gap* is bumper-to-bumper distance.
    If no obstacle is found the gap is ``float('inf')``.
    """
    if vehicle.lane is None or not vehicle.route:
        return None, float("inf")

    try:
        curr_idx = vehicle.route.index(vehicle.lane)
    except ValueError:
        return None, float("inf")

    best_leader: Optional[Any] = None
    best_gap: float = float("inf")

    # ── Layer 1: Same-lane following ────────────────────────────────────
    accumulated_dist = -vehicle.position

    end_idx = min(curr_idx + _LOOK_AHEAD_LANES, len(vehicle.route))
    for i in range(curr_idx, end_idx):
        lane = vehicle.route[i]

        # Special logic for roundabouts: connection lanes circle the same roundabout, so
        # vehicles can be on different connection lane objects but physically follow each other if they are in the same lane index.
        if getattr(network, "is_roundabout", False) and lane.lane_id.startswith("conn"):
            # Fallback only, for lanes with no circulating_radius metadata
            # (e.g. hand-built Lane objects in tests that bypass
            # RoadNetwork._get_or_create_connection_lane). A real roundabout
            # connection lane always carries its own circulating_radius
            # (see Lane.circulating_radius / network.py), which is what the
            # cross-lane-object same-index case below actually uses — each
            # circulating lane index has its own true radius, not the ring's
            # overall average.
            inner_r = getattr(network, "inner_radius", 10.0)
            outer_r = getattr(network, "outer_radius", 20.0)
            avg_radius = (inner_r + outer_r) / 2.0
            same_index_radius = getattr(lane, "circulating_radius", None)
            if same_index_radius is None:
                same_index_radius = avg_radius

            my_lane_idx = _conn_lane_index(lane.lane_id)
            if my_lane_idx is None:
                my_lane_idx = 0

            if lane is vehicle.lane:
                my_x, my_y = vehicle.coords
                theta_self = math.atan2(my_y, my_x)
                dist_to_lane_start = 0.0
            else:
                start_x, start_y = lane.start_coords
                theta_self = math.atan2(start_y, start_x)
                dist_to_lane_start = accumulated_dist

            for v in active_vehicles or []:
                if (
                    v is vehicle
                    or v.lane is None
                    or not v.lane.lane_id.startswith("conn")
                ):
                    continue

                v_lane_idx = _conn_lane_index(v.lane.lane_id)
                if v_lane_idx is not None and v_lane_idx != my_lane_idx:
                    continue

                if v.lane is vehicle.lane:
                    # Exact arc-length distance: vehicle.position/v.position
                    # already share the same coordinate system on the
                    # identical connection-lane object, so no polar-angle/
                    # avg_radius estimate is needed (or as precise) here.
                    v_dist = dist_to_lane_start + (v.position - vehicle.position)
                else:
                    v_x, v_y = v.coords
                    theta_v = math.atan2(v_y, v_x)

                    # Counter-clockwise angular distance from theta_self to theta_v
                    diff = (theta_v - theta_self) % (2 * math.pi)

                    # Only consider vehicles that are actually ahead of us in forward circular flow (within 180 degrees)
                    if not (0.0 < diff <= math.pi):
                        continue

                    # ...and, for a long vehicle on either side (V1.1), only
                    # those before this path leaves the ring. A vehicle
                    # beyond our exit is not on our path. V1.0 counted it
                    # anyway; with two cars the resulting gap stays positive
                    # and only causes mild braking, so the calibrated car
                    # results are left exactly as they were. With two 11 m
                    # bodies the gap collapses to zero: an exiting truck
                    # stopped for a truck that had just entered downstream
                    # of its exit, and the ring locked in a cycle of such
                    # waits (30% heavy vehicles, 1.0 veh/s, seed 13).
                    if (
                        vehicle.length > LONG_VEHICLE_THRESHOLD
                        or v.length > LONG_VEHICLE_THRESHOLD
                    ) and diff > _remaining_ring_angle(lane, theta_self):
                        continue

                    arc_dist = same_index_radius * diff
                    v_dist = dist_to_lane_start + arc_dist

                if v_dist > 0:
                    gap = v_dist - (vehicle.length / 2.0 + v.length / 2.0)
                    gap = max(0.0, gap)
                    if gap < best_gap:
                        best_gap = gap
                        best_leader = v
        else:
            # Scan vehicles on this lane
            for v in lane.get_vehicles():
                if v is vehicle:
                    continue
                v_dist = accumulated_dist + v.position
                if v_dist > 0:
                    gap = v_dist - (vehicle.length / 2.0 + v.length / 2.0)
                    gap = max(0.0, gap)
                    if gap < best_gap:
                        best_gap = gap
                        best_leader = v

        # ── Layer 2: Virtual obstacles (signal stop-lines) ─────────────
        virtual_obs = getattr(lane, "virtual_obstacle", None)
        if virtual_obs is not None:
            # Check if this is a yellow clearance obstacle
            # Dilemma zone: if the vehicle cannot safely stop comfortably
            # before the line, permit clearance.
            if i == curr_idx and commits_through_yellow(vehicle, virtual_obs):
                virtual_obs = None

            if virtual_obs is not None:
                obs_dist = accumulated_dist + virtual_obs.position
                if obs_dist > 0:
                    gap = obs_dist - (vehicle.length / 2.0 + virtual_obs.length / 2.0)
                    gap = max(0.0, gap)
                    if gap < best_gap:
                        best_gap = gap
                        best_leader = virtual_obs

        # If we already found something on this lane, no need to look further
        if best_leader is not None and i == curr_idx:
            # Only short-circuit on the current lane — for future lanes we
            # still want to check conflict zones
            pass

        accumulated_dist += lane.length

    # ── Layer 3: Conflict zone reservation check ───────────────────────
    if conflict_manager is not None:
        # Info on every other vehicle currently on a connection lane. Built
        # only when a connection lane ahead actually needs it (most calls
        # never reach one), then shared by every lane checked below; nothing
        # between here and there moves a vehicle.
        conn_vehicles_info: Optional[List[Dict[str, Any]]] = None

        # Check each connection lane in the vehicle's upcoming route
        acc_dist_for_conflict = -vehicle.position
        for i in range(curr_idx, end_idx):
            lane = vehicle.route[i]

            if lane.lane_id.startswith("conn"):
                # Check if we are blocked before this connection lane
                if is_blocked_before_lane(vehicle, lane):
                    acc_dist_for_conflict += lane.length
                    continue

                # Position on this connection lane
                if lane is vehicle.lane:
                    pos_on_conn = vehicle.position
                else:
                    pos_on_conn = 0.0  # haven't entered yet

                turn = (
                    getattr(vehicle, "turn_intent", TurnIntent.STRAIGHT)
                    or TurnIntent.STRAIGHT
                )

                if conn_vehicles_info is None:
                    conn_vehicles_info = [
                        {
                            "vehicle_id": av.vehicle_id,
                            "turn_intent": getattr(
                                av, "turn_intent", TurnIntent.STRAIGHT
                            ),
                            "connection_lane_id": av.lane.lane_id,
                            "position_on_lane": av.position,
                            "speed": av.speed,
                            "length": av.length,
                        }
                        for av in active_vehicles or []
                        if av is not vehicle
                        and av.lane is not None
                        and av.lane.lane_id.startswith("conn")
                    ]

                block_dist = conflict_manager.get_conflict_distance(
                    vehicle_id=vehicle.vehicle_id,
                    vehicle_turn_intent=turn,
                    connection_lane_id=lane.lane_id,
                    vehicle_position_on_lane=pos_on_conn,
                    current_time=current_time,
                    all_vehicles_info=conn_vehicles_info,
                    vehicle_speed=vehicle.speed,
                    on_connection_lane=lane is vehicle.lane,
                    vehicle_length=vehicle.length,
                )

                if block_dist < float("inf"):
                    # Convert block distance (relative to connection lane start)
                    # to distance from the vehicle's current position
                    if lane is vehicle.lane:
                        total_block_dist = block_dist
                    else:
                        total_block_dist = acc_dist_for_conflict + block_dist

                    gap = max(0.0, total_block_dist - vehicle.length / 2.0)
                    if gap < best_gap:
                        best_gap = gap
                        best_leader = VirtualObstacle(
                            position=0.0, speed=0.0, length=0.0
                        )

                # Update reservation clear time if vehicle has passed through
                if lane is vehicle.lane and pos_on_conn > 0:
                    conflict_manager.update_reservation_clear_time(
                        vehicle.vehicle_id, lane.lane_id, current_time
                    )

            acc_dist_for_conflict += lane.length

    # ── Layer 4: Emergency proximity check ─────────────────────────────
    if active_vehicles:
        my_x, my_y = vehicle.coords
        heading_rad = math.radians(vehicle.heading)
        fwd_x = math.sin(heading_rad)
        fwd_y = math.cos(heading_rad)
        # The vehicle's own side of the lane tests below, worked out once
        # rather than once per other vehicle.
        is_roundabout = getattr(network, "is_roundabout", False)
        id_a, a_is_conn, idx_a = _proximity_lane_key(vehicle.lane.lane_id)

        for other in active_vehicles:
            if other is vehicle or other.lane is None:
                continue

            # Skip parallel lanes of the same street (non-connection lanes starting with same direction prefix)
            id_b, b_is_conn, idx_b = _proximity_lane_key(other.lane.lane_id)
            if is_roundabout:
                # In a roundabout, vehicles circulating in the SAME lane
                # index are already tracked by the angular arc-length logic
                # in Layer 1 above, so skip them here to avoid double
                # braking. Vehicles on DIFFERENT circulating lane indices
                # (e.g. weaving between inner/outer rings near entries and
                # exits) are NOT covered by Layer 1's same-lane-index
                # restriction and are not handled by ConflictManager either
                # (its straight-chord conflict points don't apply to curved
                # circulating arcs — see vehicles/pool.py) — let this
                # Euclidean proximity scan catch those cross-lane conflicts.
                if a_is_conn and b_is_conn:
                    if idx_a is not None and idx_a == idx_b:
                        continue
            else:
                if not a_is_conn and not b_is_conn:
                    if id_a[0] in ("n", "s", "e", "w") and id_a[:2] == id_b[:2]:
                        continue

            ox, oy = other.coords
            dx = ox - my_x
            dy = oy - my_y

            # Forward distance along our heading
            fwd_dist = dx * fwd_x + dy * fwd_y
            if fwd_dist <= 0:
                # Other vehicle is behind or beside us — not a forward threat
                continue

            if (
                vehicle.length > LONG_VEHICLE_THRESHOLD
                or other.length > LONG_VEHICLE_THRESHOLD
            ):
                reach = (
                    vehicle.length + other.length + vehicle.width + other.width
                ) / 2.0 + _EMERGENCY_DIST
                if dx * dx + dy * dy > reach * reach:
                    continue
                probe_gap = _long_vehicle_probe_gap(
                    vehicle, my_x, my_y, fwd_x, fwd_y, other
                )
                if probe_gap is not None and probe_gap < best_gap:
                    best_gap = probe_gap
                    best_leader = VirtualObstacle(
                        position=0.0, speed=other.speed, length=other.length
                    )
                continue

            # Lateral distance perpendicular to our heading
            lat_dist = abs(-dx * fwd_y + dy * fwd_x)
            corridor_width = (vehicle.width + other.width) / 2.0 + _LATERAL_MARGIN

            if lat_dist > corridor_width:
                # Outside our lane envelope (e.g. adjacent lane, waiting at perpendicular red light)
                continue

            # Emergency braking if directly ahead in our corridor
            min_safe_dist = _EMERGENCY_DIST + (vehicle.length + other.length) / 2.0
            if fwd_dist < min_safe_dist:
                gap = max(0.0, fwd_dist - (vehicle.length + other.length) / 2.0)
                if gap < best_gap:
                    best_gap = gap
                    best_leader = VirtualObstacle(
                        position=0.0, speed=other.speed, length=other.length
                    )

    return best_leader, best_gap
