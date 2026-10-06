"""End-to-end regression for V1.1 (vehicle classes) and V1.2 (lane model).

* Legacy compatibility: single-lane, cars-only scenarios must reproduce the
  V1.0 engine exactly. The fingerprints below were produced by the V1.0
  release (commit e36bd54) and are matched bit for bit.
* Safety: mixed traffic and multi-lane junctions, signal and roundabout, run
  with zero collisions and without gridlock.
* Determinism: the same seed replays the same run, including vehicle classes
  and lane changes.
"""

import hashlib
from typing import Any, Dict, List, Optional, Tuple

import pytest

from src.controllers.factory import build_tick_callback, create_controller
from src.core.clock import Clock
from src.core.config_validation import semantic_config_errors
from src.core.engine import SimulationEngine
from src.metrics.collector import MetricCollector
from src.snapshot.builder import SnapshotBuilder

PAIRED = ["ns_green", "ns_yellow", "all_red", "ew_green", "ew_yellow", "all_red"]
URBAN_MIX = {"car": 0.6, "suv": 0.2, "bus": 0.05, "truck": 0.05, "motorcycle": 0.1}
HEAVY_MIX = {"car": 0.5, "suv": 0.1, "bus": 0.15, "truck": 0.15, "motorcycle": 0.1}


def _config(
    kind: str,
    lanes: Any,
    rate: float,
    seed: int,
    duration: float,
    mix: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    config: Dict[str, Any] = {
        "simulation": {
            "duration": duration,
            "timeStep": 0.1,
            "warmupTime": 10.0,
            "randomSeed": seed,
        },
        "geometry": {"intersectionType": kind},
        "roads": {"approachLength": 200.0, "laneWidth": 3.5, "lanesPerApproach": lanes},
        "traffic": {
            "arrivalRate": rate,
            "arrivalDistribution": "poisson",
            "totalVehicles": 1000,
        },
        "controller": {"phaseSequence": list(PAIRED)},
    }
    if mix is not None:
        config["vehicleGeneration"] = {"vehicleMix": dict(mix)}
    assert semantic_config_errors(config) == []
    return config


class _Run:
    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        self.clock = Clock(time_step=0.1)
        self.engine = SimulationEngine(
            self.clock, duration=config["simulation"]["duration"], config=config
        )
        self.controller = create_controller(config, self.engine.network)
        self.engine.controller = self.controller
        self.collector = MetricCollector(config)
        self.engine.register_tick_callback(
            build_tick_callback(
                self.controller, self.clock, self.engine, self.collector
            )
        )
        self.digest = hashlib.sha256()
        self.longest_stall = 0.0

    def run(self) -> "_Run":
        ticks = int(round(self.config["simulation"]["duration"] / 0.1))
        last_exit_tick, exited = 0, 0
        for tick in range(ticks):
            self.engine.step()
            if tick % 25 == 0:
                for v in self.engine.pool.active_vehicles:
                    lane_id = v.lane.lane_id if v.lane else ""
                    self.digest.update(
                        f"{v.vehicle_id}|{lane_id}|{v.position:.6f}|{v.speed:.6f};".encode()
                    )
            now_exited = len(self.engine.pool.exited_vehicles)
            if now_exited != exited:
                exited, last_exit_tick = now_exited, tick
            elif self.engine.pool.active_vehicles:
                self.longest_stall = max(
                    self.longest_stall, (tick - last_exit_tick) * 0.1
                )
        self.digest.update(f"exited={len(self.engine.pool.exited_vehicles)}".encode())
        return self

    @property
    def fingerprint(self) -> str:
        return self.digest.hexdigest()


# Produced by the V1.0 engine (e36bd54) with exactly this harness.
V10_FINGERPRINTS: List[Tuple[Tuple[str, int, float, int], str]] = [
    (
        ("fixed_time_signal", 1, 0.6, 21),
        "7b1f0f392d9c0bd3e5ef22e5b29d73b08ae184c61b115ad8ccd2d068547e7a79",
    ),
    (
        ("roundabout", 1, 0.6, 21),
        "2b92acc3007def7d4f1d1477cc9528f80e3e623851ac35f6dc0eeb89e2e49875",
    ),
    (
        ("fixed_time_signal", 1, 1.2, 5),
        "bc5454a576c0e6faf5197f1958e5fb920781ef7ed3f1f9ca9e96695fb2a0435e",
    ),
    (
        ("roundabout", 1, 1.2, 5),
        "390c74d2c284712f1bf3f36dd8502f4df28decd136006ec945aff4174f35394b",
    ),
]


@pytest.mark.parametrize("case,expected", V10_FINGERPRINTS)
def test_single_lane_cars_only_reproduces_v10_exactly(
    case: Tuple[str, int, float, int], expected: str
) -> None:
    kind, lanes, rate, seed = case
    config = _config(kind, lanes, rate, seed, duration=90)
    config["simulation"]["warmupTime"] = 10.0
    assert _Run(config).run().fingerprint == expected


SAFETY_CASES = [
    # (kind, lanes, rate, seed, mix)
    ("fixed_time_signal", 1, 0.6, 3, HEAVY_MIX),
    ("roundabout", 1, 0.6, 3, HEAVY_MIX),
    ("fixed_time_signal", 2, 0.8, 11, URBAN_MIX),
    ("roundabout", 2, 0.8, 11, URBAN_MIX),
    ("fixed_time_signal", 3, 0.8, 7, None),
    (
        "fixed_time_signal",
        {"north": 2, "south": 2, "east": 1, "west": 1},
        0.7,
        5,
        URBAN_MIX,
    ),
]


@pytest.mark.parametrize("kind,lanes,rate,seed,mix", SAFETY_CASES)
def test_mixed_and_multilane_runs_are_collision_and_gridlock_free(
    kind: str, lanes: Any, rate: float, seed: int, mix: Optional[Dict[str, float]]
) -> None:
    run = _Run(_config(kind, lanes, rate, seed, duration=150, mix=mix)).run()
    pool = run.engine.pool
    assert pool.collision_count == 0
    assert len(pool.exited_vehicles) >= 25
    # Longest stretch with vehicles present but nobody leaving: a signal red
    # plus queue discharge is well under a minute; a gridlock is not.
    assert run.longest_stall < 70.0
    if mix is not None:
        served = {v.vehicle_type for v in pool.exited_vehicles}
        assert len(served) >= 3


def test_multilane_runs_change_lanes_gradually() -> None:
    run = _Run(_config("fixed_time_signal", 3, 0.8, 7, duration=150)).run()
    assert run.engine.pool.lane_change_count > 0
    assert run.engine.pool.collision_count == 0


@pytest.mark.parametrize("kind", ["fixed_time_signal", "roundabout"])
def test_same_seed_replays_mixed_multilane_runs_exactly(kind: str) -> None:
    config = _config(kind, 2, 0.8, 19, duration=90, mix=URBAN_MIX)
    first = _Run(config).run()
    second = _Run(config).run()
    assert first.fingerprint == second.fingerprint
    assert [v.vehicle_type for v in first.engine.pool.exited_vehicles] == [
        v.vehicle_type for v in second.engine.pool.exited_vehicles
    ]
    assert first.engine.pool.lane_change_count == second.engine.pool.lane_change_count
    different = _Run(_config(kind, 2, 0.8, 20, duration=90, mix=URBAN_MIX)).run()
    assert different.fingerprint != first.fingerprint


def test_reset_replays_the_same_mixed_run() -> None:
    config = _config("fixed_time_signal", 2, 0.8, 23, duration=60, mix=URBAN_MIX)
    run = _Run(config).run()
    before = run.fingerprint
    run.engine.reset()
    run.digest = hashlib.sha256()
    assert run.run().fingerprint == before


def test_snapshot_reports_classes_lanes_and_breakdown() -> None:
    run = _Run(
        _config("fixed_time_signal", 2, 0.9, 13, duration=90, mix=HEAVY_MIX)
    ).run()
    builder = SnapshotBuilder("sim", "cfg", run.engine, run.collector, run.controller)
    snap = builder.build()
    active = [v for v in snap["vehicles"] if v["state"] != "exited"]
    assert active
    assert {v["vehicleType"] for v in snap["vehicles"]} <= {
        "car",
        "suv",
        "bus",
        "truck",
        "motorcycle",
    }
    for v in active:
        assert v["laneChange"] in (None, "left", "right")
        if v["laneId"].startswith(("n_in", "s_in", "e_in", "w_in")):
            assert v["laneIndex"] == int(v["laneId"].rsplit("_", 1)[1])
    approach = snap["intersection"]["approaches"][0]
    assert approach["lanePermittedTurns"] == [
        ["left", "straight"],
        ["straight", "right"],
    ]
    # Heavy vehicles in the mix: the design-vehicle stop-line setback.
    assert snap["intersection"]["stopLineSetback"] > 3.5
    breakdown = snap["metrics"]["vehicleTypeBreakdown"]
    served = sum(entry["exited"] for entry in breakdown.values())
    assert served == snap["metrics"]["throughput"]
    assert set(snap["laneModel"]) == {
        "laneChanges",
        "laneChangesInProgress",
        "missedTurns",
    }


def test_heavy_vehicles_are_slower_than_cars_on_the_same_junction() -> None:
    run = _Run(
        _config("fixed_time_signal", 1, 0.3, 31, duration=240, mix=HEAVY_MIX)
    ).run()
    exited = run.engine.pool.exited_vehicles

    def mean_speed(type_id: str) -> float:
        vs = [v.desired_speed for v in exited if v.vehicle_type == type_id]
        assert vs, type_id
        return sum(vs) / len(vs)

    assert mean_speed("truck") < mean_speed("car")
    assert mean_speed("bus") < mean_speed("car")
    lengths = {v.vehicle_type: v.length for v in exited}
    assert lengths["motorcycle"] < lengths["car"] < lengths["bus"]


@pytest.mark.parametrize(
    "lanes,mix,duration",
    [(2, URBAN_MIX, 180), (3, HEAVY_MIX, 240)],
)
def test_multilane_roundabout_mouth_with_long_vehicles(
    lanes: int, mix: Dict[str, float], duration: float
) -> None:
    """Two runs that used to end in contact at a two/three-lane roundabout
    mouth: a car turning onto the outer ring swung its tail into a bus or
    truck entering beside it (then, with that prevented, the two blocked each
    other). Long vehicles now take the whole mouth while they swing in."""
    run = _Run(_config("roundabout", lanes, 0.5, 3, duration=duration, mix=mix)).run()
    assert run.engine.pool.collision_count == 0
    assert run.longest_stall < 70.0


def test_signal_merge_onto_one_exit_lane_does_not_deadlock() -> None:
    """Three-lane signal, city mix: a car going straight and an SUV turning
    left, both already in the junction and both heading for the same exit
    lane, used to wait on each other until the run ended (50 of 162 vehicles
    served). Committed vehicles now merge in physical order."""
    run = _Run(
        _config("fixed_time_signal", 3, 0.5, 13, duration=240, mix=URBAN_MIX)
    ).run()
    assert run.engine.pool.collision_count == 0
    assert run.longest_stall < 70.0
    assert len(run.engine.pool.exited_vehicles) >= 70


@pytest.mark.slow
@pytest.mark.parametrize("kind", ["fixed_time_signal", "roundabout"])
@pytest.mark.parametrize("seed", [3, 5, 8, 13, 21])
@pytest.mark.parametrize("rate", [0.5, 1.0])
def test_heavy_mix_sweep_has_no_collisions_or_gridlock(
    kind: str, seed: int, rate: float
) -> None:
    run = _Run(_config(kind, 1, rate, seed, duration=240, mix=HEAVY_MIX)).run()
    assert run.engine.pool.collision_count == 0
    assert run.longest_stall < 70.0
