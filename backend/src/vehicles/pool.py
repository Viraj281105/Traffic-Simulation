"""Vehicle pool — manages all active and exited vehicles.

Integrates with the :class:`ConflictManager` by passing it through to
:func:`find_leader`, and runs a post-update collision audit to catch (and
log) any remaining overlaps as a safety net.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List

from src.core.enums import Direction, VehicleState
from src.vehicles.router import find_leader
from src.vehicles.vehicle import Vehicle

logger = logging.getLogger(__name__)

# Minimum centre-to-centre distance before we flag a collision.
# Only flag actual physical overlaps — same-lane close following is normal.
_COLLISION_THRESHOLD: float = 0.5  # meters


class VehiclePool:
    """Manages active and exited vehicles, coordinating their movement and lifecycle."""

    def __init__(self) -> None:
        self.active_vehicles: List[Vehicle] = []
        self.exited_vehicles: List[Vehicle] = []
        self._collision_count: int = 0

    def add_vehicle(self, vehicle: Vehicle) -> None:
        if vehicle not in self.active_vehicles:
            self.active_vehicles.append(vehicle)

    def get_active_vehicles(self) -> List[Vehicle]:
        return self.active_vehicles

    def get_exited_vehicles(self) -> List[Vehicle]:
        return self.exited_vehicles

    @property
    def collision_count(self) -> int:
        return self._collision_count

    def update(self, dt: float, engine: Any) -> None:
        """Tick all active vehicles, find leaders, update states, and cleanup exited vehicles."""
        # Get IDM physics from engine or configuration
        idm = getattr(engine, "idm", None)
        if idm is None:
            from src.vehicles.idm import IntelligentDriverModel

            config = getattr(engine, "config", {})
            veh_gen = config.get("vehicleGeneration", {})
            idm = IntelligentDriverModel(
                max_acceleration=veh_gen.get("maxAcceleration", 2.0),
                comfort_deceleration=veh_gen.get("comfortDeceleration", 3.0),
                desired_time_headway=veh_gen.get("desiredTimeHeadway", 1.5),
                minimum_gap=veh_gen.get("minimumGap", 2.0),
                idm_delta=veh_gen.get("idmDelta", 4.0),
            )

        # Optional conflict manager from engine
        conflict_manager = getattr(engine, "conflict_manager", None)
        current_time = 0.0
        clock = getattr(engine, "clock", None)
        if clock is not None:
            current_time = clock.get_elapsed_time()

        # Update conflict manager reservations
        if conflict_manager is not None:
            conflict_manager.update_reservations(current_time)

        # Update each vehicle
        to_remove: List[Vehicle] = []

        for vehicle in self.active_vehicles:
            if vehicle.state == VehicleState.EXITED:
                to_remove.append(vehicle)
                continue

            # Leader detection with all safety layers
            leader, gap = find_leader(
                vehicle,
                getattr(engine, "network", None),
                self.active_vehicles,
                conflict_manager=conflict_manager,
                current_time=current_time,
            )

            # Calculate acceleration using IDM
            acc = idm.calculate_acceleration(
                speed=vehicle.speed,
                desired_speed=vehicle.desired_speed,
                lead_speed=leader.speed if leader is not None else None,
                gap=gap if leader is not None else None,
            )

            # Update kinematics
            vehicle.update_state(acc, dt)

            if vehicle.state == VehicleState.EXITED:  # type: ignore[comparison-overlap]
                vehicle.exit_time = current_time
                # Release any conflict zone reservations
                if conflict_manager is not None:
                    conflict_manager.release_vehicle(vehicle.vehicle_id)
                to_remove.append(vehicle)

        # Move exited vehicles from active to exited list
        for vehicle in to_remove:
            if vehicle in self.active_vehicles:
                self.active_vehicles.remove(vehicle)
            if vehicle not in self.exited_vehicles:
                self.exited_vehicles.append(vehicle)

        # ── Post-update collision audit ────────────────────────────────
        self._collision_audit()

    def _collision_audit(self) -> None:
        """Scan for overlapping vehicles and apply emergency separation.

        Only flags actual physical overlaps between vehicles on *different*
        lanes/paths.  Close following on the *same* lane is normal
        car-following behavior handled by the IDM and is not a collision.
        """
        n = len(self.active_vehicles)
        for i in range(n):
            va = self.active_vehicles[i]
            if va.lane is None:
                continue
            ax, ay = va.coords

            for j in range(i + 1, n):
                vb = self.active_vehicles[j]
                if vb.lane is None:
                    continue

                # Skip vehicles on the same lane — close following is normal
                if va.lane is vb.lane:
                    continue

                # Skip vehicles that share any lane in their routes (they're
                # on the same path and the IDM handles spacing)
                va_lane_ids = {lane_obj.lane_id for lane_obj in va.route} if va.route else set()
                vb_lane_ids = {lane_obj.lane_id for lane_obj in vb.route} if vb.route else set()
                if va_lane_ids & vb_lane_ids:
                    continue

                bx, by = vb.coords

                dx = bx - ax
                dy = by - ay
                dist = math.sqrt(dx * dx + dy * dy)

                min_safe = (va.length + vb.length) / 2.0 + _COLLISION_THRESHOLD
                if dist < min_safe and dist > 0.001:
                    self._collision_count += 1
                    logger.warning(
                        "Collision detected: %s ↔ %s  dist=%.2f m (min_safe=%.2f)",
                        va.vehicle_id,
                        vb.vehicle_id,
                        dist,
                        min_safe,
                    )

                    # Emergency separation: push the slower vehicle backward
                    overlap = min_safe - dist
                    slower = va if va.speed <= vb.speed else vb

                    slower.speed = 0.0
                    slower.acceleration = 0.0

                    if slower.lane is not None:
                        slower.position = max(0.0, slower.position - overlap)

    def get_active_counts(self) -> Dict[Direction, Dict[VehicleState, int]]:
        """Returns active count summaries categorized by direction and current vehicle state."""
        summary = {d: {s: 0 for s in VehicleState} for d in Direction}

        for v in self.active_vehicles:
            if not v.route or v.state == VehicleState.EXITED:
                continue

            # Infer origin direction from route start lane ID
            lane_id = v.route[0].lane_id.lower()
            direction = None
            if lane_id.startswith("n"):
                direction = Direction.NORTH
            elif lane_id.startswith("s"):
                direction = Direction.SOUTH
            elif lane_id.startswith("e"):
                direction = Direction.EAST
            elif lane_id.startswith("w"):
                direction = Direction.WEST

            if direction is not None:
                summary[direction][v.state] += 1

        return summary
