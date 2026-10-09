import math
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from src.core.engine import SimulationEngine
from src.core.enums import Direction, TurnIntent
from src.metrics.collector import MetricCollector
from src.vehicles.vehicle import Vehicle


# Order in which a lane's permitted movements are listed (left to right as a
# driver sees the lane arrows).
def _uses_real_world_geometry(config: Dict[str, Any]) -> bool:
    """True when a config uses V1.5 geometry (missing arms, bearings or
    per-arm lane widths)."""
    if (config.get("geometry") or {}).get("arms") is not None:
        return True
    return any(
        isinstance(item, dict)
        and (item.get("bearing") is not None or item.get("laneWidth") is not None)
        for item in (config.get("roads") or {}).get("approaches") or []
    )


_TURN_ORDER = (
    TurnIntent.UTURN,
    TurnIntent.LEFT,
    TurnIntent.STRAIGHT,
    TurnIntent.RIGHT,
)


def _lane_change_side(vehicle: Vehicle) -> Optional[str]:
    """ "left"/"right" while a lane change is in progress, else None.

    The side is relative to the driver: the direction of the remaining
    lateral move (towards the target lane) against the vehicle's heading.
    """
    maneuver = vehicle.lane_change
    if maneuver is None:
        return None
    heading = math.radians(vehicle.heading)
    hx, hy = math.sin(heading), math.cos(heading)
    # Remaining move is towards the target lane: minus the offset.
    mx, my = -maneuver.offset_x, -maneuver.offset_y
    cross = hx * my - hy * mx
    return "left" if cross > 0 else "right"


class SnapshotBuilder:
    """Assembles the complete state snapshot dictionary from the active simulation engine."""

    def __init__(
        self,
        simulation_id: str,
        config_id: str,
        engine: SimulationEngine,
        collector: MetricCollector,
        controller: Any,
    ) -> None:
        self.simulation_id: str = simulation_id
        self.config_id: str = config_id
        self.engine: SimulationEngine = engine
        self.collector: MetricCollector = collector
        self.controller: Any = controller

    def build(self) -> Dict[str, Any]:
        """Assembles a state dictionary conforming to snapshot.schema.json."""
        # Hold the engine's lock for the whole build so this never reads a
        # torn tick or has pool.active_vehicles/exited_vehicles mutated out
        # from under it mid-iteration (see SimulationEngine.lock / .step()).
        # Safe to call both from a REST/WebSocket handler (a different
        # thread acquiring the lock) and from a tick callback running
        # synchronously inside step() itself (RLock allows the reentrant
        # acquisition on that same thread).
        with self.engine.lock:
            return self._build_locked()

    def _build_locked(self) -> Dict[str, Any]:
        clock = self.engine.clock
        elapsed = clock.get_elapsed_time()
        dt = clock.time_step

        # Gather vehicle states
        vehicles_list = []
        counts = {
            "active": len(self.engine.pool.active_vehicles),
            "approaching": 0,
            "waiting": 0,
            "crossing": 0,
            "inRoundabout": 0,
            "exited": len(self.engine.pool.exited_vehicles),
        }

        dir_map = {
            "n": "north",
            "s": "south",
            "e": "east",
            "w": "west",
            "north": "north",
            "south": "south",
            "east": "east",
            "west": "west",
        }
        is_roundabout = getattr(self.engine.network, "is_roundabout", False)

        # Active vehicles
        for v in self.engine.pool.active_vehicles:
            cx, cy = v.coords
            state_str = v.state.value.lower()
            if v.lane and v.lane.lane_id.startswith("conn"):
                state_str = "in_roundabout" if is_roundabout else "crossing"
            elif v.lane and "roundabout" in v.lane.lane_id:
                state_str = "in_roundabout"

            # Increment count
            if state_str == "approaching":
                counts["approaching"] += 1
            elif state_str == "waiting":
                counts["waiting"] += 1
            elif state_str == "crossing":
                counts["crossing"] += 1
            elif state_str == "in_roundabout":
                counts["inRoundabout"] += 1

            # Infer direction and turn intent conforming to schema enum (north, south, east, west)
            direction_str = "north"
            if v.route:
                raw_dir = v.route[0].lane_id.split("_")[0].lower()
                direction_str = dir_map.get(raw_dir, "north")

            # Turn intent
            turn_str = "straight"
            if len(v.route) > 1:
                # We can deduce intent based on route shape, or spawner can set v.turn_intent
                turn_intent = getattr(v, "turn_intent", None)
                if turn_intent is not None:
                    turn_str = turn_intent.value.lower()

            vehicles_list.append(
                {
                    "id": v.vehicle_id,
                    "x": round(cx, 2),
                    "y": round(cy, 2),
                    "speed": round(v.speed, 2),
                    "acceleration": round(v.acceleration, 2),
                    "heading": round(v.heading % 360, 1),
                    "length": round(v.length, 2),
                    "width": round(v.width, 2),
                    "state": state_str,
                    "laneId": v.lane.lane_id if v.lane else "",
                    "direction": direction_str,
                    "turnIntent": turn_str,
                    "waitTime": round(v.wait_time, 2),
                    "stopCount": v.stop_count,
                    "spawnTime": round(getattr(v, "spawn_time", 0.0), 2),
                    "exitTime": None,
                    "distanceTraveled": round(
                        v.position, 2
                    ),  # approximation along route
                    # V1.1 / V1.2 (additive): vehicle class, lane index
                    # across its approach (None on connection lanes of
                    # hand-built networks), and the side of a lane change in
                    # progress (None when not changing lanes).
                    "vehicleType": v.vehicle_type,
                    "laneIndex": getattr(v.lane, "index", None) if v.lane else None,
                    "laneChange": _lane_change_side(v),
                }
            )

        # Exited vehicles - serialize up to the most recent 50 to keep payload bounded
        # while snapshot["vehicleCounts"]["exited"] accurately records the full cumulative total
        exited_to_serialize = self.engine.pool.exited_vehicles
        if len(exited_to_serialize) > 50:
            exited_to_serialize = exited_to_serialize[-50:]

        for v in exited_to_serialize:
            direction_str = "north"
            if v.route:
                raw_dir = v.route[0].lane_id.split("_")[0].lower()
                direction_str = dir_map.get(raw_dir, "north")
            turn_str = "straight"
            turn_intent = getattr(v, "turn_intent", None)
            if turn_intent is not None:
                turn_str = turn_intent.value.lower()

            vehicles_list.append(
                {
                    "id": v.vehicle_id,
                    "x": 0.0,
                    "y": 0.0,
                    "speed": 0.0,
                    "acceleration": 0.0,
                    "heading": 0.0,
                    "length": round(v.length, 2),
                    "width": round(v.width, 2),
                    "state": "exited",
                    "laneId": "",
                    "direction": direction_str,
                    "turnIntent": turn_str,
                    "waitTime": round(v.wait_time, 2),
                    "stopCount": v.stop_count,
                    "spawnTime": round(getattr(v, "spawn_time", 0.0), 2),
                    "exitTime": round(getattr(v, "exit_time", elapsed), 2),
                    "distanceTraveled": round(v.position, 2),
                    "vehicleType": v.vehicle_type,
                    "laneIndex": None,
                    "laneChange": None,
                }
            )

        # Assemble intersection info
        geom_type = self.engine.config.get("geometry", {}).get(
            "intersectionType", "fixed_time_signal"
        )
        geom_center = self.engine.config.get("geometry", {}).get(
            "intersectionCenter", {"x": 0.0, "y": 0.0}
        )
        bounding_radius = self.engine.config.get("geometry", {}).get(
            "boundingRadius", 15.0
        )

        metrics_obj = self.collector.get_metrics(
            elapsed,
            self.engine.pool.active_vehicles,
            self.engine.pool.exited_vehicles,
            self.engine.spawner.spawned_count if self.engine.spawner else 0,
            self.engine.pool.collision_count,
        )

        deadlock_detector = getattr(self.engine, "deadlock_detector", None)
        if deadlock_detector is not None:
            metrics_obj["deadlockInsight"] = deadlock_detector.get_insight()

        # Map current queues for intersection object
        current_queues = metrics_obj["currentQueueLengths"]
        approaches_list = []
        network = self.engine.network
        # V1.5: a junction described with real-world geometry (missing arms,
        # bearings, per-arm lane widths) reports each arm's layout, so the
        # live map can draw it; the standard junction's snapshot is unchanged.
        real_world = _uses_real_world_geometry(self.engine.config)
        arms = network.geometry.arms if real_world else {}
        for d in Direction:
            if real_world and d not in arms:
                continue
            dir_str = d.value.lower()
            try:
                lane_count = len(
                    self.engine.network.get_incoming_approach(d).get_lanes()
                )
            except KeyError:
                lane_count = 1
            entry: Dict[str, Any] = {}
            if real_world:
                entry = {
                    "bearing": round(arms[d].bearing, 3),
                    "laneWidth": round(arms[d].lane_width, 3),
                    "stopLineDistance": round(network.stop_distances[d], 3),
                }
            approaches_list.append(
                {
                    **entry,
                    "direction": dir_str,
                    "queueLength": current_queues.get(dir_str, 0),
                    "laneCount": lane_count,
                    # Movements permitted from each incoming lane, lane 0
                    # (next to the centreline) first: the lane arrows.
                    "lanePermittedTurns": [
                        [
                            t.value
                            for t in _TURN_ORDER
                            if t in self.engine.network.permitted_turns(d, i)
                        ]
                        for i in range(lane_count)
                    ],
                }
            )

        controller_state = self.controller.get_state()
        if controller_state.get("type") == "fixed_time_signal":
            # Which way the signal times its greens (V1.3); the adaptive
            # controller reports its own, with its live decision state.
            controller_state.setdefault("signalControl", "fixed_time")

        return {
            "schemaVersion": "1.0.0",
            "simulationId": self.simulation_id,
            "configId": self.config_id,
            "timestamp": round(elapsed, 2),
            "frameNumber": clock.get_tick_count(),
            "tick": clock.get_tick_count(),
            "wallClockTime": datetime.now(timezone.utc).isoformat(),
            "samplingFrequency": round(1.0 / dt, 1) if dt > 0 else 10.0,
            "deltaTime": round(dt, 3),
            # Most of "metrics" only starts accumulating once timestamp
            # reaches this (the exceptions are instantaneous or whole-run
            # values: currentQueueLengths, activeVehicleCount,
            # averageTravelSpeed, totalVehiclesSpawned, collisionCount and
            # the config-derived spaceFootprintConsumed). Clients use it to
            # label warm-up zeros instead of presenting them as results.
            "warmupTime": self.collector.warmup_time,
            "simulationStatus": self.engine.status.value.lower(),
            "vehicles": vehicles_list,
            "intersection": {
                "type": geom_type,
                "centerX": geom_center.get("x", 0.0),
                "centerY": geom_center.get("y", 0.0),
                "boundingRadius": bounding_radius,
                "approaches": approaches_list,
                # Distance from the conflict area to each signal stop line
                # (V1.1: grows with the longest vehicle class in the mix).
                "stopLineSetback": round(
                    getattr(self.engine.network, "stop_line_setback", 3.5), 3
                ),
                # V1.4: a roundabout's circulating lanes (None for a signal),
                # which no longer always equal its approaches' lane counts.
                "circulatingLanes": (
                    int(getattr(self.engine.network, "circulating_lanes", 0) or 0)
                    or None
                ),
            },
            "controller": controller_state,
            "metrics": metrics_obj,
            "vehicleCounts": counts,
            # Lane model (V1.2): lane changes started this run (each one runs
            # to completion), those still in progress, and vehicles that
            # could not reach a lane permitting their turn in time.
            "laneModel": {
                "laneChanges": self.engine.pool.lane_change_count,
                "laneChangesInProgress": sum(
                    1
                    for v in self.engine.pool.active_vehicles
                    if v.lane_change is not None
                ),
                "missedTurns": self.engine.pool.missed_turn_count,
            },
            "units": {
                "distance": "meters",
                "speed": "meters_per_second",
                "acceleration": "meters_per_second_squared",
                "time": "seconds",
                "angle": "degrees",
            },
        }
