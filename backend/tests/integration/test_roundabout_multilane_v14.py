"""V1.4 multi-lane roundabout: safe and free of lock-ups across configurations.

The V1.0-V1.3 multi-lane ring (known limitation K1) let a vehicle leaving the
inner ring cut across the outer ring unarbitrated: low-speed contacts, and
lock-ups with heavy vehicles. V1.4 replaces it with an explicit lane
designation, keep-clear entry and exit convergence zones
(controllers/roundabout.py). These tests run complete simulations of the
configurations V1.4 supports — two-lane rings, unequal approaches, three-lane
approaches merging onto two ring lanes, mixed and heavy traffic, high demand —
and assert what failure looks like from outside: a contact counted by the
collision audit, or the junction going quiet.

Every scenario is a scenario document compiled by the product's own compiler,
so the tests exercise exactly what users run.
"""

import logging
from typing import Any, Dict, Optional

import pytest

from src.controllers.factory import build_tick_callback, create_controller
from src.core.clock import Clock
from src.core.engine import SimulationEngine
from src.core.scenario import compile_scenario, parse_scenario
from src.metrics.collector import MetricCollector

TURN = {"left": 0.2, "straight": 0.6, "right": 0.2}
MIXES: Dict[str, Optional[Dict[str, float]]] = {
    "cars": None,
    "mixed": {"car": 0.6, "suv": 0.2, "bus": 0.05, "truck": 0.05, "motorcycle": 0.1},
    "heavy": {"car": 0.5, "suv": 0.1, "bus": 0.15, "truck": 0.15, "motorcycle": 0.1},
    "moto": {"car": 0.3, "suv": 0.1, "bus": 0.05, "truck": 0.05, "motorcycle": 0.5},
}


def _scenario(
    lanes: Dict[str, int],
    total_vph: float,
    mix: Optional[Dict[str, float]],
    seed: int,
    duration: float,
    split: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    split = split or {d: 0.25 for d in ("north", "south", "east", "west")}
    return {
        "format": "urbanflow-scenario",
        "version": 1,
        "junction": {"type": "roundabout"},
        "approaches": {
            d: {
                "lanes": lanes[d],
                "vehiclesPerHour": total_vph * split[d],
                "turning": TURN,
            }
            for d in ("north", "south", "east", "west")
        },
        "vehicles": {"mix": mix},
        "roundabout": {"circulatingLanes": 2},
        "simulation": {"duration": duration, "warmup": 20, "seed": seed},
    }


def _run(doc: Dict[str, Any]) -> Dict[str, float]:
    document, errors = parse_scenario(doc)
    assert document is not None, errors
    config = compile_scenario(document, "roundabout")
    duration = config["simulation"]["duration"]
    clock = Clock(time_step=0.1)
    engine = SimulationEngine(clock, duration=duration, config=config)
    controller = create_controller(config, engine.network)
    engine.controller = controller
    collector = MetricCollector(config)
    engine.register_tick_callback(
        build_tick_callback(controller, clock, engine, collector)
    )
    logging.getLogger("src.vehicles.pool").setLevel(logging.ERROR)

    last_exit: Optional[float] = None
    longest_gap = 0.0
    standstill = 0.0
    standstill_since: Optional[float] = None
    seen = 0
    while engine.status.value.lower() != "completed":
        engine.step()
        now = clock.get_elapsed_time()
        exited = len(engine.pool.exited_vehicles)
        if exited > seen:
            if last_exit is not None:
                longest_gap = max(longest_gap, now - last_exit)
            last_exit, seen = now, exited
        inside = [
            v
            for v in engine.pool.active_vehicles
            if v.lane is not None and v.lane.lane_id.startswith("conn")
        ]
        if inside and all(v.speed < 0.1 for v in inside):
            standstill_since = now if standstill_since is None else standstill_since
            standstill = max(standstill, now - standstill_since)
        else:
            standstill_since = None
    state = controller.get_state()
    return {
        "collisions": float(engine.pool.collision_count),
        "exited": float(seen),
        "longest_gap": longest_gap,
        "standstill": standstill,
        "zone_yields": float(state["exitYieldEvents"]),
        "forced": float(state["forcedExitCommitments"]),
        "rings": float(state["circulatingLanes"]),
    }


EVEN2 = {"north": 2, "south": 2, "east": 2, "west": 2}


def test_two_lane_ring_heavy_traffic_high_demand_is_safe_and_flows() -> None:
    """Fast representative: 15 % buses + 15 % trucks at 3,240 veh/h."""
    result = _run(_scenario(EVEN2, 3240, MIXES["heavy"], seed=13, duration=150))
    assert result["rings"] == 2
    assert result["collisions"] == 0, result
    assert result["standstill"] < 20.0, result
    assert result["longest_gap"] <= 30.0, result
    # The zones are doing work, not sitting idle.
    assert result["zone_yields"] > 0, result


def test_unequal_approaches_on_a_two_lane_ring() -> None:
    """A two-lane main road and a one-lane side road: exits merge."""
    lanes = {"north": 2, "south": 2, "east": 1, "west": 1}
    result = _run(_scenario(lanes, 1700, MIXES["mixed"], seed=2, duration=150))
    assert result["collisions"] == 0, result
    assert result["standstill"] < 20.0, result
    assert result["exited"] > 30, result


def test_three_lane_approaches_merging_onto_two_ring_lanes() -> None:
    lanes = {"north": 3, "south": 3, "east": 2, "west": 2}
    result = _run(_scenario(lanes, 2400, MIXES["moto"], seed=5, duration=150))
    assert result["collisions"] == 0, result
    assert result["standstill"] < 20.0, result
    assert result["exited"] > 30, result


def test_asymmetric_demand_on_a_two_lane_ring() -> None:
    split = {"north": 0.5, "south": 0.2, "east": 0.15, "west": 0.15}
    result = _run(_scenario(EVEN2, 2600, None, seed=3, duration=150, split=split))
    assert result["collisions"] == 0, result
    assert result["standstill"] < 20.0, result


def test_a_long_vehicle_queued_past_an_exit_stops_traffic_leaving_by_it() -> None:
    """Regression (found by the V1.4 validation matrix): a 10.6 m bus stood on
    the inner lane just past an exit, its tail over the start of that exit's
    curve, and a 9.4 m truck leaving by the exit drove into it at t = 181.9 s:
    ring following ignored vehicles beyond the follower's exit, judged by the
    leader's centre. It now judges by the leader's tail (vehicles/router.py)."""
    result = _run(_scenario(EVEN2, 0.5 * 2180, MIXES["moto"], seed=2, duration=190))
    assert result["collisions"] == 0, result


@pytest.mark.slow
@pytest.mark.parametrize("mix", list(MIXES))
@pytest.mark.parametrize("ratio", [0.5, 0.9, 1.3])
@pytest.mark.parametrize("seed", [1, 2])
def test_two_lane_ring_sweep_has_no_contacts_or_lockups(
    mix: str, ratio: float, seed: int
) -> None:
    """Every mix at moderate, near-capacity and stress demand (share of the
    2-lane reference capacity, 2,180 veh/h), 300 s."""
    result = _run(_scenario(EVEN2, ratio * 2180, MIXES[mix], seed=seed, duration=300))
    assert result["collisions"] == 0, result
    assert result["standstill"] < 30.0, result
    assert result["longest_gap"] <= 30.0, result
