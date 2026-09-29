"""The optimised position/heading lookups must return exactly what the
original implementations returned (same floats, not approximately).

Lane.get_point_at_distance / get_heading_at_distance now bisect over
precomputed per-segment values, and Vehicle.coords / heading memoise on
(lane, position). The reference versions below are the original code; the
last test runs whole simulations on them and on the optimised code and
compares every vehicle's position and speed on every tick.
"""

import math
import random
from typing import Any, Dict, List, Tuple

import pytest

from src.core.limits import demand_vehicle_limit
from src.roads.lane import Lane
from src.snapshot.dual_orchestrator import DualSimulationOrchestrator
from src.vehicles.vehicle import Vehicle


def reference_point(lane: Lane, distance: float) -> Tuple[float, float]:
    dist = max(0.0, min(distance, lane.length))
    if len(lane.waypoints) == 2:
        ratio = dist / lane.length
        return (
            lane.start_coords[0] + ratio * lane.vector[0],
            lane.start_coords[1] + ratio * lane.vector[1],
        )
    cum = lane._cum_lengths
    for i in range(len(cum) - 1):
        if dist <= cum[i + 1] or i == len(cum) - 2:
            seg_ratio = (dist - cum[i]) / max(1e-6, cum[i + 1] - cum[i])
            seg_ratio = max(0.0, min(1.0, seg_ratio))
            p1, p2 = lane.waypoints[i], lane.waypoints[i + 1]
            return (
                p1[0] + seg_ratio * (p2[0] - p1[0]),
                p1[1] + seg_ratio * (p2[1] - p1[1]),
            )
    return lane.end_coords


def reference_heading(lane: Lane, distance: float) -> float:
    dist = max(0.0, min(distance, lane.length))
    if len(lane.waypoints) == 2:
        return lane.heading
    cum = lane._cum_lengths
    for i in range(len(cum) - 1):
        if dist <= cum[i + 1] or i == len(cum) - 2:
            p1, p2 = lane.waypoints[i], lane.waypoints[i + 1]
            angle = math.degrees(math.atan2(p2[0] - p1[0], p2[1] - p1[1]))
            return (angle + 360.0) % 360.0
    return lane.heading


def _network_lanes() -> List[Lane]:
    """Every lane vehicles drove on in 60 s of 2-lane traffic at both
    junctions (connection lanes are only created as routes need them)."""
    config = {
        "simulation": {"timeStep": 0.1, "duration": 60.0, "randomSeed": 1},
        "roads": {"lanesPerApproach": {"north": 2, "south": 2, "east": 2, "west": 2}},
        "traffic": {"arrivalRate": 0.8, "totalVehicles": 200},
    }
    orch = DualSimulationOrchestrator(config)
    lanes: Dict[int, Lane] = {}
    for engine in (orch.engine_signal, orch.engine_roundabout):
        for _ in range(600):
            engine.step()
            for v in engine.pool.active_vehicles:
                for lane in v.route:
                    lanes[id(lane)] = lane
    return list(lanes.values())


def test_lookups_match_the_linear_scan_exactly() -> None:
    lanes = _network_lanes()
    curved = [lane for lane in lanes if len(lane.waypoints) > 2]
    assert curved, "expected curved connection lanes to exercise the bisection"
    rng = random.Random(0)
    for lane in lanes:
        distances = [-5.0, -0.0, 0.0, lane.length, lane.length + 3.0]
        distances += list(lane._cum_lengths)  # every segment boundary
        distances += [rng.uniform(-1.0, lane.length + 1.0) for _ in range(200)]
        for d in distances:
            assert lane.get_point_at_distance(d) == reference_point(lane, d)
            assert lane.get_heading_at_distance(d) == reference_heading(lane, d)


def test_pose_memo_follows_lane_and_position() -> None:
    a = Lane("a", 0.0, 0.0, 0.0, 100.0)
    b = Lane("b", 0.0, 100.0, 100.0, 100.0)
    v = Vehicle("v", 4.5, 1.8, 10.0, [a, b], start_position=10.0)
    assert v.coords == (0.0, 10.0)
    assert v.heading == 0.0
    v.position = 20.0
    assert v.coords == (0.0, 20.0)
    v.lane = b
    assert v.coords == (20.0, 100.0)
    assert v.heading == 90.0
    v.lane = None
    assert v.coords == (0.0, 0.0)
    assert v.heading == 0.0


def _trajectory(rate: float, lanes: int, seed: int) -> List[Any]:
    duration = 60.0
    config = {
        "simulation": {
            "timeStep": 0.1,
            "duration": duration,
            "warmupTime": 10.0,
            "randomSeed": seed,
        },
        "roads": {
            "lanesPerApproach": {d: lanes for d in ("north", "south", "east", "west")}
        },
        "traffic": {
            "arrivalRate": rate,
            "totalVehicles": demand_vehicle_limit(rate, duration),
        },
    }
    orch = DualSimulationOrchestrator(config)
    ticks: List[Any] = []
    for _ in range(orch.clock_signal.ticks_for_duration(duration)):
        for engine in (orch.engine_signal, orch.engine_roundabout):
            engine.step()
            ticks.append(
                [
                    (
                        v.vehicle_id,
                        v.position,
                        v.speed,
                        v.lane.lane_id if v.lane else "",
                    )
                    for v in engine.pool.active_vehicles
                ]
            )
    ticks.append([orch.engine_signal.pool.collision_count])
    ticks.append([orch.engine_roundabout.pool.collision_count])
    return ticks


@pytest.mark.parametrize("rate,lanes,seed", [(0.6, 1, 42), (0.9, 2, 3)])
def test_simulation_is_unchanged_by_the_lookup_optimisations(
    monkeypatch: pytest.MonkeyPatch, rate: float, lanes: int, seed: int
) -> None:
    optimised = _trajectory(rate, lanes, seed)

    with monkeypatch.context() as m:
        m.setattr(Lane, "get_point_at_distance", reference_point)
        m.setattr(Lane, "get_heading_at_distance", reference_heading)
        m.setattr(
            Vehicle,
            "coords",
            property(
                lambda v: (
                    (0.0, 0.0)
                    if v.lane is None
                    else v.lane.get_point_at_distance(v.position)
                )
            ),
        )
        m.setattr(
            Vehicle,
            "heading",
            property(
                lambda v: (
                    0.0
                    if v.lane is None
                    else v.lane.get_heading_at_distance(v.position)
                )
            ),
        )
        reference = _trajectory(rate, lanes, seed)

    assert optimised == reference
