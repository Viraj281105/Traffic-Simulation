import math
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Sequence, Tuple

from src.core.enums import Direction, TurnIntent
from src.roads.approach import Approach
from src.roads.lane import Lane
from src.roads.lane_config import (
    MAX_CIRCULATING_LANES,
    default_roundabout_lane_use,
    entry_home_ring_lane,
    ring_exit_lane,
    ring_lane_for,
    ring_lane_radius,
    signal_exit_lane,
    target_direction,
)

# Radial clearance (metres) between the outer edge of a roundabout's
# circulating ring and the point where an incoming lane ends (its give-way
# line) / an outgoing lane begins.
#
# Without it, an incoming lane ended exactly at ``outer_radius`` — i.e. on
# the ring's outer edge. A vehicle held at that give-way line has its centre
# there and its *body* extends back along the lane, so roughly half its
# length protruded radially into the outermost circulating lane. Circulating
# traffic then physically overlapped stationary, correctly-yielding vehicles,
# which the collision audit (rightly) counted as a collision even though no
# controller had made a wrong decision. The setback covers half of the
# longest vehicle the spawner generates (VehicleSpawner's vehicleLength max
# defaults to 5.0 m -> 2.5 m) plus a small margin.
ROUNDABOUT_ENTRY_SETBACK: float = 4.0

# Arc length (metres) over which a roundabout connection lane transitions
# radially between the entry point and its steady circulating radius (and
# again between that radius and the exit point). See the derivation of
# ``t_trans`` in _get_or_create_connection_lane for why this is anchored to
# a fixed arc length rather than a fraction of each path's angular span.
ROUNDABOUT_TRANSITION_ARC: float = 10.0

# Arc length (metres, at the ring lane's radius) over which a path leaving the
# INNER lane of a two-lane ring spirals out to its exit lane (V1.4).
#
# With the shared 10 m it converged on the outer lane's path leaving by the
# same exit to 2.25 m centre to centre — not enough for two 2.2 m cars, let
# alone a bus, side by side. Measured separations (10/20 m and 12/22 m rings,
# every same-exit pair, 0.25 m sampling): 10 m -> 2.25 m, 8 m -> 2.5 m,
# 6 m -> 2.8 m, 4 m -> 3.2 m; longer arcs (15-45 m) are worse, because the
# spiral then cuts across the outer lane while it still carries traffic
# (down to 0 m). 5 m keeps about 3.0 m. The outer lane's own exit arc made no
# difference and is unchanged; one-lane rings keep ROUNDABOUT_TRANSITION_ARC,
# so their geometry is exactly as before. The sharper curve is honoured by the
# curve-speed rule (vehicles/speed_profile.py), so it costs speed, not safety.
ROUNDABOUT_INNER_EXIT_TRANSITION_ARC: float = 5.0

# Half-width (metres) of the splitter island between a roundabout approach's
# entry and exit carriageways.
#
# Real roundabout approaches are divided by a physical island; only signalised
# approaches are separated by nothing more than a centreline. Without it the
# entry and exit centrelines here sat one lane width (3.5 m) apart, which is
# ample for two vehicles travelling parallel but not for the mouth, where the
# two paths diverge by ~50 degrees. A 4.5 m vehicle turning through that angle
# sweeps its rectangle into the neighbouring channel, so vehicles in correctly
# separated lanes were recorded as colliding. Widening the separation to a
# realistic island removes the cause instead of excusing the symptom.
ROUNDABOUT_SPLITTER_HALF_WIDTH: float = 1.5

# Clearance (metres) between a signalised junction's conflict area and the
# stop line where waiting vehicles are held.
#
# The conflict area was taken to end at lane_count * lane_width — 3.5 m from
# the centre for a single-lane approach — and the stop line sat exactly on it.
# A 4.5 m vehicle held there therefore had well over half its body inside the
# junction box, directly on the paths of the turning movements crossing it, so
# traffic running a legitimate green struck vehicles that were correctly
# stopped at their own red. Real stop lines are set back from the conflict
# area for the same reason. This is the signalised counterpart of
# ROUNDABOUT_ENTRY_SETBACK above.
SIGNAL_STOP_LINE_SETBACK: float = 3.5

_ALL_TURNS: FrozenSet[TurnIntent] = frozenset(TurnIntent)


def lane_permitted_turns(lane_index: int, lane_count: int) -> FrozenSet[TurnIntent]:
    """Movements a vehicle may make from incoming lane ``lane_index``.

    The single lane-use policy of the model (right-hand traffic, lane 0 next
    to the centreline):

    * a single lane carries every movement;
    * straight-ahead traffic may use any lane;
    * left turns only from the left-most lane (0), right turns only from the
      right-most lane (``lane_count - 1``).

    It is the rule V1.0 already applied implicitly (VehicleSpawner placed
    turning vehicles only in their own lane and through traffic anywhere);
    stating it once lets spawning and lane changing share it.
    """
    if lane_count <= 1:
        return _ALL_TURNS
    turns = {TurnIntent.STRAIGHT}
    if lane_index == 0:
        turns.add(TurnIntent.LEFT)
    if lane_index == lane_count - 1:
        turns.add(TurnIntent.RIGHT)
    return frozenset(turns)


def resolve_lanes_per_approach(roads_cfg: Optional[Mapping[str, Any]]) -> Any:
    """Lane count per approach from a ``roads`` config section.

    ``lanesPerApproach`` is either one count for every approach or a
    per-direction object; ``approaches[].lanes`` (versioned schema) overrides
    the count of the approach it names. Returns an int when every approach
    has the same count and none was overridden (exactly what V1.0 passed to
    the network), otherwise a {direction: count} dict.
    """
    roads_cfg = roads_cfg or {}
    base = roads_cfg.get("lanesPerApproach", 2)
    overrides: Dict[str, int] = {}
    for item in roads_cfg.get("approaches") or []:
        if isinstance(item, Mapping) and item.get("lanes") is not None:
            overrides[str(item.get("direction", "")).lower()] = int(item["lanes"])
    if not overrides:
        return base
    per_direction: Dict[str, int] = {}
    for d in Direction:
        if isinstance(base, Mapping):
            per_direction[d.value] = int(base.get(d.value, 2))
        else:
            per_direction[d.value] = int(base)
    per_direction.update({k: v for k, v in overrides.items() if k in per_direction})
    return per_direction


def resolve_circulating_lanes(config: Mapping[str, Any]) -> Optional[int]:
    """The roundabout's ring lane count from ``geometry.circulatingLanes``
    (V1.4), or None to make the ring as wide as the widest approach — the
    V1.0-V1.3 behaviour. ``controller.circulatingLanes`` is the reserved V1.0
    field that never had an effect and still has none, so configs that carry
    it keep simulating exactly what they always did."""
    geometry = config.get("geometry") or {}
    value = geometry.get("circulatingLanes") if isinstance(geometry, Mapping) else None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(value)


def lane_counts(lanes_per_approach: Any) -> Dict[str, int]:
    """{direction: lane count} for an int or per-direction lane setting."""
    if isinstance(lanes_per_approach, Mapping):
        return {d.value: int(lanes_per_approach.get(d.value, 2)) for d in Direction}
    return {d.value: int(lanes_per_approach) for d in Direction}


class RoadNetwork:
    """Manages the network topology of the intersection, containing approaches and lanes.

    Connection lanes (the lanes that traverse the intersection) are created once
    and cached so that every vehicle travelling the same path shares the *same*
    ``Lane`` instance.  This is critical for correct leader detection — vehicles
    on the same physical path must see each other through the lane's vehicle list.
    """

    def __init__(self) -> None:
        self._incoming: Dict[Direction, Approach] = {}
        self._outgoing: Dict[Direction, Approach] = {}

        # Cache of connection lanes: (origin_dir, lane_idx, turn_intent) → Lane
        self._connection_lane_cache: Dict[Tuple[Direction, int, TurnIntent], Lane] = {}

        # Lane-use overrides set by a controller (see set_lane_use).
        self._lane_use: Dict[Tuple[Direction, int], FrozenSet[TurnIntent]] = {}

        # Lane use the scenario configures (V1.4, roads.approaches[].laneUse),
        # and the roundabout's own default where approaches and ring differ.
        # Both sit under a controller's set_lane_use and above the default
        # policy (see permitted_turns).
        self._configured_lane_use: Dict[
            Tuple[Direction, int], FrozenSet[TurnIntent]
        ] = {}

        # Circulating lanes of a roundabout (V1.4); 0 for a signal.
        self.circulating_lanes: int = 0
        # Arc length over which an inner-lane path spirals out to its exit.
        self.inner_exit_transition_arc: float = ROUNDABOUT_INNER_EXIT_TRANSITION_ARC

    def add_incoming_approach(self, approach: Approach) -> None:
        self._incoming[approach.direction] = approach

    def add_outgoing_approach(self, approach: Approach) -> None:
        self._outgoing[approach.direction] = approach

    def get_incoming_approach(self, direction: Direction) -> Approach:
        if direction not in self._incoming:
            raise KeyError(f"No incoming approach for direction {direction}")
        return self._incoming[direction]

    def get_outgoing_approach(self, direction: Direction) -> Approach:
        if direction not in self._outgoing:
            raise KeyError(f"No outgoing approach for direction {direction}")
        return self._outgoing[direction]

    def lane_count(self, direction: Direction) -> int:
        """Number of incoming lanes on ``direction``'s approach (0 if none)."""
        approach = self._incoming.get(direction)
        return len(approach.get_lanes()) if approach is not None else 0

    def permitted_turns(
        self, direction: Direction, lane_index: int
    ) -> FrozenSet[TurnIntent]:
        """Movements allowed from incoming lane ``lane_index`` of ``direction``:
        the controller's lane use if it set one, else the default policy
        (:func:`lane_permitted_turns`)."""
        override = self._lane_use.get((direction, lane_index))
        if override is not None:
            return override
        configured = self._configured_lane_use.get((direction, lane_index))
        if configured is not None:
            return configured
        return lane_permitted_turns(lane_index, self.lane_count(direction))

    def configured_turns(
        self, direction: Direction, lane_index: int
    ) -> Optional[FrozenSet[TurnIntent]]:
        """The scenario's own lane use for a lane (V1.4), if it sets one.

        A controller reads this to show the lane's arrows on its signal head;
        None means the lane follows the default policy.
        """
        return self._configured_lane_use.get((direction, lane_index))

    def lane_use(self, direction: Direction) -> List[FrozenSet[TurnIntent]]:
        """Movements permitted from each incoming lane of an approach."""
        return [
            self.permitted_turns(direction, i)
            for i in range(self.lane_count(direction))
        ]

    def set_lane_use(
        self, direction: Direction, lane_index: int, turns: FrozenSet[TurnIntent]
    ) -> None:
        """Restrict an incoming lane to ``turns`` (a controller's lane markings).

        A controller that releases a lane only for some movements (a signal
        head showing a left arrow alone) makes that lane a lane for those
        movements; spawning and lane changing then respect it.
        """
        if not turns:
            raise ValueError("A lane must permit at least one movement")
        self._lane_use[(direction, lane_index)] = frozenset(turns)

    def get_all_connection_lanes(self) -> List[Lane]:
        """Return every cached connection lane (useful for conflict pre-computation)."""
        return list(self._connection_lane_cache.values())

    def validate_connectivity(self) -> None:
        # Check all directions are present in both incoming and outgoing
        for d in Direction:
            if d not in self._incoming:
                raise ValueError("Missing incoming approach")
            if d not in self._outgoing:
                raise ValueError("Missing outgoing approach")

            if len(self._incoming[d].get_lanes()) == 0:
                raise ValueError(f"Incoming approach {d} has zero lanes")
            if len(self._outgoing[d].get_lanes()) == 0:
                raise ValueError(f"Outgoing approach {d} has zero lanes")

    def setup_default_intersection(
        self,
        approach_length: float = 100.0,
        lane_width: float = 3.5,
        lanes_per_approach: Any = 2,
        is_roundabout: bool = False,
        inner_radius: float = 10.0,
        outer_radius: float = 20.0,
        design_vehicle_allowance: float = 0.0,
        approach_lengths: Optional[Mapping[Direction, float]] = None,
        lane_use: Optional[Mapping[Direction, Sequence[FrozenSet[TurnIntent]]]] = None,
        circulating_lanes: Optional[int] = None,
    ) -> None:
        """Build the four-arm junction.

        ``design_vehicle_allowance`` (V1.1) is how much longer than the 5 m
        reference car the longest vehicle using the junction is. A junction
        that serves buses and trucks is laid out for them (the design-vehicle
        principle): every signal stop line is set back by the allowance, and
        since the turning paths run from stop line to stop line, their corner
        radii grow with it. Without it a 12 m truck turning right in a
        one-lane junction (corner radius about 5 m) was still half on its
        approach while its nose was across the crossing paths, and the box
        locked. Zero — the V1.0 geometry — whenever no vehicle is longer
        than 5 m. The roundabout's geometry is set by its radii and is not
        changed.

        V1.4: ``approach_lengths`` gives individual approaches their own
        length (others use ``approach_length``); ``lane_use`` is the
        scenario's lane use per approach (lane 0 first); and
        ``circulating_lanes`` is the roundabout's ring lane count, which
        defaults to the widest approach — the V1.0-V1.3 relationship, under
        which every path is laid out exactly as before.
        """
        self.is_roundabout = is_roundabout
        self.inner_radius = inner_radius
        self.outer_radius = outer_radius
        # Distance from the conflict area to each signal stop line.
        self.stop_line_setback = SIGNAL_STOP_LINE_SETBACK + max(
            0.0, design_vehicle_allowance
        )

        # Clear existing
        self._incoming.clear()
        self._outgoing.clear()
        self._connection_lane_cache.clear()
        self._lane_use.clear()
        self._configured_lane_use.clear()

        counts = lane_counts(lanes_per_approach)
        # Unset: as wide as the widest approach, up to the lanes the V1.4
        # designation supports (a 3-lane approach then merges onto 2).
        self.circulating_lanes = (
            int(
                circulating_lanes
                or min(max(counts.values()) or 1, MAX_CIRCULATING_LANES)
            )
            if is_roundabout
            else 0
        )
        lengths = {
            d: float((approach_lengths or {}).get(d, approach_length))
            for d in Direction
        }
        self.approach_lengths = lengths
        # The signalised junction box is square and sized to the widest road
        # crossing it. Each stop line used to be set from its OWN approach's
        # lane count, which only coincides with that when every approach has
        # the same number of lanes. With unequal counts a narrow approach's
        # stop line sat inside the wider crossing road, so its waiting
        # vehicles were parked on that road's travel lanes and the junction
        # locked solid (N1/S2/E1/W2 at 0.8 veh/s, seed 5: 14 of 171 vehicles
        # got through in 240 s). Equal counts give exactly the old boundary.
        widest_road = max(counts.values()) if counts else 1

        for d in Direction:
            in_approach = Approach(d)
            out_approach = Approach(d)
            # This arm's own length (the lane coordinates below read it).
            approach_length = lengths[d]

            # Support both int and dict configurations
            if isinstance(lanes_per_approach, dict):
                lane_count = lanes_per_approach.get(d.value, 2)
            else:
                lane_count = int(lanes_per_approach)

            boundary = (
                (outer_radius + ROUNDABOUT_ENTRY_SETBACK)
                if is_roundabout
                else (widest_road * lane_width + self.stop_line_setback)
            )

            # Roundabout approaches carry a splitter island between the entry
            # and exit carriageways; signalised approaches do not, so their
            # geometry is left exactly as it was.
            splitter = ROUNDABOUT_SPLITTER_HALF_WIDTH if is_roundabout else 0.0

            for i in range(lane_count):
                if d == Direction.NORTH:
                    # Incoming: North to South (moves down, x < 0)
                    in_x = -((i + 0.5) * lane_width + splitter)
                    in_lane = Lane(
                        f"n_in_{i}",
                        start_x=in_x,
                        start_y=approach_length,
                        end_x=in_x,
                        end_y=boundary,
                    )
                    # Outgoing: South to North (moves up, x > 0)
                    out_x = (i + 0.5) * lane_width + splitter
                    out_lane = Lane(
                        f"n_out_{i}",
                        start_x=out_x,
                        start_y=boundary,
                        end_x=out_x,
                        end_y=approach_length,
                    )

                elif d == Direction.SOUTH:
                    # Incoming: South to North (moves up, x > 0)
                    in_x = (i + 0.5) * lane_width + splitter
                    in_lane = Lane(
                        f"s_in_{i}",
                        start_x=in_x,
                        start_y=-approach_length,
                        end_x=in_x,
                        end_y=-boundary,
                    )
                    # Outgoing: North to South (moves down, x < 0)
                    out_x = -((i + 0.5) * lane_width + splitter)
                    out_lane = Lane(
                        f"s_out_{i}",
                        start_x=out_x,
                        start_y=-boundary,
                        end_x=out_x,
                        end_y=-approach_length,
                    )

                elif d == Direction.EAST:
                    # Incoming: East to West (moves left, y > 0)
                    in_y = (i + 0.5) * lane_width + splitter
                    in_lane = Lane(
                        f"e_in_{i}",
                        start_x=approach_length,
                        start_y=in_y,
                        end_x=boundary,
                        end_y=in_y,
                    )
                    # Outgoing: West to East (moves right, y < 0)
                    out_y = -((i + 0.5) * lane_width + splitter)
                    out_lane = Lane(
                        f"e_out_{i}",
                        start_x=boundary,
                        start_y=out_y,
                        end_x=approach_length,
                        end_y=out_y,
                    )

                elif d == Direction.WEST:
                    # Incoming: West to East (moves right, y < 0)
                    in_y = -((i + 0.5) * lane_width + splitter)
                    in_lane = Lane(
                        f"w_in_{i}",
                        start_x=-approach_length,
                        start_y=in_y,
                        end_x=-boundary,
                        end_y=in_y,
                    )
                    # Outgoing: East to West (moves left, y > 0)
                    out_y = (i + 0.5) * lane_width + splitter
                    out_lane = Lane(
                        f"w_out_{i}",
                        start_x=-boundary,
                        start_y=out_y,
                        end_x=-approach_length,
                        end_y=out_y,
                    )

                in_lane.approach, in_lane.index, in_lane.role = d, i, "incoming"
                out_lane.approach, out_lane.index, out_lane.role = d, i, "outgoing"
                in_approach.add_lane(in_lane)
                out_approach.add_lane(out_lane)

            self.add_incoming_approach(in_approach)
            self.add_outgoing_approach(out_approach)

        # Lane use: the scenario's where it sets one; on a roundabout whose
        # approaches do not all match the ring, the default policy restricted
        # to what each lane can reach (lane_config.default_roundabout_lane_use).
        # Neither is recorded when it equals the default policy, so the
        # V1.0-V1.3 junctions carry no configured lane use at all.
        dir_counts = {d: counts[d.value] for d in Direction}
        for d in Direction:
            turns_by_lane: Optional[Sequence[FrozenSet[TurnIntent]]] = None
            if lane_use is not None and d in lane_use:
                turns_by_lane = lane_use[d]
            elif is_roundabout:
                turns_by_lane = default_roundabout_lane_use(
                    d, dir_counts, self.circulating_lanes
                )
            if turns_by_lane is None:
                continue
            n = dir_counts[d]
            for i, turns in enumerate(list(turns_by_lane)[:n]):
                if turns and turns != lane_permitted_turns(i, n):
                    self._configured_lane_use[(d, i)] = frozenset(turns)

        # Pre-create all possible connection lanes
        self._precompute_connection_lanes()

    # ------------------------------------------------------------------
    # Connection lane management
    # ------------------------------------------------------------------

    def _precompute_connection_lanes(self) -> None:
        """Create and cache every possible connection lane.

        This ensures that all vehicles taking the same path through the
        intersection share the *same* Lane object, which is essential for
        correct lane-based leader detection.
        """
        for direction in Direction:
            try:
                incoming = self.get_incoming_approach(direction)
            except KeyError:
                continue

            for lane_idx in range(len(incoming.get_lanes())):
                for turn in TurnIntent:
                    try:
                        self._get_or_create_connection_lane(direction, lane_idx, turn)
                    except (KeyError, IndexError, ValueError):
                        # Some combinations might not be valid (on a
                        # roundabout, a lane that cannot reach the exit)
                        pass

    def _base_turns(
        self, direction: Direction, lane_index: int
    ) -> FrozenSet[TurnIntent]:
        """Lane use before any controller marking: configured, else default."""
        configured = self._configured_lane_use.get((direction, lane_index))
        if configured is not None:
            return configured
        return lane_permitted_turns(lane_index, self.lane_count(direction))

    def ring_lane_for(
        self, origin: Direction, lane_index: int, turn: TurnIntent
    ) -> Optional[int]:
        """Circulating lane a roundabout movement uses (None if the lane cannot
        reach that exit, or this is not a roundabout)."""
        if not getattr(self, "is_roundabout", False):
            return None
        return ring_lane_for(
            lane_index,
            self.lane_count(origin),
            self.circulating_lanes,
            self.lane_count(target_direction(origin, turn)),
            turn,
        )

    def _path_ring_lane(
        self, origin: Direction, lane_index: int, turn: TurnIntent
    ) -> int:
        """Ring lane a path is laid out on.

        A movement the lane designation does not allow from this entry lane
        (ring_lane_for -> None) still gets a path, on the entry lane's own
        ring lane, exactly as V1.0-V1.3 built a path for every lane and
        movement. Lane use never sends traffic onto it — spawning, lane
        changing and missed turns only use permitted movements, and
        validation rejects a lane use that permits it — but code that
        inspects the geometry of every path keeps working.
        """
        ring = self.ring_lane_for(origin, lane_index, turn)
        if ring is not None:
            return ring
        return min(
            entry_home_ring_lane(
                lane_index, self.lane_count(origin), self.circulating_lanes
            ),
            self.circulating_lanes - 1,
        )

    def _exit_lane_index(
        self, origin: Direction, lane_index: int, turn: TurnIntent
    ) -> int:
        """Outgoing lane a movement ends in (see lane_config)."""
        target = target_direction(origin, turn)
        exit_lanes = len(self.get_outgoing_approach(target).get_lanes())
        if getattr(self, "is_roundabout", False):
            ring = self._path_ring_lane(origin, lane_index, turn)
            return ring_exit_lane(ring, self.circulating_lanes, exit_lanes)
        lanes = self.lane_count(origin)
        return signal_exit_lane(
            lane_index,
            turn,
            [self._base_turns(origin, i) for i in range(lanes)],
            exit_lanes,
        )

    @staticmethod
    def _resolve_exit_lane_index(
        lane_index: int,
        total_in_lanes: int,
        total_out_lanes: int,
        turn_intent: TurnIntent,
    ) -> int:
        if total_out_lanes <= 1:
            return 0
        if turn_intent == TurnIntent.LEFT:
            return 0
        elif turn_intent == TurnIntent.RIGHT:
            return total_out_lanes - 1
        else:  # STRAIGHT
            if total_in_lanes <= 1:
                return total_out_lanes // 2
            if lane_index == 0:
                return 0
            if lane_index == total_in_lanes - 1:
                return total_out_lanes - 1
            # Map middle lanes proportionally
            in_ratio = lane_index / (total_in_lanes - 1)
            out_idx = round(in_ratio * (total_out_lanes - 1))
            return max(0, min(out_idx, total_out_lanes - 1))

    def _get_or_create_connection_lane(
        self, origin_direction: Direction, lane_index: int, turn_intent: TurnIntent
    ) -> Lane:
        """Return the cached connection lane, creating it if necessary."""
        key = (origin_direction, lane_index, turn_intent)
        if key in self._connection_lane_cache:
            return self._connection_lane_cache[key]

        incoming_approach = self.get_incoming_approach(origin_direction)
        incoming_lane = incoming_approach.get_lanes()[lane_index]

        exit_target = self._resolve_target_direction(origin_direction, turn_intent)
        outgoing_approach = self.get_outgoing_approach(exit_target)

        exit_lane_index = self._exit_lane_index(
            origin_direction, lane_index, turn_intent
        )
        exit_lane = outgoing_approach.get_lanes()[exit_lane_index]

        conn_id = f"conn_{origin_direction.value}_{lane_index}_{turn_intent.value}"
        start_x, start_y = incoming_lane.end_coords
        end_x, end_y = exit_lane.start_coords

        waypoints = None
        target_r: Optional[float] = None
        ring_lane: Optional[int] = None
        last_steady = 0
        if getattr(self, "is_roundabout", False):
            # Circular roundabout geometry. The ring lane is chosen by the
            # V1.4 lane assignment (lane_config); with as many ring lanes as
            # entry lanes it is the entry lane itself, as in V1.0-V1.3.
            inner_r = getattr(self, "inner_radius", 10.0)
            outer_r = getattr(self, "outer_radius", 20.0)
            ring_lane = self._path_ring_lane(origin_direction, lane_index, turn_intent)
            target_r = ring_lane_radius(
                inner_r, outer_r, self.circulating_lanes, ring_lane
            )

            # Straight tangential run from the give-way line to the ring
            # itself, before any curvature begins.
            #
            # The path used to start curving immediately at the give-way line,
            # so a vehicle pulling away swung sideways across the mouth while
            # still alongside the queue in the neighbouring entry lane, and
            # their bodies overlapped. A real entry runs straight up to the
            # give-way line and only then turns, which is also what keeps
            # adjacent entry lanes parallel through the mouth.
            #
            # ROUNDABOUT_ENTRY_SETBACK is exactly the distance by which the
            # give-way line sits outside the ring, so advancing that far along
            # the incoming lane's own heading lands on the ring's outer edge.
            entry_vec_x, entry_vec_y = incoming_lane.vector
            entry_vec_len = math.hypot(entry_vec_x, entry_vec_y) or 1.0
            mouth_x = start_x + (entry_vec_x / entry_vec_len) * (
                ROUNDABOUT_ENTRY_SETBACK
            )
            mouth_y = start_y + (entry_vec_y / entry_vec_len) * (
                ROUNDABOUT_ENTRY_SETBACK
            )

            # Mirror image on the way out: leave the ring, then run straight
            # down the outgoing lane's heading to where that lane begins.
            exit_vec_x, exit_vec_y = exit_lane.vector
            exit_vec_len = math.hypot(exit_vec_x, exit_vec_y) or 1.0
            throat_x = end_x - (exit_vec_x / exit_vec_len) * (ROUNDABOUT_ENTRY_SETBACK)
            throat_y = end_y - (exit_vec_y / exit_vec_len) * (ROUNDABOUT_ENTRY_SETBACK)

            # The curved section now runs mouth -> throat; the straight stubs
            # are prepended/appended to it below.
            curve_start = (mouth_x, mouth_y)
            curve_end = (throat_x, throat_y)
            start_x, start_y = curve_start
            end_x, end_y = curve_end

            # Polar angles
            angle_entry = math.atan2(start_y, start_x)
            angle_exit = math.atan2(end_y, end_x)

            # Roundabout circulates counter-clockwise (increasing angle in standard polar coordinates)
            # Ensure angle_exit > angle_entry
            if angle_exit <= angle_entry:
                angle_exit += 2 * math.pi

            entry_r = math.hypot(start_x, start_y)
            exit_r = math.hypot(end_x, end_y)
            angular_span = angle_exit - angle_entry

            # Length of the radial entry/exit transition, expressed as a
            # fraction of the path's angular span but derived from a FIXED
            # arc length.
            #
            # This used to be a fixed fraction (t < 0.2 / t > 0.8) of each
            # connection lane's own angular span. Because those spans differ
            # enormously by turn intent (a right turn covers ~90 deg, a left
            # ~270 deg), the same entry mouth produced wildly different
            # radial profiles: a right-turner snapped onto its ring within a
            # few metres while a left-turner from the SAME incoming lane was
            # still drifting inward 15 m later. Two vehicles entering from
            # one lane therefore occupied different radii at the same angle
            # and overlapped, and — because they were on different Lane
            # objects at different radii — neither the same-ring follower
            # logic nor the collision audit's "parallel lanes" grouping
            # treated them as the single physical channel they really are.
            #
            # Anchoring the transition to a fixed arc length instead makes
            # every path leaving a given entry mouth share one radial
            # profile, so vehicles from the same incoming lane genuinely
            # follow one another through the entry taper.
            steady_arc = max(1e-6, abs(angular_span) * target_r)
            t_trans = min(0.35, ROUNDABOUT_TRANSITION_ARC / steady_arc)
            # V1.4: a path leaving the INNER lane of a two-lane ring spirals
            # out over a shorter arc, which keeps it clear of the outer lane's
            # path to the same exit (see ROUNDABOUT_INNER_EXIT_TRANSITION_ARC).
            # One-lane rings and every outer-lane path are unchanged.
            t_exit = t_trans
            if (
                ring_lane is not None
                and self.circulating_lanes > 1
                and ring_lane < self.circulating_lanes - 1
            ):
                t_exit = min(0.35, self.inner_exit_transition_arc / steady_arc)

            waypoints = []
            num_pts = 30 if t_exit == t_trans else 60
            # Index (into the full waypoint list, entry stub first) of the
            # last point still on the steady circulating radius: beyond it
            # the path spirals out towards its exit.
            last_steady = 1
            for i in range(num_pts + 1):
                t = i / float(num_pts)
                if t <= 1.0 - t_exit:
                    last_steady = i + 1
                angle = angle_entry + t * angular_span

                # Smoothly transition the radius from entry_radius to
                # target_r, hold the steady circulating radius, then
                # transition out to exit_radius.
                if t < t_trans:
                    u = t / t_trans
                    r = entry_r + u * (target_r - entry_r)
                elif t > 1.0 - t_exit:
                    u = (t - (1.0 - t_exit)) / t_exit
                    r = target_r + u * (exit_r - target_r)
                else:
                    r = target_r

                px = r * math.cos(angle)
                py = r * math.sin(angle)
                waypoints.append((px, py))

            # Bracket the arc with the straight entry and exit stubs, so the
            # lane still spans give-way line -> outgoing lane start.
            entry_point = incoming_lane.end_coords
            exit_point = exit_lane.start_coords
            waypoints = [entry_point] + waypoints + [exit_point]
        elif turn_intent in (TurnIntent.LEFT, TurnIntent.RIGHT):
            if origin_direction in (Direction.NORTH, Direction.SOUTH):
                cx, cy = start_x, end_y
            else:
                cx, cy = end_x, start_y

            waypoints = []
            num_pts = 12
            for i in range(num_pts + 1):
                t = i / float(num_pts)
                omt = 1.0 - t
                px = omt * omt * start_x + 2.0 * omt * t * cx + t * t * end_x
                py = omt * omt * start_y + 2.0 * omt * t * cy + t * t * end_y
                waypoints.append((px, py))

        connection_lane = Lane(
            conn_id,
            start_x=start_x,
            start_y=start_y,
            end_x=end_x,
            end_y=end_y,
            speed_limit=incoming_approach.speed_limit,
            waypoints=waypoints,
        )
        if target_r is not None:
            connection_lane.circulating_radius = target_r
        if ring_lane is not None:
            # V1.4: the ring lane this path circulates on, and where along the
            # path it starts leaving that lane for its exit (the spiral-out).
            connection_lane.ring_lane = ring_lane
            connection_lane.exit_transition_start = (
                connection_lane.distance_to_waypoint(last_steady)
            )
            connection_lane.exit_direction = exit_target
        connection_lane.approach = origin_direction
        connection_lane.index = lane_index
        connection_lane.role = "connection"

        self._connection_lane_cache[key] = connection_lane
        return connection_lane

    @staticmethod
    def _resolve_target_direction(origin: Direction, turn: TurnIntent) -> Direction:
        """Determine the exit direction given origin and turn intent.

        Convention (right-hand traffic, driving on the right):
            LEFT:     N→E, E→S, S→W, W→N
            STRAIGHT: N→S, E→W, S→N, W→E
            RIGHT:    N→W, E→N, S→E, W→S
        """
        mapping = {
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
        }
        return mapping[turn][origin]

    def generate_route(
        self, origin_direction: Direction, lane_index: int, turn_intent: TurnIntent
    ) -> List[Lane]:
        """Build a three-segment route: incoming lane → connection lane → exit lane.

        The connection lane is *shared* across all vehicles taking the same
        path, so lane-based leader detection works correctly.
        """
        incoming_approach = self.get_incoming_approach(origin_direction)
        incoming_lane = incoming_approach.get_lanes()[lane_index]

        connection_lane = self._get_or_create_connection_lane(
            origin_direction, lane_index, turn_intent
        )

        exit_target = self._resolve_target_direction(origin_direction, turn_intent)
        outgoing_approach = self.get_outgoing_approach(exit_target)
        exit_lane_index = self._exit_lane_index(
            origin_direction, lane_index, turn_intent
        )
        exit_lane = outgoing_approach.get_lanes()[exit_lane_index]

        return [incoming_lane, connection_lane, exit_lane]

