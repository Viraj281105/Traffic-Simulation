"""Tests and full factorial execution for Driver Aggression Profiles (V3.0 W4-T5, ADR-016, Strategy §14.4).

Executes the 108-cell factorial interaction matrix:
- Profiles (3): standard, moderate, high
- Vehicle mixes (3): car-only (the calibrated legacy population, no vehicle mix), mixed, heavy-vehicle
- Strategies (4): fixed_time_signal, adaptive_signal, conventional_roundabout, metered_entry_roundabout
- Densities (3): low (200 vph/arm), medium (500 vph/arm), saturated (1000 vph/arm)

Two tiers:
- Smoke (every CI run): all 108 cells for 45 s. It proves every cell builds, runs to completion
  and is collision-free. It is too short to say anything about liveness (a 45 s run cannot show a
  70 s stall), so it asserts none.
- Full strength (``-m slow``, nightly): all 108 cells for 240 s after which a stall longer than
  the 70 s project bound (signal and metered-roundabout precedent) is a real lock-up. Asserts zero
  collisions, no deadlock-detector trip at any tick, no stall, termination within the tick budget,
  and the measured direction of the headway and standstill-gap levers. Throughput, delay, queues
  and spillback (unserved demand) are reported against ``standard`` for every cell, with adverse
  directions listed rather than asserted away: aggression is not assumed to improve anything.

Every cell also checks it exercised what it claims: the controller class of its strategy, and the
vehicle classes of its mix.
"""

from __future__ import annotations

import concurrent.futures
import math
import os
from collections import defaultdict
from typing import Any, Dict, List, Mapping, Tuple

import pytest

from src.controllers.factory import create_controller
from src.core.clock import Clock
from src.engine.simulation_engine import SimulationEngine
from src.engine.tick_callback import build_tick_callback
from src.metrics.collector import MetricCollector
from src.scenario.documents import compile_scenario, parse_scenario
from src.vehicles.driver_aggression import apply_aggression_to_profile
from src.vehicles.vehicle_types import (
    DEFAULT_PROFILES,
    VEHICLE_CLASSES,
)

PROFILES: Tuple[str, ...] = ("standard", "moderate", "high")

# None: no vehicle mix at all, i.e. the calibrated cars-only population that
# stored scenarios and the presets without a mix run.
VEHICLE_MIXES: Dict[str, Any] = {
    "car-only": None,
    "mixed": {
        "car": 0.6,
        "suv": 0.2,
        "bus": 0.05,
        "truck": 0.05,
        "motorcycle": 0.1,
    },
    "heavy-vehicle": {"car": 0.3, "bus": 0.3, "truck": 0.4},
}

STRATEGIES: Tuple[str, ...] = (
    "fixed_time_signal",
    "adaptive_signal",
    "conventional_roundabout",
    "metered_entry_roundabout",
)

# The controller each strategy must actually build (create_controller).
EXPECTED_CONTROLLER: Dict[str, str] = {
    "fixed_time_signal": "FixedTimeSignalController",
    "adaptive_signal": "AdaptiveSignalController",
    "conventional_roundabout": "RoundaboutController",
    "metered_entry_roundabout": "SignalisedRoundaboutController",
}

DENSITIES: Dict[str, int] = {
    "low": 200,  # 200 vph / arm (800 vph total)
    "medium": 500,  # 500 vph / arm (2000 vph total)
    "saturated": 1000,  # 1000 vph / arm (4000 vph total)
}

TIME_STEP = 0.1
SMOKE_DURATION = 45.0
SMOKE_WARMUP = 10.0
FULL_DURATION = 240.0
FULL_WARMUP = 30.0
# Longest time vehicles may be present with none leaving the junction: the
# project's lock-up bound (test_signalised_roundabout, test_vehicle_types_and_lanes).
STALL_BOUND = 70.0
CANONICAL_SEED = 1

# Headway sampling: every second after warm-up, same-lane following pairs on
# the approach lanes.
_SAMPLE_EVERY_TICKS = 10
_FOLLOWING_MIN_SPEED = 3.0  # m/s: car-following, not queue creep
_FOLLOWING_MAX_GAP = 60.0  # m: an interacting leader, not free flow
_STANDSTILL_SPEED = 0.1  # m/s
_STANDSTILL_MAX_GAP = 15.0  # m: queued behind the leader


def build_scenario_doc(
    profile: str,
    mix_name: str,
    strategy: str,
    density_name: str,
    seed: int = CANONICAL_SEED,
    duration: float = SMOKE_DURATION,
    warmup: float = SMOKE_WARMUP,
) -> Dict[str, Any]:
    """Construct an urbanflow-scenario specification for one cell of the factorial matrix."""
    vph = DENSITIES[density_name]
    mix = VEHICLE_MIXES[mix_name]
    is_roundabout = "roundabout" in strategy

    doc: Dict[str, Any] = {
        "format": "urbanflow-scenario",
        "version": 1,
        "name": f"cell-{profile}-{mix_name}-{strategy}-{density_name}",
        "junction": {"type": "roundabout" if is_roundabout else "fixed_time_signal"},
        "approaches": {
            d: {
                "lanes": 2,
                "length": 150.0,
                "vehiclesPerHour": vph,
                "turning": {"left": 0.25, "straight": 0.5, "right": 0.25},
            }
            for d in ("north", "south", "east", "west")
        },
        "traffic": {"driverAggression": profile},
        "simulation": {"duration": duration, "warmup": warmup, "seed": seed},
    }
    if mix is not None:
        doc["vehicles"] = {"mix": mix}

    if is_roundabout:
        doc["roundabout"] = {
            "circulatingLanes": 2,
            "innerRadius": 10.0,
            "outerRadius": 20.0,
            "criticalGap": 4.0,
            "followUpTime": 2.5,
            "entrySpeed": 5.0,
            "circulatingSpeed": 8.0,
        }
        if strategy == "metered_entry_roundabout":
            doc["roundabout"]["entryControl"] = "metered_entry"
            doc["roundabout"]["entryMetering"] = {
                "phases": [
                    {"entries": ["north", "south"], "green": 20.0},
                    {"entries": ["east", "west"], "green": 20.0},
                ],
                "yellow": 3.0,
                "allRed": 2.0,
            }
    else:
        doc["signal"] = {
            "greenTime": 30.0,
            "yellowTime": 4.0,
            "allRedTime": 2.0,
        }
        if strategy == "adaptive_signal":
            doc["signal"]["adaptive"] = {
                "minGreen": 10.0,
                "maxGreen": 50.0,
                "extensionStep": 2.5,
                "detectionDistance": 30.0,
                "demandThreshold": 1,
            }

    return doc


def _sample_headways(
    active: List[Any], time_headways: List[float], standstill_gaps: List[float]
) -> None:
    """Same-lane following pairs on the approach lanes: time headway when moving, gap when queued."""
    by_lane: Dict[str, List[Any]] = defaultdict(list)
    for v in active:
        lane_id = getattr(v.lane, "lane_id", "")
        if "_in_" in lane_id and v.lane_change is None:
            by_lane[lane_id].append(v)
    for vehicles in by_lane.values():
        vehicles.sort(key=lambda v: v.position)
        for follower, leader in zip(vehicles, vehicles[1:]):
            # Positions are body centres (router.find_leader).
            gap = (
                leader.position
                - follower.position
                - (leader.length + follower.length) / 2.0
            )
            if gap <= 0.0:
                continue
            if follower.speed >= _FOLLOWING_MIN_SPEED and gap <= _FOLLOWING_MAX_GAP:
                time_headways.append(gap / follower.speed)
            elif (
                follower.speed < _STANDSTILL_SPEED
                and leader.speed < _STANDSTILL_SPEED
                and gap <= _STANDSTILL_MAX_GAP
            ):
                standstill_gaps.append(gap)


def _mean(values: List[float]) -> float | None:
    return round(math.fsum(values) / len(values), 4) if values else None


def execute_single_cell(
    cell_spec: Tuple[str, str, str, str, int, float, float],
) -> Dict[str, Any]:
    """Execute one simulation configuration and collect safety, liveness and performance metrics."""
    profile, mix_name, strategy, density_name, seed, duration, warmup = cell_spec
    cell: Dict[str, Any] = {
        "profile": profile,
        "mix": mix_name,
        "strategy": strategy,
        "density": density_name,
        "seed": seed,
        "duration": duration,
    }
    try:
        doc = build_scenario_doc(
            profile, mix_name, strategy, density_name, seed, duration, warmup
        )
        parsed, errs = parse_scenario(doc)
        if errs:
            return {**cell, "valid": False, "error": f"Parse errors: {errs}"}

        config = compile_scenario(parsed, strategy)
        clock = Clock(time_step=TIME_STEP)
        engine = SimulationEngine(clock, duration=duration, config=config)
        ctrl = create_controller(config, engine.network)
        engine.controller = ctrl
        collector = MetricCollector(config)
        engine.register_tick_callback(
            build_tick_callback(ctrl, clock, engine, collector)
        )

        seen_exits = 0
        last_exit_tick = 0
        longest_stall = 0.0
        deadlock_seen = False
        tick = 0
        # A run that has not completed by then never will: it is a freeze.
        tick_budget = int(round(duration / TIME_STEP)) + 10
        warmup_ticks = int(round(warmup / TIME_STEP))
        time_headways: List[float] = []
        standstill_gaps: List[float] = []
        vehicle_types: set[str] = set()

        while engine.status.value.lower() != "completed" and tick < tick_budget:
            engine.step()
            now_exits = len(engine.pool.exited_vehicles)
            if now_exits > seen_exits:
                seen_exits = now_exits
                last_exit_tick = tick
            elif engine.pool.active_vehicles:
                longest_stall = max(longest_stall, (tick - last_exit_tick) * TIME_STEP)
            detector = engine.deadlock_detector
            if detector is not None and detector.has_occurred:
                deadlock_seen = True
            for v in engine.pool.active_vehicles:
                vehicle_types.add(
                    v.params.profile.type_id if v.params is not None else "car"
                )
            if tick >= warmup_ticks and tick % _SAMPLE_EVERY_TICKS == 0:
                _sample_headways(
                    engine.pool.active_vehicles, time_headways, standstill_gaps
                )
            tick += 1
        terminated = engine.status.value.lower() == "completed"

        metrics = collector.get_metrics(
            clock.get_elapsed_time(),
            engine.pool.active_vehicles,
            engine.pool.exited_vehicles,
            engine.spawner.spawned_count if engine.spawner else 0,
            engine.pool.collision_count,
        )
        spawned = int(engine.spawner.spawned_count if engine.spawner else 0)
        # Poisson mean of the demand offered over the run (4 arms).
        offered = DENSITIES[density_name] * 4 * duration / 3600.0

        return {
            **cell,
            "valid": True,
            "error": None,
            "controller": type(ctrl).__name__,
            "vehicleTypes": sorted(vehicle_types),
            "terminated": terminated,
            "collisions": int(engine.pool.collision_count),
            "deadlock": deadlock_seen,
            "longest_stall": round(longest_stall, 2),
            "throughput": int(metrics["throughput"]),
            "throughput_rate": round(float(metrics["throughputRate"]), 2),
            "average_delay": round(float(metrics["averageDelay"]), 2),
            "median_delay": round(float(metrics["medianDelay"]), 2),
            "p95_delay": round(float(metrics["p95Delay"]), 2),
            "average_queue": round(float(metrics["averageQueueLength"]), 2),
            "max_queue": int(metrics["maxQueueLength"]),
            "qsi": round(float(metrics["queueStabilityIndex"]), 3),
            "near_misses": int(metrics.get("nearMissCount") or 0),
            "total_spawned": spawned,
            "active_vehicles": len(engine.pool.active_vehicles),
            # Entry spillback: offered demand the approaches could not admit.
            "unserved_share": round(max(0.0, 1.0 - spawned / offered), 3),
            "mean_time_headway": _mean(time_headways),
            "headway_samples": len(time_headways),
            "mean_standstill_gap": _mean(standstill_gaps),
            "gap_samples": len(standstill_gaps),
        }
    except Exception as exc:
        return {**cell, "valid": False, "error": f"{type(exc).__name__}: {exc}"}


def run_full_factorial_matrix(
    seed: int = CANONICAL_SEED,
    duration: float = SMOKE_DURATION,
    warmup: float = SMOKE_WARMUP,
    workers: int = 4,
) -> List[Dict[str, Any]]:
    """Execute the complete 108 configurations in parallel, in cell order."""
    cell_specs = [
        (prof, mix, strat, dens, seed, duration, warmup)
        for prof in PROFILES
        for mix in VEHICLE_MIXES
        for strat in STRATEGIES
        for dens in DENSITIES
    ]
    assert len(cell_specs) == 108

    max_w = min(workers, os.cpu_count() or 4)
    with concurrent.futures.ProcessPoolExecutor(max_workers=max_w) as executor:
        return list(executor.map(execute_single_cell, cell_specs))


def compare_against_standard(
    results: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Per (mix, strategy, density): each non-standard profile's change against standard."""
    groups: Dict[Tuple[str, str, str], Dict[str, Dict[str, Any]]] = defaultdict(dict)
    for r in results:
        groups[(r["mix"], r["strategy"], r["density"])][r["profile"]] = r
    rows = []
    for (mix, strategy, density), cells in sorted(groups.items()):
        std = cells["standard"]
        for prof in ("moderate", "high"):
            cell = cells[prof]
            rows.append(
                {
                    "mix": mix,
                    "strategy": strategy,
                    "density": density,
                    "profile": prof,
                    **{
                        f"d_{key}": (
                            None
                            if cell.get(key) is None or std.get(key) is None
                            else round(cell[key] - std[key], 4)
                        )
                        for key in (
                            "throughput",
                            "average_delay",
                            "average_queue",
                            "max_queue",
                            "unserved_share",
                            "mean_time_headway",
                            "mean_standstill_gap",
                        )
                    },
                }
            )
    return rows


def _assert_cells_exercise_their_paths(results: List[Dict[str, Any]]) -> None:
    for r in results:
        assert r["controller"] == EXPECTED_CONTROLLER[r["strategy"]], r
        types = set(r["vehicleTypes"])
        mix = VEHICLE_MIXES[r["mix"]]
        if mix is None:
            assert types == {"car"}, r
        else:
            assert types <= set(mix), r
            assert len(types) >= 2, f"{r['mix']} ran as a single class: {r}"


def _profile_means(results: List[Dict[str, Any]], key: str) -> Dict[str, float]:
    """Unweighted mean over the cells of each profile that measured *key*."""
    out = {}
    for prof in PROFILES:
        vals = [r[key] for r in results if r["profile"] == prof and r[key] is not None]
        assert vals, f"no cell of {prof} measured {key}"
        out[prof] = math.fsum(vals) / len(vals)
    return out


@pytest.fixture(scope="module")
def matrix_results() -> List[Dict[str, Any]]:
    """Cached module-level execution of the 108-cell smoke matrix."""
    return run_full_factorial_matrix(
        seed=CANONICAL_SEED,
        duration=SMOKE_DURATION,
        warmup=SMOKE_WARMUP,
        workers=4,
    )


class TestAggressionDirectionalPhysics:
    """Verifies that driver aggression levers exert the exact required directional effects."""

    def test_directional_headway_reduction_across_vehicle_classes(self) -> None:
        """Desired time headway T must decrease strictly monotonically: standard > moderate > high."""
        for v_cls in VEHICLE_CLASSES:
            base = DEFAULT_PROFILES[v_cls]
            std_p = apply_aggression_to_profile(base, "standard")
            mod_p = apply_aggression_to_profile(base, "moderate")
            hi_p = apply_aggression_to_profile(base, "high")

            assert std_p.desired_time_headway == base.desired_time_headway
            assert mod_p.desired_time_headway == pytest.approx(
                base.desired_time_headway * 0.85, rel=1e-5
            )
            assert hi_p.desired_time_headway == pytest.approx(
                base.desired_time_headway * 0.70, rel=1e-5
            )
            assert (
                std_p.desired_time_headway
                > mod_p.desired_time_headway
                > hi_p.desired_time_headway
            )

    def test_directional_standstill_gap_reduction_across_vehicle_classes(self) -> None:
        """Minimum standstill gap s0 must decrease strictly monotonically: standard > moderate > high."""
        for v_cls in VEHICLE_CLASSES:
            base = DEFAULT_PROFILES[v_cls]
            std_p = apply_aggression_to_profile(base, "standard")
            mod_p = apply_aggression_to_profile(base, "moderate")
            hi_p = apply_aggression_to_profile(base, "high")

            assert std_p.minimum_gap == base.minimum_gap
            assert mod_p.minimum_gap == pytest.approx(
                base.minimum_gap * 0.875, rel=1e-5
            )
            assert hi_p.minimum_gap == pytest.approx(base.minimum_gap * 0.75, rel=1e-5)
            assert std_p.minimum_gap > mod_p.minimum_gap > hi_p.minimum_gap

    def test_directional_stopline_saturation_flow_increase(self) -> None:
        """Theoretical (analytic, not simulated) stop-line saturation flow: standard < moderate < high."""
        for v_cls in VEHICLE_CLASSES:
            base = DEFAULT_PROFILES[v_cls]
            flows = {}
            for prof in PROFILES:
                p = apply_aggression_to_profile(base, prof)
                # Saturation headway h_sat ~ T + (L_eff + s0) / v_launch
                # Capacity S = 3600 / h_sat
                h_sat = p.desired_time_headway + (p.length[1] + p.minimum_gap) / (
                    math.sqrt(2.0 * p.max_acceleration * 10.0)
                )
                flows[prof] = 3600.0 / h_sat

            assert flows["high"] > flows["moderate"] > flows["standard"], (
                f"{v_cls}: {flows}"
            )


class TestFactorialMatrixSmoke:
    """All 108 cells, 45 s each: every cell builds, completes, is collision-free and runs its own paths."""

    def test_108_cell_matrix_completeness_and_collisions(
        self, matrix_results: List[Dict[str, Any]]
    ) -> None:
        assert len(matrix_results) == 108, (
            f"Expected 108 runs, got {len(matrix_results)}"
        )

        failed_runs = [r for r in matrix_results if not r["valid"]]
        assert not failed_runs, f"Failed or invalid runs detected: {failed_runs}"

        unterminated = [r for r in matrix_results if not r["terminated"]]
        assert not unterminated, f"Runs did not complete: {unterminated}"

        collision_runs = [r for r in matrix_results if r["collisions"] > 0]
        assert not collision_runs, f"Collisions detected in runs: {collision_runs}"

        _assert_cells_exercise_their_paths(matrix_results)

    def test_seed_determinism_per_profile(self) -> None:
        """Rerunning an identical cell specification under the same seed produces identical metrics."""
        specs = (
            ("standard", "mixed", "fixed_time_signal", "medium", 1, 30.0, 5.0),
            ("moderate", "mixed", "conventional_roundabout", "medium", 1, 30.0, 5.0),
            ("high", "heavy-vehicle", "adaptive_signal", "saturated", 1, 30.0, 5.0),
            ("high", "car-only", "metered_entry_roundabout", "medium", 1, 30.0, 5.0),
        )
        for spec in specs:
            run1 = execute_single_cell(spec)
            run2 = execute_single_cell(spec)
            assert run1["valid"] and run2["valid"], (run1, run2)
            assert run1 == run2

    def test_every_cell_is_compared_against_standard(
        self, matrix_results: List[Dict[str, Any]]
    ) -> None:
        """36 baselines, each compared with moderate and high on every reported metric."""
        rows = compare_against_standard(matrix_results)
        assert len(rows) == 72
        assert {(r["mix"], r["strategy"], r["density"]) for r in rows} == {
            (m, s, d) for m in VEHICLE_MIXES for s in STRATEGIES for d in DENSITIES
        }


@pytest.mark.slow
class TestFactorialMatrixFullStrength:
    """All 108 cells, 240 s each: the safety, liveness and direction evidence for gate G-AG."""

    @pytest.fixture(scope="class")
    def full_results(self) -> List[Dict[str, Any]]:
        return run_full_factorial_matrix(
            seed=CANONICAL_SEED,
            duration=FULL_DURATION,
            warmup=FULL_WARMUP,
            workers=os.cpu_count() or 4,
        )

    def test_safety_and_liveness(self, full_results: List[Dict[str, Any]]) -> None:
        assert len(full_results) == 108
        failed = [r for r in full_results if not r["valid"]]
        assert not failed, f"Failed or invalid runs: {failed}"
        assert FULL_DURATION > STALL_BOUND  # else the stall check could never fail

        problems = [
            r
            for r in full_results
            if not r["terminated"]
            or r["collisions"] > 0
            or r["deadlock"]
            or r["longest_stall"] > STALL_BOUND
        ]
        assert not problems, f"Safety/liveness failures: {problems}"
        _assert_cells_exercise_their_paths(full_results)

    def test_measured_headway_and_gap_levers(
        self, full_results: List[Dict[str, Any]]
    ) -> None:
        """Measured in the simulation, not computed: following headway and queue gap shrink with aggression.

        Declared minimum effect: high's mean measured time headway and mean queued gap are each at
        least 10 % below standard's (the parameters drop 30 % and 25 %; congestion dilutes that).
        Measured on 2026-10-22 (seed 1, after ADR-019): -15.7 % and -17.5 %. The thresholds were
        set after that run, with margin, so they guard the direction, not a pre-registered effect
        size.
        """
        headway = _profile_means(full_results, "mean_time_headway")
        gap = _profile_means(full_results, "mean_standstill_gap")
        assert headway["standard"] > headway["moderate"] > headway["high"], headway
        assert gap["standard"] > gap["moderate"] > gap["high"], gap
        assert headway["high"] <= 0.9 * headway["standard"], headway
        assert gap["high"] <= 0.9 * gap["standard"], gap

    def test_outcomes_are_reported_against_standard(
        self, full_results: List[Dict[str, Any]]
    ) -> None:
        """Throughput, delay, queue and spillback are reported for every comparison; never asserted to improve."""
        rows = compare_against_standard(full_results)
        assert len(rows) == 72
        for row in rows:
            for key in (
                "d_throughput",
                "d_average_delay",
                "d_average_queue",
                "d_unserved_share",
            ):
                assert row[key] is not None and math.isfinite(row[key]), row
        adverse = [
            row
            for row in rows
            if row["d_throughput"] < 0 or row["d_unserved_share"] > 0
        ]
        # Reported, not hidden: printed with -s / -rA so the matrix review sees them.
        print(f"\n{len(adverse)} of 72 comparisons are adverse against standard:")
        for row in adverse:
            print(f"  {row}")


def summarise(results: List[Mapping[str, Any]]) -> Dict[str, Any]:
    """The matrix summary recorded in docs/simulation/driver-aggression.md."""
    rows = compare_against_standard(list(results))  # type: ignore[arg-type]
    return {
        "cells": len(results),
        "valid": sum(1 for r in results if r["valid"]),
        "collisions": sum(r.get("collisions", 0) for r in results),
        "deadlocks": sum(1 for r in results if r.get("deadlock")),
        "longestStall": max(r.get("longest_stall", 0.0) for r in results),
        "comparisons": rows,
    }
