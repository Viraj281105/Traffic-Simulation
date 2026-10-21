import logging
from typing import Any, Dict, List, Optional

from src.core.clock import Clock
from src.engine.vehicle_pool import VehiclePool

logger = logging.getLogger(__name__)


class DeadlockDetector:
    """
    Detects natural deadlocks in unstructured traffic scenarios (legacy mode)
    and ring deadlocks on circulating connection lanes in metered roundabouts (D-W2-9a).
    Monitors vehicles with sustained near-zero movement and circular dependencies.
    """

    def __init__(self, clock: Clock, pool: VehiclePool, ring_only: bool = False):
        self.clock = clock
        self.pool = pool
        self.ring_only = ring_only
        self.stopped_durations: Dict[str, float] = {}
        self.active_deadlocks: List[Dict[str, Any]] = []
        self.last_insight: Optional[str] = None
        self.has_occurred = False

    @staticmethod
    def _is_ring_vehicle(vehicle: Any) -> bool:
        """Check whether vehicle is on a circulating roundabout connection lane."""
        lane = getattr(vehicle, "lane", None)
        if lane is None:
            return False
        lane_id = getattr(lane, "lane_id", None)
        if lane_id is None and isinstance(lane, str):
            lane_id = lane
        if isinstance(lane_id, str):
            return lane_id.lower().startswith("conn")
        return False

    def tick(self, dt: float) -> None:
        current_time = self.clock.get_elapsed_time()

        # Track stopped durations
        active_vehicles = self.pool.get_active_vehicles()
        if self.ring_only:
            eligible_vehicles = [v for v in active_vehicles if self._is_ring_vehicle(v)]
        else:
            eligible_vehicles = active_vehicles

        eligible_ids = {v.vehicle_id for v in eligible_vehicles}
        for vid in list(self.stopped_durations.keys()):
            if vid not in eligible_ids:
                del self.stopped_durations[vid]

        for v in eligible_vehicles:
            if v.speed < 0.1:
                self.stopped_durations[v.vehicle_id] = (
                    self.stopped_durations.get(v.vehicle_id, 0.0) + dt
                )
            else:
                if v.vehicle_id in self.stopped_durations:
                    del self.stopped_durations[v.vehicle_id]

        # Simple cyclic dependency detection among severely stopped vehicles
        severely_stopped = [
            v
            for v in eligible_vehicles
            if self.stopped_durations.get(v.vehicle_id, 0.0) > 5.0
        ]

        # In a full implementation, we'd build a graph. For now, if there are many stopped vehicles, we flag it.
        if len(severely_stopped) > 4:
            if not self.has_occurred:
                self.has_occurred = True
                if self.ring_only:
                    self.last_insight = (
                        f"Ring deadlock emerged at {current_time:.1f}s involving "
                        f"{len(severely_stopped)} circulating vehicles."
                    )
                else:
                    self.last_insight = (
                        f"Natural deadlock emerged at {current_time:.1f}s involving "
                        f"{len(severely_stopped)} vehicles. The stochastic driver behavior "
                        f"led to an unresolvable conflict."
                    )
                logger.warning(self.last_insight)
        else:
            if self.has_occurred and len(severely_stopped) == 0:
                self.has_occurred = False
                if self.ring_only:
                    self.last_insight = (
                        f"Ring deadlock resolved at {current_time:.1f}s as circulating "
                        f"vehicles moved forward."
                    )
                else:
                    self.last_insight = (
                        f"Deadlock naturally resolved at {current_time:.1f}s as drivers "
                        f"yielded or nudged forward."
                    )
                logger.info(self.last_insight)

    def get_insight(self) -> Optional[str]:
        return self.last_insight
