from typing import List, Optional, Tuple

from src.core.enums import VehicleState
from src.roads.lane import Lane


class Vehicle:
    """Represents a single microscopic vehicle moving along a predefined route of lanes."""

    def __init__(
        self,
        vehicle_id: str,
        length: float,
        width: float,
        desired_speed: float,
        route: List[Lane],
        start_position: float = 0.0,
        initial_speed: float = 0.0,
    ) -> None:
        if not route:
            raise ValueError("Vehicle route cannot be empty")
        if length <= 0 or width <= 0:
            raise ValueError("Vehicle dimensions (length, width) must be positive")
        if desired_speed <= 0:
            raise ValueError("Desired speed must be positive")
        if initial_speed < 0:
            raise ValueError("Initial speed cannot be negative")

        self.vehicle_id: str = vehicle_id
        self.length: float = length
        self.width: float = width
        self.desired_speed: float = desired_speed
        self.route: List[Lane] = route

        self.lane: Optional[Lane] = route[0]
        self.position: float = start_position
        self.speed: float = initial_speed
        self.acceleration: float = 0.0

        # Wait threshold speed
        self._wait_threshold: float = 0.01

        # Register vehicle to the first lane
        self.lane.add_vehicle(self)

        # Tracking variables
        self.wait_time: float = 0.0
        if self.speed < self._wait_threshold:
            self.state: VehicleState = VehicleState.WAITING
            self.stop_count: int = 1
        else:
            self.state = VehicleState.APPROACHING
            self.stop_count = 0

    @property
    def coords(self) -> Tuple[float, float]:
        if self.lane is None:
            return (0.0, 0.0)
        return self.lane.get_point_at_distance(self.position)

    @property
    def heading(self) -> float:
        if self.lane is None:
            return 0.0
        return self.lane.heading

    @property
    def lane_id(self) -> str:
        if self.lane is None:
            return ""
        return self.lane.lane_id

    def update_state(self, acceleration: float, dt: float) -> None:
        if self.state == VehicleState.EXITED:
            return

        self.acceleration = acceleration

        # Calculate new speed (cannot be negative)
        old_speed = self.speed
        self.speed = max(0.0, self.speed + acceleration * dt)

        # Update position
        self.position += self.speed * dt

        # Manage state transitions and stop counting
        is_stopped = self.speed < self._wait_threshold
        was_stopped = old_speed < self._wait_threshold

        if is_stopped:
            self.state = VehicleState.WAITING
            self.wait_time += dt
            if not was_stopped:
                self.stop_count += 1
        else:
            self.state = VehicleState.APPROACHING

        # Handle lane transitions
        while self.lane is not None and self.position > self.lane.length:
            try:
                curr_idx = self.route.index(self.lane)
                if curr_idx < len(self.route) - 1:
                    next_lane = self.route[curr_idx + 1]
                    self.position -= self.lane.length
                    self.lane.remove_vehicle(self)
                    self.lane = next_lane
                    self.lane.add_vehicle(self)
                else:
                    # Traversed past the end of the last lane
                    self.lane.remove_vehicle(self)
                    self.lane = None
                    self.state = VehicleState.EXITED
                    self.speed = 0.0
                    break
            except ValueError:
                # Fallback if current lane is somehow not in the route
                self.lane.remove_vehicle(self)
                self.lane = None
                self.state = VehicleState.EXITED
                self.speed = 0.0
                break

    def get_bounding_box(self) -> List[Tuple[float, float]]:
        import math

        cx, cy = self.coords
        heading_rad = math.radians(self.heading)

        h_x = math.sin(heading_rad)
        h_y = math.cos(heading_rad)

        r_x = h_y
        r_y = -h_x

        half_l = self.length / 2.0
        half_w = self.width / 2.0

        # Front-Left: center + L/2 * H - W/2 * R
        fl_x = cx + half_l * h_x - half_w * r_x
        fl_y = cy + half_l * h_y - half_w * r_y

        # Front-Right: center + L/2 * H + W/2 * R
        fr_x = cx + half_l * h_x + half_w * r_x
        fr_y = cy + half_l * h_y + half_w * r_y

        # Rear-Right: center - L/2 * H + W/2 * R
        rr_x = cx - half_l * h_x + half_w * r_x
        rr_y = cy - half_l * h_y + half_w * r_y

        # Rear-Left: center - L/2 * H - W/2 * R
        rl_x = cx - half_l * h_x - half_w * r_x
        rl_y = cy - half_l * h_y - half_w * r_y

        return [(fl_x, fl_y), (fr_x, fr_y), (rr_x, rr_y), (rl_x, rl_y)]
