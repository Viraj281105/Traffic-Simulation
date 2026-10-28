"""Virtual obstacle — a zero-speed barrier used by traffic controllers.

Used by both signal controllers (stop-line blocking) and the leader-detection
router (conflict zone / emergency braking obstacles).
"""


class VirtualObstacle:
    """A stationary or slow-moving obstacle at a given position on a lane.

    Attributes match the subset of :class:`Vehicle` that the IDM caller needs:
    ``position``, ``speed``, ``length``, and ``vehicle_id``.

    ``stop_line`` marks a road marking a vehicle stops at (a signal stop line,
    a roundabout yield line, a refused admission held at the line), as opposed
    to a stand-in for another vehicle. A driver-aggression profile shortens the
    standstill gap to the vehicle ahead, not where a driver stops at a line
    (see VehiclePool and ADR-019).
    """

    __slots__ = ("position", "speed", "length", "vehicle_id", "is_yellow", "stop_line")

    def __init__(
        self,
        position: float,
        speed: float = 0.0,
        length: float = 0.0,
        is_yellow: bool = False,
        stop_line: bool = False,
    ) -> None:
        self.position = position
        self.speed = speed
        self.length = length
        self.vehicle_id = "virtual_stop_line"
        self.is_yellow = is_yellow
        self.stop_line = stop_line
