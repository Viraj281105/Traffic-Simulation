from typing import Any, Dict, List

from src.core.enums import Direction, VehicleState
from src.vehicles.router import find_leader
from src.vehicles.vehicle import Vehicle


class VehiclePool:
    """Manages active and exited vehicles, coordinating their movement and lifecycle."""

    def __init__(self) -> None:
        self.active_vehicles: List[Vehicle] = []
        self.exited_vehicles: List[Vehicle] = []

    def add_vehicle(self, vehicle: Vehicle) -> None:
        if vehicle not in self.active_vehicles:
            self.active_vehicles.append(vehicle)

    def get_active_vehicles(self) -> List[Vehicle]:
        return self.active_vehicles

    def get_exited_vehicles(self) -> List[Vehicle]:
        return self.exited_vehicles

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

        # Update each vehicle
        to_remove = []
        for vehicle in self.active_vehicles:
            current_state = vehicle.state
            if current_state == VehicleState.EXITED:
                to_remove.append(vehicle)
                continue

            # Leader detection
            leader, gap = find_leader(
                vehicle,
                getattr(engine, "network", None),
                self.active_vehicles,
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

            if vehicle.state == VehicleState.EXITED:
                to_remove.append(vehicle)

        # Move exited vehicles from active to exited list
        for vehicle in to_remove:
            if vehicle in self.active_vehicles:
                self.active_vehicles.remove(vehicle)
            if vehicle not in self.exited_vehicles:
                self.exited_vehicles.append(vehicle)

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
