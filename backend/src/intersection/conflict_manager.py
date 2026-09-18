"""Reservation-based intersection conflict zone manager.

Pre-computes crossing points between all connection lane pairs and maintains a
reservation table so that at most one vehicle occupies each conflict zone at
any time.  Priority rules mirror real-world right-hand-traffic conventions:
    - Right-turners yield to straight-goers.
    - Left-turners yield to everyone.
    - Equal-priority ties are broken by vehicle-ID (lower ID wins).
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Set, Tuple

from src.core.enums import TurnIntent
from src.roads.lane import Lane

# ---------------------------------------------------------------------------
# Geometric helper
# ---------------------------------------------------------------------------


def _segment_intersection(
    p0: Tuple[float, float],
    p1: Tuple[float, float],
    p2: Tuple[float, float],
    p3: Tuple[float, float],
) -> Optional[Tuple[float, float]]:
    """Return the intersection point of segments p0→p1 and p2→p3, or *None*."""
    s1_x = p1[0] - p0[0]
    s1_y = p1[1] - p0[1]
    s2_x = p3[0] - p2[0]
    s2_y = p3[1] - p2[1]

    denom = -s2_x * s1_y + s1_x * s2_y
    if abs(denom) < 1e-9:
        return None

    s = (-s1_y * (p0[0] - p2[0]) + s1_x * (p0[1] - p2[1])) / denom
    t = (s2_x * (p0[1] - p2[1]) - s2_y * (p0[0] - p2[0])) / denom

    if 0.0 <= s <= 1.0 and 0.0 <= t <= 1.0:
        return (p0[0] + t * s1_x, p0[1] + t * s1_y)
    return None


def _shares_entry_lane(lane_id_a: str, lane_id_b: str) -> bool:
    """True when two connection lanes are fed by the same incoming lane.

    Connection lane ids are ``conn_{origin}_{lane_index}_{turn}``, so matching
    on origin and lane index identifies vehicles that queued in the same entry
    lane and are therefore strictly one behind the other.
    """
    if not lane_id_a or not lane_id_b:
        return False
    parts_a = lane_id_a.split("_")
    parts_b = lane_id_b.split("_")
    if len(parts_a) < 3 or len(parts_b) < 3:
        return False
    return parts_a[:3] == parts_b[:3]


# Centre-to-centre clearance (metres) below which two paths are treated as
# sharing the same road. Sized to a vehicle width plus margin: closer than this
# and two vehicles cannot occupy both paths at once.
_PATH_CONFLICT_CLEARANCE: float = 3.0

# Arc-length step (metres) used when sampling a connection lane's path. Fine
# enough to locate a crossing to within half a vehicle length, coarse enough
# that the one-off pairwise scan stays cheap.
_PATH_SAMPLE_STEP: float = 0.75


def _sample_lane(lane: Lane) -> List[Tuple[float, float, float]]:
    """Sample a lane's path as ``(arc_distance, x, y)`` points."""
    out: List[Tuple[float, float, float]] = []
    steps = max(2, int(lane.length / _PATH_SAMPLE_STEP) + 1)
    for i in range(steps + 1):
        d = lane.length * i / steps
        x, y = lane.get_point_at_distance(d)
        out.append((d, x, y))
    return out


def _closest_approach(
    samples_a: List[Tuple[float, float, float]],
    samples_b: List[Tuple[float, float, float]],
) -> Optional[Tuple[float, float, float, float]]:
    """Closest point between two sampled paths, if within the clearance.

    Returns ``(dist_along_a, dist_along_b, x, y)`` at the closest approach, or
    ``None`` when the paths never come near enough to conflict.
    """
    best_sq = _PATH_CONFLICT_CLEARANCE * _PATH_CONFLICT_CLEARANCE
    best: Optional[Tuple[float, float, float, float]] = None

    for da, ax, ay in samples_a:
        for db, bx, by in samples_b:
            dx = ax - bx
            dy = ay - by
            gap_sq = dx * dx + dy * dy
            if gap_sq < best_sq:
                best_sq = gap_sq
                best = (da, db, (ax + bx) / 2.0, (ay + by) / 2.0)
    return best


def _distance_along_lane(lane: Lane, point: Tuple[float, float]) -> float:
    """Return the distance along *lane* from its start to *point*."""
    dx = point[0] - lane.start_coords[0]
    dy = point[1] - lane.start_coords[1]
    return math.sqrt(dx * dx + dy * dy)


# ---------------------------------------------------------------------------
# Conflict Zone data structures
# ---------------------------------------------------------------------------


class ConflictPoint:
    """A single crossing point between two connection lanes."""

    __slots__ = (
        "lane_id_a",
        "lane_id_b",
        "x",
        "y",
        "dist_on_a",
        "dist_on_b",
    )

    def __init__(
        self,
        lane_id_a: str,
        lane_id_b: str,
        x: float,
        y: float,
        dist_on_a: float,
        dist_on_b: float,
    ) -> None:
        self.lane_id_a = lane_id_a
        self.lane_id_b = lane_id_b
        self.x = x
        self.y = y
        self.dist_on_a = dist_on_a
        self.dist_on_b = dist_on_b


class Reservation:
    """Records which vehicle currently owns a conflict zone.

    ``lane_id`` is the connection lane the owner is travelling, kept so that a
    follower approaching on the same entry lane can tell that the holder is
    ahead of it in one queue rather than crossing its path.
    """

    __slots__ = ("vehicle_id", "clear_time", "lane_id")

    def __init__(self, vehicle_id: str, clear_time: float, lane_id: str = "") -> None:
        self.vehicle_id = vehicle_id
        self.clear_time = clear_time
        self.lane_id = lane_id


# ---------------------------------------------------------------------------
# Turn-intent priority (higher number = higher priority = goes first)
# ---------------------------------------------------------------------------

# Speed (m/s) at or below which a vehicle counts as stationary for the purpose
# of holding a conflict-zone reservation. Matches the project-wide
# stopSpeedThreshold default.
_STOPPED_SPEED: float = 0.1

# Arc distance from a conflict point within which a vehicle's BODY covers it:
# half a 4.5 m vehicle plus a margin. Distinct from ZONE_RADIUS, which is the
# reservation safety buffer -- two different physical quantities that must not
# share a constant. A vehicle this close to a crossing is on it, whether it is
# moving or not, and nothing may be driven through it.
_ZONE_BODY_RADIUS: float = 3.0


_TURN_PRIORITY: Dict[TurnIntent, int] = {
    TurnIntent.STRAIGHT: 3,
    TurnIntent.RIGHT: 2,
    TurnIntent.LEFT: 1,
}


# ---------------------------------------------------------------------------
# ConflictManager
# ---------------------------------------------------------------------------


class ConflictManager:
    """Manages conflict detection and reservation for intersection crossing.

    Lifecycle
    ---------
    1. At simulation init, call :meth:`register_connection_lanes` with every
       connection lane generated by the road network.
    2. Call :meth:`compute_conflict_points` once to pre-compute all pairwise
       crossing points.
    3. Each tick, call :meth:`update_reservations` to expire stale locks, then
       :meth:`check_and_reserve` for each vehicle approaching the intersection
       to determine whether it may proceed.
    """

    # Safety buffer: distance (meters) before/after the conflict point that
    # counts as "in the zone"
    ZONE_RADIUS: float = 6.0

    # Time (seconds) a reservation persists after the vehicle has cleared
    CLEARANCE_TIME: float = 2.0

    def __init__(self) -> None:
        # All registered connection lanes, keyed by lane_id
        self._connection_lanes: Dict[str, Lane] = {}

        # Pre-computed conflict points:  (sorted-lane-pair) → ConflictPoint
        self._conflict_points: Dict[Tuple[str, str], ConflictPoint] = {}

        # Reservation table:  (sorted-lane-pair) → Reservation
        self._reservations: Dict[Tuple[str, str], Reservation] = {}

        # Mapping: connection_lane_id → set of conflict-pair keys it participates in
        self._lane_conflicts: Dict[str, Set[Tuple[str, str]]] = {}

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def register_connection_lane(self, lane: Lane) -> None:
        """Register a connection lane for conflict analysis."""
        self._connection_lanes[lane.lane_id] = lane

    def compute_conflict_points(self) -> None:
        """Pre-compute where each pair of connection lanes shares road.

        Works on the lanes' actual paths, sampled by arc length, rather than
        on the straight chord between their endpoints.

        The chord approximation was wrong in both directions for a signalised
        junction, whose turn paths are curves. It *missed* the conflict
        between two opposing left turns — chords that never intersect, while
        the real paths pass within 1.24 m of each other — so nothing arbitrated
        the single most dangerous permissive movement at the junction. And it
        *invented* a conflict between a left turn and the opposing through
        movement, whose real paths stay 5.97 m apart, needlessly serialising
        two movements that do not interact.

        Sampling by arc length also makes ``dist_on_a``/``dist_on_b``
        directly comparable with ``vehicle.position``, which a straight-line
        distance from the lane start is not once a path curves.
        """
        lane_ids = list(self._connection_lanes.keys())
        self._conflict_points.clear()
        self._lane_conflicts.clear()

        samples = {
            lane_id: _sample_lane(self._connection_lanes[lane_id])
            for lane_id in lane_ids
        }

        for i in range(len(lane_ids)):
            for j in range(i + 1, len(lane_ids)):
                id_a = lane_ids[i]
                id_b = lane_ids[j]

                hit = _closest_approach(samples[id_a], samples[id_b])
                if hit is None:
                    continue
                dist_a, dist_b, x, y = hit

                key = (min(id_a, id_b), max(id_a, id_b))
                if key[0] == id_a:
                    da, db = dist_a, dist_b
                else:
                    da, db = dist_b, dist_a

                self._conflict_points[key] = ConflictPoint(
                    lane_id_a=key[0],
                    lane_id_b=key[1],
                    x=x,
                    y=y,
                    dist_on_a=da,
                    dist_on_b=db,
                )
                self._lane_conflicts.setdefault(key[0], set()).add(key)
                self._lane_conflicts.setdefault(key[1], set()).add(key)

    # ------------------------------------------------------------------
    # Per-tick maintenance
    # ------------------------------------------------------------------

    def update_reservations(self, current_time: float) -> None:
        """Expire reservations whose clearance time has passed."""
        expired = [
            key
            for key, res in self._reservations.items()
            if current_time >= res.clear_time
        ]
        for key in expired:
            del self._reservations[key]

    def reset_reservations(self) -> None:
        """Drop every outstanding reservation.

        Used when the simulation is reset: reservations are keyed by vehicle id
        and expire against simulation time, which has just gone back to zero,
        so any survivor would block the new run's vehicles out of zones that
        nobody occupies. The pre-computed conflict points are geometry, not run
        state, so they are deliberately kept.
        """
        self._reservations.clear()

    def release_vehicle(self, vehicle_id: str) -> None:
        """Immediately release all reservations held by a vehicle (e.g. on exit)."""
        to_del = [
            key
            for key, res in self._reservations.items()
            if res.vehicle_id == vehicle_id
        ]
        for key in to_del:
            del self._reservations[key]

    # ------------------------------------------------------------------
    # Query / reservation
    # ------------------------------------------------------------------

    def get_conflict_distance(
        self,
        vehicle_id: str,
        vehicle_turn_intent: TurnIntent,
        connection_lane_id: str,
        vehicle_position_on_lane: float,
        current_time: float,
        all_vehicles_info: Optional[List[Dict[str, Any]]] = None,
        vehicle_speed: float = 0.0,
        on_connection_lane: bool = True,
    ) -> float:
        """Return the distance to the nearest *blocked* conflict zone, or inf.

        If the vehicle itself already holds the reservation, it is *not*
        blocked by its own lock.  If the zone is free (or can be acquired),
        the vehicle silently acquires it and returns inf.

        Parameters
        ----------
        vehicle_id : str
        vehicle_turn_intent : TurnIntent
        connection_lane_id : str
            The ``lane_id`` of the connection lane the vehicle is on or
            approaching.
        vehicle_position_on_lane : float
            How far along the connection lane the vehicle currently is.
        current_time : float
            Simulation clock time.
        all_vehicles_info : list, optional
            List of dicts with keys ``vehicle_id``, ``turn_intent``,
            ``connection_lane_id``, ``position_on_lane`` for all active
            vehicles currently on connection lanes. Used for priority
            arbitration when two vehicles approach the same zone simultaneously.

        Returns
        -------
        float
            Distance to the conflict point that blocks this vehicle, or
            ``float('inf')`` if the path is clear.
        """
        conflict_keys = self._lane_conflicts.get(connection_lane_id, set())
        if not conflict_keys:
            return float("inf")

        # -- Phase 1: judge every zone on this lane, commit to nothing ------
        #
        # Judgement is separated from acquisition because the admission
        # decision below is all-or-nothing: it has to know about every zone on
        # the path before it claims any of them.
        min_block_dist = float("inf")
        verdicts: List[Tuple[Tuple[str, str], float, str]] = []

        for key in conflict_keys:
            cp = self._conflict_points[key]

            # Distance of *this* vehicle to the conflict point
            if connection_lane_id == cp.lane_id_a:
                dist_to_cp = cp.dist_on_a
            else:
                dist_to_cp = cp.dist_on_b

            remaining = dist_to_cp - vehicle_position_on_lane

            # Vehicle has already passed this conflict point -> skip
            if remaining < -self.ZONE_RADIUS:
                continue

            verdict = self._judge_zone(
                key=key,
                cp=cp,
                connection_lane_id=connection_lane_id,
                vehicle_id=vehicle_id,
                vehicle_turn_intent=vehicle_turn_intent,
                remaining=remaining,
                all_vehicles_info=all_vehicles_info,
            )

            # A conflict point BEHIND the vehicle cannot obstruct it going
            # forward, so it must not brake for one.
            #
            # Points within ZONE_RADIUS behind are still walked, because the
            # vehicle is physically over them and must keep its claim until it
            # is clear. They used to brake it as well: block_dist is
            # max(0.0, remaining - ZONE_RADIUS), which for negative remaining
            # is 0.0 -- a dead stop for a crossing already driven past. That
            # is the keystone of the jam this whole change set is chasing. A
            # vehicle 2.7 m beyond a crossing was held by the vehicle 2.1 m
            # short of it, while that vehicle was held in turn by the first,
            # each sitting inside the other's occupancy radius. Neither could
            # ever move, and the arms behind them filled until the junction
            # was solid. Freeing the vehicle that is on its way out is what
            # breaks the cycle: it clears the box and everyone behind follows.
            if verdict == "blocked" and remaining >= 0.0:
                min_block_dist = min(
                    min_block_dist, max(0.0, remaining - self.ZONE_RADIUS)
                )

            verdicts.append((key, remaining, verdict))

        # -- Phase 2a: already in the junction, so committed ----------------
        #
        # A vehicle between the stop line and its exit cannot be un-admitted,
        # so it keeps what it holds and picks up zones as it reaches them,
        # exactly as before.
        if on_connection_lane:
            for key, remaining, verdict in verdicts:
                if verdict == "free" and remaining <= self.ZONE_RADIUS * 2:
                    self._acquire(key, vehicle_id, connection_lane_id, current_time)
            return min_block_dist

        # -- Phase 2b: still approaching, so admission control --------------
        #
        # This is the rule that makes the junction deadlock-free, and the one
        # the old incremental scheme did not enforce. Zones used to be claimed
        # only within 2x ZONE_RADIUS, which is 12 m against connection lanes
        # 8.5-14.2 m long: a vehicle could enter holding its first crossings,
        # then find a later one taken and stop inside the box, still holding
        # everything it had claimed on the way in. Four vehicles doing that,
        # one per arm, each waiting on a zone another of them held, is a
        # circular wait that nothing can break -- the model has no reverse
        # gear. At 1.5 veh/s it froze the entire network.
        #
        # So a vehicle is admitted only if EVERY zone on its path through the
        # junction is available, and it then claims them all at once.
        # Hold-and-wait cannot arise, because a vehicle never holds a partial
        # set: if it cannot have all of them it takes none and waits at the
        # stop line, outside the box, where waiting costs only its own delay.
        if vehicle_speed <= _STOPPED_SPEED:
            # Stopped short of the junction, so it holds nothing: a vehicle
            # waiting outside the box must not lock crossing traffic out of a
            # junction it has not entered and may not enter for many seconds.
            # Cycles of that form deadlocked the approaches in their own
            # right. It re-acquires normally once moving again.
            for key, _remaining, _verdict in verdicts:
                held = self._reservations.get(key)
                if held is not None and held.vehicle_id == vehicle_id:
                    del self._reservations[key]
            return min_block_dist

        if min_block_dist != float("inf"):
            # Not admitted. Claim nothing new -- taking the free part of the
            # path is exactly the partial hold that deadlocked the box. What
            # it already holds it keeps for now; it is braking for the stop
            # line, and the release above fires as soon as it gets there.
            return min_block_dist

        # Admitted: every zone on the path is available, so take them all in
        # one go. A vehicle never holds a partial set, so hold-and-wait --
        # and with it the circular wait -- cannot arise.
        for key, _remaining, verdict in verdicts:
            if verdict in ("free", "owned"):
                self._acquire(key, vehicle_id, connection_lane_id, current_time)

        return min_block_dist

    def _acquire(
        self,
        key: Tuple[str, str],
        vehicle_id: str,
        connection_lane_id: str,
        current_time: float,
    ) -> None:
        """Claim one conflict zone for *vehicle_id*."""
        self._reservations[key] = Reservation(
            vehicle_id,
            current_time + self.CLEARANCE_TIME + 5.0,  # generous default
            connection_lane_id,
        )

    def _judge_zone(
        self,
        key: Tuple[str, str],
        cp: "ConflictPoint",
        connection_lane_id: str,
        vehicle_id: str,
        vehicle_turn_intent: TurnIntent,
        remaining: float,
        all_vehicles_info: Optional[List[Dict[str, Any]]],
    ) -> str:
        """Classify one conflict zone for this vehicle.

        ``blocked``  someone crossing us holds or occupies it
        ``owned``    we already hold it
        ``shared``   held by a vehicle from our own entry lane: it does not
                     block us, but it is not ours to claim
        ``free``     unheld, and ours to claim


        Reads reservation and vehicle state but changes neither, so that
        :meth:`get_conflict_distance` can weigh every zone on a path before
        claiming any of them.
        """
        # Never drive into a conflict point that is physically occupied.
        #
        # A reservation says the zone is *claimed*, not that it is clear. A
        # vehicle that yielded and came to rest on the crossing still sits
        # there, and whoever held the claim would drive straight through it.
        # That is how the remaining signal collisions happened: two opposing
        # left-turners, one stopped mid-box, the other arriving at full speed
        # with a valid reservation.
        if self._zone_occupied_by_stalled_vehicle(
            cp, connection_lane_id, vehicle_id, all_vehicles_info
        ):
            return "blocked"

        reservation = self._reservations.get(key)
        if reservation is not None:
            if reservation.vehicle_id == vehicle_id:
                return "owned"
            if _shares_entry_lane(reservation.lane_id, connection_lane_id):
                # The holder entered from the same lane we did, so it is ahead
                # of us in a single-file queue, not crossing us.
                #
                # Yielding to it serialised every platoon through the
                # junction: each vehicle waited out its own leader's clearance
                # timer before it could move, which collapsed saturation flow
                # to a couple of vehicles per green. Two vehicles from one
                # entry lane can never be side by side, so ordinary
                # car-following is the correct and sufficient model.
                #
                # "shared", not "free": we are not blocked by our leader, but
                # the zone is emphatically not ours to take. Claiming it would
                # overwrite the claim of a vehicle that is still inside the
                # junction and hand the zone's protection to one queued behind
                # it, after which a crossing movement is admitted straight on
                # top of the leader. That is how the box deadlocked even with
                # admission control in force.
                return "shared"
            return "blocked"

        # Unreserved. Arbitrate against others converging on the same zone,
        # but only where the two are close enough for the order to matter.
        # Applying the priority tie-break along the whole path instead cost
        # more than the deadlock did: a left turn crosses 9 zones on a 1-lane
        # signal, losing the tie-break on any one of them denied admission,
        # and with one lane per approach the refused left-turner blocks the
        # through traffic queued behind it. Served flow at 2160 veh/h offered
        # fell to 566 veh/h that way, against 1491 before any of this.
        if remaining > self.ZONE_RADIUS * 2:
            return "free"

        if not all_vehicles_info:
            return "free"

        my_priority = _TURN_PRIORITY.get(vehicle_turn_intent, 2)

        for other_info in all_vehicles_info:
            other_id = other_info["vehicle_id"]
            if other_id == vehicle_id:
                continue

            other_conn = other_info.get("connection_lane_id", "")
            if other_conn not in (cp.lane_id_a, cp.lane_id_b):
                continue
            if other_conn == connection_lane_id:
                # Same lane -- handled by lane-following, not conflict zones
                continue

            # Other vehicle is on the *other* lane of this conflict pair
            if other_conn == cp.lane_id_a:
                other_dist_to_cp = cp.dist_on_a
            else:
                other_dist_to_cp = cp.dist_on_b

            other_remaining = other_dist_to_cp - other_info.get("position_on_lane", 0.0)

            # Only consider if the other vehicle is also approaching
            if other_remaining < -self.ZONE_RADIUS:
                continue

            other_priority = _TURN_PRIORITY.get(
                other_info.get("turn_intent", TurnIntent.STRAIGHT), 2
            )

            if other_priority > my_priority:
                return "blocked"
            if other_priority == my_priority and other_id < vehicle_id:
                # Tiebreak: lower vehicle ID wins
                return "blocked"

        return "free"

    def _zone_occupied_by_stalled_vehicle(
        self,
        cp: "ConflictPoint",
        connection_lane_id: str,
        vehicle_id: str,
        all_vehicles_info: Optional[List[Dict[str, Any]]],
    ) -> bool:
        """True when another vehicle is on this conflict point.

        Two separate hazards, with different reaches:

        * a vehicle whose *body* covers the point, moving or not, within
          ``_ZONE_BODY_RADIUS``. Driving into one is a collision now. Checking
          only stationary vehicles left exactly that gap: a vehicle crossing
          the point stopped counting as occupying it the instant it began to
          move, so a second vehicle was cleared to enter while the first was
          still physically crossing, and the two met in the box.
        * a *stationary* vehicle anywhere within the wider ``ZONE_RADIUS``
          safety buffer. One that has come to rest near a crossing is a
          standing hazard rather than a passing one, and it is what a
          reservation alone fails to describe -- the holder of a claim would
          otherwise drive straight through a car that had yielded and stopped
          on the crossing.

        Only the *other* lane of the pair is considered: a stopped vehicle on
        our own lane is ordinary car-following, which find_leader handles with
        an exact gap.
        """
        if not all_vehicles_info:
            return False

        for info in all_vehicles_info:
            if info["vehicle_id"] == vehicle_id:
                continue
            other_lane = info.get("connection_lane_id", "")
            if other_lane == connection_lane_id:
                continue
            if other_lane == cp.lane_id_a:
                other_dist_to_cp = cp.dist_on_a
            elif other_lane == cp.lane_id_b:
                other_dist_to_cp = cp.dist_on_b
            else:
                continue

            offset = abs(other_dist_to_cp - info.get("position_on_lane", 0.0))

            if offset <= _ZONE_BODY_RADIUS:
                return True
            if info.get("speed", 0.0) <= _STOPPED_SPEED and offset <= self.ZONE_RADIUS:
                return True
        return False

    def update_reservation_clear_time(
        self, vehicle_id: str, connection_lane_id: str, current_time: float
    ) -> None:
        """Update the clearance time for reservations held by a vehicle that
        has passed through the conflict point (so they expire promptly)."""
        conflict_keys = self._lane_conflicts.get(connection_lane_id, set())
        for key in conflict_keys:
            res = self._reservations.get(key)
            if res is not None and res.vehicle_id == vehicle_id:
                # cp = self._conflict_points[key]  # removed unused variable
                # Set a tight clearance window
                res.clear_time = current_time + self.CLEARANCE_TIME

    def get_all_conflict_points(self) -> List[ConflictPoint]:
        """Return all pre-computed conflict points (useful for debugging/visualization)."""
        return list(self._conflict_points.values())

    def get_reservation_count(self) -> int:
        """Return the number of active reservations."""
        return len(self._reservations)
