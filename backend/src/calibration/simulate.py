"""Run the unchanged engine once and tally what comparison needs.

A read-only adapter: it steps the engine exactly as ``study.runner.
simulate_geometry`` does, then reads the pool's exited vehicles (origin,
movement, class, travel time), which the metric collector does not break down
by movement. Nothing here writes to the engine, pool or collector.
"""

from __future__ import annotations

from typing import Any, Dict, List

from src.metrics.definitions.approach_breakdown import origin_of
from src.snapshot.dual_orchestrator import DualSimulationOrchestrator


def geometry_for(strategy: str) -> str:
    return "roundabout" if strategy == "roundabout" else "signal"


def simulate_once(config: Dict[str, Any], strategy: str) -> Dict[str, Any]:
    """Run ``config`` for its own duration; return the measured window's tally.

    {measuredSeconds, flowCount{approach}, movementCount{approach:{move}},
     travelTimes{approach:[s]}, movementTravelTimes{approach:{move:[s]}},
     classCount{class}, exited, metrics{approachBreakdown, signalTiming, ...}}
    """
    geometry = geometry_for(strategy)
    orch = DualSimulationOrchestrator(config)
    engine = getattr(orch, f"engine_{geometry}")
    clock = getattr(orch, f"clock_{geometry}")
    collector = getattr(orch, f"collector_{geometry}")

    duration = float(config["simulation"]["duration"])
    for _ in range(clock.ticks_for_duration(duration)):
        engine.step()

    elapsed = clock.get_elapsed_time()
    warmup = float(collector.warmup_time)
    metrics = collector.get_metrics(
        elapsed,
        engine.pool.active_vehicles,
        engine.pool.exited_vehicles,
        engine.spawner.spawned_count if engine.spawner else 0,
        engine.pool.collision_count,
    )

    flow: Dict[str, int] = {}
    movement: Dict[str, Dict[str, int]] = {}
    times: Dict[str, List[float]] = {}
    move_times: Dict[str, Dict[str, List[float]]] = {}
    classes: Dict[str, int] = {}
    exited = 0
    for v in engine.pool.exited_vehicles:
        if v.exit_time is None or v.exit_time < warmup:
            continue
        origin = origin_of(v)
        if origin is None:
            continue
        exited += 1
        travel = float(v.exit_time - v.spawn_time)
        turn = v.turn_intent.value if v.turn_intent is not None else "unknown"
        flow[origin] = flow.get(origin, 0) + 1
        movement.setdefault(origin, {})
        movement[origin][turn] = movement[origin].get(turn, 0) + 1
        times.setdefault(origin, []).append(travel)
        move_times.setdefault(origin, {}).setdefault(turn, []).append(travel)
        cls = v.vehicle_type
        classes[cls] = classes.get(cls, 0) + 1

    return {
        "measuredSeconds": max(0.0, elapsed - warmup),
        "elapsed": elapsed,
        "warmup": warmup,
        "timeStep": clock.time_step,
        "flowCount": flow,
        "movementCount": movement,
        "travelTimes": times,
        "movementTravelTimes": move_times,
        "classCount": classes,
        "exited": exited,
        "metrics": {
            "approachBreakdown": metrics.get("approachBreakdown") or {},
            "signalTiming": metrics.get("signalTiming") or {},
            "vehicleLimitReached": bool(metrics.get("vehicleLimitReached")),
            "collisionCount": int(metrics.get("collisionCount") or 0),
            "averageDelay": metrics.get("averageDelay"),
        },
    }
