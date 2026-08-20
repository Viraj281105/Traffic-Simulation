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
from typing import Any, Dict, List, Optional, Tuple

from src.core.enums import TurnIntent
from src.roads.network import RoadNetwork
from src.vehicles.vehicle import Vehicle

# ---------------------------------------------------------------------------
# Lightweight obstacle stand-in (same interface expected by IDM caller)
# ---------------------------------------------------------------------------

class VirtualObstacle:
    """A stationary or slow-moving obstacle on a lane (e.g. stop-line)."""

    __slots__ = ("position", "speed", "length", "vehicle_id")

    def __init__(
        self, position: float, speed: float = 0.0, length: float = 0.0
    ) -> None:
        self.position = position
        self.speed = speed
        self.length = length
        self.vehicle_id = "virtual_stop_line"


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_EMERGENCY_DIST: float = 2.5        # meters — triggers emergency braking
_SENSOR_RANGE: float = 30.0         # meters — max 360° sensor reach
_LOOK_AHEAD_LANES: int = 3          # how many route lanes to scan forward


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

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
        # Build info list for all vehicles currently on connection lanes
        conn_vehicles_info: List[Dict[str, Any]] = []
        if active_vehicles:
            for av in active_vehicles:
                if av is vehicle:
                    continue
                if av.lane is not None and av.lane.lane_id.startswith("conn"):
                    conn_vehicles_info.append(
                        {
                            "vehicle_id": av.vehicle_id,
                            "turn_intent": getattr(av, "turn_intent", TurnIntent.STRAIGHT),
                            "connection_lane_id": av.lane.lane_id,
                            "position_on_lane": av.position,
                        }
                    )

        # Check each connection lane in the vehicle's upcoming route
        acc_dist_for_conflict = -vehicle.position
        for i in range(curr_idx, end_idx):
            lane = vehicle.route[i]

            if lane.lane_id.startswith("conn"):
                # Position on this connection lane
                if lane is vehicle.lane:
                    pos_on_conn = vehicle.position
                else:
                    pos_on_conn = 0.0  # haven't entered yet

                turn = getattr(vehicle, "turn_intent", TurnIntent.STRAIGHT) or TurnIntent.STRAIGHT

                block_dist = conflict_manager.get_conflict_distance(
                    vehicle_id=vehicle.vehicle_id,
                    vehicle_turn_intent=turn,
                    connection_lane_id=lane.lane_id,
                    vehicle_position_on_lane=pos_on_conn,
                    current_time=current_time,
                    all_vehicles_info=conn_vehicles_info,
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
        for other in active_vehicles:
            if other is vehicle or other.lane is None:
                continue

            ox, oy = other.coords
            dx = ox - my_x
            dy = oy - my_y
            dist = math.sqrt(dx * dx + dy * dy)

            if dist > _SENSOR_RANGE:
                continue

            # Check if this vehicle is actually *ahead* of us (not behind)
            # Use dot product with our heading to determine
            heading_rad = math.radians(vehicle.heading)
            fwd_x = math.sin(heading_rad)
            fwd_y = math.cos(heading_rad)
            dot = dx * fwd_x + dy * fwd_y

            if dot <= 0:
                # Other vehicle is behind or beside us — not a forward threat
                continue

            # Emergency braking if dangerously close
            if dist < _EMERGENCY_DIST + (vehicle.length + other.length) / 2.0:
                gap = max(0.0, dist - (vehicle.length + other.length) / 2.0)
                if gap < best_gap:
                    best_gap = gap
                    best_leader = VirtualObstacle(
                        position=0.0, speed=other.speed, length=other.length
                    )

    return best_leader, best_gap
