import random
import math
from typing import Optional
from src.vehicles.idm import IntelligentDriverModel

class StochasticIDM(IntelligentDriverModel):
    """
    A stochastic wrapper over the Intelligent Driver Model for unstructured traffic.
    Introduces variable reaction times, inconsistent yielding, hesitation, and gap acceptance scaling.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aggression = random.uniform(0.5, 1.5)
        self.hesitation_timer = 0.0
        self.last_acc = 0.0

    def calculate_acceleration(
        self,
        speed: float,
        desired_speed: float,
        lead_speed: Optional[float] = None,
        gap: Optional[float] = None,
    ) -> float:
        # Stochastic hesitation: occasionally stop/hesitate when speed is very low
        if speed < 2.0 and random.random() < 0.03:
            self.hesitation_timer = random.uniform(1.0, 3.0)
            
        if self.hesitation_timer > 0:
            self.hesitation_timer -= 0.1  # assuming dt is approx 0.1
            return -self._max_deceleration

        # Varying gap acceptance based on aggression
        temp_min_gap = self._minimum_gap
        temp_time_headway = self._desired_time_headway
        if self.aggression > 1.2:
            self._minimum_gap = max(0.2, self._minimum_gap * 0.5)
            self._desired_time_headway = max(0.3, self._desired_time_headway * 0.5)
        elif self.aggression < 0.8:
            self._minimum_gap = self._minimum_gap * 1.5
            self._desired_time_headway = self._desired_time_headway * 1.5
            
        acc = super().calculate_acceleration(speed, desired_speed, lead_speed, gap)
        
        # Restore gaps
        self._minimum_gap = temp_min_gap
        self._desired_time_headway = temp_time_headway
        
        # Add occasional random hard braking or abrupt acceleration (chaos factor)
        if random.random() < 0.005:
            return -self._max_deceleration * random.uniform(0.5, 1.0)
            
        # Variable reaction time jitter
        if random.random() < 0.3:
            acc = self.last_acc
        else:
            self.last_acc = acc
            
        return acc
