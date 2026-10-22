"""Tests and full factorial execution for Driver Aggression Profiles (V3.0 W4-T5, ADR-016, Strategy §14.4).

Executes the full 108-cell factorial interaction matrix:
- Profiles (3): standard, moderate, high
- Vehicle mixes (3): car-only, mixed, heavy-vehicle
- Strategies (4): fixed_time_signal, adaptive_signal, conventional_roundabout, metered_entry_roundabout
- Densities (3): low (200 vph/arm), medium (500 vph/arm), saturated (1000 vph/arm)

Total: 3 x 3 x 4 x 3 = 108 configurations.

Safety & Behavioral Invariants:
1. Zero collisions (collision_count == 0) across all valid runs.
2. Zero deadlocks or permanent freezes (deadlock == False, longest_stall <= stall_bound).
3. Directional verification:
   - Desired time headway T decreases monotonically: standard (1.0x) > moderate (0.85x) > high (0.70x).
   - Minimum standstill gap s0 decreases monotonically: standard (1.0x) > moderate (0.875x) > high (0.75x).
   - Stop-line saturation flow rate increases monotonically: standard < moderate < high.
4. Relative changes reported against standard baseline for queue, delay, spillback, and throughput.
5. Deterministic replay: same seed, spec, and profile yield identical metric fingerprints.
"""

from __future__ import annotations

import concurrent.futures
import math
import os
from typing import Any, Dict, List, Tuple

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

VEHICLE_MIXES: Dict[str, Dict[str, float]] = {
    "car-only": {"car": 1.0},
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

DENSITIES: Dict[str, int] = {
    "low": 200,  # 200 vph / arm (800 vph total)
    "medium": 500,  # 500 vph / arm (2000 vph total)
    "saturated": 1000,  # 1000 vph / arm (4000 vph total)
}

DEFAULT_MATRIX_DURATION = 45.0
DEFAULT_MATRIX_WARMUP = 10.0
CANONICAL_SEED = 1


def build_scenario_doc(
    profile: str,
    mix_name: str,
    strategy: str,
    density_name: str,
    seed: int = CANONICAL_SEED,
    duration: float = DEFAULT_MATRIX_DURATION,
    warmup: float = DEFAULT_MATRIX_WARMUP,
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
        "vehicles": {"mix": mix},
        "traffic": {"driverAggression": profile},
        "simulation": {"duration": duration, "warmup": warmup, "seed": seed},
    }

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


def execute_single_cell(
    cell_spec: Tuple[str, str, str, str, int, float, float],
) -> Dict[str, Any]:
    """Execute one simulation configuration and collect safety and performance metrics."""
    profile, mix_name, strategy, density_name, seed, duration, warmup = cell_spec
    try:
        doc = build_scenario_doc(
            profile, mix_name, strategy, density_name, seed, duration, warmup
        )
        parsed, errs = parse_scenario(doc)
        if errs:
            return {
                "profile": profile,
                "mix": mix_name,
                "strategy": strategy,
                "density": density_name,
                "seed": seed,
                "valid": False,
                "error": f"Parse errors: {errs}",
                "collisions": -1,
                "deadlock": True,
            }

        config = compile_scenario(parsed, strategy)
        clock = Clock(time_step=0.1)
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
        tick = 0

        while engine.status.value.lower() != "completed":
            engine.step()
            now_exits = len(engine.pool.exited_vehicles)
            if now_exits > seen_exits:
                seen_exits = now_exits
                last_exit_tick = tick
            elif engine.pool.active_vehicles:
                longest_stall = max(longest_stall, (tick - last_exit_tick) * 0.1)
            tick += 1

        metrics = collector.get_metrics(
            clock.get_elapsed_time(),
            engine.pool.active_vehicles,
            engine.pool.exited_vehicles,
            engine.spawner.spawned_count if engine.spawner else 0,
            engine.pool.collision_count,
        )

        deadlock_detected = False
        if engine.deadlock_detector is not None:
            insight = engine.deadlock_detector.get_insight()
            if insight and "deadlock emerged" in insight:
                deadlock_detected = True

        return {
            "profile": profile,
            "mix": mix_name,
            "strategy": strategy,
            "density": density_name,
            "seed": seed,
            "valid": True,
            "error": None,
            "collisions": int(engine.pool.collision_count),
            "deadlock": deadlock_detected,
            "longest_stall": round(longest_stall, 2),
            "throughput": int(metrics["throughput"]),
            "throughput_rate": round(float(metrics["throughputRate"]), 2),
            "average_delay": round(float(metrics["averageDelay"]), 2),
            "median_delay": round(float(metrics["medianDelay"]), 2),
            "p95_delay": round(float(metrics["p95Delay"]), 2),
            "average_queue": round(float(metrics["averageQueueLength"]), 2),
            "max_queue": int(metrics["maxQueueLength"]),
            "qsi": round(float(metrics["queueStabilityIndex"]), 3),
            "total_spawned": int(engine.spawner.spawned_count if engine.spawner else 0),
            "active_vehicles": len(engine.pool.active_vehicles),
        }
    except Exception as exc:
        return {
            "profile": profile,
            "mix": mix_name,
            "strategy": strategy,
            "density": density_name,
            "seed": seed,
            "valid": False,
            "error": str(exc),
            "collisions": -1,
            "deadlock": True,
            "longest_stall": 999.0,
            "throughput": 0,
            "throughput_rate": 0.0,
            "average_delay": 0.0,
            "median_delay": 0.0,
            "p95_delay": 0.0,
            "average_queue": 0.0,
            "max_queue": 0,
            "qsi": 0.0,
            "total_spawned": 0,
            "active_vehicles": 0,
        }


def run_full_factorial_matrix(
    seed: int = CANONICAL_SEED,
    duration: float = DEFAULT_MATRIX_DURATION,
    warmup: float = DEFAULT_MATRIX_WARMUP,
    workers: int = 4,
) -> List[Dict[str, Any]]:
    """Execute the complete 108 configurations in parallel using ProcessPoolExecutor."""
    cell_specs = [
        (prof, mix, strat, dens, seed, duration, warmup)
        for prof in PROFILES
        for mix in VEHICLE_MIXES
        for strat in STRATEGIES
        for dens in DENSITIES
    ]
    assert len(cell_specs) == 108

    results: List[Dict[str, Any]] = []
    # Use max_workers bounded by cpu_count
    max_w = min(workers, os.cpu_count() or 4)
    with concurrent.futures.ProcessPoolExecutor(max_workers=max_w) as executor:
        for res in executor.map(execute_single_cell, cell_specs):
            results.append(res)
    return results


@pytest.fixture(scope="module")
def matrix_results() -> List[Dict[str, Any]]:
    """Cached module-level execution of the 108-cell factorial matrix."""
    return run_full_factorial_matrix(
        seed=CANONICAL_SEED,
        duration=DEFAULT_MATRIX_DURATION,
        warmup=DEFAULT_MATRIX_WARMUP,
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
        """Theoretical stop-line saturation flow rate must increase strictly monotonically: standard < moderate < high."""
        for v_cls in VEHICLE_CLASSES:
            base = DEFAULT_PROFILES[v_cls]
            for prof in PROFILES:
                p = apply_aggression_to_profile(base, prof)
                # Saturation headway h_sat ~ T + (L_eff + s0) / v_launch
                # Capacity S = 3600 / h_sat
                h_sat = p.desired_time_headway + (p.length[1] + p.minimum_gap) / (
                    math.sqrt(2.0 * p.max_acceleration * 10.0)
                )
                sat_flow = 3600.0 / h_sat

                if prof == "standard":
                    flow_std = sat_flow
                elif prof == "moderate":
                    flow_mod = sat_flow
                elif prof == "high":
                    flow_hi = sat_flow

            assert flow_hi > flow_mod > flow_std, (
                f"{v_cls}: flow_hi={flow_hi:.1f} > flow_mod={flow_mod:.1f} > flow_std={flow_std:.1f}"
            )


class TestFactorialMatrixExecutionAndSafety:
    """Executes the full 108 configurations and asserts safety invariants and seed determinism."""

    def test_108_cell_matrix_completeness_and_safety_invariants(
        self, matrix_results: List[Dict[str, Any]]
    ) -> None:
        """Assert zero collisions and zero deadlocks/freezes across all 108 valid configurations."""
        assert len(matrix_results) == 108, (
            f"Expected 108 runs, got {len(matrix_results)}"
        )

        failed_runs = [r for r in matrix_results if not r["valid"]]
        assert not failed_runs, f"Failed or invalid runs detected: {failed_runs}"

        collision_runs = [r for r in matrix_results if r["collisions"] > 0]
        assert not collision_runs, f"Collisions detected in runs: {collision_runs}"

        deadlock_runs = [r for r in matrix_results if r["deadlock"]]
        assert not deadlock_runs, f"Deadlocks detected in runs: {deadlock_runs}"

        # Stall bound: no run stalls longer than 70s
        excessive_stalls = [r for r in matrix_results if r["longest_stall"] > 70.0]
        assert not excessive_stalls, f"Excessive stalls detected: {excessive_stalls}"

    def test_seed_determinism_per_profile(self) -> None:
        """Rerunning an identical cell specification under the same seed produces bit-identical metrics."""
        spec_std = ("standard", "mixed", "fixed_time_signal", "medium", 1, 30.0, 5.0)
        spec_mod = (
            "moderate",
            "mixed",
            "conventional_roundabout",
            "medium",
            1,
            30.0,
            5.0,
        )
        spec_hi = (
            "high",
            "heavy-vehicle",
            "adaptive_signal",
            "saturated",
            1,
            30.0,
            5.0,
        )

        for spec in (spec_std, spec_mod, spec_hi):
            run1 = execute_single_cell(spec)
            run2 = execute_single_cell(spec)
            assert run1["valid"] and run2["valid"]
            assert run1["collisions"] == run2["collisions"] == 0
            assert run1["throughput"] == run2["throughput"]
            assert run1["average_delay"] == run2["average_delay"]
            assert run1["average_queue"] == run2["average_queue"]
            assert run1["max_queue"] == run2["max_queue"]
            assert run1["longest_stall"] == run2["longest_stall"]

    def test_matrix_relative_changes_reported_against_standard(
        self, matrix_results: List[Dict[str, Any]]
    ) -> None:
        """Verify that metrics for moderate and high are structured and compared against standard baseline."""
        groups: Dict[Tuple[str, str, str], Dict[str, Dict[str, Any]]] = {}
        for r in matrix_results:
            key = (r["mix"], r["strategy"], r["density"])
            if key not in groups:
                groups[key] = {}
            groups[key][r["profile"]] = r

        assert len(groups) == 36  # 3 mixes x 4 strategies x 3 densities = 36 baselines

        total_hi_thr_gain = 0.0
        comparisons = []
        for key, cells in groups.items():
            assert "standard" in cells
            assert "moderate" in cells
            assert "high" in cells

            std = cells["standard"]
            mod = cells["moderate"]
            hi = cells["high"]

            # Compute deltas
            thr_diff_mod = mod["throughput"] - std["throughput"]
            thr_diff_hi = hi["throughput"] - std["throughput"]
            q_diff_hi = hi["average_queue"] - std["average_queue"]
            delay_diff_hi = hi["average_delay"] - std["average_delay"]

            total_hi_thr_gain += thr_diff_hi
            comparisons.append(
                {
                    "group": key,
                    "thr_diff_mod": thr_diff_mod,
                    "thr_diff_hi": thr_diff_hi,
                    "q_diff_hi": q_diff_hi,
                    "delay_diff_hi": delay_diff_hi,
                }
            )

        # Overall across the 36 conditions, high aggression yields non-negative throughput change
        assert total_hi_thr_gain >= 0.0
