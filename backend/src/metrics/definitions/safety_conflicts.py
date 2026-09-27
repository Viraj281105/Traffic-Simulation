"""Measurement-only surrogate safety metrics: TTC and PET.

Both are read-only observations computed from existing vehicle kinematics
and existing intersection geometry. Nothing here mutates a Vehicle, a
Lane, a ConflictManager reservation, or any other simulation state --
these functions only read `Vehicle.coords` / `.speed` / `.heading` /
`.lane` / `.position` and `ConflictManager.get_all_conflict_points()`
(itself a read-only accessor). They cannot change vehicle behaviour,
controller behaviour, or collision handling.

TTC (Time-to-Collision)
------------------------
Standard two-body constant-velocity TTC: each vehicle is approximated as a
circle (radius = half its bounding-box diagonal -- a conservative envelope
larger than the true oriented rectangle in most headings, matching common
practice for lightweight surrogate-safety proximity checks). Given current
position and velocity vectors, TTC is the smallest non-negative time at
which the two circles would touch under constant-velocity extrapolation.
This is the same closed-form used throughout traffic-conflict / ADAS
literature (e.g. Hayward 1972's original TTC formulation, generalised from
1D car-following to 2D). It does not predict what the vehicles will
actually do -- IDM, the controller, and the conflict manager will very
likely alter their trajectories before "TTC seconds" pass. It is an
instantaneous, extrapolated proximity read, not a collision forecast.

PET (Post-Encroachment Time)
------------------------------
Only implemented where the simulation already has a geometrically
validated notion of a shared conflict area: `ConflictManager`'s
pre-computed lane-pair crossing points, which exist only for
fixed_time_signal geometry (see VehiclePool.update's own comment on why a
straight-chord conflict point is geometrically wrong for a roundabout's
curved connection lanes -- reusing that reasoning here rather than
inventing new geometry for roundabouts). PET is therefore only measurable
for signal geometry; callers must treat `petApplicable=False` runs
(roundabout) as "not measured", never as "zero conflicts".
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from src.vehicles.vehicle import Vehicle

if TYPE_CHECKING:
    from src.intersection.conflict_manager import ConflictPoint

# ---------------------------------------------------------------------------
# TTC
# ---------------------------------------------------------------------------

# Relative-speed-squared below which two vehicles are treated as not closing
# at all, to avoid dividing by (near-)zero in the time-of-closest-approach
# formula. 0.01 (m/s)^2 corresponds to a relative speed of 0.1 m/s -- the
# same order of magnitude as this project's existing stopSpeedThreshold
# default (0.1 m/s), reused here for consistency rather than picking an
# unrelated new constant.
_MIN_CLOSING_SPEED_SQ: float = 0.01


def _velocity_vector(v: Vehicle) -> Tuple[float, float]:
    """Vehicle's 2D velocity vector, using the same heading convention as
    Vehicle.get_bounding_box (h_x = sin(heading), h_y = cos(heading))."""
    heading_rad = math.radians(v.heading)
    return (v.speed * math.sin(heading_rad), v.speed * math.cos(heading_rad))


def _effective_radius(v: Vehicle) -> float:
    """A single isotropic collision radius approximating this vehicle's
    rectangular footprint, used as its TTC collision envelope.

    The full bounding-box half-diagonal (hypot(length/2, width/2)) was
    tried first and rejected: for a typical 4x2 m vehicle it is about
    2.24 m, so two vehicles in ordinary adjacent lanes (3.5 m apart) would
    already read as "overlapping" before any velocity is even considered
    -- a circle large enough to contain the rectangle from every heading
    is necessarily wider than the vehicle across its short axis. Averaging
    the half-length and half-width instead gives an isotropic radius close
    to the vehicle's true footprint in an "average" orientation, at the
    cost of being an approximation rather than a bound in the worst case
    (nose-on or broadside). That trade-off is appropriate for a lightweight
    proximity read; it is not the exact-envelope guarantee the SAT-based
    collision detector provides.
    """
    return (v.length + v.width) / 4.0


def compute_ttc(va: Vehicle, vb: Vehicle) -> Optional[float]:
    """Time-to-collision between two vehicles under constant-velocity
    extrapolation, or None when TTC is undefined.

    Undefined (returns None) when:
      - the vehicles are not closing (separating, or the gap is momentarily
        constant) -- see module docstring;
      - the relative speed is at or near zero (nothing to extrapolate);
      - even at closest approach under constant velocity, the two vehicles'
        circular envelopes never come within collision range.
    """
    ax, ay = va.coords
    bx, by = vb.coords
    dpx, dpy = bx - ax, by - ay

    r = _effective_radius(va) + _effective_radius(vb)
    c = dpx * dpx + dpy * dpy - r * r
    if c <= 0.0:
        # Envelopes already overlap right now -- true regardless of
        # velocity direction, so this is checked before the closing test
        # below (which is degenerate when Δp is exactly zero).
        return 0.0

    dvx, dvy = _velocity_vector(vb)
    avx, avy = _velocity_vector(va)
    dvx -= avx
    dvy -= avy

    closing_dot = dpx * dvx + dpy * dvy
    if closing_dot >= 0.0:
        # Separating, or the gap isn't decreasing right now.
        return None

    rel_speed_sq = dvx * dvx + dvy * dvy
    if rel_speed_sq < _MIN_CLOSING_SPEED_SQ:
        return None

    # Solve |Δp + Δv t|^2 = r^2 for the smallest non-negative root:
    #   a t^2 + b t + c = 0
    a = rel_speed_sq
    b = 2.0 * closing_dot

    discriminant = b * b - 4.0 * a * c
    if discriminant < 0.0:
        # Closing, but the closest approach under constant velocity never
        # reaches collision range.
        return None

    t = (-b - math.sqrt(discriminant)) / (2.0 * a)
    return max(0.0, t)


def find_ttc_events(
    active_vehicles: List[Vehicle], search_radius: float
) -> List[Tuple[str, str, float]]:
    """All (vehicle_a_id, vehicle_b_id, ttc) triples with a defined TTC
    among `active_vehicles`.

    Candidate pairs are limited to (a) different lanes -- same-lane
    following is not a crossing/merging conflict and is already governed
    safely by IDM car-following, so including it would drown out genuine
    conflict signals with routine following -- and (b) within
    `search_radius` of each other, to bound cost on a busy network. Pairs
    on parallel or opposing-but-separated lanes are excluded naturally by
    the TTC physics itself (near-zero relative speed for same-direction
    parallel lanes; closest-approach distance exceeding the vehicles'
    combined radius for laterally-offset opposing lanes), not by a second,
    duplicated lane-classification pass -- see module docstring.
    """
    events: List[Tuple[str, str, float]] = []
    search_radius_sq = search_radius * search_radius

    # `coords` is a Vehicle property computed from lane geometry; guarded
    # with getattr rather than assumed, so a lightweight vehicle-like
    # object without real lane geometry (e.g. a test double that only
    # implements the handful of attributes an unrelated metric needs) is
    # silently skipped for TTC instead of raising -- this metric must not
    # be able to break unrelated callers that never asked for it.
    positioned: List[Tuple[Vehicle, float, float]] = []
    for v in active_vehicles:
        if v.lane is None:
            continue
        coords = getattr(v, "coords", None)
        if coords is None:
            continue
        positioned.append((v, coords[0], coords[1]))

    n = len(positioned)
    for i in range(n):
        va, ax, ay = positioned[i]

        for j in range(i + 1, n):
            vb, bx, by = positioned[j]
            if va.lane is vb.lane:
                continue

            dx, dy = bx - ax, by - ay
            if dx * dx + dy * dy > search_radius_sq:
                continue

            ttc = compute_ttc(va, vb)
            if ttc is not None:
                events.append((va.vehicle_id, vb.vehicle_id, ttc))

    return events


# ---------------------------------------------------------------------------
# PET
# ---------------------------------------------------------------------------


@dataclass
class _ZoneState:
    occupant_id: Optional[str] = None
    last_exit_id: Optional[str] = None
    last_exit_time: Optional[float] = None


@dataclass
class ConflictZoneOccupancyTracker:
    """Tracks, per pre-computed signal conflict point, when it is entered
    and left, and reports a PET value whenever a *different* vehicle enters
    a zone that a previous vehicle has cleanly left (no time overlap).

    Only meaningful for geometry with real ConflictManager crossing points
    (fixed_time_signal) -- see module docstring for why roundabouts are
    out of scope. The caller decides whether to use this tracker at all;
    it does not know or care what geometry it is being used for.
    """

    _zones: Dict[Tuple[str, str], _ZoneState] = field(default_factory=dict)

    def reset(self) -> None:
        self._zones.clear()

    def update(
        self,
        current_time: float,
        active_vehicles: List[Vehicle],
        conflict_points: List["ConflictPoint"],
        zone_radius: float,
    ) -> List[float]:
        """Advances the occupancy state machine by one tick and returns
        every newly-observed PET value this tick (usually 0 or 1 per
        conflict point, occasionally more with several conflict points)."""
        pet_values: List[float] = []

        # Vehicles currently within `zone_radius` (arc-length, matching
        # ConflictManager.ZONE_RADIUS's own units) of dist_on_a/dist_on_b,
        # indexed by lane_id for a fast lookup per conflict point below.
        by_lane: Dict[str, List[Vehicle]] = {}
        for v in active_vehicles:
            if v.lane is not None:
                by_lane.setdefault(v.lane.lane_id, []).append(v)

        for cp in conflict_points:
            key = (cp.lane_id_a, cp.lane_id_b)
            state = self._zones.setdefault(key, _ZoneState())

            occupant = self._occupant_in_zone(
                by_lane, cp.lane_id_a, cp.dist_on_a, zone_radius
            ) or self._occupant_in_zone(
                by_lane, cp.lane_id_b, cp.dist_on_b, zone_radius
            )

            if occupant is None:
                if state.occupant_id is not None:
                    # Zone just emptied.
                    state.last_exit_id = state.occupant_id
                    state.last_exit_time = current_time
                    state.occupant_id = None
                continue

            if occupant.vehicle_id == state.occupant_id:
                continue  # Same occupant still there -- no transition.

            if state.occupant_id is None and state.last_exit_time is not None:
                if occupant.vehicle_id != state.last_exit_id:
                    pet = current_time - state.last_exit_time
                    if pet >= 0.0:
                        pet_values.append(pet)

            state.occupant_id = occupant.vehicle_id

        return pet_values

    @staticmethod
    def _occupant_in_zone(
        by_lane: Dict[str, List[Vehicle]],
        lane_id: str,
        dist_on_lane: float,
        zone_radius: float,
    ) -> Optional[Vehicle]:
        candidates = by_lane.get(lane_id)
        if not candidates:
            return None
        in_zone = [
            v for v in candidates if abs(v.position - dist_on_lane) <= zone_radius
        ]
        if not in_zone:
            return None
        # Deterministic tie-break for the rare tick where more than one
        # vehicle is simultaneously within the zone radius (e.g. a leader
        # clearing as a follower arrives) -- lowest vehicle_id, purely for
        # a stable, reproducible choice, not a safety judgement.
        return min(in_zone, key=lambda v: v.vehicle_id)
