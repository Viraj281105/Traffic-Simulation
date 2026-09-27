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

Stability
---------
The geometry above is recomputed from scratch every tick, but the *decision*
about who gives way must not be. It was originally re-derived each tick from
instantaneous speed, and that is a feedback loop: braking the yielder changes
the very speed the rule was keyed on, so two vehicles creeping out of adjacent
entry lanes swapped roles every tick — one stopped while the other moved, then
the reverse — at ~0.2 m/s, indefinitely. That limit cycle is what locked the
ring at high demand (and, as the vehicles crept, eventually produced contact).

Four things keep the decision stable, and the resolver therefore keeps a
small amount of per-run state (see :meth:`PredictiveConflictResolver.reset`):

* *structural* priority (a vehicle leaving beats one inside, which beats one
  still waiting) only ever moves one way as a vehicle progresses, so it cannot
  oscillate, and it is applied before anything speed-dependent;
* "stopped" is hysteretic — a vehicle stops counting as stopped only once it
  has genuinely got going, not the tick after it was braked to a crawl;
* a stopped vehicle whose box really is in a mover's path is an obstacle, and
  the mover yields. That is re-derived every tick rather than remembered —
  a remembered "A yields to B" is wrong once A has stopped in B's way — and,
  given the hysteresis, cannot flap;
* whatever remains is an arbitrary tie between equals, made once and remembered
  for as long as the pair stays in conflict: vehicles that came in through the
  same mouth go in the order they physically are, and vehicles from different
  approaches go first-in-first-out (a total order, so waits cannot form a
  cycle).
"""

from __future__ import annotations

import math
from typing import Any, Dict, FrozenSet, List, Optional, Sequence, Set, Tuple

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

# Speed (m/s) a stopped vehicle must exceed before it counts as moving again.
# Deliberately well above _STOPPED_SPEED: a vehicle that has just been released
# from a hold accelerates through 0.1-0.2 m/s within a tick, and treating that
# as "moving" is what let the yielder role flip every tick (see the module
# docstring). Matches the project-wide waitSpeedThreshold default.
_MOVING_SPEED: float = 0.5

# A stationary vehicle is compared against its neighbour's path by real
# oriented-box clearance rather than by circumscribed circle: it cannot be
# closing on anything, so the circle's orientation-independence buys nothing,
# while its radius (sum of two half-diagonals, ~5 m) exceeds the 3.5 m spacing
# of adjacent entry lanes and flagged every vehicle passing a queue as a
# conflict. The other vehicle's path is sampled this densely (metres) up to
# _DENSE_REACH because the boxes are small next to the coarse sample ladder.
#
# _BOX_CLEARANCE is how close a mover's box may come to a stationary vehicle's
# before the mover is made to stop. It is deliberately smaller than
# _SAFETY_MARGIN, which pads the coarse circle test that has to tolerate
# sampling error. Here the geometry is exact, and in a two-lane mouth a turning
# car's swinging tail routinely passes within ~0.5 m of its neighbour without
# touching. At 0.5 m that near-miss counted as a block, the vehicle that had
# priority stopped for the one giving way to it, and the pair crept in a limit
# cycle (measured: one contact in 32 runs, and a run that cleared 17 vehicles
# a minute instead of ~35). At 0.2 m both are gone.
_BOX_CLEARANCE: float = 0.2
_DENSE_STEP: float = 1.0
_DENSE_REACH: float = 20.0
_DENSE_DISTANCES: Tuple[float, ...] = tuple(
    i * _DENSE_STEP for i in range(int(_DENSE_REACH / _DENSE_STEP) + 1)
)

# How many calls (ticks) a remembered give-way decision outlives the conflict
# it was made for. Two vehicles that have just braked apart can drop out of
# conflict for a tick or two and come back; forgetting the decision in between
# meant it was re-made from the changed situation, sometimes the other way
# round, and the vehicle that had been told to go was then told to stop.
_DECISION_MEMORY_TICKS: int = 30

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


# (x, y, heading in degrees) — the pose of a vehicle at some point on its path.
_Pose = Tuple[float, float, float]


def _project_poses(
    vehicle: Vehicle, distances: Sequence[float]
) -> List[Optional[_Pose]]:
    """Return the vehicle's pose after travelling each of ``distances``.

    The walk follows the vehicle's real route lane by lane, so a projection
    that runs off the end of the current lane continues onto the next one
    using that lane's own geometry (including curved connection-lane
    waypoints). ``None`` marks a distance that runs past the end of the
    route — the vehicle will have left the network by then and can no longer
    conflict with anything.
    """
    results: List[Optional[_Pose]] = []
    if vehicle.lane is None or not vehicle.route:
        return [None] * len(distances)

    try:
        start_idx = vehicle.route.index(vehicle.lane)
    except ValueError:
        return [None] * len(distances)

    for distance in distances:
        remaining = vehicle.position + distance
        idx = start_idx
        pose: Optional[_Pose] = None
        while idx < len(vehicle.route):
            lane = vehicle.route[idx]
            if remaining <= lane.length:
                x, y = lane.get_point_at_distance(remaining)
                pose = (x, y, lane.get_heading_at_distance(remaining))
                break
            remaining -= lane.length
            idx += 1
        results.append(pose)
    return results


def _project_path(
    vehicle: Vehicle, distances: Sequence[float]
) -> List[Optional[Tuple[float, float]]]:
    """Positions only; see :func:`_project_poses`."""
    return [
        None if pose is None else (pose[0], pose[1])
        for pose in _project_poses(vehicle, distances)
    ]


def _boxes_overlap(
    pose_a: _Pose,
    vehicle_a: Vehicle,
    pose_b: _Pose,
    vehicle_b: Vehicle,
    clearance: float,
) -> bool:
    """True if the two vehicles' boxes come within ``clearance`` of each other.

    Separating-axis test on two oriented rectangles, each grown by half of
    ``clearance`` per side, so that boxes whose gap is under ``clearance`` count
    as overlapping.
    """
    pad = clearance / 2.0
    ax, ay, ah = pose_a
    bx, by, bh = pose_b
    rad_a, rad_b = math.radians(ah), math.radians(bh)
    # Each rectangle contributes its forward and right unit vectors as axes.
    axes = (
        (math.sin(rad_a), math.cos(rad_a)),
        (math.cos(rad_a), -math.sin(rad_a)),
        (math.sin(rad_b), math.cos(rad_b)),
        (math.cos(rad_b), -math.sin(rad_b)),
    )
    half_la, half_wa = vehicle_a.length / 2.0 + pad, vehicle_a.width / 2.0 + pad
    half_lb, half_wb = vehicle_b.length / 2.0 + pad, vehicle_b.width / 2.0 + pad
    dx, dy = bx - ax, by - ay
    for ux, uy in axes:
        reach_a = half_la * abs(math.sin(rad_a) * ux + math.cos(rad_a) * uy) + (
            half_wa * abs(math.cos(rad_a) * ux - math.sin(rad_a) * uy)
        )
        reach_b = half_lb * abs(math.sin(rad_b) * ux + math.cos(rad_b) * uy) + (
            half_wb * abs(math.cos(rad_b) * ux - math.sin(rad_b) * uy)
        )
        if abs(dx * ux + dy * uy) > reach_a + reach_b:
            return False
    return True


class PredictiveConflictResolver:
    """Computes per-vehicle braking constraints from projected trajectories.

    The *geometry* is recomputed from live vehicle states every call, so there
    is no reservation table. The give-way *decision* is not: it has to outlive
    a single tick or it oscillates (see the module docstring). The state kept
    for that is small and self-cleaning — everything is keyed by vehicle id and
    dropped as soon as the vehicle or the conflict is gone — but ids repeat
    from run to run, so :meth:`reset` must be called when a run restarts
    (:meth:`VehiclePool.reset` does).
    """

    def __init__(
        self,
        sample_distances: Sequence[float] = _SAMPLE_DISTANCES,
        safety_margin: float = _SAFETY_MARGIN,
        safe_headway: float = _SAFE_HEADWAY,
        eta_speed_floor: float = _MIN_SPEED_FOR_ETA,
    ) -> None:
        self.sample_distances: Tuple[float, ...] = tuple(sample_distances)
        self.safety_margin: float = safety_margin
        self.safe_headway: float = safe_headway
        self.eta_speed_floor: float = eta_speed_floor

        # Monotonic call counter; orders junction entries (see _entry_order).
        self._tick: int = 0
        # Vehicles currently counted as stopped, with hysteresis
        # (_STOPPED_SPEED to enter, _MOVING_SPEED to leave).
        self._stopped: Set[str] = set()
        # vehicle_id -> tick on which it was first seen inside the junction.
        self._entry_order: Dict[str, int] = {}
        # Remembered give-way decision per pair -> (yielder's id, last tick the
        # pair was in conflict).
        self._priority: Dict[FrozenSet[str], Tuple[str, int]] = {}
        # Per-call cache of densely projected poses for moving vehicles.
        self._dense_poses: Dict[str, List[Optional[_Pose]]] = {}

    def reset(self) -> None:
        """Forget every remembered decision. Call when a run restarts."""
        self._tick = 0
        self._stopped = set()
        self._entry_order = {}
        self._priority = {}
        self._dense_poses = {}

    def _refresh_vehicle_state(self, movers: List[Vehicle]) -> None:
        """Update stopped-ness and entry order, dropping vehicles that are gone."""
        self._tick += 1
        live = {v.vehicle_id for v in movers}
        stopped: Set[str] = set()
        entry_order: Dict[str, int] = {}
        for v in movers:
            vid = v.vehicle_id
            if v.speed <= _STOPPED_SPEED or (
                v.speed <= _MOVING_SPEED and vid in self._stopped
            ):
                stopped.add(vid)
            if vid in self._entry_order:
                entry_order[vid] = self._entry_order[vid]
            elif self._inside_intersection(v) or self._has_left_intersection(v):
                entry_order[vid] = self._tick
        self._stopped = stopped
        self._entry_order = entry_order
        self._dense_poses = {}
        self._priority = {
            pair: (yielder, seen)
            for pair, (yielder, seen) in self._priority.items()
            if self._tick - seen <= _DECISION_MEMORY_TICKS
            and all(vid in live for vid in pair)
        }

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
        self._refresh_vehicle_state(movers)
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
            dists = (0.0,) if v.vehicle_id in self._stopped else self.sample_distances
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
        dist_a, dist_b, by_box = hit

        yielder, dist = self._select_yielder(va, vb, dist_a, dist_b)

        if entry_gated_by_controller and not self._inside_intersection(yielder):
            # The junction controller owns the give-way decision here; adding a
            # second, independent gate only rejects gaps it already accepted.
            return

        # A vehicle already inside the junction is never asked to stop for one
        # that has not entered yet — stopping mid-junction blocks everything
        # behind it and seizes the ring — and _select_yielder guarantees that
        # by ranking "inside" above every other consideration. That conflict
        # is prevented earlier instead, at the give-way line.
        #
        # This used to be an explicit filter here with an exception for a
        # vehicle "parked on the conflict point". The exception is what broke
        # it: a vehicle the controller was holding at the give-way line counts
        # as stopped, so it qualified, and the vehicle already inside the mouth
        # beside it was braked to a halt for it. That is the deadlock.

        if by_box:
            # ``dist`` is where the yielder's box first comes within clearance
            # of the other's, so its nose is already at the obstacle there;
            # stopping one probe step short is all that is needed.
            allowed = max(0.0, dist - _DENSE_STEP)
        else:
            # Stop short of the conflict point by the yielder's own half-length
            # plus clearance, so its nose does not end up inside the crossing.
            allowed = max(0.0, dist - _footprint_radius(yielder) - self.safety_margin)
        existing = constraints.get(yielder.vehicle_id)
        if existing is None or allowed < existing:
            constraints[yielder.vehicle_id] = allowed

    def _dense_poses_for(self, vehicle: Vehicle) -> List[Optional[_Pose]]:
        """Fine-grained path poses, cached for the current call."""
        cached = self._dense_poses.get(vehicle.vehicle_id)
        if cached is None:
            cached = _project_poses(vehicle, _DENSE_DISTANCES)
            self._dense_poses[vehicle.vehicle_id] = cached
        return cached

    def _find_box_conflict(
        self, va: Vehicle, vb: Vehicle
    ) -> Optional[Tuple[float, float]]:
        """Conflict test for a pair in which at least one vehicle is stopped.

        A stopped vehicle occupies exactly the road under it, so the question
        is simply whether the other vehicle's path runs through that box (with
        the safety margin as clearance). There is no arrival-time question —
        the stopped vehicle is not going to arrive anywhere.

        Returns ``(distance_along_a, distance_along_b)``, or ``None``.
        """
        a_stopped = va.vehicle_id in self._stopped
        b_stopped = vb.vehicle_id in self._stopped
        threshold = _footprint_radius(va) + _footprint_radius(vb) + self.safety_margin

        if a_stopped and b_stopped:
            (pose_a,) = _project_poses(va, (0.0,))
            (pose_b,) = _project_poses(vb, (0.0,))
            if pose_a is None or pose_b is None:
                return None
            if _boxes_overlap(pose_a, va, pose_b, vb, _BOX_CLEARANCE):
                return (0.0, 0.0)
            return None

        still, mover = (va, vb) if a_stopped else (vb, va)
        (still_pose,) = _project_poses(still, (0.0,))
        if still_pose is None:
            return None
        # Forward path only: index 0 is where the mover already is. Braking
        # cannot help with a pair that is already that close, and in the mouth
        # a turning car's swinging tail is routinely within clearance of its
        # neighbour's box while pulling *away* from it. Testing that pose made
        # the mover stop for a vehicle it was leaving behind, which is the
        # other half of a limit cycle.
        for step, mover_pose in zip(
            _DENSE_DISTANCES[1:], self._dense_poses_for(mover)[1:]
        ):
            if mover_pose is None:
                break
            if math.hypot(
                mover_pose[0] - still_pose[0], mover_pose[1] - still_pose[1]
            ) < threshold and _boxes_overlap(
                mover_pose, mover, still_pose, still, _BOX_CLEARANCE
            ):
                return (0.0, step) if a_stopped else (step, 0.0)
        return None

    def _find_conflict(
        self,
        va: Vehicle,
        vb: Vehicle,
        projections: Dict[str, List[Optional[Tuple[float, float]]]],
        samples: Dict[str, Tuple[float, ...]],
    ) -> Optional[Tuple[float, float, bool]]:
        """Earliest point where the paths share road *at the same time*.

        Space and time are tested together, per sampled pair. Testing them
        separately — finding the closest approach anywhere along the paths and
        only then asking about timing — conflates "these routes cross"
        (true for nearly every pair at a junction) with "these two vehicles
        will be there together", and brings the whole network to a standstill.

        Returns ``(distance_along_a, distance_along_b, by_box)``, or ``None``.
        ``by_box`` marks a pair with a stationary member, resolved by exact box
        clearance (:meth:`_find_box_conflict`) rather than by the sampled ladder.
        """
        if va.vehicle_id in self._stopped or vb.vehicle_id in self._stopped:
            box_hit = self._find_box_conflict(va, vb)
            return None if box_hit is None else (box_hit[0], box_hit[1], True)

        threshold = _footprint_radius(va) + _footprint_radius(vb) + self.safety_margin
        proj_a = projections[va.vehicle_id]
        proj_b = projections[vb.vehicle_id]
        dists_a = samples[va.vehicle_id]
        dists_b = samples[vb.vehicle_id]

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

                # Both under way: they only conflict if they arrive at this
                # shared patch at roughly the same moment.
                eta_a = sa / max(va.speed, self.eta_speed_floor)
                eta_b = sb / max(vb.speed, self.eta_speed_floor)
                if abs(eta_a - eta_b) > self.safe_headway:
                    continue

                if best is None or sa + sb < best[0] + best[1]:
                    best = (sa, sb)
        return None if best is None else (best[0], best[1], False)

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

        Rules 1 and 2 are structural: a vehicle only ever progresses from
        outside to inside to leaving, so they cannot flip back and need no
        memory. They also come *first*. A stopped vehicle used to outrank them
        (as an "obstacle"), which let a vehicle the controller was holding at
        the give-way line beat one already inside the mouth beside it.
        Rule 3 is geometric and re-derived every tick. Whatever remains is an
        arbitrary tie between equals, remembered for as long as the pair stays
        in conflict.
        """
        # 1. A vehicle that has reached its outgoing lane has cleared the
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

        # 2. Traffic already inside the junction has right of way over traffic
        #    still waiting to enter. Braking the vehicle that has not entered
        #    yet is also the only safe option: it can still stop at the
        #    give-way line, whereas stopping the one already crossing would
        #    leave it stranded across the other's path.
        if a_inside != b_inside:
            yielder = vb if a_inside else va
            return yielder, (dist_b if a_inside else dist_a)

        # 3. A stopped vehicle in the way is an obstacle, not a negotiating
        #    party: it cannot yield any harder than it already is, and the
        #    mover has to stop for it. (Only reached for a pair the geometry
        #    says really does overlap — see _find_box_conflict — so a stopped
        #    vehicle merely nearby never claims priority.)
        #
        #    This is deliberately re-evaluated every tick and never
        #    remembered. A remembered "A yields to B" is wrong the moment A has
        #    stopped in B's path: B is then unconstrained and drives into it.
        #    It cannot flip-flop either, because "stopped" has hysteresis.
        a_stopped = va.vehicle_id in self._stopped
        b_stopped = vb.vehicle_id in self._stopped
        if a_stopped != b_stopped:
            yielder = vb if a_stopped else va
            return yielder, (dist_a if yielder is va else dist_b)

        # Same class and same motion state from here on: the choice is
        # arbitrary, so what matters is only that it is made once. Reuse the
        # decision already taken for this pair, if any.
        pair = frozenset((va.vehicle_id, vb.vehicle_id))
        remembered = self._priority.get(pair)
        if remembered is not None:
            yielder = va if va.vehicle_id == remembered[0] else vb
        else:
            yielder = self._first_decision(va, vb, a_inside)
        self._priority[pair] = (yielder.vehicle_id, self._tick)
        return yielder, (dist_a if yielder is va else dist_b)

    @staticmethod
    def _entered_from(vehicle: Vehicle) -> Optional[str]:
        """Approach a vehicle inside the junction came in from, e.g. ``"west"``.

        Connection lanes are named ``conn_{origin}_{lane}_{turn}``.
        """
        parts = vehicle.lane.lane_id.lower().split("_") if vehicle.lane else []
        return parts[1] if len(parts) >= 4 and parts[0] == "conn" else None

    def _first_decision(self, va: Vehicle, vb: Vehicle, both_inside: bool) -> Vehicle:
        """Decide a same-class, same-motion pair that has no decision yet."""
        if both_inside:
            origin = self._entered_from(va)
            if origin is not None and origin == self._entered_from(vb):
                # 4. Two vehicles that came in through the same mouth (adjacent
                #    lanes) share it and merge or diverge within a few metres,
                #    so the physical truth is simply who is ahead: the one
                #    further along goes first. Entry order is no guide here —
                #    two vehicles released together have no meaningful order,
                #    and giving way to the one *behind* leaves both wedged in
                #    the mouth. ``position`` is comparable because both lanes
                #    start at the same give-way line. (Distance to the conflict
                #    would be the other candidate, but it moves as the yielder
                #    brakes and so can invert the very decision it produced.)
                if abs(va.position - vb.position) > 1e-9:
                    return va if va.position < vb.position else vb

            # 5. Vehicles from different approaches: first in, first through.
            #    Entry order is a total order fixed at the moment of entry, so
            #    it cannot flip, and because every wait it creates points at an
            #    earlier entrant, no cycle of vehicles each waiting for the next
            #    can form. (Comparing ``position`` across different approaches,
            #    as this used to, is meaningless: connection lanes differ in
            #    length by turn, so 16 m along a 55 m lane says nothing about
            #    53 m along a 73 m one.)
            order_a = self._entry_order.get(va.vehicle_id, self._tick)
            order_b = self._entry_order.get(vb.vehicle_id, self._tick)
            if order_a != order_b:
                return va if order_a > order_b else vb
        # 6. Both still on approach lanes, which are all the same length, so
        #    the vehicle further along its lane is the more committed one.
        elif abs(va.position - vb.position) > 1e-9:
            return va if va.position < vb.position else vb

        # 7. Deterministic tiebreak — never depends on iteration order, so
        #    identical seeds keep producing identical runs.
        return va if va.vehicle_id > vb.vehicle_id else vb

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
