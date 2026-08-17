from typing import Dict, Tuple


class IntersectionGeometry:
    """Manages the spatial bounds, coordinates, and approach connection maps for the intersection."""

    def __init__(
        self, center_x: float, center_y: float, bounding_radius: float
    ) -> None:
        self.center_x: float = center_x
        self.center_y: float = center_y
        self.bounding_radius: float = bounding_radius

        # Maps incoming lane IDs to their connection entry coordinates (crossing start points)
        self.entry_nodes: Dict[str, Tuple[float, float]] = {}
        # Maps outgoing lane IDs to their connection exit coordinates (crossing end points)
        self.exit_nodes: Dict[str, Tuple[float, float]] = {}

    def register_entry_node(self, lane_id: str, coords: Tuple[float, float]) -> None:
        self.entry_nodes[lane_id] = coords

    def register_exit_node(self, lane_id: str, coords: Tuple[float, float]) -> None:
        self.exit_nodes[lane_id] = coords

    def is_within_intersection(self, x: float, y: float) -> bool:
        """Determines if a coordinate is within the circular boundary of the intersection."""
        dx = x - self.center_x
        dy = y - self.center_y
        # Use simple circular distance
        return dx * dx + dy * dy <= self.bounding_radius * self.bounding_radius
