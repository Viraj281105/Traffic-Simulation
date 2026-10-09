import random
import math
from typing import Optional
from src.vehicles.idm import IntelligentDriverModel

class StochasticIDM(IntelligentDriverModel):
    """
    A stochastic wrapper over the Intelligent Driver Model for unstructured traffic.
    Introduces variable reaction times, inconsistent yielding, hesitation, and gap acceptance scaling.
    """
    def __init__(self, *args, rng: Optional[random.Random] = None, **kwargs):
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
            
        # Nudge forward: occasionally inch forward if stopped to break deadlocks
        if speed < 0.1 and gap is not None and gap < 5.0:
            if self.rng.random() < 0.05:
                return self._max_acceleration * 0.4
                
        # Stochastic hesitation: occasionally hesitate when speed is very low
        if speed < 2.0 and speed >= 0.1 and self.rng.random() < 0.005:
            return -self._max_deceleration

        acc = super().calculate_acceleration(speed, desired_speed, lead_speed, gap)
        
        # Restore gaps
        self._minimum_gap = temp_min_gap
        self._desired_time_headway = temp_time_headway
        
        # Add occasional random hard braking or abrupt acceleration (chaos factor)
        if self.rng.random() < 0.005:
            return -self._max_deceleration * self.rng.uniform(0.5, 1.0)
            
        # Variable reaction time jitter
        if self.rng.random() < 0.1:
            acc += self.rng.uniform(-0.5, 0.5)
            
        return acc
