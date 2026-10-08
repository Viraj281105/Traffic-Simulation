"""Per-approach lane configuration (V1.4) and roundabout lane assignment.

Pure functions only: nothing here touches a running simulation, so the same
rules serve the network that builds the junction, the spawner and lane
changing that use it, and the validation that decides whether a configuration
can be simulated at all. A rule stated once cannot drift between those.

Lane indices follow the rest of the model: right-hand traffic, lane 0 next to
the centreline (the left-most lane of an incoming carriageway). Ring lanes of
a roundabout are numbered the same way, 0 innermost.

Roundabout lane assignment (two-lane designation)
-------------------------------------------------
V1.0-V1.3 tied the ring to the approach: entry lane *i* was ring *i*, so the
ring count was the approach lane count, unequal approaches built rings of
different radii, and a vehicle leaving an inner ring cut across the outer one
with nothing deciding who went first (known limitation K1).

V1.4 gives the ring its own lane count (1 or 2) and the standard two-lane
designation: a **left turn uses the inner lane, a right turn the outer lane,
straight on either** — the entry lane's own. Entry lanes are right-aligned
onto the ring (the right-most entry lane feeds the outer lane); a one-lane
approach feeds both ring lanes; where an approach has one more lane than the
ring, its two left-hand lanes share the inner lane and take turns at the
give-way line (a merging entry). Ring lanes are right-aligned onto each exit;
where the exit road has one lane, both ring lanes leave into it. With as many
ring lanes as entry lanes, every path is exactly the V1.0-V1.3 one.

The weave this leaves — a vehicle leaving the inner lane crosses outer-lane
traffic that continues past its exit, and converges with outer-lane traffic
leaving by the same exit — is no longer left to chance: the roundabout
controller treats the stretch around each exit as a convergence zone that
vehicles from the two ring lanes take in strict arrival order, and lets a
vehicle start across the outer lane on entry only when there is room to
finish (controllers/roundabout.py).

Development record (measured, 2-3 lanes, 0.3-1.2 veh/s, seeds 1-3, 300 s):
an explicit inner-lane exit give-way alone locked the ring (standstills over
120 s, contacts 2 -> 17); a turbo designation (outer lane for right turns
only) was safe but added almost no capacity over one lane, since inner-lane
entries then face the same conflicting flow as on a one-lane ring.

Three circulating lanes would need a middle lane to weave across both others
at every exit, which has not been modelled or validated, so validation
rejects them rather than running it.
"""

from __future__ import annotations

from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Sequence, Tuple

from src.core.enums import Direction, TurnIntent

# The movements of V1.0-V1.4, which every default lane use is built from.
# A U-turn (V1.5) is only ever where a scenario's lane use puts it.
CORE_TURNS: Tuple[TurnIntent, ...] = (
    TurnIntent.LEFT,
    TurnIntent.STRAIGHT,
    TurnIntent.RIGHT,
)

# How many exits along the ring each movement leaves at, counted in compass
# slots (a three-arm junction keeps the slot of its missing arm).
EXIT_DISTANCE: Dict[TurnIntent, int] = {
    TurnIntent.RIGHT: 1,
    TurnIntent.STRAIGHT: 2,
    TurnIntent.LEFT: 3,
    TurnIntent.UTURN: 4,
}

# Left-to-right order of movements as a driver reads the lane arrows. A
# U-turn is left of a left turn: it starts from the lane nearest the centre.
TURN_ORDER: Dict[TurnIntent, int] = {
    TurnIntent.UTURN: -1,
    TurnIntent.LEFT: 0,
    TurnIntent.STRAIGHT: 1,
    TurnIntent.RIGHT: 2,
}

_TARGET: Dict[TurnIntent, Dict[Direction, Direction]] = {
    TurnIntent.LEFT: {
        Direction.NORTH: Direction.EAST,
        Direction.EAST: Direction.SOUTH,
        Direction.SOUTH: Direction.WEST,
        Direction.WEST: Direction.NORTH,
    },
    TurnIntent.STRAIGHT: {
        Direction.NORTH: Direction.SOUTH,
        Direction.EAST: Direction.WEST,
        Direction.SOUTH: Direction.NORTH,
        Direction.WEST: Direction.EAST,
    },
    TurnIntent.RIGHT: {
        Direction.NORTH: Direction.WEST,
        Direction.EAST: Direction.NORTH,
        Direction.SOUTH: Direction.EAST,
        Direction.WEST: Direction.SOUTH,
    },
    TurnIntent.UTURN: {d: d for d in Direction},
}

# Narrowest circulating lane (m) the model accepts. Signalised approach lanes
# go down to 2.5 m (schema); a ring lane carries vehicles on a curve, whose
# swept path is wider, so it needs at least this much.
MIN_CIRCULATING_LANE_WIDTH: float = 3.0

# Lateral clearance (m) a circulating lane must leave beside the widest
# vehicle in the mix.
CIRCULATING_LANE_SIDE_CLEARANCE: float = 0.5

# Ring lanes the V1.4 lane designation supports (see the module docstring).
MAX_CIRCULATING_LANES: int = 2


def target_direction(origin: Direction, turn: TurnIntent) -> Direction:
    """Arm a movement leaves by (right-hand traffic, counter-clockwise ring)."""
    return _TARGET[turn][origin]


def parse_turns(values: Any) -> Optional[FrozenSet[TurnIntent]]:
    """A lane's movement list (``["left", "straight"]``) as TurnIntents, or
    None if it is not a list of known movement names."""
    if not isinstance(values, (list, tuple)):
        return None
    turns = set()
    for value in values:
        try:
            turns.add(TurnIntent(str(value).lower()))
        except ValueError:
            return None
    return frozenset(turns)


def configured_lane_use(
    roads_cfg: Optional[Mapping[str, Any]],
) -> Dict[Direction, List[FrozenSet[TurnIntent]]]:
    """``roads.approaches[].laneUse`` per approach, lane 0 first.

    Approaches without a ``laneUse`` list are absent (they use the default
    policy). Malformed entries are skipped here; validation reports them.
    """
    found: Dict[Direction, List[FrozenSet[TurnIntent]]] = {}
    for item in (roads_cfg or {}).get("approaches") or []:
        if not isinstance(item, Mapping):
            continue
        try:
            direction = Direction(str(item.get("direction", "")).lower())
        except ValueError:
            continue
        raw = item.get("laneUse")
        if not isinstance(raw, list):
            continue
        lanes = [parse_turns(entry) for entry in raw]
        if any(lane is None for lane in lanes):
            continue
        found[direction] = [lane for lane in lanes if lane is not None]
    return found


def configured_approach_lengths(
    roads_cfg: Optional[Mapping[str, Any]],
) -> Dict[Direction, float]:
    """``roads.approaches[].length`` overrides, by approach."""
    found: Dict[Direction, float] = {}
    for item in (roads_cfg or {}).get("approaches") or []:
        if not isinstance(item, Mapping) or item.get("length") is None:
            continue
        try:
            found[Direction(str(item.get("direction", "")).lower())] = float(
                item["length"]
            )
        except (ValueError, TypeError):
            continue
    return found


def approach_length_for(
    roads_cfg: Optional[Mapping[str, Any]], direction: Direction
) -> float:
    roads_cfg = roads_cfg or {}
    return configured_approach_lengths(roads_cfg).get(
        direction, float(roads_cfg.get("approachLength", 200.0))
    )


def shortest_approach_length(roads_cfg: Optional[Mapping[str, Any]]) -> float:
    return min(approach_length_for(roads_cfg, d) for d in Direction)


# ---------------------------------------------------------------------------
# Roundabout lane assignment
# ---------------------------------------------------------------------------


def entry_home_ring_lane(lane_index: int, entry_lanes: int, ring_lanes: int) -> int:
    """Ring lane an entry lane feeds by default (right-aligned)."""
    if entry_lanes <= ring_lanes:
        return lane_index + (ring_lanes - entry_lanes)
    return max(0, lane_index - (entry_lanes - ring_lanes))


def designated_ring_lanes(ring_lanes: int, turn: TurnIntent) -> FrozenSet[int]:
    """Ring lanes a movement may use: a right turn (the next exit) only the
    outer lane, a left turn only the inner lane, straight on either."""
    if ring_lanes <= 1:
        return frozenset({0})
    if EXIT_DISTANCE[turn] == 1:
        return frozenset({ring_lanes - 1})
    if EXIT_DISTANCE[turn] >= 3:
        return frozenset({0})
    return frozenset(range(ring_lanes))


def ring_lane_for(
    lane_index: int,
    entry_lanes: int,
    ring_lanes: int,
    exit_lanes: int,
    turn: TurnIntent,
) -> Optional[int]:
    """Ring lane a movement from an entry lane circulates on, or None when that
    entry lane does not feed one the movement may use (see the module
    docstring). An entry lane takes its own (home) ring lane where it can;
    the left-most lane of an approach narrower than the ring may also
    continue inward. ``exit_lanes`` is accepted for symmetry with the exit
    mapping: every ring lane can leave into every exit."""
    del exit_lanes
    allowed = designated_ring_lanes(ring_lanes, turn)
    home = entry_home_ring_lane(lane_index, entry_lanes, ring_lanes)
    if home in allowed:
        return home
    lowest = 0 if (lane_index == 0 and entry_lanes < ring_lanes) else home
    reachable = [k for k in range(lowest, home + 1) if k in allowed]
    return max(reachable) if reachable else None


def ring_exit_lane(ring_lane: int, ring_lanes: int, exit_lanes: int) -> int:
    """Exit lane a ring lane leaves into (right-aligned; on a one-lane exit
    every ring lane leaves into it)."""
    return max(0, ring_lane + exit_lanes - ring_lanes)


def exit_merges(ring_lanes: int, exit_lanes: int) -> bool:
    """True where more ring lanes leave into an exit than it has lanes."""
    return ring_lanes > exit_lanes


def ring_lane_radius(
    inner_radius: float, outer_radius: float, ring_lanes: int, ring_lane: int
) -> float:
    # Written as (k + 0.5) * (w / C), the V1.0 expression, so legacy paths
    # are reproduced to the last bit.
    return inner_radius + (ring_lane + 0.5) * (
        (outer_radius - inner_radius) / max(1, ring_lanes)
    )


def roundabout_movement_routable(
    origin: Direction,
    lane_index: int,
    turn: TurnIntent,
    counts: Mapping[Direction, int],
    ring_lanes: int,
) -> bool:
    exit_lanes = counts[target_direction(origin, turn)]
    if exit_lanes <= 0:
        return False  # V1.5: no arm in that slot
    return (
        ring_lane_for(lane_index, counts[origin], ring_lanes, exit_lanes, turn)
        is not None
    )


def merging_entry_groups(entry_lanes: int, ring_lanes: int) -> List[List[int]]:
    """Groups of entry lanes that feed the same ring lane (only when an
    approach has more lanes than the ring). Lanes in a group take turns."""
    if entry_lanes <= ring_lanes:
        return []
    groups: Dict[int, List[int]] = {}
    for j in range(entry_lanes):
        groups.setdefault(entry_home_ring_lane(j, entry_lanes, ring_lanes), []).append(
            j
        )
    return [g for g in groups.values() if len(g) > 1]


# ---------------------------------------------------------------------------
# Default and configured lane use
# ---------------------------------------------------------------------------


def default_policy_turns(lane_index: int, lane_count: int) -> FrozenSet[TurnIntent]:
    """The V1.2 default: one lane carries everything; otherwise straight from
    any lane, left from the left-most, right from the right-most. Never a
    U-turn (V1.5): that is only where a scenario's lane use puts it."""
    if lane_count <= 1:
        return frozenset(CORE_TURNS)
    turns = {TurnIntent.STRAIGHT}
    if lane_index == 0:
        turns.add(TurnIntent.LEFT)
    if lane_index == lane_count - 1:
        turns.add(TurnIntent.RIGHT)
    return frozenset(turns)


def default_roundabout_lane_use(
    origin: Direction, counts: Mapping[Direction, int], ring_lanes: int
) -> List[FrozenSet[TurnIntent]]:
    """The default policy, restricted to what each lane can actually reach.

    When every approach has as many lanes as the ring this is exactly the
    default policy. Otherwise a movement the policy puts in a lane that
    cannot reach its exit is moved to the lanes that can (e.g. a left turn
    into a one-lane road from a two-lane ring must use the right-hand lane).
    """
    n = counts[origin]
    lanes = []
    for i in range(n):
        lanes.append(
            {
                t
                for t in default_policy_turns(i, n)
                if roundabout_movement_routable(origin, i, t, counts, ring_lanes)
            }
        )
    for turn in CORE_TURNS:
        if any(turn in lane for lane in lanes):
            continue
        for i in range(n):
            if roundabout_movement_routable(origin, i, turn, counts, ring_lanes):
                lanes[i].add(turn)
    return [frozenset(lane) for lane in lanes]


def default_signal_lane_use(
    origin: Direction, counts: Mapping[Direction, int]
) -> List[FrozenSet[TurnIntent]]:
    """The default policy at a signal, without movements into a slot that has
    no arm (V1.5). With all four arms it is exactly the default policy. A
    lane it leaves with no movement (the middle lane of a three-lane stem of
    a T) is returned empty: validation then asks for explicit lane use rather
    than guessing which movement that lane should carry."""
    n = counts[origin]
    return [
        frozenset(
            t
            for t in default_policy_turns(i, n)
            if counts[target_direction(origin, t)] > 0
        )
        for i in range(n)
    ]


def signal_exit_lane(
    lane_index: int,
    turn: TurnIntent,
    lane_use: Sequence[FrozenSet[TurnIntent]],
    exit_lanes: int,
) -> int:
    """Exit lane a signalised movement turns into.

    Turning lanes are paired with receiving lanes in order: the k-th lane
    from the left permitting a left turn turns into exit lane k, the k-th
    from the right permitting a right turn into the k-th exit lane from the
    right. Straight-ahead lanes keep their index (opposite approaches have
    equal lane counts), mapped proportionally if the counts differ. With the
    default policy this is exactly the V1.0 mapping: one left lane into exit
    lane 0, one right lane into the right-most exit lane.
    """
    if exit_lanes <= 1:
        return 0
    n = len(lane_use)
    if turn == TurnIntent.UTURN:
        # V1.5: into the kerb-side lane of the road it came along, which
        # gives the turn its widest possible radius (junction_geometry).
        return exit_lanes - 1
    if turn == TurnIntent.LEFT:
        order = [i for i in range(n) if TurnIntent.LEFT in lane_use[i]]
        k = order.index(lane_index) if lane_index in order else 0
        return min(k, exit_lanes - 1)
    if turn == TurnIntent.RIGHT:
        order = [i for i in reversed(range(n)) if TurnIntent.RIGHT in lane_use[i]]
        k = order.index(lane_index) if lane_index in order else 0
        return max(0, exit_lanes - 1 - k)
    if n <= 1:
        return exit_lanes // 2
    if lane_index == 0:
        return 0
    if lane_index == n - 1:
        return exit_lanes - 1
    out_idx = round(lane_index / (n - 1) * (exit_lanes - 1))
    return max(0, min(out_idx, exit_lanes - 1))


def lane_use_order_errors(
    label: str, lane_use: Sequence[FrozenSet[TurnIntent]]
) -> List[str]:
    """Signal lane arrows must not cross: every movement of a lane must be at
    or to the right of every movement of the lanes to its left."""
    errors: List[str] = []
    for i in range(len(lane_use) - 1):
        left, right = lane_use[i], lane_use[i + 1]
        if not left or not right:
            continue
        if max(TURN_ORDER[t] for t in left) > min(TURN_ORDER[t] for t in right):
            errors.append(
                f"{label} lanes {i + 1} and {i + 2} cross: lane {i + 1} allows "
                f"{_names(left)} but lane {i + 2}, to its right, allows "
                f"{_names(right)}. Arrange lanes left turn → straight → right "
                "turn from the centre line outwards"
            )
    return errors


def _names(turns: FrozenSet[TurnIntent]) -> str:
    return "/".join(t.value for t in sorted(turns, key=TURN_ORDER.__getitem__))


__all__ = [
    "CIRCULATING_LANE_SIDE_CLEARANCE",
    "CORE_TURNS",
    "EXIT_DISTANCE",
    "MAX_CIRCULATING_LANES",
    "MIN_CIRCULATING_LANE_WIDTH",
    "TURN_ORDER",
    "approach_length_for",
    "configured_approach_lengths",
    "configured_lane_use",
    "default_policy_turns",
    "default_roundabout_lane_use",
    "default_signal_lane_use",
    "entry_home_ring_lane",
    "lane_use_order_errors",
    "merging_entry_groups",
    "parse_turns",
    "ring_exit_lane",
    "ring_lane_for",
    "ring_lane_radius",
    "roundabout_movement_routable",
    "shortest_approach_length",
    "signal_exit_lane",
    "target_direction",
]
