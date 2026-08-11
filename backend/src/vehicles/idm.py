import math
from typing import Optional


class IntelligentDriverModel:
    """Calculates longitudinal acceleration using the Intelligent Driver Model (IDM)."""

    def __init__(
        self,
        max_acceleration: float = 2.0,
        comfort_deceleration: float = 3.0,
        desired_time_headway: float = 1.5,
        minimum_gap: float = 2.0,
        idm_delta: float = 4.0,
        max_deceleration: float = 9.0,
    ) -> None:
        """Initialize the Intelligent Driver Model.

        Args:
            max_acceleration: Maximum comfortable acceleration (m/s^2) (a0).
            comfort_deceleration: Comfortable deceleration (m/s^2) (b).
            desired_time_headway: Desired following time headway (seconds) (T).
            minimum_gap: Minimum spacing between vehicles at standstill (meters)
              (s0).
            idm_delta: Acceleration exponent (delta).
            max_deceleration: Absolute maximum deceleration limit (m/s^2).

        Raises:
            ValueError: If any parameter is less than or equal to zero.
        """
        if max_acceleration <= 0 or comfort_deceleration <= 0:
            raise ValueError(
                "Acceleration and deceleration parameters must be positive."
            )
        if desired_time_headway <= 0 or minimum_gap <= 0:
            raise ValueError("Headway and gap parameters must be positive.")
        if idm_delta <= 0:
            raise ValueError("IDM delta exponent must be positive.")
        if max_deceleration <= 0:
            raise ValueError("Max deceleration limit must be positive.")

        self._max_acceleration: float = max_acceleration
        self._comfort_deceleration: float = comfort_deceleration
        self._desired_time_headway: float = desired_time_headway
        self._minimum_gap: float = minimum_gap
        self._idm_delta: float = idm_delta
        self._max_deceleration: float = max_deceleration

    def calculate_acceleration(
        self,
        speed: float,
        desired_speed: float,
        lead_speed: Optional[float] = None,
        gap: Optional[float] = None,
    ) -> float:
        """Calculate the target acceleration based on current state and leading vehicle.

        Args:
            speed: Current speed of the subject vehicle (m/s) (v).
            desired_speed: Desired speed of the subject vehicle (m/s) (v0).
            lead_speed: Current speed of the leading vehicle (m/s), if any.
            gap: Spacing/distance to the leading vehicle (meters), if any.

        Returns:
            Calculated acceleration in m/s^2.

        Raises:
            ValueError: If speed is negative or desired_speed is <= 0.
        """
        if speed < 0:
            raise ValueError("Vehicle speed cannot be negative.")
        if desired_speed <= 0:
            raise ValueError("Desired speed must be greater than zero.")

        # Free-road acceleration component
        # a_free = a0 * (1 - (v / v0)^delta)
        ratio = speed / desired_speed
        acc_free = self._max_acceleration * (1.0 - math.pow(ratio, self._idm_delta))

        # Interaction component (following behavior)
        if lead_speed is None or gap is None:
            acc = acc_free
        else:
            if gap <= 0.0:
                # Collision or zero gap: return absolute deceleration limit
                return -self._max_deceleration

            # Delta v (closing speed): positive means subject is faster than leader
            delta_v = speed - lead_speed

            # Target gap s* = s0 + v*T + (v * delta_v) / (2 * sqrt(a * b))
            denom = 2.0 * math.sqrt(self._max_acceleration * self._comfort_deceleration)
            spacing_term = (speed * delta_v) / denom

            target_gap = (
                self._minimum_gap + speed * self._desired_time_headway + spacing_term
            )
            # Cap target gap to be non-negative
            target_gap = max(0.0, target_gap)

            # Acceleration = a_free - a0 * (s* / s)^2
            acc = acc_free - self._max_acceleration * math.pow(target_gap / gap, 2)

        # Cap deceleration at absolute physical limit
        return max(-self._max_deceleration, acc)
