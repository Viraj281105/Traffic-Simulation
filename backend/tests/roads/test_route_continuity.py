"""Every route the network can build is one continuous path.

``Vehicle.update_state`` moves a vehicle that runs off the end of a lane onto
the next lane of its route at the overflow distance, so a route whose lanes do
not meet end to start would teleport vehicles across the gap. This sweeps the
supported layouts (signal and roundabout, 1-4 lanes, 1-3 ring lanes, three and
four arms, a skewed arm) and checks every route a vehicle can be given: each
lane finite and of positive length, each join exact.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

import pytest

from src.core.clock import Clock
from src.core.enums import Direction
from src.engine.simulation_engine import SimulationEngine
from src.scenario.documents import compile_scenario, parse_scenario

Layout = Tuple[str, int, Optional[int], int, Optional[float]]

LAYOUTS: List[Layout] = [
    ("signal", lanes, None, arms, bearing)
    for lanes in (1, 2, 3, 4)
    for arms in (4, 3)
    for bearing in (None, 110.0)
] + [
    ("roundabout", lanes, rings, arms, None)
    for lanes in (1, 2, 3, 4)
    for rings in (1, 2, 3)
    for arms in (4, 3)
]


def _document(layout: Layout) -> Dict[str, Any]:
    junction, lanes, rings, arms, bearing = layout
    approaches: Dict[str, Any] = {
        d: {"lanes": lanes, "length": 150.0, "vehiclesPerHour": 300}
        for d in ("north", "south", "east", "west")
    }
    if arms == 3:
        approaches["west"] = None
    if bearing is not None:
        approaches["east"] = dict(approaches["east"], bearing=bearing)
    doc: Dict[str, Any] = {
        "format": "urbanflow-scenario",
        "version": 1,
        "name": "continuity",
        "junction": {
            "type": "roundabout" if junction == "roundabout" else "fixed_time_signal"
        },
        "approaches": approaches,
        "simulation": {"duration": 60, "warmup": 0, "seed": 1},
    }
    if junction == "roundabout":
        doc["roundabout"] = {"circulatingLanes": rings}
    return doc


@pytest.mark.parametrize(
    "layout", LAYOUTS, ids=lambda layout: "-".join(str(x) for x in layout)
)
def test_every_route_is_continuous_and_finite(layout: Layout) -> None:
    parsed, errors = parse_scenario(_document(layout))
    assert not errors, errors
    strategy = "roundabout" if layout[0] == "roundabout" else "fixed_time"
    network = SimulationEngine(
        Clock(0.1), duration=60.0, config=compile_scenario(parsed, strategy)
    ).network
    routes = 0
    for direction in Direction:
        try:
            lanes = network.lane_count(direction)
        except KeyError:
            continue  # the slot with no arm
        for index in range(lanes):
            for turn in network.permitted_turns(direction, index):
                target = network._resolve_target_direction(direction, turn)
                try:
                    network.get_outgoing_approach(target)
                except KeyError:
                    # Into the missing arm: validate_scenario rejects any
                    # turning share that would use it (F-39).
                    continue
                route = network.generate_route(direction, index, turn)
                routes += 1
                for lane in route:
                    assert math.isfinite(lane.length) and lane.length > 0, lane.lane_id
                    assert all(
                        math.isfinite(c) for point in lane.waypoints for c in point
                    ), lane.lane_id
                for a, b in zip(route, route[1:]):
                    assert math.dist(a.end_coords, b.start_coords) < 1e-9, (
                        f"{a.lane_id} ends {a.end_coords}, {b.lane_id} starts "
                        f"{b.start_coords}"
                    )
    assert routes > 0


def test_a_turn_into_the_missing_arm_fails_with_a_clear_error() -> None:
    """validate_scenario rejects such turning shares; a caller that compiles a
    document without it gets a ValueError naming the arm, not a KeyError from
    inside the connection-lane builder (F-39)."""
    from src.core.enums import TurnIntent
    from src.scenario.documents import validate_scenario

    doc = _document(("signal", 2, None, 3, None))
    for approach in doc["approaches"].values():
        if approach is not None:
            approach["turning"] = {"left": 0.2, "straight": 0.6, "right": 0.2}
    assert not validate_scenario(doc, ["fixed_time"])["valid"]
    parsed, errors = parse_scenario(doc)
    assert not errors
    network = SimulationEngine(
        Clock(0.1), duration=60.0, config=compile_scenario(parsed, "fixed_time")
    ).network
    with pytest.raises(ValueError, match="no west arm"):
        network.generate_route(Direction.EAST, 0, TurnIntent.STRAIGHT)
