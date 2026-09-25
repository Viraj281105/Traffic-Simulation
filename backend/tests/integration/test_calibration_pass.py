"""Regression tests for the 2026-09-25 calibration pass.

* entering roundabout drivers no longer give way to circulating vehicles
  that leave the ring before reaching them;
* the roundabout's free-flow (geometric) delay is no longer inflated by a
  60 m crawl at entry speed;
* lane count changes what both junctions can carry;
* the calibrated demand table is the same in backend and frontend.
"""

import copy
import math
import re
from pathlib import Path
from typing import Any, Dict

import pytest

from src.controllers.factory import build_tick_callback, create_controller
from src.controllers.roundabout import RoundaboutController
from src.core.clock import Clock
from src.core.engine import SimulationEngine
from src.core.enums import Direction, TurnIntent
from src.metrics.collector import MetricCollector
from src.roads.network import RoadNetwork
from src.study.calibration import (
    DEMAND_LEVEL_RATIOS,
    REFERENCE_CAPACITY_VPH,
    demand_vph,
)
from src.vehicles.vehicle import Vehicle

SIGNAL = {
    "straightRightDuration": 30.0,
    "yellowDuration": 4.0,
    "allRedDuration": 2.0,
    "phaseSequence": [
        "ns_green",
        "ns_yellow",
        "all_red",
        "ew_green",
        "ew_yellow",
        "all_red",
    ],
}
ROUNDABOUT = {
    "innerRadius": 10.0,
    "outerRadius": 20.0,
    "criticalGap": 4.0,
    "followUpTime": 2.5,
    "entrySpeed": 5.0,
    "circulatingSpeed": 8.0,
}


def _run(kind: str, vph: float, lanes: int, seed: int, duration: float):
    config: Dict[str, Any] = {
        "simulation": {
            "duration": duration,
            "timeStep": 0.1,
            "warmupTime": 30.0,
            "randomSeed": seed,
        },
        "geometry": {"intersectionType": kind},
        "roads": {"approachLength": 200.0, "laneWidth": 3.5, "lanesPerApproach": lanes},
        "traffic": {"arrivalRate": vph / 3600.0, "totalVehicles": 5000},
        "controller": copy.deepcopy(ROUNDABOUT if kind == "roundabout" else SIGNAL),
    }
    clock = Clock(time_step=0.1)
    engine = SimulationEngine(clock, duration=duration, config=config)
    controller = create_controller(config, engine.network)
    engine.controller = controller
    collector = MetricCollector(config)
    engine.register_tick_callback(
        build_tick_callback(controller, clock, engine, collector)
    )
    while engine.status.value.lower() != "completed":
        engine.step()
    return engine, collector.get_metrics(
        clock.get_elapsed_time(),
        engine.pool.active_vehicles,
        engine.pool.exited_vehicles,
        engine.spawner.spawned_count if engine.spawner else 0,
        engine.pool.collision_count,
    )


# ── Gap acceptance ────────────────────────────────────────────────────────


def _ring(critical_gap: float):
    network = RoadNetwork()
    network.setup_default_intersection(
        approach_length=200.0, lane_width=3.5, lanes_per_approach=1, is_roundabout=True
    )
    controller = RoundaboutController(
        {
            "controller": {
                **ROUNDABOUT,
                "criticalGap": critical_gap,
                "followUpTime": 0.0,
            }
        },
        network,
    )
    return network, controller


def _place_at_angle(network, origin: Direction, turn: TurnIntent, angle_deg: float):
    """A circulating vehicle on the given path, at the given polar angle."""
    lane = network._get_or_create_connection_lane(origin, 0, turn)
    best = None
    s = 0.0
    while s <= lane.length:
        x, y = lane.get_point_at_distance(s)
        d = abs(((math.degrees(math.atan2(y, x)) - angle_deg) + 180) % 360 - 180)
        if best is None or d < best[0]:
            best = (d, s)
        s += 0.25
    assert best is not None and best[0] < 2.0
    veh = Vehicle(
        f"c_{origin.value}_{turn.value}",
        4.5,
        1.9,
        13.0,
        [lane],
        start_position=best[1],
        initial_speed=8.0,
    )
    return veh


def _east_entry_blocked(network, controller, vehicles) -> bool:
    controller.update(0.1, vehicles)
    east = network.get_incoming_approach(Direction.EAST).get_lanes()[0]
    return east.virtual_obstacle is not None


def test_entry_ignores_vehicles_leaving_before_the_entry() -> None:
    """West→south (right turn) exits at ~262°, before the east entry (~8°)."""
    network, controller = _ring(critical_gap=6.0)
    leaving = _place_at_angle(network, Direction.WEST, TurnIntent.RIGHT, 240.0)
    assert not _east_entry_blocked(network, controller, [leaving])


def test_entry_still_yields_to_vehicles_that_pass_it() -> None:
    """South→north (straight) passes the east entry: a real conflict."""
    network, controller = _ring(critical_gap=6.0)
    passing = _place_at_angle(network, Direction.SOUTH, TurnIntent.STRAIGHT, 330.0)
    assert _east_entry_blocked(network, controller, [passing])


# ── Free-flow speed and delay ─────────────────────────────────────────────


def test_empty_roundabout_geometric_delay_is_bounded() -> None:
    """At 180 veh/h nobody waits; the roundabout's delay is only slowing for
    the ring (13.4 s before the calibration pass, from a 60 m crawl)."""
    _, m = _run("roundabout", 180.0, 1, 1, 180.0)
    assert m["averageWaitTime"] == pytest.approx(0.0, abs=0.2)
    assert 3.0 < m["averageDelay"] < 10.0


def test_roundabout_has_lower_delay_than_signal_when_empty() -> None:
    """With equal speed assumptions, an empty roundabout costs less time
    than red lights (seed 1, 360 veh/h)."""
    _, sig = _run("fixed_time_signal", 360.0, 1, 1, 180.0)
    _, rnd = _run("roundabout", 360.0, 1, 1, 180.0)
    assert rnd["averageDelay"] < sig["averageDelay"]


# ── Lanes ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("kind", ["fixed_time_signal", "roundabout"])
def test_more_lanes_serve_more_traffic_fast(kind: str) -> None:
    """2,880 veh/h is beyond 1-lane capacity for both controls; two lanes
    carry clearly more of it."""
    _, one = _run(kind, 2880.0, 1, 1, 150.0)
    _, two = _run(kind, 2880.0, 2, 1, 150.0)
    assert two["throughput"] > one["throughput"] * 1.2


@pytest.mark.slow
@pytest.mark.parametrize("kind", ["fixed_time_signal", "roundabout"])
@pytest.mark.parametrize("seed", [1, 2, 3])
def test_capacity_rises_with_lanes(kind: str, seed: int) -> None:
    served = []
    for lanes in (1, 2, 3):
        _, m = _run(kind, 5400.0, lanes, seed, 240.0)
        served.append(m["throughput"])
    assert served[0] < served[1] < served[2]


@pytest.mark.slow
@pytest.mark.parametrize("seed", [1, 2, 3])
@pytest.mark.parametrize("level", list(DEMAND_LEVEL_RATIOS))
def test_single_lane_calibrated_levels_are_collision_free(
    seed: int, level: str
) -> None:
    for kind in ("fixed_time_signal", "roundabout"):
        engine, _ = _run(kind, float(demand_vph(level, 1)), 1, seed, 240.0)
        assert engine.pool.collision_count == 0, (kind, level, seed)


# ── Demand table parity ───────────────────────────────────────────────────


def test_demand_table_matches_the_frontend() -> None:
    ts = (
        Path(__file__).resolve().parents[3] / "frontend" / "src" / "types" / "demand.ts"
    ).read_text(encoding="utf-8")
    caps = dict(
        (int(k), int(v))
        for k, v in re.findall(
            r"^\s*([123]):\s*(\d+),",
            ts[ts.index("REFERENCE_CAPACITY_VPH") :],
            re.M,
        )[:3]
    )
    assert caps == REFERENCE_CAPACITY_VPH
    ratios = dict(re.findall(r'id: "(\w+)",\s*label: "[^"]+",\s*ratio: ([\d.]+)', ts))
    assert {k: float(v) for k, v in ratios.items()} == DEMAND_LEVEL_RATIOS


def test_levels_span_free_flow_to_oversaturation() -> None:
    """Light is well under, Over capacity well over, both controls' capacity
    at every lane count (capacities from the 2026-09-25 matrix)."""
    measured = {1: (1183, 1331), 2: (2457, 1903), 3: (3103, 2146)}
    for lanes, (sig, rnd) in measured.items():
        assert demand_vph("light", lanes) < 0.4 * min(sig, rnd)
        assert demand_vph("over", lanes) > max(sig, rnd)
