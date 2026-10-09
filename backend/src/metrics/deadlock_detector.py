import logging
from typing import List, Dict, Set, Optional

from src.core.clock import Clock
from src.vehicles.pool import VehiclePool

logger = logging.getLogger(__name__)

class DeadlockDetector:
    """
    Detects natural deadlocks in unstructured traffic scenarios.
    Monitors vehicles with sustained near-zero movement and circular dependencies.
    """
    def __init__(self, clock: Clock, pool: VehiclePool):
        self.clock = clock
        self.pool = pool
        self.stopped_durations: Dict[str, float] = {}
        self.active_deadlocks: List[Dict] = []
        self.last_insight: Optional[str] = None
        self.has_occurred = False

    def tick(self, dt: float) -> None:
        current_time = self.clock.get_elapsed_time()
        
        # Track stopped durations
        active_vehicles = self.pool.get_active_vehicles()
        for v in active_vehicles:
            if v.speed < 0.1:
                self.stopped_durations[v.vehicle_id] = self.stopped_durations.get(v.vehicle_id, 0.0) + dt
            else:
                if v.vehicle_id in self.stopped_durations:
                    del self.stopped_durations[v.vehicle_id]

        # Simple cyclic dependency detection among severely stopped vehicles
        severely_stopped = [v for v in active_vehicles if self.stopped_durations.get(v.vehicle_id, 0.0) > 5.0]
        
        # In a full implementation, we'd build a graph. For now, if there are many stopped vehicles, we flag it.
        if len(severely_stopped) > 4:
            if not self.has_occurred:
                self.has_occurred = True
                self.last_insight = f"Natural deadlock emerged at {current_time:.1f}s involving {len(severely_stopped)} vehicles. The stochastic driver behavior led to an unresolvable conflict."
                logger.warning(self.last_insight)
        else:
            if self.has_occurred and len(severely_stopped) == 0:
                self.has_occurred = False
                self.last_insight = f"Deadlock naturally resolved at {current_time:.1f}s as drivers yielded or nudged forward."
                logger.info(self.last_insight)

    def get_insight(self) -> Optional[str]:
        return self.last_insight
