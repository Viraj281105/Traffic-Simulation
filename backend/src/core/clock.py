import math


class Clock:
    """Manages the discrete simulation time steps, elapsed time, and tick counting."""

    def __init__(self, time_step: float) -> None:
        if time_step <= 0:
            raise ValueError("Time step must be positive and non-zero")
        self.time_step: float = time_step
        self._ticks: int = 0
        self._elapsed_time: float = 0.0

    def tick(self) -> None:
        self._ticks += 1
        self._elapsed_time = self._ticks * self.time_step

    def reset(self) -> None:
        self._ticks = 0
        self._elapsed_time = 0.0

    def get_tick_count(self) -> int:
        return self._ticks

    def get_elapsed_time(self) -> float:
        return self._elapsed_time

    def seconds_to_ticks(self, seconds: float) -> int:
        if seconds < 0:
            raise ValueError("Seconds cannot be negative")
        return math.floor(seconds / self.time_step + 0.5)

    def ticks_to_seconds(self, ticks: int) -> float:
        if ticks < 0:
            raise ValueError("Ticks cannot be negative")
        return ticks * self.time_step
