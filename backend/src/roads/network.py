from typing import Dict, List, Tuple
from src.core.enums import Direction, TurnIntent
from src.roads.approach import Approach
from src.roads.lane import Lane


class RoadNetwork:
    """Manages the network topology of the intersection, containing approaches and lanes."""

    def __init__(self) -> None:
        self._incoming: Dict[Direction, Approach] = {}
        self._outgoing: Dict[Direction, Approach] = {}

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
        lanes_per_approach: int = 2,
    ) -> None:
        boundary = lanes_per_approach * lane_width

        # Clear existing
        self._incoming.clear()
        self._outgoing.clear()

        for d in Direction:
            in_approach = Approach(d)
            out_approach = Approach(d)

            for i in range(lanes_per_approach):
                if d == Direction.NORTH:
                    # Incoming: North to South (moves down, x < 0)
                    in_x = -(i + 0.5) * lane_width
                    in_lane = Lane(
                        f"n_in_{i}",
                        start_x=in_x,
                        start_y=approach_length,
                        end_x=in_x,
                        end_y=boundary,
                    )
                    # Outgoing: South to North (moves up, x > 0)
                    out_x = (i + 0.5) * lane_width
                    out_lane = Lane(
                        f"n_out_{i}",
                        start_x=out_x,
                        start_y=boundary,
                        end_x=out_x,
                        end_y=approach_length,
                    )

                elif d == Direction.SOUTH:
                    # Incoming: South to North (moves up, x > 0)
                    in_x = (i + 0.5) * lane_width
                    in_lane = Lane(
                        f"s_in_{i}",
                        start_x=in_x,
                        start_y=-approach_length,
                        end_x=in_x,
                        end_y=-boundary,
                    )
                    # Outgoing: North to South (moves down, x < 0)
                    out_x = -(i + 0.5) * lane_width
                    out_lane = Lane(
                        f"s_out_{i}",
                        start_x=out_x,
                        start_y=-boundary,
                        end_x=out_x,
                        end_y=-approach_length,
                    )

                elif d == Direction.EAST:
                    # Incoming: East to West (moves left, y > 0)
                    in_y = (i + 0.5) * lane_width
                    in_lane = Lane(
                        f"e_in_{i}",
                        start_x=approach_length,
                        start_y=in_y,
                        end_x=boundary,
                        end_y=in_y,
                    )
                    # Outgoing: West to East (moves right, y < 0)
                    out_y = -(i + 0.5) * lane_width
                    out_lane = Lane(
                        f"e_out_{i}",
                        start_x=boundary,
                        start_y=out_y,
                        end_x=approach_length,
                        end_y=out_y,
                    )

                elif d == Direction.WEST:
                    # Incoming: West to East (moves right, y < 0)
                    in_y = -(i + 0.5) * lane_width
                    in_lane = Lane(
                        f"w_in_{i}",
                        start_x=-approach_length,
                        start_y=in_y,
                        end_x=-boundary,
                        end_y=in_y,
                    )
                    # Outgoing: East to West (moves left, y > 0)
                    out_y = (i + 0.5) * lane_width
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

    def generate_route(
        self, origin_direction: Direction, lane_index: int, turn_intent: TurnIntent
    ) -> List[Lane]:
        incoming_approach = self.get_incoming_approach(origin_direction)
        incoming_lane = incoming_approach.get_lanes()[lane_index]

        # Determine target outgoing direction based on TurnIntent
        # LEFT: N->E, E->S, S->W, W->N
        # STRAIGHT: N->S, E->W, S->N, W->E
        # RIGHT: N->W, E->N, S->E, W->S
        if turn_intent == TurnIntent.LEFT:
            target_direction = {
                Direction.NORTH: Direction.EAST,
                Direction.EAST: Direction.SOUTH,
                Direction.SOUTH: Direction.WEST,
                Direction.WEST: Direction.NORTH,
            }[origin_direction]
        elif turn_intent == TurnIntent.STRAIGHT:
            target_direction = {
                Direction.NORTH: Direction.SOUTH,
                Direction.EAST: Direction.WEST,
                Direction.SOUTH: Direction.NORTH,
                Direction.WEST: Direction.EAST,
            }[origin_direction]
        else:  # RIGHT
            target_direction = {
                Direction.NORTH: Direction.WEST,
                Direction.EAST: Direction.NORTH,
                Direction.SOUTH: Direction.EAST,
                Direction.WEST: Direction.SOUTH,
            }[origin_direction]

        outgoing_approach = self.get_outgoing_approach(target_direction)
        exit_lane = outgoing_approach.get_lanes()[lane_index]

        # Create connection lane
        conn_id = f"conn_{origin_direction.value}_{lane_index}_{turn_intent.value}"
        start_x, start_y = incoming_lane.end_coords
        end_x, end_y = exit_lane.start_coords
        connection_lane = Lane(
            conn_id,
            start_x=start_x,
            start_y=start_y,
            end_x=end_x,
            end_y=end_y,
            speed_limit=incoming_approach.speed_limit,
        )

        return [incoming_lane, connection_lane, exit_lane]
