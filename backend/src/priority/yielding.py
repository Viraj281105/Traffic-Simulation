"""Yield and clearance behaviour of traffic ahead of an emergency vehicle (F12).

**Simplification (documented).** The vehicle model has no shoulder, no free
lateral movement and no driver-perception model, so a driver cannot pull over
or stop to let an emergency vehicle pass. What the model *can* express is how a
driver follows and accelerates, so yielding is modelled as clearing the lane:

* a vehicle in the emergency vehicle's lane, ahead of it and within
  ``YieldConfig.distance_m``, gets shorter desired headway and stronger
  acceleration (the persistent driver-trait multipliers of ADR-020, applied to
  that vehicle only), so a standing queue closes up and moves off promptly when
  released, and
* its desired speed is lifted to at least ``speed_floor_factor`` x the speed
  limit, so a slow vehicle (a bus, a cautious driver) does not hold the lane.

Both are undone when the emergency vehicle is no longer within the distance of
the vehicle, or has left the junction, and the vehicle's own values return
exactly. Vehicles are never made to stop for the emergency vehicle, to leave
their lane or to enter the junction against the signal, so the junction's own
safety logic (conflict zones, signal stop lines, collision avoidance) is
unchanged. Results from this model describe in-model clearing, not observed
driver behaviour.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple

from src.priority.models import YieldConfig
from src.priority.vehicles import EmergencyVehicle
from src.vehicles.vehicle import Vehicle

_Saved = Tuple[Optional[Tuple[float, float, float]], float]


class YieldManager:
    def __init__(self, config: YieldConfig, speed_limit: float) -> None:
        self.config = config
        self.speed_limit = speed_limit
        self._saved: Dict[str, _Saved] = {}
        self._vehicles: Dict[str, Vehicle] = {}
        #: Distinct vehicles that yielded at some point this run.
        self.yielded_ids: set[str] = set()

    def reset(self) -> None:
        self.restore_all()
        self.yielded_ids.clear()

    def update(
        self, emergencies: Iterable[EmergencyVehicle], vehicles: List[Vehicle]
    ) -> None:
        """Apply clearing to the vehicles ahead of each emergency vehicle and
        restore those no longer ahead of one."""
        if not self.config.enabled:
            return
        ahead: Dict[str, Vehicle] = {}
        for ev in emergencies:
            if ev.lane is None:
                continue
            for other in ev.lane.get_vehicles():
                if other is ev or getattr(other, "priority", False):
                    continue
                gap = other.position - ev.position
                if 0.0 < gap <= self.config.distance_m:
                    ahead[other.vehicle_id] = other
        for vid in [v for v in self._saved if v not in ahead]:
            self._restore(vid)
        for vid, vehicle in ahead.items():
            if vid not in self._saved:
                self._apply(vehicle)

    def _apply(self, vehicle: Vehicle) -> None:
        cfg = self.config
        self._saved[vehicle.vehicle_id] = (
            vehicle.driver_factors,
            vehicle.desired_speed,
        )
        self._vehicles[vehicle.vehicle_id] = vehicle
        self.yielded_ids.add(vehicle.vehicle_id)
        headway, accel, decel = vehicle.driver_factors or (1.0, 1.0, 1.0)
        vehicle.driver_factors = (
            headway * cfg.headway_factor,
            accel * cfg.acceleration_factor,
            decel,
        )
        # Vehicle.driver_idm caches the scaled model per base model, not per
        # factors, so the cache must be dropped when the factors change.
        vehicle._driver_idm = None
        vehicle.desired_speed = max(
            vehicle.desired_speed, self.speed_limit * cfg.speed_floor_factor
        )

    def _restore(self, vehicle_id: str) -> None:
        factors, desired = self._saved.pop(vehicle_id)
        vehicle = self._vehicles.pop(vehicle_id)
        vehicle.driver_factors = factors
        vehicle._driver_idm = None
        vehicle.desired_speed = desired

    def restore_all(self) -> None:
        for vid in list(self._saved):
            self._restore(vid)

    @property
    def active_count(self) -> int:
        return len(self._saved)
