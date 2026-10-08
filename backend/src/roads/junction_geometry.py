"""Real-world junction geometry (V1.5).

V1.0-V1.4 built one shape: four arms on the compass axes, one lane width.
V1.5 lets a scenario describe the junction it actually has — three or four
arms, each on its own bearing, with its own lane count, lane width and
length — while keeping the separation the rest of the model relies on:

    scenario intent -> validated scenario -> geometry (this module)
    -> lanes and paths (roads/network.py) -> simulation

Nothing here runs per tick. The network asks it once, at set-up, where each
arm's lanes lie and where its stop line is; vehicle control never sees a
bearing.

Compass slots
-------------
Each arm occupies one of the four compass *slots* (north, east, south,
west). The slot is what gives a movement its meaning: a left turn from the
south slot leaves by the west slot, the north and south slots share the
"ns" signal phase, and a roundabout counts exits in slots. An arm's bearing
may differ from its slot's by up to MAX_SLOT_DEVIATION, so a junction whose
roads meet at 70 and 110 degrees is described faithfully, but arms never
change order around the junction — which is what keeps every one of those
rules valid. A junction that cannot be described this way (two arms, five
or more, or arms bunched so that two share a slot) is rejected with the
reason, never squeezed into a shape it does not have.

Frame
-----
Bearings are compass bearings: degrees clockwise from north, measured from
the junction centre outwards along the arm. World coordinates are x east, y
north. An arm's ``along`` axis points outwards; ``lateral`` is positive on
the arm's outgoing (exit) side, which in right-hand traffic is to the left
of a driver arriving on it. An arm on its slot's own bearing is laid out by
exact sign changes, not trigonometry, so the V1.0-V1.4 junction is
reproduced to the last bit.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import permutations
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from src.core.enums import Direction

# Clockwise order of the slots, and each slot's own bearing.
SLOT_ORDER: Tuple[Direction, ...] = (
    Direction.NORTH,
    Direction.EAST,
    Direction.SOUTH,
    Direction.WEST,
)
SLOT_BEARING: Dict[Direction, float] = {
    Direction.NORTH: 0.0,
    Direction.EAST: 90.0,
    Direction.SOUTH: 180.0,
    Direction.WEST: 270.0,
}
OPPOSITE_SLOT: Dict[Direction, Direction] = {
    Direction.NORTH: Direction.SOUTH,
    Direction.SOUTH: Direction.NORTH,
    Direction.EAST: Direction.WEST,
    Direction.WEST: Direction.EAST,
}

# How far (degrees) an arm may lie from its slot's bearing. Half the 90
# degrees between slots would let two arms meet in the middle; 30 leaves
# every pair of neighbouring arms at least 30 degrees apart before the
# separation rule below is even applied, and covers the skew of most real
# crossroads and T-junctions.
MAX_SLOT_DEVIATION: float = 30.0

# Smallest angle (degrees) between neighbouring arms. Closer than this the
# two carriageways overlap so far out from the junction that the stop lines
# would sit tens of metres back and the "junction" would be a long shared
# road the model does not represent.
MIN_ARM_SEPARATION: float = 45.0

# A junction needs at least three arms (two is a bend in a road); the slot
# model holds at most four.
MIN_ARMS: int = 3
MAX_ARMS: int = 4

# Approach lane (m) that must remain in front of the stop line on a skewed
# junction, whose stop lines are set further back than a square one's.
MIN_APPROACH_STORAGE: float = 20.0

# A straight-through path whose two arms are within this many degrees of a
# straight line is drawn as a straight segment (exactly the V1.0 path).
STRAIGHT_PATH_TOLERANCE: float = 1.0

# Minimum centreline turning radius (m) of each vehicle class's design
# vehicle: AASHTO, A Policy on Geometric Design of Highways and Streets
# (2018), Table 2-2 — P (passenger car) 6.4 m, CITY-BUS 11.5 m, SU-9
# single-unit truck 11.6 m. An SUV is covered by the P vehicle. AASHTO has
# no motorcycle design vehicle, so motorcycles are held to the car's value
# (conservative). These are design-guide inputs used to reject turns a class
# cannot make, not values calibrated by UrbanFlow.
DESIGN_TURNING_RADIUS: Dict[str, float] = {
    "car": 6.4,
    "suv": 6.4,
    "motorcycle": 6.4,
    "bus": 11.5,
    "truck": 11.6,
}
DESIGN_VEHICLE_NAMES: Dict[str, str] = {
    "car": "car",
    "suv": "SUV",
    "motorcycle": "motorcycle",
    "bus": "bus",
    "truck": "truck",
}


def normalise_bearing(bearing: float) -> float:
    return bearing % 360.0


def bearing_difference(a: float, b: float) -> float:
    """Smallest absolute angle (degrees) between two bearings."""
    d = abs(normalise_bearing(a) - normalise_bearing(b)) % 360.0
    return min(d, 360.0 - d)


def slot_deviation(direction: Direction, bearing: float) -> float:
    """Signed difference (degrees, clockwise positive) of a bearing from its
    slot's bearing, in (-180, 180]."""
    d = (normalise_bearing(bearing) - SLOT_BEARING[direction]) % 360.0
    return d - 360.0 if d > 180.0 else d


@dataclass(frozen=True)
class ArmGeometry:
    """One arm of the junction as the network lays it out."""

    direction: Direction
    bearing: float
    lanes: int
    lane_width: float
    length: float

    @property
    def on_slot(self) -> bool:
        """True when the arm lies exactly on its slot's axis (V1.0 layout)."""
        return normalise_bearing(self.bearing) == SLOT_BEARING[self.direction]

    @property
    def half_width(self) -> float:
        """Half the carriageway: as many lanes each way as the approach has."""
        return self.lanes * self.lane_width

    def unit(self) -> Tuple[float, float]:
        """Outward unit vector along the arm."""
        if self.on_slot:
            return {
                Direction.NORTH: (0.0, 1.0),
                Direction.EAST: (1.0, 0.0),
                Direction.SOUTH: (0.0, -1.0),
                Direction.WEST: (-1.0, 0.0),
            }[self.direction]
        rad = math.radians(self.bearing)
        return (math.sin(rad), math.cos(rad))

    def point(self, along: float, lateral: float) -> Tuple[float, float]:
        """World point ``along`` metres out from the centre on the arm's
        axis, ``lateral`` metres to its outgoing side."""
        if self.on_slot:
            # Exact sign changes: the V1.0 coordinates, bit for bit.
            if self.direction == Direction.NORTH:
                return (lateral, along)
            if self.direction == Direction.SOUTH:
                return (-lateral, -along)
            if self.direction == Direction.EAST:
                return (along, -lateral)
            return (-along, lateral)
        ux, uy = self.unit()
        # Outgoing side: the outward axis turned 90 degrees clockwise.
        nx, ny = uy, -ux
        return (along * ux + lateral * nx, along * uy + lateral * ny)


@dataclass(frozen=True)
class JunctionGeometry:
    """The arms that exist, in slot order."""

    arms: Dict[Direction, ArmGeometry]

    @property
    def directions(self) -> Tuple[Direction, ...]:
        return tuple(d for d in Direction if d in self.arms)

    @property
    def skewed(self) -> bool:
        return any(not arm.on_slot for arm in self.arms.values())


def configured_arms(config: Mapping[str, Any]) -> Optional[Tuple[Direction, ...]]:
    """``geometry.arms`` (V1.5): the slots that have an arm, or None when the
    config does not say (every slot has one, as before V1.5)."""
    geometry = config.get("geometry") or {}
    raw = geometry.get("arms") if isinstance(geometry, Mapping) else None
    if not isinstance(raw, list):
        return None
    found = []
    for value in raw:
        try:
            found.append(Direction(str(value).lower()))
        except ValueError:
            continue
    return tuple(d for d in Direction if d in found)


def present_arms(config: Mapping[str, Any]) -> Tuple[Direction, ...]:
    """The slots that have an arm (all four unless ``geometry.arms`` says)."""
    arms = configured_arms(config)
    return tuple(Direction) if arms is None else arms


def _road_items(config: Mapping[str, Any]) -> Dict[Direction, Mapping[str, Any]]:
    roads = config.get("roads") or {}
    found: Dict[Direction, Mapping[str, Any]] = {}
    for item in (roads.get("approaches") if isinstance(roads, Mapping) else None) or []:
        if not isinstance(item, Mapping):
            continue
        try:
            found[Direction(str(item.get("direction", "")).lower())] = item
        except ValueError:
            continue
    return found


def _finite(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def configured_bearings(config: Mapping[str, Any]) -> Dict[Direction, float]:
    """``roads.approaches[].bearing`` (V1.5) where set."""
    return {
        d: float(item["bearing"])
        for d, item in _road_items(config).items()
        if _finite(item.get("bearing"))
    }


def configured_lane_widths(config: Mapping[str, Any]) -> Dict[Direction, float]:
    """``roads.approaches[].laneWidth`` (V1.5) where set."""
    return {
        d: float(item["laneWidth"])
        for d, item in _road_items(config).items()
        if _finite(item.get("laneWidth"))
    }


def build_junction_geometry(
    lane_counts: Mapping[Direction, int],
    lengths: Mapping[Direction, float],
    lane_width: float,
    arms: Optional[Sequence[Direction]] = None,
    bearings: Optional[Mapping[Direction, float]] = None,
    lane_widths: Optional[Mapping[Direction, float]] = None,
) -> JunctionGeometry:
    present = tuple(Direction) if arms is None else tuple(arms)
    return JunctionGeometry(
        arms={
            d: ArmGeometry(
                direction=d,
                bearing=normalise_bearing(
                    float((bearings or {}).get(d, SLOT_BEARING[d]))
                ),
                lanes=int(lane_counts[d]),
                lane_width=float((lane_widths or {}).get(d, lane_width)),
                length=float(lengths[d]),
            )
            for d in Direction
            if d in present
        }
    )


def resolve_junction_geometry(config: Mapping[str, Any]) -> JunctionGeometry:
    """The geometry a compiled engine config describes."""
    # Imported here: network imports this module.
    from src.roads.lane_config import approach_length_for
    from src.roads.network import lane_counts, resolve_lanes_per_approach

    roads = config.get("roads") or {}
    counts = lane_counts(resolve_lanes_per_approach(roads))
    return build_junction_geometry(
        {d: counts[d.value] for d in Direction},
        {d: approach_length_for(roads, d) for d in Direction},
        float(roads.get("laneWidth", 3.5)),
        arms=present_arms(config),
        bearings=configured_bearings(config),
        lane_widths=configured_lane_widths(config),
    )


# ---------------------------------------------------------------------------
# Signal geometry
# ---------------------------------------------------------------------------


def _crossing_clearance(a: ArmGeometry, b: ArmGeometry) -> float:
    """Distance out along ``a`` beyond which its carriageway no longer
    overlaps ``b``'s.

    A point ``s`` out along a's axis and ``t`` across it (|t| <= a's half
    width) is ``|s sin(theta) + t cos(theta)|`` from b's axis, theta being
    the angle between the arms; it is clear of b's carriageway when that is
    more than b's half width for every t, i.e. when
    ``s > (w_b + w_a |cos theta|) / |sin theta|``. For perpendicular arms it
    is b's half width — the V1.0 box.
    """
    theta = math.radians(bearing_difference(a.bearing, b.bearing))
    return (b.half_width + a.half_width * abs(math.cos(theta))) / abs(math.sin(theta))


def signal_stop_distances(
    geometry: JunctionGeometry, setback: float
) -> Dict[Direction, float]:
    """Distance from the centre to each arm's stop line (where its incoming
    lanes end and its outgoing lanes begin).

    The V1.0 box is square and sized to the widest road crossing it. That is
    kept as the floor. On a skewed junction each arm's stop line is moved out
    until the arm is clear of every road crossing it (the opposite slot is
    the same road continuing, not a crossing), so vehicles held at a red are
    never standing on another arm's lanes.
    """
    floor = max((arm.half_width for arm in geometry.arms.values()), default=0.0)
    if not geometry.skewed:
        return {d: floor + setback for d in geometry.arms}
    found: Dict[Direction, float] = {}
    for d, arm in geometry.arms.items():
        need = floor
        for other_d, other in geometry.arms.items():
            if other_d == d or other_d == OPPOSITE_SLOT[d]:
                continue
            need = max(need, _crossing_clearance(arm, other))
        found[d] = need + setback
    return found


def line_intersection(
    p: Tuple[float, float],
    u: Tuple[float, float],
    q: Tuple[float, float],
    v: Tuple[float, float],
) -> Optional[Tuple[float, float]]:
    """Where the line through ``p`` along ``u`` meets the line through ``q``
    along ``v`` (None when they are parallel)."""
    denom = u[0] * v[1] - u[1] * v[0]
    if abs(denom) < 1e-9:
        return None
    t = ((q[0] - p[0]) * v[1] - (q[1] - p[1]) * v[0]) / denom
    return (p[0] + t * u[0], p[1] + t * u[1])


def uturn_radius(arm: ArmGeometry, lane_index: int) -> float:
    """Radius (m) of a signalised U-turn from incoming lane ``lane_index``.

    The turn runs as a half circle from the stop line into the kerb-side
    outgoing lane of the same arm, so its diameter is the distance between
    those two lane centres: (lane_index + 0.5) + (lanes - 0.5) lane widths.
    """
    return (lane_index + arm.lanes) * arm.lane_width / 2.0


def uturn_lanes_needed(radius: float, lane_width: float) -> int:
    """Fewest lanes each way an arm needs for a U-turn from its lane 1 to
    reach ``radius`` at ``lane_width``."""
    return max(1, math.ceil(2.0 * radius / lane_width - 1e-9))


# ---------------------------------------------------------------------------
# Roundabout geometry
# ---------------------------------------------------------------------------


def roundabout_mouth_half_angle(
    arm: ArmGeometry, entry_radius: float, splitter: float
) -> float:
    """Half the angle (degrees) an arm's two carriageways and splitter island
    span where they meet the roundabout (at the give-way line)."""
    ratio = (arm.half_width + splitter) / max(entry_radius, 1e-9)
    if ratio >= 1.0:
        return 90.0
    return math.degrees(math.asin(ratio))


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _arm_list(arms: Sequence[Direction]) -> str:
    return ", ".join(d.value for d in arms)


def arm_count_errors(arms: Sequence[Direction]) -> List[str]:
    if len(arms) < MIN_ARMS:
        return [
            f"geometry.arms lists {len(arms)} arm(s) ({_arm_list(arms) or 'none'}): "
            f"a junction needs {MIN_ARMS} or {MAX_ARMS} arms. Two arms are a "
            "bend in one road, not a junction; give a three-arm (T or Y) or a "
            "four-arm junction"
        ]
    return []


def geometry_errors(
    geometry: JunctionGeometry, is_roundabout: bool, stop_setback: float
) -> List[str]:
    """Every geometric rule a junction breaks, each saying what is wrong,
    where, why, and what would be valid."""
    errors = arm_count_errors(geometry.directions)
    if errors:
        return errors
    for d, arm in geometry.arms.items():
        dev = slot_deviation(d, arm.bearing)
        if abs(dev) > MAX_SLOT_DEVIATION + 1e-9:
            low = normalise_bearing(SLOT_BEARING[d] - MAX_SLOT_DEVIATION)
            high = normalise_bearing(SLOT_BEARING[d] + MAX_SLOT_DEVIATION)
            errors.append(
                f"roads.approaches[{d.value}].bearing ({arm.bearing:g}°) is "
                f"{abs(dev):.0f}° from the {d.value} slot ({SLOT_BEARING[d]:g}°). "
                f"Arms keep their compass order so that left, straight and right "
                f"keep their meaning, so an arm may lie at most "
                f"{MAX_SLOT_DEVIATION:g}° from its slot: give the {d.value} arm a "
                f"bearing from {low:g}° to {high:g}°, or describe this road as the "
                "arm of the slot it is nearest to"
            )
    if errors:
        return errors
    ordered = [geometry.arms[d] for d in SLOT_ORDER if d in geometry.arms]
    for i, arm in enumerate(ordered):
        nxt = ordered[(i + 1) % len(ordered)]
        gap = (nxt.bearing - arm.bearing) % 360.0
        if gap < MIN_ARM_SEPARATION - 1e-9:
            errors.append(
                f"The {arm.direction.value} and {nxt.direction.value} arms are only "
                f"{gap:.0f}° apart (bearings {arm.bearing:g}° and {nxt.bearing:g}°): "
                f"neighbouring arms must be at least {MIN_ARM_SEPARATION:g}° apart, "
                "or their carriageways overlap far beyond the junction, which the "
                "model does not represent. Spread the arms further apart"
            )
    if errors:
        return errors
    if is_roundabout:
        return errors  # see roundabout_geometry_errors
    if geometry.skewed:
        stops = signal_stop_distances(geometry, stop_setback)
        for d, arm in geometry.arms.items():
            storage = arm.length - stops[d]
            if storage < MIN_APPROACH_STORAGE - 1e-9:
                errors.append(
                    f"The {d.value} approach is too short for this junction's angles: "
                    f"its stop line has to sit {stops[d]:.1f} m from the centre to "
                    "clear the roads crossing it, which leaves "
                    f"{max(0.0, storage):.1f} m of approach lane; at least "
                    f"{MIN_APPROACH_STORAGE:g} m is needed. Make it at least "
                    f"{stops[d] + MIN_APPROACH_STORAGE:.0f} m long, or bring the arms "
                    "closer to right angles"
                )
    return errors


def roundabout_geometry_errors(
    geometry: JunctionGeometry, outer_radius: float
) -> List[str]:
    """Neighbouring arms must meet the ring without their mouths overlapping."""
    from src.roads.network import (
        ROUNDABOUT_ENTRY_SETBACK,
        ROUNDABOUT_SPLITTER_HALF_WIDTH,
    )

    errors: List[str] = []
    entry_radius = outer_radius + ROUNDABOUT_ENTRY_SETBACK
    ordered = [geometry.arms[d] for d in SLOT_ORDER if d in geometry.arms]
    for i, arm in enumerate(ordered):
        nxt = ordered[(i + 1) % len(ordered)]
        gap = (nxt.bearing - arm.bearing) % 360.0
        need = roundabout_mouth_half_angle(
            arm, entry_radius, ROUNDABOUT_SPLITTER_HALF_WIDTH
        ) + roundabout_mouth_half_angle(
            nxt, entry_radius, ROUNDABOUT_SPLITTER_HALF_WIDTH
        )
        if gap < need - 1e-9:
            errors.append(
                f"At the roundabout the {arm.direction.value} and "
                f"{nxt.direction.value} arms overlap where they meet the ring: they "
                f"are {gap:.0f}° apart but their carriageways and splitter islands "
                f"need {need:.0f}° at the give-way line ({entry_radius:g} m from the "
                "centre). Increase roundabout.outerRadius, spread the arms further "
                "apart, or use fewer or narrower lanes"
            )
    return errors


# ---------------------------------------------------------------------------
# Import foundation
# ---------------------------------------------------------------------------


def assign_slots(
    bearings: Sequence[float],
) -> Tuple[Optional[Dict[Direction, float]], List[str]]:
    """Map measured arm bearings (any order, e.g. from a survey or a map) onto
    compass slots, or explain why they cannot be.

    This is the step a future importer (OpenStreetMap, a GIS layer, a site
    survey) needs between "roads leave this node at these bearings" and a
    scenario document: it picks, for each arm, the slot that keeps the arms'
    order around the junction with the smallest largest deviation, and
    rejects junctions the slot model cannot hold rather than bending them.
    """
    values = [normalise_bearing(float(b)) for b in bearings]
    if not MIN_ARMS <= len(values) <= MAX_ARMS:
        return None, [
            f"{len(values)} arm(s) given: UrbanFlow models junctions of "
            f"{MIN_ARMS} or {MAX_ARMS} arms. "
            + (
                "Five or more arms need movement rules (which exit is 'left') "
                "and signal phases the slot model does not have; split the site "
                "into junctions of at most four arms or wait for multi-arm support"
                if len(values) > MAX_ARMS
                else "Two arms are a bend in one road, not a junction"
            )
        ]
    order = sorted(range(len(values)), key=lambda i: values[i])
    best: Optional[Tuple[float, Dict[Direction, float]]] = None
    for slots in permutations(SLOT_ORDER, len(values)):
        assignment = {slots[k]: values[order[k]] for k in range(len(values))}
        # Arms must keep their clockwise order: walking the slots clockwise
        # must visit the bearings in increasing (cyclic) order.
        seq = [assignment[d] for d in SLOT_ORDER if d in assignment]
        turns = sum(
            ((seq[(i + 1) % len(seq)] - seq[i]) % 360.0) for i in range(len(seq))
        )
        if abs(turns - 360.0) > 1e-6:
            continue
        worst = max(abs(slot_deviation(d, b)) for d, b in assignment.items())
        if best is None or worst < best[0] - 1e-9:
            best = (worst, assignment)
    if best is None or best[0] > MAX_SLOT_DEVIATION + 1e-9:
        worst = best[0] if best is not None else 180.0
        return None, [
            "These arm bearings ("
            + ", ".join(f"{v:g}°" for v in sorted(values))
            + f") cannot be placed on compass slots: the best placement leaves an "
            f"arm {worst:.0f}° from its slot, more than the {MAX_SLOT_DEVIATION:g}° "
            "the model allows (it keeps arms in compass order so that left, "
            "straight and right keep their meaning)"
        ]
    assignment = best[1]
    geometry = JunctionGeometry(
        arms={
            d: ArmGeometry(d, b, 1, 3.5, 200.0)
            for d, b in sorted(
                assignment.items(), key=lambda kv: SLOT_ORDER.index(kv[0])
            )
        }
    )
    errors = [
        e
        for e in geometry_errors(geometry, is_roundabout=True, stop_setback=0.0)
        if "apart" in e
    ]
    if errors:
        return None, errors
    return assignment, []


__all__ = [
    "ArmGeometry",
    "DESIGN_TURNING_RADIUS",
    "JunctionGeometry",
    "MAX_ARMS",
    "MAX_SLOT_DEVIATION",
    "MIN_APPROACH_STORAGE",
    "MIN_ARMS",
    "MIN_ARM_SEPARATION",
    "OPPOSITE_SLOT",
    "SLOT_BEARING",
    "SLOT_ORDER",
    "assign_slots",
    "bearing_difference",
    "build_junction_geometry",
    "configured_arms",
    "configured_bearings",
    "configured_lane_widths",
    "geometry_errors",
    "line_intersection",
    "present_arms",
    "resolve_junction_geometry",
    "roundabout_geometry_errors",
    "signal_stop_distances",
    "slot_deviation",
    "uturn_lanes_needed",
    "uturn_radius",
]
