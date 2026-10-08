"""Adaptive signal control (V1.3) on whole simulations.

* Safety: on every tick of busy multi-lane and mixed-traffic runs, crossing
  roads are never released together and a road is only released after an
  all-red; no collisions, no gridlock.
* The conflict manager and collision checks stay authoritative: the adaptive
  signal changes when phases change, not who may enter.
* Determinism: the same seed replays the same run, decisions included.
* Fixed-time runs are unchanged (the V1.0 fingerprints in
  test_vehicle_types_and_lanes.py run through the same tick callback that now
  also measures green time).
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional

import jsonschema
import pytest

from src.controllers.adaptive_signal import AdaptiveSignalController
from src.core.enums import Direction
from src.snapshot.builder import SnapshotBuilder
from tests.integration.test_vehicle_types_and_lanes import (
    HEAVY_MIX,
    URBAN_MIX,
    _config,
    _Run,
)

SNAPSHOT_SCHEMA = json.loads(
    (
        Path(__file__).resolve().parents[3]
        / "shared"
        / "schemas"
        / "snapshot.schema.json"
    ).read_text(encoding="utf-8")
)
_NS = {Direction.NORTH, Direction.SOUTH}
_EW = {Direction.EAST, Direction.WEST}


def _adaptive(
    lanes: Any,
    rate: float,
    seed: int,
    duration: float,
    mix: Optional[Dict[str, float]] = None,
    lane_change: bool = True,
    **settings: Any,
) -> Dict[str, Any]:
    config = _config("fixed_time_signal", lanes, rate, seed, duration, mix)
    config["controller"]["signalControl"] = "adaptive"
    if settings:
        config["controller"]["adaptive"] = settings
    if not lane_change:
        config["roads"]["laneChange"] = {"enabled": False}
    return config


class _CheckedRun(_Run):
    """_Run plus a tick-level signal safety check."""

    def __init__(self, config: Dict[str, Any]) -> None:
        super().__init__(config)
        self.engine.register_tick_callback(self._check)
        self._released_before: set[Direction] = set()
        self._cleared = True
        self.ticks_checked = 0

    def _check(self) -> None:
        network = self.engine.network
        released = {
            d
            for d in Direction
            for lane in network.get_incoming_approach(d).get_lanes()
            if lane.virtual_obstacle is None
        }
        assert not (released & _NS and released & _EW), released
        if released - self._released_before:
            assert self._cleared, "a road was released without an all-red"
            self._cleared = False
        if self.controller.current_phase.name == "all_red":
            assert not released
            self._cleared = True
        self._released_before = released
        self.ticks_checked += 1


SAFETY_CASES = [
    # (lanes, rate, seed, mix, lane changing)
    (1, 0.3, 3, None, True),
    (1, 0.6, 21, HEAVY_MIX, True),
    (2, 0.8, 11, URBAN_MIX, True),
    (2, 0.6, 5, None, False),
    (3, 0.9, 7, URBAN_MIX, True),
    ({"north": 2, "south": 2, "east": 1, "west": 1}, 0.7, 5, URBAN_MIX, True),
]


@pytest.mark.parametrize("lanes,rate,seed,mix,lane_change", SAFETY_CASES)
def test_adaptive_runs_are_safe_and_flow(
    lanes: Any,
    rate: float,
    seed: int,
    mix: Optional[Dict[str, float]],
    lane_change: bool,
) -> None:
    run = _CheckedRun(_adaptive(lanes, rate, seed, 180, mix, lane_change)).run()
    assert isinstance(run.controller, AdaptiveSignalController)
    pool = run.engine.pool
    assert pool.collision_count == 0
    assert run.longest_stall < 70.0
    assert len(pool.exited_vehicles) >= 25
    assert run.ticks_checked == 1800
    decisions = run.controller.get_state()["adaptive"]["decisions"]
    assert decisions["greens"] >= 3
    assert decisions["gapOuts"] + decisions["maxOuts"] >= 2
    if lane_change and lanes != 1:
        assert pool.lane_change_count > 0


def test_adaptive_one_direction_plan_with_protected_lefts_is_safe() -> None:
    config = _adaptive(2, 0.5, 9, 240)
    del config["controller"]["phaseSequence"]
    run = _CheckedRun(config).run()
    assert run.engine.pool.collision_count == 0
    assert run.longest_stall < 70.0
    assert len(run.engine.pool.exited_vehicles) >= 40


def test_same_seed_replays_the_same_adaptive_run() -> None:
    config = _adaptive(2, 0.8, 19, 120, URBAN_MIX)
    first = _Run(config).run()
    second = _Run(config).run()
    assert first.fingerprint == second.fingerprint
    a, b = first.controller.get_state(), second.controller.get_state()
    assert a["adaptive"]["recentDecisions"] == b["adaptive"]["recentDecisions"]
    assert a["adaptive"]["decisions"] == b["adaptive"]["decisions"]
    assert first.engine.pool.lane_change_count == second.engine.pool.lane_change_count
    other = _Run(_adaptive(2, 0.8, 20, 120, URBAN_MIX)).run()
    assert other.fingerprint != first.fingerprint


def test_reset_replays_the_same_adaptive_run() -> None:
    import hashlib

    run = _Run(_adaptive(1, 0.4, 23, 90)).run()
    before = run.fingerprint
    run.engine.reset()
    run.digest = hashlib.sha256()
    assert run.run().fingerprint == before


def test_adaptive_differs_from_fixed_time_on_the_same_traffic() -> None:
    """Same seed, same arrivals: the adaptive signal makes its own timing
    decisions (it is not the fixed timetable under another name)."""
    fixed = _Run(_config("fixed_time_signal", 1, 0.2, 4, 150)).run()
    adaptive = _Run(_adaptive(1, 0.2, 4, 150)).run()
    assert fixed.fingerprint != adaptive.fingerprint
    assert fixed.engine.spawner is not None and adaptive.engine.spawner is not None
    assert fixed.engine.spawner.spawned_count == adaptive.engine.spawner.spawned_count


def test_green_time_is_measured_for_both_signals() -> None:
    fixed = _Run(_config("fixed_time_signal", 1, 0.3, 8, 240)).run()
    adaptive = _Run(_adaptive(1, 0.3, 8, 240)).run()
    timing = {}
    for name, run in (("fixed", fixed), ("adaptive", adaptive)):
        pool = run.engine.pool
        m = run.collector.get_metrics(
            240.0,
            pool.active_vehicles,
            pool.exited_vehicles,
            run.engine.spawner.spawned_count if run.engine.spawner else 0,
            pool.collision_count,
        )
        timing[name] = m["signalTiming"]
    assert timing["fixed"]["signalControl"] == "fixed_time"
    # 30 s greens (the harness's paired plan uses the 30 s default).
    assert timing["fixed"]["averageGreenDuration"] == pytest.approx(30.0, abs=0.2)
    assert timing["adaptive"]["signalControl"] == "adaptive"
    for t in timing.values():
        assert t["phaseChanges"] >= 2
        assert 0.0 <= t["greenUtilisation"] <= 1.0
        assert t["unusedGreenSeconds"] <= t["greenSeconds"]


def test_adaptive_snapshot_matches_the_schema() -> None:
    run = _Run(_adaptive(2, 0.7, 13, 60, HEAVY_MIX)).run()
    snap = SnapshotBuilder(
        "sim", "cfg", run.engine, run.collector, run.controller
    ).build()
    jsonschema.validate(snap, SNAPSHOT_SCHEMA)
    assert snap["controller"]["signalControl"] == "adaptive"
    assert snap["controller"]["adaptive"]["decisions"]["greens"] >= 1
    assert snap["metrics"]["signalTiming"]["signalControl"] == "adaptive"


def test_fixed_time_snapshot_reports_its_control() -> None:
    run = _Run(_config("fixed_time_signal", 1, 0.3, 2, 45)).run()
    snap = SnapshotBuilder(
        "sim", "cfg", run.engine, run.collector, run.controller
    ).build()
    jsonschema.validate(snap, SNAPSHOT_SCHEMA)
    assert snap["controller"]["signalControl"] == "fixed_time"
    assert "adaptive" not in snap["controller"]
    assert snap["metrics"]["signalTiming"]["signalControl"] == "fixed_time"


def test_roundabout_has_no_signal_timing() -> None:
    run = _Run(_config("roundabout", 1, 0.3, 2, 45)).run()
    snap = SnapshotBuilder(
        "sim", "cfg", run.engine, run.collector, run.controller
    ).build()
    jsonschema.validate(snap, SNAPSHOT_SCHEMA)
    assert snap["metrics"]["signalTiming"] is None
    assert "signalControl" not in snap["controller"]


@pytest.mark.slow
@pytest.mark.parametrize("lanes", [1, 2, 3])
@pytest.mark.parametrize("seed", [3, 8, 21])
@pytest.mark.parametrize("rate", [0.3, 0.7, 1.1])
def test_adaptive_sweep_has_no_collisions_or_gridlock(
    lanes: int, seed: int, rate: float
) -> None:
    mix = HEAVY_MIX if seed == 21 else None
    run = _CheckedRun(_adaptive(lanes, rate, seed, 240, mix)).run()
    assert run.engine.pool.collision_count == 0
    assert run.longest_stall < 70.0
