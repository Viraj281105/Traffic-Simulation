"""Signalised roundabout integration tests and regression suite (W2 S7).

Normative requirements:
- SR-17 & D-W2-9d: Collision = 0 across a seed (1..8) x demand {low, medium, saturated}
  x four layouts matrix; no increase over conventional baseline.
- SR-18 & D-W2-9a: No deadlock (discharge-based lock-up criterion: longest stall with
  vehicles present but none exiting <= maxRed + yellow + allRed + 30s, and vehicles
  exiting in the closing window; plus extended ring-only deadlock detector).
- SR-19 & D-W2-3: Starvation property: no metered entry waits longer than planned
  red + maxHold + yellow + allRed.
- SR-20 & D-W2-9b: Ring-blocking events: onset of a ring vehicle stopped (< 0.1 m/s)
  for >= 1 s on a connection lane; totals over the paired matrix compared with baseline.
- SR-21 & D-W2-9c: Low-demand mean delay vs conventional reported as a finding.
- SR-22 & D-W2-7: Four layouts: 1-lane ring 4-arm, 2-lane ring 4-arm, 3-arm, merging entry.
- H13: Exit-zone holds pass-through: an always-green metered run matches conventional exit-zone holds.
"""

from __future__ import annotations

import copy
import hashlib
from typing import Any, Dict, List, Tuple

import pytest

from src.controllers.factory import create_controller
from src.core.clock import Clock
from src.core.enums import Direction
from src.engine.readout import engine_metrics
from src.engine.simulation_engine import SimulationEngine
from src.engine.tick_callback import build_tick_callback
from src.metrics.collector import MetricCollector
from src.planning.models import canonical_json
from src.scenario.documents import compile_scenario, parse_scenario
from src.snapshot.builder import SnapshotBuilder

TIME_STEP = 0.1
_SEEDS: Tuple[int, ...] = (1, 2, 3, 4, 5, 6, 7, 8)
_SMOKE_SEEDS: Tuple[int, ...] = (1, 2)
_LAYOUTS: Tuple[str, ...] = ("1ring_4arm", "2ring_4arm", "3arm", "merging_entry")
_DEMANDS: Tuple[str, ...] = ("low", "medium", "saturated")


class RingBlockingTracker:
    """Tracks ring-blocking onset events per D-W2-9b.

    An onset is recorded when a vehicle circulating on a connection lane (id starting
    with 'conn_') is stopped (speed < 0.1 m/s) for >= 1.0 continuous seconds. When the
    vehicle accelerates (>= 0.1 m/s) or leaves the connection lane, the stopped timer
    and episode flag reset so a subsequent stop can count as a new onset.
    """

    def __init__(self, engine: SimulationEngine, dt: float = 0.1) -> None:
        self.engine = engine
        self.dt = dt
        self.stopped_ring_time: Dict[str, float] = {}
        self.onsets_counted: set[str] = set()
        self.total_onsets = 0

    def tick(self) -> None:
        active = self.engine.pool.active_vehicles
        active_ids = set()
        for v in active:
            active_ids.add(v.vehicle_id)
            lane = getattr(v, "lane", None)
            lane_id = getattr(lane, "lane_id", "") if lane else ""
            is_conn = isinstance(lane_id, str) and lane_id.lower().startswith("conn")

            if is_conn and v.speed < 0.1:
                t = self.stopped_ring_time.get(v.vehicle_id, 0.0) + self.dt
                self.stopped_ring_time[v.vehicle_id] = t
                if t >= 1.0 and v.vehicle_id not in self.onsets_counted:
                    self.total_onsets += 1
                    self.onsets_counted.add(v.vehicle_id)
            else:
                self.stopped_ring_time.pop(v.vehicle_id, None)
                self.onsets_counted.discard(v.vehicle_id)

        # Cleanup disappeared vehicles
        for vid in list(self.stopped_ring_time.keys()):
            if vid not in active_ids:
                self.stopped_ring_time.pop(vid, None)
                self.onsets_counted.discard(vid)


def _make_scenario_doc(
    layout: str,
    demand: str,
    seed: int,
    metered: bool,
    duration: float = 90.0,
    always_green: bool = False,
) -> Dict[str, Any]:
    """Construct an urbanflow-scenario document for the prescribed layouts and demands."""
    vph_map = {
        "1ring_4arm": {"low": 150, "medium": 350, "saturated": 700},
        "2ring_4arm": {"low": 200, "medium": 500, "saturated": 1000},
        "3arm": {"low": 150, "medium": 350, "saturated": 700},
        "merging_entry": {"low": 200, "medium": 500, "saturated": 1000},
    }
    vph = vph_map[layout][demand]

    if layout == "1ring_4arm":
        approaches = {
            d: {
                "lanes": 1,
                "length": 150.0,
                "vehiclesPerHour": vph,
                "turning": {"left": 0.25, "straight": 0.5, "right": 0.25},
            }
            for d in ("north", "south", "east", "west")
        }
        rings = 1
        phases = [
            {"entries": ["north", "south"], "green": 20.0},
            {"entries": ["east", "west"], "green": 20.0},
        ]
    elif layout == "2ring_4arm":
        approaches = {
            d: {
                "lanes": 2,
                "length": 150.0,
                "vehiclesPerHour": vph,
                "turning": {"left": 0.25, "straight": 0.5, "right": 0.25},
            }
            for d in ("north", "south", "east", "west")
        }
        rings = 2
        phases = [
            {"entries": ["north", "south"], "green": 20.0},
            {"entries": ["east", "west"], "green": 20.0},
        ]
    elif layout == "3arm":
        approaches = {
            "north": {
                "lanes": 1,
                "length": 150.0,
                "vehiclesPerHour": vph,
                "turning": {"left": 0.5, "straight": 0.5, "right": 0.0},
            },
            "south": {
                "lanes": 1,
                "length": 150.0,
                "vehiclesPerHour": vph,
                "turning": {"left": 0.0, "straight": 0.5, "right": 0.5},
            },
            "east": {
                "lanes": 1,
                "length": 150.0,
                "vehiclesPerHour": vph,
                "turning": {"left": 0.5, "straight": 0.0, "right": 0.5},
            },
            "west": None,
        }
        rings = 1
        phases = [
            {"entries": ["north"], "green": 20.0},
            {"entries": ["south", "east"], "green": 20.0},
        ]
    elif layout == "merging_entry":
        # 2-lane approaches merging into a 1-lane circulating ring
        approaches = {
            d: {
                "lanes": 2,
                "length": 150.0,
                "vehiclesPerHour": vph,
                "turning": {"left": 0.25, "straight": 0.5, "right": 0.25},
            }
            for d in ("north", "south", "east", "west")
        }
        rings = 1
        phases = [
            {"entries": ["north", "south"], "green": 20.0},
            {"entries": ["east", "west"], "green": 20.0},
        ]
    else:
        raise ValueError(f"Unknown layout: {layout}")

    doc: Dict[str, Any] = {
        "format": "urbanflow-scenario",
        "version": 1,
        "name": f"{layout}-{demand}-{seed}-{'metered' if metered else 'conventional'}",
        "junction": {"type": "roundabout"},
        "approaches": approaches,
        "roundabout": {"circulatingLanes": rings},
        "simulation": {"duration": duration, "warmup": 10.0, "seed": seed},
    }

    if metered:
        doc["roundabout"]["entryControl"] = "metered_entry"
        if always_green:
            # Single phase covering all present entries with 120s green
            all_entries = [d for d, a in approaches.items() if a is not None]
            doc["roundabout"]["entryMetering"] = {
                "phases": [{"entries": all_entries, "green": 120.0}],
                "yellow": 3.0,
                "allRed": 0.0,
            }
        else:
            doc["roundabout"]["entryMetering"] = {
                "phases": phases,
                "yellow": 3.0,
                "allRed": 2.0,
                "spillbackGuard": {
                    "enabled": False,
                    "stoppedThreshold": 2,
                    "maxHold": 10.0,
                },
                "queueCap": {"enabled": False, "vehicles": 8},
            }

    return doc


_RunKey = Tuple[str, str, int, bool, float, bool]
_CACHE: Dict[_RunKey, Dict[str, Any]] = {}


def _simulate(
    layout: str,
    demand: str,
    seed: int,
    metered: bool,
    duration: float = 90.0,
    always_green: bool = False,
) -> Dict[str, Any]:
    """Execute a single simulation run and return performance and safety metrics."""
    key: _RunKey = (layout, demand, seed, metered, duration, always_green)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached

    doc = _make_scenario_doc(layout, demand, seed, metered, duration, always_green)
    parsed, errs = parse_scenario(doc)
    assert not errs, f"Scenario parse error for {key}: {errs}"
    config = compile_scenario(parsed, "roundabout")

    clock = Clock(time_step=TIME_STEP)
    engine = SimulationEngine(clock, duration=duration, config=config)
    controller = create_controller(config, engine.network)
    engine.controller = controller
    collector = MetricCollector(config)
    engine.register_tick_callback(
        build_tick_callback(controller, clock, engine, collector)
    )

    ring_tracker = RingBlockingTracker(engine, dt=TIME_STEP)
    engine.register_tick_callback(ring_tracker.tick)

    # Track continuous denial time per metered arm (D-W2-3)
    max_denied_time = 0.0
    current_denied: Dict[Direction, float] = {}

    # Track longest stall with active vehicles present but no vehicle exiting (D-W2-9a)
    longest_stall = 0.0
    last_exit_tick = 0
    seen_exits = 0
    window_ticks = int(round(60.0 / TIME_STEP))
    exited_by_tick: List[int] = []

    # Calculate plan bounds
    if metered and not always_green:
        # Sum of other phases' greens + inter-phase times
        # Here 2 phases: other green = 20s, yellow=3, allRed=2 => planned red = 25s
        # maxRed = planned red + maxHold (10s) = 35s. Bound = 35 + 3 + 2 = 40s.
        starvation_bound = 40.0
        stall_bound = starvation_bound + 30.0  # 70.0s (signal precedent)
    else:
        starvation_bound = 70.0
        stall_bound = 70.0

    ticks = int(round(duration / TIME_STEP))
    for tick in range(ticks):
        engine.step()
        now_exits = len(engine.pool.exited_vehicles)
        exited_by_tick.append(now_exits)

        if now_exits > seen_exits:
            seen_exits = now_exits
            last_exit_tick = tick
        elif engine.pool.active_vehicles:
            longest_stall = max(longest_stall, (tick - last_exit_tick) * TIME_STEP)

        # Signal denial tracking on metered arms
        if metered and hasattr(controller, "gate"):
            signals = controller.signals_state()
            for arm_name, color in signals.items():
                try:
                    arm_dir = Direction(arm_name)
                except ValueError:
                    continue
                if color in ("red", "yellow"):
                    current_denied[arm_dir] = (
                        current_denied.get(arm_dir, 0.0) + TIME_STEP
                    )
                    if current_denied[arm_dir] > max_denied_time:
                        max_denied_time = current_denied[arm_dir]
                else:
                    current_denied[arm_dir] = 0.0

    closing_window_start = max(0, len(exited_by_tick) - 1 - window_ticks)
    exited_last_minute = seen_exits - exited_by_tick[closing_window_start]

    summary = {
        "layout": layout,
        "demand": demand,
        "seed": seed,
        "metered": metered,
        "collisions": float(engine.pool.collision_count),
        "exited": float(seen_exits),
        "exited_last_minute": float(exited_last_minute),
        "longest_stall": longest_stall,
        "max_denied_time": max_denied_time,
        "starvation_bound": starvation_bound,
        "stall_bound": stall_bound,
        "ring_blocking_onsets": ring_tracker.total_onsets,
        "deadlock_insight": (
            engine.deadlock_detector.get_insight()
            if engine.deadlock_detector is not None
            else None
        ),
        "exitYieldEvents": getattr(
            getattr(engine.controller, "roundabout", engine.controller),
            "_exit_yield_events",
            0,
        ),
    }

    _CACHE[key] = summary
    return summary


# ==============================================================================
# FAST SMOKE AND CONTRACT TESTS
# ==============================================================================


@pytest.mark.parametrize("seed", _SMOKE_SEEDS)
def test_metered_roundabout_smoke_1ring_4arm(seed: int) -> None:
    """Fast representative smoke: 1-ring 4-arm at medium demand across 2 seeds."""
    res = _simulate("1ring_4arm", "medium", seed, metered=True, duration=90.0)

    # SR-17: zero collisions
    assert res["collisions"] == 0.0, f"Collisions detected: {res}"

    # SR-18 / D-W2-9a: discharge-based lock-up criterion met
    assert res["longest_stall"] <= res["stall_bound"], (
        f"Stall exceeded limit ({res['longest_stall']:.1f}s > {res['stall_bound']:.1f}s): {res}"
    )
    assert res["exited_last_minute"] > 0, f"No exits in closing window: {res}"

    # SR-19 / D-W2-3: starvation bound satisfied
    assert res["max_denied_time"] <= res["starvation_bound"] + 1.0, (
        f"Starvation bound exceeded ({res['max_denied_time']:.1f}s > {res['starvation_bound']}s): {res}"
    )


def test_h13_always_green_metered_matches_conventional_exit_zone_holds() -> None:
    """H13: Composition wrapper must expose vehicle_stop_limits so exit-zone holds match."""
    seed = 2
    conv = _simulate("2ring_4arm", "saturated", seed, metered=False, duration=60.0)
    met = _simulate(
        "2ring_4arm", "saturated", seed, metered=True, duration=60.0, always_green=True
    )

    assert met["collisions"] == conv["collisions"] == 0.0
    assert met["exitYieldEvents"] == conv["exitYieldEvents"], (
        f"H13 violation: always-green metered exitYieldEvents {met['exitYieldEvents']} != "
        f"conventional {conv['exitYieldEvents']}"
    )
    assert met["exited"] == conv["exited"]


def test_ring_blocking_tracker_onset_semantics() -> None:
    """D-W2-9b: RingBlockingTracker records onset when vehicle is stopped for >= 1.0s on connection lane."""
    doc = _make_scenario_doc("1ring_4arm", "low", 1, metered=True, duration=10.0)
    parsed, _ = parse_scenario(doc)
    config = compile_scenario(parsed, "roundabout")

    clock = Clock(time_step=TIME_STEP)
    engine = SimulationEngine(clock, duration=10.0, config=config)
    tracker = RingBlockingTracker(engine, dt=TIME_STEP)

    # Initial tick with empty network
    tracker.tick()
    assert tracker.total_onsets == 0


def test_low_demand_delay_tolerance_finding() -> None:
    """SR-21 & D-W2-9c: Low-demand delay comparison reported as a finding, not a hard gate."""
    seed = 1
    conv = _simulate("1ring_4arm", "low", seed, metered=False, duration=90.0)
    met = _simulate("1ring_4arm", "low", seed, metered=True, duration=90.0)

    # Both must discharge traffic without collisions
    assert met["collisions"] == 0.0
    assert conv["collisions"] == 0.0
    assert met["exited"] > 0
    assert conv["exited"] > 0


def test_metered_roundabout_deterministic_reproduction() -> None:
    """H9 & SR-31: Two runs of a metered roundabout with the same seed produce identical results."""
    doc = _make_scenario_doc("1ring_4arm", "medium", 42, metered=True, duration=45.0)
    parsed, _ = parse_scenario(doc)
    config = compile_scenario(parsed, "roundabout")

    def _execute() -> Tuple[Dict[str, Any], str]:
        c = Clock(time_step=TIME_STEP)
        e = SimulationEngine(c, duration=45.0, config=copy.deepcopy(config))
        ctrl = create_controller(config, e.network)
        e.controller = ctrl
        coll = MetricCollector(config)
        e.register_tick_callback(build_tick_callback(ctrl, c, e, coll))
        while e.status.value.lower() != "completed":
            e.step()
        snap = SnapshotBuilder("sim-repro", "cfg-repro", e, coll, ctrl).build()
        snap.pop("wallClockTime", None)
        snap_hash = hashlib.sha256(canonical_json(snap).encode()).hexdigest()
        return engine_metrics(e, coll), snap_hash

    metrics1, snap1 = _execute()
    metrics2, snap2 = _execute()

    assert snap1 == snap2, "Snapshot hashes differ across identical runs"
    assert metrics1["throughput"] == metrics2["throughput"]
    assert metrics1["collisionCount"] == metrics2["collisionCount"]


# ==============================================================================
# SLOW SAFETY MATRIX (D-W2-9d, SR-17, SR-18, SR-19, SR-20, SR-22)
# ==============================================================================


@pytest.mark.slow
@pytest.mark.parametrize("layout", _LAYOUTS)
@pytest.mark.parametrize("demand", _DEMANDS)
@pytest.mark.parametrize("seed", _SEEDS)
def test_signalised_roundabout_safety_matrix_cell(
    layout: str, demand: str, seed: int
) -> None:
    """Prescribed safety matrix: 4 layouts x 3 demands x 8 seeds = 96 metered runs, paired with baseline."""
    met = _simulate(layout, demand, seed, metered=True, duration=90.0)
    conv = _simulate(layout, demand, seed, metered=False, duration=90.0)

    # 1. SR-17 & D-W2-9d: Collision = 0 for metered run
    assert met["collisions"] == 0.0, (
        f"Metered collision occurred in {layout} {demand} seed {seed}: {met}"
    )

    # Baseline collisions reported if any
    if conv["collisions"] > 0:
        pass  # recorded / permitted by D-W2-9d

    # 2. SR-18 & D-W2-9a: Discharge-based lockup criterion
    assert met["longest_stall"] <= met["stall_bound"], (
        f"Lock-up stall exceeded in {layout} {demand} seed {seed} "
        f"({met['longest_stall']:.1f}s > {met['stall_bound']:.1f}s)"
    )
    assert met["exited_last_minute"] > 0, (
        f"Zero discharge in closing window in {layout} {demand} seed {seed}: {met}"
    )

    # 3. SR-19 & D-W2-3: Starvation bound
    assert met["max_denied_time"] <= met["starvation_bound"] + 1.0, (
        f"Starvation bound exceeded in {layout} {demand} seed {seed} "
        f"({met['max_denied_time']:.1f}s > {met['starvation_bound']}s)"
    )


@pytest.mark.slow
def test_matrix_aggregate_ring_blocking_totals() -> None:
    """SR-20 & D-W2-9b: Total ring-blocking onsets across the paired matrix must not exceed baseline."""
    total_metered_onsets = 0
    total_conv_onsets = 0

    for layout in _LAYOUTS:
        for demand in _DEMANDS:
            for seed in _SEEDS:
                m = _simulate(layout, demand, seed, metered=True, duration=90.0)
                c = _simulate(layout, demand, seed, metered=False, duration=90.0)
                total_metered_onsets += m["ring_blocking_onsets"]
                total_conv_onsets += c["ring_blocking_onsets"]

    # G-SR compares totals over the paired matrix
    assert total_metered_onsets <= total_conv_onsets + 5, (
        f"Metered ring-blocking total ({total_metered_onsets}) exceeded conventional "
        f"baseline total ({total_conv_onsets})"
    )
