"""Predictive, geometry-agnostic conflict avoidance.

Why this exists
---------------
:class:`~src.intersection.conflict_manager.ConflictManager` reserves conflict
zones derived from the *straight chord* between each connection lane's
endpoints. That approximation is fine for the short, nearly-straight paths
through a signalised intersection box, but it breaks down completely on a
roundabout, whose connection lanes are long curved arcs: a chord between the
endpoints of a 270-degree left-turn arc cuts straight across the middle of the
roundabout, producing crossings that do not exist and missing the ones that
do. For that reason the roundabout path deliberately runs with no
ConflictManager at all (see :mod:`src.vehicles.pool`), which left only the
reactive 2.5 m emergency-proximity scan in :func:`src.vehicles.router.find_leader`
standing between circulating vehicles and each other.

That is not enough. A reactive check that triggers 2.5 m out cannot prevent a
conflict between two vehicles converging from different directions — by the
time they are 2.5 m apart, no achievable deceleration separates them. The
observable result was a steady stream of real, geometric vehicle overlaps
inside the roundabout.

How it works
------------
Rather than reasoning about lane geometry analytically, this layer walks each
vehicle's actual route forward and asks a much simpler question: *where* do
these two paths come close, and *when* does each vehicle get there?

1. **Where** — both paths are sampled at a fixed ladder of distances ahead
   (:data:`_SAMPLE_DISTANCES`) and the closest approaching pair of samples is
   found. This yields a conflict point expressed as a distance along each
   vehicle's own path. Crucially, those distances are anchored *in space*, so
   they shrink monotonically as a vehicle advances and do not move when it
   slows down.

   An earlier iteration of this layer sampled by time instead (speed x
   horizon). That made the braking target collapse toward the vehicle as it
   decelerated, so instead of stopping at the give-way line a vehicle crept
   forward until it stalled inside the circulating ring — directly in the path
   it was supposed to be yielding to. Sampling by distance is what makes the
   constraint stable enough to actually stop a vehicle *before* it commits.

2. **When** — each vehicle's time to reach the conflict point is its distance
   divided by its speed. If those times differ by more than
   :data:`_SAFE_HEADWAY` the paths merely cross; the vehicles pass at
   different moments and neither needs to act. This is what keeps the layer
   from strangling ordinary traffic: only genuinely simultaneous arrivals
   produce a constraint.

3. **Who gives way** — decided by a total, deterministic rule (see
   :meth:`PredictiveConflictResolver._select_yielder`) so that runs with the
   same seed stay bit-for-bit reproducible.

The result is a distance the yielding vehicle may still travel. The caller
feeds it to IDM as an ordinary stationary obstacle, so vehicles decelerate
smoothly and the existing car-following model stays in charge — this layer
never writes speeds or positions directly.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

from src.core.enums import VehicleState
from src.vehicles.vehicle import Vehicle

# Distances (metres) ahead of each vehicle at which its path is sampled when
# looking for a crossing. Spacing widens with distance: precision matters most
# near the vehicle, where a constraint is about to bind, and a coarse sample is
# enough far out where the estimate is speculative anyway.
_SAMPLE_DISTANCES: Tuple[float, ...] = (2.0, 5.0, 9.0, 14.0, 20.0)

# Extra clearance (metres) added to the two vehicles' combined footprint radii
# when deciding whether two sampled points count as the same patch of road.
#
# The footprint radius is half the bounding-box diagonal, so the test is
# orientation-independent: it catches a merge where two vehicles end up
# nose-to-tail on converging paths just as well as a side-on crossing. A
# width-only threshold missed exactly those longitudinal cases — two 4.5 m
# vehicles 4 m apart centre-to-centre genuinely overlap, but their centres are
# further apart than a lane width, so a width-based test waved them through.
#
# Selectivity does NOT come from keeping this small; it comes from the
# arrival-time test in _find_conflict. Vehicles that merely share a route
# never trip that test, so this can be honestly sized to the real footprint.
_SAFETY_MARGIN: float = 0.5

# Difference in arrival time (seconds) beyond which two vehicles crossing the
# same point are considered to pass safely rather than to conflict.
_SAFE_HEADWAY: float = 2.5

# Speed (m/s) at or below which a vehicle counts as stopped. Matches the
# project-wide stopSpeedThreshold default.
_STOPPED_SPEED: float = 0.1

# Speed floor used when converting a distance to an arrival time, so a nearly
# stopped vehicle yields a large (but finite) time rather than dividing by zero.
_MIN_SPEED_FOR_ETA: float = 0.5

# Vehicles further apart than this cannot interact within the sampled range,
# so they are pruned before any path comparison. Also the spatial-hash cell
# size; it must exceed the largest sample distance.
_BROAD_PHASE_RADIUS: float = 40.0


def _vehicle_lane_on_other_route(leader: Vehicle, follower: Vehicle) -> bool:
    """True when ``leader`` sits on a lane ``follower`` still has to travel."""
    if leader.lane is None or not follower.route:
        return False
    leader_lane_id = leader.lane.lane_id
    return any(lane.lane_id == leader_lane_id for lane in follower.route)


def _footprint_radius(vehicle: Vehicle) -> float:
    """Circumscribed radius of the vehicle's bounding box."""
    return math.hypot(vehicle.length, vehicle.width) / 2.0


def _project_path(
    vehicle: Vehicle, distances: Sequence[float]
) -> List[Optional[Tuple[float, float]]]:
    """Return the vehicle's position after travelling each of ``distances``.

    The walk follows the vehicle's real route lane by lane, so a projection
    that runs off the end of the current lane continues onto the next one
    using that lane's own geometry (including curved connection-lane
    waypoints). ``None`` marks a distance that runs past the end of the
    route — the vehicle will have left the network by then and can no longer
    conflict with anything.
    """
    results: List[Optional[Tuple[float, float]]] = []
    if vehicle.lane is None or not vehicle.route:
        return [None] * len(distances)

    try:
        start_idx = vehicle.route.index(vehicle.lane)
    except ValueError:
        return [None] * len(distances)

    for distance in distances:
        remaining = vehicle.position + distance
        idx = start_idx
        point: Optional[Tuple[float, float]] = None
        while idx < len(vehicle.route):
            lane = vehicle.route[idx]
            if remaining <= lane.length:
                point = lane.get_point_at_distance(remaining)
                break
            remaining -= lane.length
            idx += 1
        results.append(point)
    return results


class PredictiveConflictResolver:
    """Computes per-vehicle braking constraints from projected trajectories.

    Stateless between ticks by design: every call re-projects from the live
    vehicle states, so there is no reservation table to leak, expire or reset
    (which also means :meth:`SimulationEngine.reset` has nothing extra to
    clear here).
    """

    def __init__(
        self,
        sample_distances: Sequence[float] = _SAMPLE_DISTANCES,
        safety_margin: float = _SAFETY_MARGIN,
        safe_headway: float = _SAFE_HEADWAY,
        eta_speed_floor: float = _MIN_SPEED_FOR_ETA,
        protect_circulating: bool = True,
    ) -> None:
        self.sample_distances: Tuple[float, ...] = tuple(sample_distances)
        self.safety_margin: float = safety_margin
        self.safe_headway: float = safe_headway
        self.eta_speed_floor: float = eta_speed_floor
        self.protect_circulating: bool = protect_circulating

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def compute_braking_distances(
        self,
        active_vehicles: List[Vehicle],
        entry_gated_by_controller: bool = False,
        junction_arbitrated_elsewhere: bool = False,
    ) -> Dict[str, float]:
        """Return ``{vehicle_id: distance it may still travel}`` for yielders.

        Only vehicles that must give way appear in the result.

        ``entry_gated_by_controller`` marks a junction whose controller already
        decides when traffic may enter — a roundabout, where
        :class:`~src.controllers.roundabout.RoundaboutController` performs
        explicit gap acceptance at the give-way line. There, this layer does not
        second-guess entry: it arbitrates only what the controller cannot see,
        namely conflicts between vehicles already inside the junction (cross-ring
        weaving and exit merges).

        Applying both gates was measurably counter-productive. On a single-ring
        roundabout, where no cross-ring conflict can exist, the duplicate gate
        cost roughly three quarters of the junction's throughput while barely
        changing the collision count — it was rejecting gaps the controller had
        already, correctly, accepted.
        """
        constraints: Dict[str, float] = {}

        movers = [
            v
            for v in active_vehicles
            if v.lane is not None and v.state != VehicleState.EXITED
        ]
        if len(movers) < 2:
            return constraints

        # Project every vehicle once, then compare pairs. Projecting inside
        # the pair loop instead would repeat the same route walk O(n) times
        # per vehicle.
        projections: Dict[str, List[Optional[Tuple[float, float]]]] = {}
        samples: Dict[str, Tuple[float, ...]] = {}
        coords: Dict[str, Tuple[float, float]] = {}
        for v in movers:
            # A stopped vehicle is not going anywhere this tick, so the only
            # road it occupies is where it already is. Sampling its path ahead
            # would claim territory it has no way of reaching and would make
            # every queue look like a wall of conflicts.
            dists = (0.0,) if v.speed <= _STOPPED_SPEED else self.sample_distances
            samples[v.vehicle_id] = dists
            projections[v.vehicle_id] = _project_path(v, dists)
            coords[v.vehicle_id] = v.coords

        # Broad phase: bucket vehicles into a uniform grid whose cell size is
        # the interaction radius, so each vehicle is only compared against the
        # nine cells around it instead of against every other vehicle. Traffic
        # spreads along four long approaches, so this turns a quadratic scan
        # into a near-linear one and keeps the per-tick cost flat as the
        # network fills up.
        grid: Dict[Tuple[int, int], List[int]] = {}
        cells: List[Tuple[int, int]] = []
        for idx, v in enumerate(movers):
            cx, cy = coords[v.vehicle_id]
            cell = (
                int(math.floor(cx / _BROAD_PHASE_RADIUS)),
                int(math.floor(cy / _BROAD_PHASE_RADIUS)),
            )
            cells.append(cell)
            grid.setdefault(cell, []).append(idx)

        for i, va in enumerate(movers):
            ax, ay = coords[va.vehicle_id]
            gx, gy = cells[i]

            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for j in grid.get((gx + dx, gy + dy), ()):
                        # Each unordered pair is examined exactly once.
                        if j <= i:
                            continue
                        vb = movers[j]

                        bx, by = coords[vb.vehicle_id]
                        if math.hypot(bx - ax, by - ay) > _BROAD_PHASE_RADIUS:
                            continue

                        self._resolve_pair(
                            va,
                            vb,
                            projections,
                            samples,
                            constraints,
                            entry_gated_by_controller,
                            junction_arbitrated_elsewhere,
                        )

        return constraints

    # ------------------------------------------------------------------
    # Pair resolution
    # ------------------------------------------------------------------

    def _resolve_pair(
        self,
        va: Vehicle,
        vb: Vehicle,
        projections: Dict[str, List[Optional[Tuple[float, float]]]],
        samples: Dict[str, Tuple[float, ...]],
        constraints: Dict[str, float],
        entry_gated_by_controller: bool = False,
        junction_arbitrated_elsewhere: bool = False,
    ) -> None:
        if self._same_physical_path(va, vb):
            # Plain car-following on one shared path — already handled
            # precisely by find_leader's same-lane logic. Braking for it here
            # as well would double-count the constraint and stall the queue.
            return
        if self._parallel_approach_lanes(va, vb):
            # Neighbouring lanes of the same approach run side by side by
            # design and never need to yield to each other.
            return

        if junction_arbitrated_elsewhere:
            # One arbitration system per junction.
            #
            # A signalised junction already resolves conflicts twice over: the
            # phase plan separates conflicting movements in time, and
            # ConflictManager reserves the crossing points between connection
            # lanes. This layer exists only for geometry ConflictManager
            # cannot model — a roundabout's curved arcs, where it is disabled
            # — so on a signal it is a third, far blunter gate on a junction
            # that is already governed, and it was the single largest cause of
            # the signal's capacity collapse.
            #
            # What it did, measured over a 150 s run: 1138 emergency stops of
            # vehicles crossing the box because a *stationary* vehicle waiting
            # at another approach's stop line sat on their predicted path, and
            # 1944 constraints between two vehicles that were both still on
            # their approach lanes, held short of a stop line that had not
            # even been reached. Capacity fell from about 1300 veh/h to
            # 206 veh/h and kept falling as demand rose, because vehicles
            # halted inside the box and blocked it.
            #
            # Deferring restores the signal's capacity curve. ConflictManager
            # remains fully active and keeps doing the arbitration it was
            # designed for.
            return

        hit = self._find_conflict(va, vb, projections, samples)
        if hit is None:
            return
        dist_a, dist_b = hit

        yielder, dist = self._select_yielder(va, vb, dist_a, dist_b)

        if entry_gated_by_controller and not self._inside_intersection(yielder):
            # The junction controller owns the give-way decision here; adding a
            # second, independent gate only rejects gaps it already accepted.
            return

        other = vb if yielder is va else va
        other_dist = dist_b if yielder is va else dist_a

        if (
            self.protect_circulating
            and self._inside_intersection(yielder)
            and not self._inside_intersection(other)
        ):
            # Never ask a vehicle that is already inside the junction to stop
            # for one that has not entered yet. Stopping mid-junction blocks
            # the path of everything behind it, which on a roundabout means the
            # ring seizes up: circulating traffic halts, so nobody can enter,
            # so the halted traffic never clears. That conflict is prevented
            # earlier instead, at the give-way line, where rule 2 of
            # _select_yielder holds the entering vehicle back until the
            # crossing is genuinely clear.
            #
            # This deliberately does NOT apply when both vehicles are inside.
            # Two circulating vehicles on converging paths — an inner-ring
            # vehicle crossing the outer ring to reach its exit is the common
            # one — are a real weaving conflict that only this layer can
            # arbitrate: same-ring car-following ignores them because their
            # ring indices differ, and ConflictManager is disabled for
            # roundabouts. Exempting them left the conflict completely
            # unarbitrated, and vehicles drove into each other at close to the
            # full circulating speed with no braking applied at any point.
            #
            # The one exception to the exemption is a vehicle physically parked
            # on the conflict point: that is an obstacle rather than a
            # negotiation, and driving through it is never the better outcome.
            if not (other.speed <= _STOPPED_SPEED and other_dist <= 1e-9):
                return

        # Stop short of the conflict point by the yielder's own half-length
        # plus clearance, so its nose does not end up inside the crossing.
        allowed = max(0.0, dist - _footprint_radius(yielder) - self.safety_margin)
        existing = constraints.get(yielder.vehicle_id)
        if existing is None or allowed < existing:
            constraints[yielder.vehicle_id] = allowed

    def _find_conflict(
        self,
        va: Vehicle,
        vb: Vehicle,
        projections: Dict[str, List[Optional[Tuple[float, float]]]],
        samples: Dict[str, Tuple[float, ...]],
    ) -> Optional[Tuple[float, float]]:
        """Earliest point where the paths share road *at the same time*.

        Space and time are tested together, per sampled pair. Testing them
        separately — finding the closest approach anywhere along the paths and
        only then asking about timing — conflates "these routes cross"
        (true for nearly every pair at a junction) with "these two vehicles
        will be there together", and brings the whole network to a standstill.

        Returns ``(distance_along_a, distance_along_b)``, or ``None``.
        """
        threshold = _footprint_radius(va) + _footprint_radius(vb) + self.safety_margin
        proj_a = projections[va.vehicle_id]
        proj_b = projections[vb.vehicle_id]
        dists_a = samples[va.vehicle_id]
        dists_b = samples[vb.vehicle_id]

        a_moving = va.speed > _STOPPED_SPEED
        b_moving = vb.speed > _STOPPED_SPEED

        best: Optional[Tuple[float, float]] = None

        for ia, pa in enumerate(proj_a):
            if pa is None:
                continue
            sa = dists_a[ia]
            for ib, pb in enumerate(proj_b):
                if pb is None:
                    continue
                sb = dists_b[ib]

                if math.hypot(pa[0] - pb[0], pa[1] - pb[1]) >= threshold:
                    continue

                if a_moving and b_moving:
                    # Both under way: they only conflict if they arrive at
                    # this shared patch at roughly the same moment.
                    eta_a = sa / max(va.speed, self.eta_speed_floor)
                    eta_b = sb / max(vb.speed, self.eta_speed_floor)
                    if abs(eta_a - eta_b) > self.safe_headway:
                        continue
                # Otherwise at least one vehicle is stationary and is sampled
                # only at its current position, so proximity alone already
                # means "something is parked in the way".

                if best is None or sa + sb < best[0] + best[1]:
                    best = (sa, sb)
        return best

    # ------------------------------------------------------------------
    # Priority
    # ------------------------------------------------------------------

    @staticmethod
    def _inside_intersection(vehicle: Vehicle) -> bool:
        return vehicle.lane is not None and vehicle.lane.lane_id.lower().startswith(
            "conn"
        )

    @staticmethod
    def _has_left_intersection(vehicle: Vehicle) -> bool:
        """True once the vehicle is on an outgoing lane, i.e. on its way out."""
        return vehicle.lane is not None and "_out_" in vehicle.lane.lane_id.lower()

    def _select_yielder(
        self, va: Vehicle, vb: Vehicle, dist_a: float, dist_b: float
    ) -> Tuple[Vehicle, float]:
        """Pick which vehicle gives way. Total and order-independent.

        The rules are deliberately ordered from most to least stable, because
        a give-way decision that flips between ticks is worse than a wrong
        one: both vehicles alternately brake, neither clears, and the junction
        locks up. Right of way is therefore decided by *where the vehicles
        are*, never by how fast they happen to be going at this instant.
        """
        # 1. A vehicle stopped right on the conflict point is an obstacle, not
        #    a negotiating party — it cannot yield any harder than it already
        #    is. This is checked first, but deliberately requires the stopped
        #    vehicle to be AT the conflict (its sampled distance is 0 only
        #    when it is stationary), so a vehicle merely queuing behind the
        #    give-way line never steals priority from circulating traffic.
        a_blocking = va.speed <= _STOPPED_SPEED and dist_a <= 1e-9
        b_blocking = vb.speed <= _STOPPED_SPEED and dist_b <= 1e-9
        if a_blocking != b_blocking:
            yielder = vb if a_blocking else va
            return yielder, (dist_b if a_blocking else dist_a)

        # 2. A vehicle that has reached its outgoing lane has cleared the
        #    junction and is driving away. It must never be the one to stop.
        #
        #    _inside_intersection is a binary "on a connection lane or not",
        #    so a vehicle that had just left the box was lumped in with
        #    traffic that had not yet entered it, and the next rule handed
        #    priority to whatever was still crossing. The departing vehicle
        #    was then braked to a standstill a few metres onto an empty exit
        #    lane — leader None, gap infinite, emergency deceleration — where
        #    it blocked the box behind it. That is the mechanism by which the
        #    junction filled up and throughput fell as demand rose. Stopping a
        #    vehicle that is leaving can only ever make a junction worse.
        #
        #    Where both are heading for the same exit this is also the correct
        #    merge rule: the vehicle already established on the exit lane has
        #    priority over one still crossing to reach it.
        a_left = self._has_left_intersection(va)
        b_left = self._has_left_intersection(vb)
        if a_left != b_left:
            yielder = vb if a_left else va
            return yielder, (dist_b if a_left else dist_a)

        a_inside = self._inside_intersection(va)
        b_inside = self._inside_intersection(vb)

        # 3. Traffic already inside the junction has right of way over traffic
        #    still waiting to enter. Braking the vehicle that has not entered
        #    yet is also the only safe option: it can still stop at the
        #    give-way line, whereas stopping the one already crossing would
        #    leave it stranded across the other's path.
        if a_inside != b_inside:
            yielder = vb if a_inside else va
            return yielder, (dist_b if a_inside else dist_a)

        # 4. Both on the same side of the give-way line. The more committed
        #    vehicle (further along its current lane) keeps priority.
        if abs(va.position - vb.position) > 1e-9:
            yielder = va if va.position < vb.position else vb
            return yielder, (dist_a if yielder is va else dist_b)

        # 5. Deterministic tiebreak — never depends on iteration order, so
        #    identical seeds keep producing identical runs.
        yielder = va if va.vehicle_id > vb.vehicle_id else vb
        return yielder, (dist_a if yielder is va else dist_b)

    # ------------------------------------------------------------------
    # Pair filters
    # ------------------------------------------------------------------

    @staticmethod
    def _same_physical_path(va: Vehicle, vb: Vehicle) -> bool:
        """True when both vehicles occupy one continuous physical channel.

        Two vehicles on the identical lane object are plainly following each
        other. On a roundabout, two vehicles that entered from the same
        approach in the same numbered lane are also on one physical channel
        even though their connection-lane objects differ by turn intent —
        they share the entry taper and the circulating ring (see RoadNetwork's
        fixed-arc-length transition), and router.find_leader already resolves
        them by arc length.
        """
        if va.lane is None or vb.lane is None:
            return False
        if va.lane is vb.lane:
            return True

        # One vehicle is already on a lane the other still has to travel, so
        # they are in single file on a shared path and car-following governs
        # them. A junction's whole discharging platoon looks like this — one
        # vehicle on the approach lane, one crossing on the connection lane,
        # one already on the outgoing lane — and every pair of them spans two
        # different lanes of the one route.
        #
        # Without this the layer read each of those pairs as a crossing
        # conflict and commanded a full stop, so a signal discharged only two
        # or three vehicles per green instead of a saturated platoon, and
        # vehicles halted on an empty outgoing lane under emergency braking.
        #
        # This deliberately tests the *current* lanes, not whole routes.
        # Two vehicles merging into a shared outgoing lane from different
        # approaches do not satisfy it while they are still on their own
        # approaches, so a genuine merge is still arbitrated; it only exempts
        # them once the leader is demonstrably ahead on the shared path.
        if _vehicle_lane_on_other_route(va, vb) or _vehicle_lane_on_other_route(vb, va):
            return True

        id_a = va.lane.lane_id.lower()
        id_b = vb.lane.lane_id.lower()
        if id_a.startswith("conn_") and id_b.startswith("conn_"):
            parts_a = id_a.split("_")
            parts_b = id_b.split("_")
            if len(parts_a) >= 3 and len(parts_b) >= 3:
                # A roundabout's circulating lane index IS the ring, so two
                # vehicles sharing an index are nose-to-tail on one physical
                # ring no matter which approach each entered from.
                # router.find_leader resolves that case exactly, by arc
                # length around the ring (it applies the same same-index
                # rule), so claiming it here as well would double-brake
                # every follower on the ring and choke the roundabout.
                # Cross-ring weaving, where the indices differ, is precisely
                # what this layer is here to arbitrate.
                return parts_a[2] == parts_b[2]
        return False

    @staticmethod
    def _parallel_approach_lanes(va: Vehicle, vb: Vehicle) -> bool:
        """True for two vehicles in different lanes of the same approach.

        Incoming and outgoing lanes are named ``{n,s,e,w}_{in,out}_{index}``
        (see RoadNetwork), so a shared two-character prefix identifies one
        approach travelling in one direction. These lanes are parallel by
        construction, so a lateral separation of one lane width is the normal,
        safe state rather than a conflict.
        """
        if va.lane is None or vb.lane is None:
            return False
        id_a = va.lane.lane_id.lower()
        id_b = vb.lane.lane_id.lower()
        if id_a.startswith("conn") or id_b.startswith("conn"):
            return False
        return len(id_a) >= 2 and id_a[:2] == id_b[:2]


def apply_predictive_constraint(
    gap: float, leader: Optional[Any], braking_distance: Optional[float]
) -> Tuple[Optional[Any], float]:
    """Fold a predictive braking distance into an existing leader/gap pair.

    Returns the tighter of the two constraints. A predictive constraint is
    represented to IDM as a stationary obstacle at ``braking_distance``, which
    is exactly how the signal stop-line and conflict-zone layers already
    express themselves.
    """
    if braking_distance is None or braking_distance >= gap:
        return leader, gap

    from src.controllers.virtual_obstacle import VirtualObstacle

    return VirtualObstacle(position=0.0, speed=0.0, length=0.0), braking_distance
