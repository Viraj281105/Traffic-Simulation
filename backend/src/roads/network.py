import math
from typing import Any, Dict, List, Optional, Tuple

from src.core.enums import Direction, TurnIntent
from src.roads.approach import Approach
from src.roads.lane import Lane

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
    ) -> None:
        self.is_roundabout = is_roundabout
        self.inner_radius = inner_radius
        self.outer_radius = outer_radius

        # Clear existing
        self._incoming.clear()
        self._outgoing.clear()
        self._connection_lane_cache.clear()

        for d in Direction:
            in_approach = Approach(d)
            out_approach = Approach(d)

            # Support both int and dict configurations
            if isinstance(lanes_per_approach, dict):
                lane_count = lanes_per_approach.get(d.value, 2)
            else:
                lane_count = int(lanes_per_approach)

            boundary = (
                (outer_radius + ROUNDABOUT_ENTRY_SETBACK)
                if is_roundabout
                else (lane_count * lane_width + SIGNAL_STOP_LINE_SETBACK)
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

                in_approach.add_lane(in_lane)
                out_approach.add_lane(out_lane)

            self.add_incoming_approach(in_approach)
            self.add_outgoing_approach(out_approach)

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
                    except (KeyError, IndexError):
                        # Some combinations might not be valid
                        pass

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

        target_direction = self._resolve_target_direction(origin_direction, turn_intent)
        outgoing_approach = self.get_outgoing_approach(target_direction)

        total_in_lanes = len(incoming_approach.get_lanes())
        total_out_lanes = len(outgoing_approach.get_lanes())
        exit_lane_index = self._resolve_exit_lane_index(
            lane_index, total_in_lanes, total_out_lanes, turn_intent
        )
        exit_lane = outgoing_approach.get_lanes()[exit_lane_index]

        conn_id = f"conn_{origin_direction.value}_{lane_index}_{turn_intent.value}"
        start_x, start_y = incoming_lane.end_coords
        end_x, end_y = exit_lane.start_coords

        waypoints = None
        target_r: Optional[float] = None
        if getattr(self, "is_roundabout", False):
            # Circular roundabout geometry
            inner_r = getattr(self, "inner_radius", 10.0)
            outer_r = getattr(self, "outer_radius", 20.0)
            total_in_lanes = len(incoming_approach.get_lanes())
            w_ring = outer_r - inner_r
            target_r = inner_r + (lane_index + 0.5) * (w_ring / total_in_lanes)

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

            waypoints = []
            num_pts = 30
            for i in range(num_pts + 1):
                t = i / float(num_pts)
                angle = angle_entry + t * angular_span

                # Smoothly transition the radius from entry_radius to
                # target_r, hold the steady circulating radius, then
                # transition out to exit_radius.
                if t < t_trans:
                    u = t / t_trans
                    r = entry_r + u * (target_r - entry_r)
                elif t > 1.0 - t_trans:
                    u = (t - (1.0 - t_trans)) / t_trans
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

        target_direction = self._resolve_target_direction(origin_direction, turn_intent)
        outgoing_approach = self.get_outgoing_approach(target_direction)

        total_in_lanes = len(incoming_approach.get_lanes())
        total_out_lanes = len(outgoing_approach.get_lanes())
        exit_lane_index = self._resolve_exit_lane_index(
            lane_index, total_in_lanes, total_out_lanes, turn_intent
        )
        exit_lane = outgoing_approach.get_lanes()[exit_lane_index]

        return [incoming_lane, connection_lane, exit_lane]
