from typing import Any, Dict, List

from src.controllers.base import BaseController
from src.controllers.fixed_time_signal import VirtualObstacle
from src.core.enums import Direction
from src.roads.network import RoadNetwork
from src.vehicles.vehicle import Vehicle


class RoundaboutController(BaseController):
    """Manages entry yielding logic and circulating traffic flow inside a roundabout intersection."""

    def __init__(self, config: Dict[str, Any], network: RoadNetwork) -> None:
        self.config: Dict[str, Any] = config
        self.network: RoadNetwork = network

        ctrl_cfg = config.get("controller", {})
        self.inner_radius: float = ctrl_cfg.get("innerRadius", 10.0)
        self.outer_radius: float = ctrl_cfg.get("outerRadius", 20.0)
        self.circulating_lanes: int = ctrl_cfg.get("circulatingLanes", 1)
        self.critical_gap: float = ctrl_cfg.get("criticalGap", 4.0)
        self.follow_up_time: float = ctrl_cfg.get("followUpTime", 2.5)
        self.entry_speed: float = ctrl_cfg.get("entrySpeed", 5.0)
        self.circulating_speed: float = ctrl_cfg.get("circulatingSpeed", 8.0)

        self.time_in_current_state: float = 0.0
        self.reset()

    def reset(self) -> None:
        self.time_in_current_state = 0.0
        # Clear all entry obstacles initially
        for d in Direction:
            try:
                approach = self.network.get_incoming_approach(d)
                for lane in approach.get_lanes():
                    lane.virtual_obstacle = None  # type: ignore[attr-defined]
            except KeyError:
                pass

    def update(self, delta_time: float, active_vehicles: List[Vehicle]) -> None:
        self.update_active_vehicles_ref(active_vehicles)
        self.time_in_current_state += delta_time

        # Identify all circulating vehicles (those on connection/circulating lanes)
        circulating_vehicles = [
            v
            for v in active_vehicles
            if v.lane is not None and v.lane.lane_id.startswith("conn")
        ]

        for d in Direction:
            try:
                approach = self.network.get_incoming_approach(d)
                for lane in approach.get_lanes():
                    # Calculate if there is an oncoming circulating vehicle that blocks entry.
                    # We check circulating vehicles approaching this direction's entry node.
                    # The entry point of this lane is lane.end_coords.
                    entry_pt = lane.end_coords
                    should_yield = False

                    for cv in circulating_vehicles:
                        # Distance from circulating vehicle to our entry point along the circle
                        # For simplicity, we can use Euclidean distance or coordinate bounds
                        # Let's say if circulating vehicle is within 15 meters of entry point
                        cv_x, cv_y = cv.coords
                        dist_to_entry = (
                            (cv_x - entry_pt[0]) ** 2 + (cv_y - entry_pt[1]) ** 2
                        ) ** 0.5

                        # If circulating vehicle is approaching our entry point
                        # (We estimate the time gap based on circulating speed)
                        if dist_to_entry < 15.0:
                            time_gap = dist_to_entry / self.circulating_speed
                            if time_gap < self.critical_gap:
                                should_yield = True
                                break

                    if should_yield:
                        lane.virtual_obstacle = VirtualObstacle(position=lane.length)  # type: ignore[attr-defined]
                    else:
                        lane.virtual_obstacle = None  # type: ignore[attr-defined]
            except KeyError:
                pass

    def get_state(self) -> Dict[str, Any]:
        # Count circulating vehicles
        circulating_count = 0
        yielding_count = 0

        # We need a references of active vehicles. We can scan lanes or count from active pool.
        # But this is formatted for snapshot. Let's find yielding count:
        # vehicles at the end of incoming lanes with speed < 0.1
        for d in Direction:
            try:
                approach = self.network.get_incoming_approach(d)
                for lane in approach.get_lanes():
                    for v in lane.get_vehicles():
                        if v.position >= lane.length - 5.0 and v.speed < 0.5:
                            yielding_count += 1
            except KeyError:
                pass

            # Count circulating from connection lanes
            # Let's check connection lanes inside network or active vehicles
            # Since get_state does not have access to active_vehicles list directly,
            # we can look up vehicles registered on connection lanes in the network.
            # But wait! We can just scan all active vehicles if we store a reference or
            # count from the lanes.
            # We can find connection vehicles by finding vehicles in all exit/incoming lanes?
            # No, connection lanes are not inside incoming/outgoing approaches, but they have vehicles.
            # In setup_default_intersection, we create connection lanes. Let's make sure
            # we can count them:
            # For simplicity, let's scan all incoming lanes' vehicles and see if any vehicle is on a connection lane.
            # Wait, the vehicle pool has active vehicles. But BaseController.get_state() signature does not pass active_vehicles.
            # So we can look at the vehicles registered on the connection lanes of the routes of active vehicles in approaches,
            # or just look at all lanes.
            # Let's query all vehicles in incoming/outgoing approaches, and check if any vehicle's current lane is a connection lane.
            # But connection lanes are not inside incoming or outgoing.
            # Let's traverse vehicles from incoming approaches:
            # Actually, vehicles transition from incoming to connection.
            # When on connection, the vehicle's `lane` is the connection lane.
            # We can traverse the vehicles in the connection lanes if we track them.
            # Since `Lane.get_vehicles()` tracks vehicles on it, we can find them if we keep a reference to connection lanes.
            # In `generate_route` we create connection lanes dynamically, which means they are new instances every time.
            # Wait, is that a problem?
            # Yes! If we create connection lanes dynamically in `generate_route`, they are new instances,
            # so the vehicle is added to a dynamically created lane instance!
            # But the simulation loop updates vehicles, and the vehicle calls `self.lane.add_vehicle(self)`.
            # So the dynamically created lane instance will correctly have the vehicle in its `_vehicles` list!
            # But how do we find these connection lanes?
            # We can traverse all active vehicles in the simulation.
            # Wait, how does `get_state` access active vehicles?
            # We can store a reference to the active vehicles list during `update(self, dt, active_vehicles)`!
            # Yes! `self._active_vehicles = active_vehicles`.
            # That is incredibly simple and robust!

        active_vehs = getattr(self, "_active_vehicles", [])
        circulating_count = sum(
            1
            for v in active_vehs
            if v.lane is not None and v.lane.lane_id.startswith("conn")
        )

        return {
            "type": "roundabout",
            "timeInCurrentState": round(self.time_in_current_state, 2),
            "innerRadius": self.inner_radius,
            "outerRadius": self.outer_radius,
            "circulatingCount": circulating_count,
            "yieldingCount": yielding_count,
            "gapAcceptance": self.critical_gap,
        }

    def update_active_vehicles_ref(self, active_vehicles: List[Vehicle]) -> None:
        self._active_vehicles = active_vehicles
