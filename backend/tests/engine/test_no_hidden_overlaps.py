"""No two vehicle bodies overlap, including pairs the collision audit skips (F-37).

``VehiclePool._collision_audit`` does not test pairs on the same lane, on
parallel lanes of one street, or sharing any route lane (unless one is
changing lane): close following is normal there. The same exemption also
covers two vehicles from different approaches bound for one exit lane. So a
car-following failure, or a merge into a shared exit, would never reach
``collisionCount``, and a reported 0 could not show it.

This checks every pair, exempt or not, with the audit's own oriented-box
test, at every tick of two representative busy runs (the leader-trace
scenarios). Measured in checkpoint 6: 0 overlaps in these and in 12 runs of
240 s (signal, adaptive, one- and two-ring roundabout, mixed vehicles, three
seeds).
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import pytest

from src.controllers.factory import create_controller
from src.core.clock import Clock
from src.engine.simulation_engine import SimulationEngine
from src.engine.tick_callback import build_tick_callback
from src.engine.vehicle_pool import _check_sat_overlap
from src.metrics.collector import MetricCollector
from src.scenario.documents import compile_scenario, parse_scenario
from tests.vehicles.test_leader_trace_pins import MIXED, _document

CASES: List[Tuple[str, Dict[str, Any], str]] = [
    (
        "roundabout-2ring-saturated-mixed",
        _document("roundabout", 2, 1000, 3, 60.0, rings=2, mix=MIXED),
        "roundabout",
    ),
    (
        "signal-2lane-busy-mixed",
        _document("fixed_time_signal", 2, 900, 7, 60.0, mix=MIXED),
        "fixed_time",
    ),
]


def _overlapping_pairs(engine: SimulationEngine) -> List[Tuple[str, str]]:
    vehicles = [v for v in engine.pool.active_vehicles if v.lane is not None]
    placed = [(v, v.coords) for v in vehicles]
    found = []
    for i, (va, (ax, ay)) in enumerate(placed):
        for vb, (bx, by) in placed[i + 1 :]:
            reach = (va.length + vb.length) * 0.6
            if (bx - ax) ** 2 + (by - ay) ** 2 > reach * reach:
                continue
            if _check_sat_overlap(va.get_bounding_box(), vb.get_bounding_box()):
                found.append((va.vehicle_id, vb.vehicle_id))
    return found


@pytest.mark.parametrize(
    "case_id, document, strategy", CASES, ids=[c[0] for c in CASES]
)
def test_no_vehicle_bodies_overlap_even_where_the_audit_does_not_look(
    case_id: str, document: Dict[str, Any], strategy: str
) -> None:
    parsed, errors = parse_scenario(document)
    assert not errors, errors
    config = compile_scenario(parsed, strategy)
    duration = float(document["simulation"]["duration"])
    clock = Clock(time_step=0.1)
    engine = SimulationEngine(clock, duration=duration, config=config)
    controller = create_controller(config, engine.network)
    engine.controller = controller
    engine.register_tick_callback(
        build_tick_callback(controller, clock, engine, MetricCollector(config))
    )

    for _ in range(clock.ticks_for_duration(duration)):
        engine.step()
        pairs = _overlapping_pairs(engine)
        assert not pairs, (
            f"{case_id}: vehicle bodies overlap at t={clock.get_elapsed_time():.1f} s: "
            f"{pairs[:3]}"
        )

    assert engine.pool.collision_count == 0
    assert engine.spawner is not None and engine.spawner.spawned_count > 50
