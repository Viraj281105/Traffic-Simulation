"""Every leader decision the engine makes, pinned (F-30 groundwork).

``vehicles/router.find_leader`` is the engine's most expensive call: its
roundabout branch and its emergency proximity scan visit every active vehicle
for every vehicle, every tick. Any future speed-up (an index, a spatial
filter) must leave its *decisions* exactly as they are, not merely the
end-of-run metrics, which can hide a changed tie-break or a missed obstacle.

This test records, for every call in three representative runs, which vehicle
asked, what it found (a vehicle by id, a virtual obstacle by its fields, or
nothing) and the gap, and pins a digest of that trace. Gaps are rounded to
1 µm, as the portable roundabout pins are, so the digest survives float noise
between platforms but not a different decision.

Do not re-record a pin to make a change pass: a different digest means the
simulation behaves differently. Re-record only for an intended, reviewed
behaviour change, with the reason in the same diff.
"""

from __future__ import annotations

import hashlib
import math
from typing import Any, Dict, List, Tuple

import pytest

import src.engine.vehicle_pool as vehicle_pool
from src.controllers.factory import create_controller
from src.core.clock import Clock
from src.engine.simulation_engine import SimulationEngine
from src.engine.tick_callback import build_tick_callback
from src.metrics.collector import MetricCollector
from src.scenario.documents import compile_scenario, parse_scenario
from src.vehicles.vehicle import Vehicle

TIME_STEP = 0.1
MIXED = {"car": 0.6, "suv": 0.1, "bus": 0.1, "truck": 0.1, "motorcycle": 0.1}


def _document(
    junction: str, lanes: int, vph: float, seed: int, duration: float, **extra: Any
) -> Dict[str, Any]:
    approach: Dict[str, Any] = {
        "lanes": lanes,
        "length": 150.0,
        "vehiclesPerHour": vph,
        "turning": {"left": 0.25, "straight": 0.5, "right": 0.25},
    }
    if extra.get("mix"):
        approach["vehicleMix"] = dict(extra["mix"])
    doc: Dict[str, Any] = {
        "format": "urbanflow-scenario",
        "version": 1,
        "name": "leader trace",
        "junction": {"type": junction},
        "approaches": {d: dict(approach) for d in ("north", "south", "east", "west")},
        "simulation": {"duration": duration, "warmup": 10.0, "seed": seed},
    }
    if junction == "roundabout":
        doc["roundabout"] = {"circulatingLanes": extra.get("rings", 1)}
    return doc


# (id, scenario document, strategy, pinned digest, pinned number of calls).
# Recorded 2026-10-29 at eb01213 + checkpoint 2; identical on Windows/Python
# 3.14.7 and Linux/Python 3.11.16.
CASES: List[Tuple[str, Dict[str, Any], str, str, int]] = [
    (
        "roundabout-2ring-saturated-mixed",
        _document("roundabout", 2, 1000, 3, 60.0, rings=2, mix=MIXED),
        "roundabout",
        "47fdb3f9a73df3dfa11961ca21150c2867459907d043d3a5f4f1e7062dff31c4",
        16640,
    ),
    (
        "signal-2lane-busy-mixed",
        _document("fixed_time_signal", 2, 900, 7, 60.0, mix=MIXED),
        "fixed_time",
        "7899c03384258243db351fd278f7822c43a66a326739b0a6f8da649d24b0ab44",
        15245,
    ),
    (
        "roundabout-1ring-cars",
        _document("roundabout", 1, 600, 11, 60.0, rings=1),
        "roundabout",
        "1fdb24e5e0e47aad01c69a48225f1804bec7e0b786996f5c8fd8e4df6687fe3b",
        12837,
    ),
]


def _describe(found: Any) -> str:
    if found is None:
        return "none"
    if isinstance(found, Vehicle):
        return f"v:{found.vehicle_id}"
    fields = ("position", "speed", "length")
    values = ",".join(f"{float(getattr(found, f, 0.0)):.6f}" for f in fields)
    return f"o:{values}:{int(bool(getattr(found, 'stop_line', False)))}"


def _gap(gap: float) -> str:
    return "inf" if math.isinf(gap) else f"{gap:.6f}"


def trace(document: Dict[str, Any], strategy: str) -> Tuple[str, int]:
    """Digest and call count of every find_leader decision in one run."""
    parsed, errors = parse_scenario(document)
    assert not errors, errors
    config = compile_scenario(parsed, strategy)
    duration = float(document["simulation"]["duration"])
    clock = Clock(time_step=TIME_STEP)
    engine = SimulationEngine(clock, duration=duration, config=config)
    controller = create_controller(config, engine.network)
    engine.controller = controller
    collector = MetricCollector(config)
    engine.register_tick_callback(
        build_tick_callback(controller, clock, engine, collector)
    )

    digest = hashlib.sha256()
    calls = 0
    original = vehicle_pool.find_leader

    def recording(vehicle: Any, *args: Any, **kwargs: Any) -> Tuple[Any, float]:
        nonlocal calls
        found, gap = original(vehicle, *args, **kwargs)
        calls += 1
        line = f"{clock.get_tick_count()}|{vehicle.vehicle_id}|{_describe(found)}|{_gap(gap)}\n"
        digest.update(line.encode("ascii"))
        return found, gap

    vehicle_pool.find_leader = recording  # type: ignore[assignment]
    try:
        for _ in range(clock.ticks_for_duration(duration)):
            engine.step()
    finally:
        vehicle_pool.find_leader = original  # type: ignore[assignment]
    return digest.hexdigest(), calls


@pytest.mark.parametrize(
    "case_id, document, strategy, pinned, pinned_calls",
    CASES,
    ids=[c[0] for c in CASES],
)
def test_every_leader_decision_matches_its_pin(
    case_id: str,
    document: Dict[str, Any],
    strategy: str,
    pinned: str,
    pinned_calls: int,
) -> None:
    digest, calls = trace(document, strategy)
    assert calls == pinned_calls, f"{case_id}: {calls} find_leader calls"
    assert digest == pinned, (
        f"{case_id}: the leader trace changed ({digest}). A speed-up must not "
        "change which leader a vehicle finds or the gap to it; do not re-record "
        "this pin to make a change pass."
    )
