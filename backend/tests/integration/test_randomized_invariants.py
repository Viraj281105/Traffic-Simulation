"""Physical invariants over randomly drawn, valid scenarios.

``run_invariant_checks`` (study/validation.py) checks one configuration: two
lanes, 0.4 veh/s, fixed-time signal and roundabout, comparing delay and
throughput. This samples the scenario space the product accepts -- every
strategy including adaptive, one and two lanes, three- and four-arm
junctions, light to oversaturated demand, mixed vehicle classes -- through
the same compiler the API uses (``compile_scenario``), and checks every tick:

* vehicle conservation: spawned == active + exited;
* every active vehicle has a finite, non-negative speed and finite position;
* a signal (fixed-time or adaptive) never shows conflicting greens;
* the clock advances by exactly one time step per tick;

and per run: no collisions, and an identical second run reproduces the
*complete* metrics document bit for bit (same process, same seed).

The draw is seeded, so a failure names a reproducible configuration. The fast
test samples a few configurations; the slow one many more (nightly CI).
"""

import json
import math
import random
from typing import Any, Dict, List, Tuple

import pytest

from src.controllers.factory import create_controller
from src.core.clock import Clock
from src.core.enums import Direction, TurnIntent
from src.engine.simulation_engine import SimulationEngine
from src.engine.tick_callback import build_tick_callback
from src.metrics.collector import MetricCollector
from src.roads.lane_config import target_direction
from src.scenario.documents import compile_scenario, parse_scenario, validate_scenario

ARMS = ("north", "south", "east", "west")
STRATEGIES = ("fixed_time", "adaptive", "roundabout")
NS, EW = {"north", "south"}, {"east", "west"}


def _draw(rng: random.Random, index: int) -> Tuple[Dict[str, Any], str]:
    lanes = rng.choice((1, 2))
    arms = ARMS if rng.random() < 0.75 else ARMS[:3]
    per_lane_vph = rng.choice((150, 400, 700, 1000))
    approaches: Dict[str, Any] = {}
    for arm in arms:
        shares = {
            "left": rng.choice((0.1, 0.2, 0.3)),
            "straight": rng.choice((0.5, 0.6, 0.7)),
            "right": rng.choice((0.1, 0.2)),
        }
        # No traffic toward an arm the junction does not have (the validator
        # refuses it); the remaining shares are renormalised.
        for turn in list(shares):
            exit_arm = target_direction(Direction(arm), TurnIntent(turn))
            if exit_arm.value not in arms:
                shares[turn] = 0.0
        total = sum(shares.values())
        turning = {t: round(v / total, 4) for t, v in shares.items()}
        turning["straight"] = round(1 - turning["left"] - turning["right"], 4)
        approaches[arm] = {
            "lanes": lanes,
            "vehiclesPerHour": per_lane_vph * lanes * rng.uniform(0.6, 1.2),
            "turning": turning,
        }
    if len(arms) < len(ARMS):
        approaches["west"] = None  # a three-arm (T) junction
    document: Dict[str, Any] = {
        "format": "urbanflow-scenario",
        "version": 1,
        "name": f"random-{index}",
        "junction": {"type": "fixed_time_signal"},
        "approaches": approaches,
        "simulation": {"duration": 45, "warmup": 5, "seed": rng.randrange(10_000)},
    }
    if rng.random() < 0.4:
        document["vehicles"] = {
            "mix": {
                "car": 0.7,
                "suv": 0.1,
                "bus": 0.1,
                "truck": 0.05,
                "motorcycle": 0.05,
            }
        }
    return document, rng.choice(STRATEGIES)


def _cases(count: int, seed: int) -> List[Tuple[Dict[str, Any], str]]:
    rng = random.Random(seed)
    cases = []
    while len(cases) < count:
        document, strategy = _draw(rng, len(cases))
        # Only what the product's own validator accepts is in scope.
        if validate_scenario(document, [strategy])["valid"]:
            cases.append((document, strategy))
    return cases


def _signal_greens(controller: Any) -> set[str]:
    state = controller.get_state() if hasattr(controller, "get_state") else {}
    return {
        str(s.get("direction", "")).lower()
        for s in (state.get("signals") or [])
        if s.get("color") == "green"
    }


def _run_checked(config: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    sim = config["simulation"]
    clock = Clock(time_step=sim["timeStep"])
    engine = SimulationEngine(clock, duration=sim["duration"], config=config)
    controller = create_controller(config, engine.network)
    engine.controller = controller
    collector = MetricCollector(config)
    engine.register_tick_callback(
        build_tick_callback(controller, clock, engine, collector)
    )
    is_signal = config["geometry"]["intersectionType"] != "roundabout"

    problems: List[str] = []
    tick = 0
    while engine.status.value.lower() != "completed" and len(problems) < 5:
        engine.step()
        tick += 1
        spawned = engine.spawner.spawned_count if engine.spawner else 0
        active, exited = engine.pool.active_vehicles, engine.pool.exited_vehicles
        if spawned != len(active) + len(exited):
            problems.append(
                f"tick {tick}: spawned {spawned} != active {len(active)} + exited {len(exited)}"
            )
        for v in active:
            if not math.isfinite(v.speed) or v.speed < -0.01:
                problems.append(f"tick {tick}: {v.vehicle_id} speed {v.speed}")
            if not math.isfinite(v.position):
                problems.append(f"tick {tick}: {v.vehicle_id} position {v.position}")
        if not math.isclose(
            clock.get_elapsed_time(), tick * sim["timeStep"], abs_tol=1e-9
        ):
            problems.append(f"tick {tick}: clock at {clock.get_elapsed_time()}")
        if is_signal:
            greens = _signal_greens(controller)
            if greens & NS and greens & EW:
                problems.append(f"tick {tick}: conflicting greens {sorted(greens)}")
    if engine.pool.collision_count:
        problems.append(f"{engine.pool.collision_count} collision(s)")
    metrics = collector.get_metrics(
        clock.get_elapsed_time(),
        engine.pool.active_vehicles,
        engine.pool.exited_vehicles,
        engine.spawner.spawned_count if engine.spawner else 0,
        engine.pool.collision_count,
    )
    return metrics, problems


def _check(document: Dict[str, Any], strategy: str) -> None:
    parsed, errors = parse_scenario(document)
    assert parsed is not None, errors
    config = compile_scenario(parsed, strategy)
    first, problems = _run_checked(config)
    label = f"{strategy} {json.dumps(document, sort_keys=True)}"
    assert not problems, (label, problems)
    second, _ = _run_checked(compile_scenario(parsed, strategy))
    assert json.dumps(first, sort_keys=True, default=str) == json.dumps(
        second, sort_keys=True, default=str
    ), f"same seed, different metrics: {label}"


@pytest.mark.parametrize("case", range(6))
def test_invariants_hold_on_random_valid_scenarios(case: int) -> None:
    # Seed 1's six cases cover every strategy, one and two lanes, a T
    # junction and mixed traffic (the slow test below draws 48 more).
    document, strategy = _cases(6, seed=1)[case]
    _check(document, strategy)


@pytest.mark.slow
@pytest.mark.parametrize("case", range(48))
def test_invariants_hold_on_many_random_valid_scenarios(case: int) -> None:
    document, strategy = _cases(48, seed=7)[case]
    _check(document, strategy)
