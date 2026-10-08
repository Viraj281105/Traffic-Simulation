from enum import Enum


class Direction(str, Enum):
    NORTH = "north"
    SOUTH = "south"
    EAST = "east"
    WEST = "west"


class TurnIntent(str, Enum):
    LEFT = "left"
    STRAIGHT = "straight"
    RIGHT = "right"
    # V1.5: back out along the approach the vehicle came from. Never part of
    # a default lane use: a lane carries U-turns only when the scenario says
    # so (roads/lane_config.CORE_TURNS are the V1.0 movements).
    UTURN = "uturn"


class SimulationStatus(str, Enum):
    INITIALIZED = "initialized"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"


class VehicleState(str, Enum):
    WAITING = "waiting"
    APPROACHING = "approaching"
    EXITED = "exited"
