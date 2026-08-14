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
