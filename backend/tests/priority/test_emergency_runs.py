"""Emergency pre-emption on a running junction: safety, effect, determinism.

The statistical claim is made on a congested junction (two lanes per approach,
1.2 vehicles per second in total) over a fixed seed set, comparing the mean
travel time of the same ambulance with pre-emption on and off. Safety is
checked two ways: from the controller's own transition log (``audit``) and
independently, by sampling the colours the lanes actually show every tick.
"""

from functools import lru_cache
from typing import Any, Dict, List, Tuple

import pytest

from src.controllers.factory import create_controller
from src.core.clock import Clock
from src.core.enums import Direction, SimulationStatus
from src.engine.simulation_engine import SimulationEngine
from src.priority.comparison import run_emergency_comparison
from src.priority.models import (
    EmergencySpec,
    PreemptionConfig,
    ScenarioSpec,
    YieldConfig,
)
from src.priority.runs import PriorityRun, build_config, build_run, execute

CONGESTED = ScenarioSpec(duration_s=200.0)  # 2 lanes, 1.2 veh/s
AMBULANCE = [EmergencySpec("ambulance", "north", "straight", 100.0)]
FIXED_SEEDS = (1, 2, 3)

BUSY = ScenarioSpec(duration_s=150.0, arrival_rate=0.7)
TWO_VEHICLES = [
    EmergencySpec("ambulance", "east", "straight", 15.0),
    EmergencySpec("fire_truck", "north", "left", 70.0),
]


@lru_cache(maxsize=None)
def _comparison() -> Dict[str, Any]:
    return run_emergency_comparison(
        CONGESTED, AMBULANCE, PreemptionConfig(), YieldConfig(), FIXED_SEEDS
    )


# -- effect and collateral cost -------------------------------------------------


def test_preemption_effect_cost_and_safety_over_a_fixed_seed_set() -> None:
    """One comparison (six full runs), several claims; it is computed once
    because each run of a congested junction is the expensive part."""
    result = _comparison()
    assert result["seeds"] == list(FIXED_SEEDS), result["droppedSeeds"]

    # Effect: the same ambulance is through the junction sooner, every seed.
    travel = result["comparison"]["emergencyTravelTime"]
    assert travel["meanWithPriority"] < travel["meanBaseline"]
    assert travel["difference"] < 0
    # Interval and p-value come from the repository's paired statistics.
    assert travel["ci_upper"] < 0
    assert travel["p_value"] < 0.05
    assert travel["direction"] == "a_lower"
    assert travel["verdict"].startswith("A beats B")
    with_p, base = result["perSeed"]["withPreemption"], result["perSeed"]["baseline"]
    assert all(a < b for a, b in zip(with_p["travelTime"], base["travelTime"]))
    assert result["comparison"]["emergencyDelay"]["difference"] < 0
    assert result["comparison"]["emergencyWaitTime"]["difference"] < 0

    # Cost: the collateral delay is reported and bounded.
    collateral = result["comparison"]["collateralDelay"]
    assert collateral["meanBaseline"] > 0
    assert collateral["changePercent"] is not None
    assert collateral["changePercent"] < 25.0
    assert result["inModelOnly"] is True

    # Safety: no collision, vehicle-loss or signal-clearance regression.
    for arm in ("withPreemption", "baseline"):
        safety = result["safety"][arm]
        assert safety["vehiclesConserved"] is True
        assert safety["signalAuditOk"] is True, safety["signalViolations"]
    assert all(
        a <= b
        for a, b in zip(
            result["safety"]["withPreemption"]["collisions"],
            result["safety"]["baseline"]["collisions"],
        )
    )
    assert all(n >= 1 for n in result["safety"]["withPreemption"]["preemptions"])
    assert result["safety"]["baseline"]["preemptions"] == [0, 0, 0]


# -- signal safety, observed independently -------------------------------------


def _step_sampling(run: PriorityRun) -> List[Tuple[float, str, str]]:
    """(time, north colour, east colour) every tick, from the lane-facing state."""
    samples: List[Tuple[float, str, str]] = []
    engine = run.engine
    while engine.status != SimulationStatus.COMPLETED:
        engine.step()
        colours = run.controller.signals_state()
        samples.append(
            (
                engine.clock.get_elapsed_time(),
                colours[Direction.NORTH],
                colours[Direction.EAST],
            )
        )
    return samples


def _runs(
    samples: List[Tuple[float, str, str]], index: int
) -> List[Tuple[str, float, float]]:
    """Run-length encoding of one approach's colour: (colour, start, length)."""
    out: List[Tuple[str, float, float]] = []
    start = samples[0][0]
    colour = samples[0][index]
    for sample in samples[1:]:
        if sample[index] != colour:
            out.append((colour, start, sample[0] - start))
            start, colour = sample[0], sample[index]
    return out


@pytest.mark.parametrize("min_green", [7.0, 15.0])
def test_preemption_never_violates_clearance_or_minimum_green(min_green: float) -> None:
    pre = PreemptionConfig(min_green_s=min_green)
    run = build_run(
        BUSY, seed=11, emergencies=TWO_VEHICLES, preemption=pre, yielding=YieldConfig()
    )
    samples = _step_sampling(run)
    spec, dt = BUSY, BUSY.time_step_s
    assert run.controller.preemption_count >= 2, (
        "the scenario must exercise pre-emption"
    )

    # 1. Conflicting approaches are never both released (green or yellow) together.
    for _, north, east in samples:
        assert not (north in ("green", "yellow") and east in ("green", "yellow"))

    ns, ew = _runs(samples, 1), _runs(samples, 2)
    # 2. Every yellow is shown in full.
    for colour, start, length in ns + ew:
        if colour == "yellow":
            assert length >= spec.yellow_s - 1.5 * dt, (start, length)

    # 3. Between one approach's yellow ending and the other's green starting the
    #    junction is all-red for at least the plan's all-red time.
    for first, second in ((ns, ew), (ew, ns)):
        for colour, start, length in first:
            if colour != "yellow":
                continue
            end = start + length
            next_green = min(
                (s for c, s, _ in second if c == "green" and s >= end - 1e-9),
                default=None,
            )
            if next_green is not None and next_green - end < 60.0:
                assert next_green - end >= spec.all_red_s - 1.5 * dt, (end, next_green)

    # 4. No completed green is cut below the safety minimum.
    for colour, start, length in ns + ew:
        if colour == "green":
            assert length >= min_green - 1.5 * dt, (start, length)

    # The controller's own audit agrees.
    from src.priority.audit import audit_phase_log

    audit = audit_phase_log(
        run.controller.phase_log,
        yellow_s=spec.yellow_s,
        all_red_s=spec.all_red_s,
        min_green_s=min_green,
        time_step_s=dt,
    )
    assert audit["ok"], audit["violations"]
    assert audit["transitions"] > 0


def test_the_pre_empted_plan_is_restored_at_the_interrupted_green() -> None:
    run = build_run(
        BUSY,
        seed=11,
        emergencies=TWO_VEHICLES,
        preemption=PreemptionConfig(),
        yielding=YieldConfig(),
    )
    execute(run)
    events = run.controller.events
    kinds = [e["type"] for e in events]
    assert kinds.count("preempt_start") == kinds.count("hold_start") >= 2
    assert kinds.count("restored") >= 1
    # Recovery is documented to resume at the interrupted green: the group that
    # was running when pre-emption began is the one shown again.
    for start, restored in zip(
        (e for e in events if e["type"] == "preempt_start"),
        (e for e in events if e["type"] == "restored"),
    ):
        target_group = start["target"].split("_")[0]
        interrupted_group = start["interrupted"].split("_")[0]
        if interrupted_group != target_group and start["interrupted"].endswith(
            "_green"
        ):
            assert restored["phase"].split("_")[0] == interrupted_group
    # The plan carries on after the last pre-emption (a green is showing in
    # the normal state again).
    assert run.controller.state in ("normal", "hold", "clearing", "recovering")


def test_no_second_preemption_inside_the_recovery_lockout() -> None:
    run = build_run(
        BUSY,
        seed=11,
        emergencies=[
            EmergencySpec("ambulance", "east", "straight", 15.0),
            EmergencySpec("ambulance", "north", "straight", 22.0),
        ],
        preemption=PreemptionConfig(min_recovery_s=40.0),
        yielding=YieldConfig(),
    )
    execute(run)
    events = run.controller.events
    restored_times = [e["time"] for e in events if e["type"] == "restored"]
    start_times = [e["time"] for e in events if e["type"] == "preempt_start"]
    for restored in restored_times:
        later = [t for t in start_times if t > restored]
        assert all(t - restored >= 40.0 - 0.2 for t in later)


def test_hold_is_bounded() -> None:
    run = build_run(
        CONGESTED,
        seed=4,  # a long queue: the ambulance cannot clear quickly
        emergencies=AMBULANCE,
        preemption=PreemptionConfig(max_hold_s=10.0),
        yielding=YieldConfig(),
    )
    execute(run)
    holds = [e for e in run.controller.events if e["type"] == "hold_end"]
    assert holds
    assert all(h["heldSeconds"] <= 10.0 + 0.2 for h in holds)
    assert any(h["timedOut"] for h in holds)


def test_detection_distance_is_respected() -> None:
    run = build_run(
        BUSY,
        seed=11,
        emergencies=[EmergencySpec("ambulance", "east", "straight", 15.0)],
        preemption=PreemptionConfig(detection_distance_m=40.0, detection_time_s=None),
        yielding=None,
    )
    execute(run)
    starts = [e for e in run.controller.events if e["type"] == "preempt_start"]
    assert starts and all(s["distance"] <= 40.0 + 1.5 for s in starts)


# -- behaviour preservation, determinism, conservation ---------------------------


def _snapshot(vehicles: List[Any]) -> List[Tuple[str, str, float, float]]:
    return sorted(
        (
            v.vehicle_id,
            v.lane.lane_id if v.lane else "",
            round(v.position, 6),
            round(v.speed, 6),
        )
        for v in vehicles
    )


def test_without_priority_the_wrapper_is_transparent() -> None:
    spec = ScenarioSpec(duration_s=80.0, arrival_rate=0.8)
    config = build_config(spec, seed=7)
    clock = Clock(time_step=spec.time_step_s)
    engine = SimulationEngine(clock, duration=spec.duration_s, config=config)
    engine.controller = create_controller(config, engine.network)
    while engine.status != SimulationStatus.COMPLETED:
        engine.step()
    plain = _snapshot(engine.pool.active_vehicles + engine.pool.exited_vehicles)

    run = build_run(spec, seed=7)  # no vehicles, no pre-emption, no yielding
    execute(run)
    wrapped = _snapshot(
        run.engine.pool.active_vehicles + run.engine.pool.exited_vehicles
    )
    assert wrapped == plain
    assert run.controller.phase_log
    assert run.engine.pool.collision_count == engine.pool.collision_count


def test_runs_are_deterministic() -> None:
    kwargs: Dict[str, Any] = {
        "emergencies": TWO_VEHICLES,
        "preemption": PreemptionConfig(),
        "yielding": YieldConfig(),
    }
    first = execute(build_run(BUSY, 5, **kwargs))
    second = execute(build_run(BUSY, 5, **kwargs))
    assert first == second
    other_seed = execute(build_run(BUSY, 6, **kwargs))
    assert other_seed != first


def test_every_vehicle_is_accounted_for_and_the_first_ambulance_gets_through() -> None:
    run = build_run(
        BUSY,
        seed=5,
        emergencies=TWO_VEHICLES,
        preemption=PreemptionConfig(),
        yielding=YieldConfig(),
    )
    metrics = execute(run)
    pool = run.engine.pool
    ids = [v.vehicle_id for v in pool.active_vehicles + pool.exited_vehicles]
    assert len(ids) == len(set(ids))
    spawner = run.engine.spawner
    assert spawner is not None
    expected = {f"veh_{i}" for i in range(spawner.spawned_count)} | {"ev_0", "ev_1"}
    assert set(ids) == expected
    assert not {v.vehicle_id for v in pool.active_vehicles} & {
        v.vehicle_id for v in pool.exited_vehicles
    }
    assert metrics["vehicles"]["conserved"] is True
    assert metrics["emergencyNotPlaced"] == 0
    assert len(metrics["emergency"]) == 2
    assert metrics["emergency"][0]["completed"]  # the east ambulance, early in the run
    assert metrics["collisions"] == 0


def test_yielding_is_undone_at_the_end_of_a_run() -> None:
    run = build_run(
        BUSY,
        seed=5,
        emergencies=TWO_VEHICLES,
        preemption=PreemptionConfig(),
        yielding=YieldConfig(),
    )
    metrics = execute(run)
    assert metrics["signal"]["vehiclesYielded"] > 0
    manager = run.controller.yield_manager
    assert manager is not None and manager.active_count == 0
    for v in run.engine.pool.active_vehicles + run.engine.pool.exited_vehicles:
        assert v.driver_factors is None
