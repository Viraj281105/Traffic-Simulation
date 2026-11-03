import random
from typing import TYPE_CHECKING, Any, Optional

from src.vehicles.idm import IntelligentDriverModel

if TYPE_CHECKING:
    from src.vehicles.vehicle_types import VehicleTypeProfile


class StochasticIDM(IntelligentDriverModel):
    """
    A stochastic wrapper over the Intelligent Driver Model for unstructured traffic.
    Introduces variable reaction times, inconsistent yielding, hesitation, and gap acceptance scaling.
    """

    def __init__(
        self, *args: Any, rng: Optional[random.Random] = None, **kwargs: Any
    ) -> None:
        super().__init__(*args, **kwargs)
        # Use provided RNG for deterministic playback, fallback to global random if absent.
        self.rng = rng if rng is not None else random

    def calculate_acceleration(
        self,
        speed: float,
        desired_speed: float,
        lead_speed: Optional[float] = None,
        gap: Optional[float] = None,
    ) -> float:
        aggression = self.rng.uniform(0.5, 1.5)
        # Varying gap acceptance based on aggression
        temp_min_gap = self._minimum_gap
        temp_time_headway = self._desired_time_headway
        if aggression > 1.2:
            self._minimum_gap = max(0.2, self._minimum_gap * 0.5)
            self._desired_time_headway = max(0.3, self._desired_time_headway * 0.5)
        elif aggression < 0.8:
            self._minimum_gap = self._minimum_gap * 1.5
            self._desired_time_headway = self._desired_time_headway * 1.5

        # The scaled gap and headway apply to this call only. They are
        # restored however the call ends: the two early returns below used to
        # skip the restore, so each one compounded the scaling into the shared
        # model and the configured values drifted for the rest of the run
        # (2.0 m / 1.5 s to 0.2 m / 0.3 s within 120 s).
        try:
            # Nudge forward: occasionally inch forward if stopped to break deadlocks
            if speed < 0.1 and gap is not None and gap < 5.0:
                if self.rng.random() < 0.05:
                    return self._max_acceleration * 0.4

            # Stochastic hesitation: occasionally hesitate when speed is very low
            if speed < 2.0 and speed >= 0.1 and self.rng.random() < 0.005:
                return -self._max_deceleration

            acc = super().calculate_acceleration(speed, desired_speed, lead_speed, gap)
        finally:
            self._minimum_gap = temp_min_gap
            self._desired_time_headway = temp_time_headway

        # Add occasional random hard braking or abrupt acceleration (chaos factor)
        if self.rng.random() < 0.005:
            return -self._max_deceleration * self.rng.uniform(0.5, 1.0)

        # Variable reaction time jitter
        if self.rng.random() < 0.1:
            acc += self.rng.uniform(-0.5, 0.5)

        return acc


def stochastic_idm_for(
    profile: "VehicleTypeProfile", rng: random.Random
) -> StochasticIDM:
    """The stochastic model with one vehicle class's own IDM parameters.

    Under unstructuredTraffic every class drives with the same imperfections
    (hesitation, variable reaction, blocking) around its own baseline, so a
    bus stays a bus: longer headway, gentler acceleration (F-38).
    """
    return StochasticIDM(
        max_acceleration=profile.max_acceleration,
        comfort_deceleration=profile.comfort_deceleration,
        desired_time_headway=profile.desired_time_headway,
        minimum_gap=profile.minimum_gap,
        idm_delta=profile.idm_delta,
        rng=rng,
    )
