"""The TTC pair scan reports exactly the events it always did (F-44).

``find_ttc_events`` works each vehicle's velocity and radius out once per call
instead of once per pair. That may not change a single event: which pairs are
tested, which yield a TTC, the values, or their order. Two checks, at every
tick of two busy runs (the leader-trace scenarios):

* the scan equals the specification it optimises, ``compute_ttc`` applied to
  every pair on different lanes within the search radius, in scan order;
* a digest of every event equals the one recorded with the per-pair
  implementation at ``eb01213`` (values rounded to 1 µs, as the leader-trace
  pins round gaps, so the digest survives float noise between platforms but
  not a different event).

Do not re-record a pin to make a change pass.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Tuple

import pytest

from src.controllers.factory import create_controller
from src.core.clock import Clock
from src.engine.simulation_engine import SimulationEngine
from src.metrics.definitions.safety_conflicts import compute_ttc, find_ttc_events
from src.scenario.documents import compile_scenario, parse_scenario
from src.vehicles.vehicle import Vehicle
from tests.vehicles.test_leader_trace_pins import MIXED, _document

SEARCH_RADIUS = 50.0  # MetricCollector's default ttcSearchRadius

# (id, document, strategy, pinned digest, pinned number of events); recorded
# 2026-10-30 with the per-pair scan of eb01213, before the F-44 change.
CASES: List[Tuple[str, Dict[str, Any], str, str, int]] = [
    (
        "roundabout-2ring-saturated-mixed",
        _document("roundabout", 2, 1000, 3, 60.0, rings=2, mix=MIXED),
        "roundabout",
        "88243e9e75102e87155a021f80715e3b2e025026c3fcaddc3489a49d8b03cc94",
        7371,
    ),
    (
        "signal-2lane-busy-mixed",
        _document("fixed_time_signal", 2, 900, 7, 60.0, mix=MIXED),
        "fixed_time",
        "d0f15a4de0b3ef2de2fba40ab9c3b45ba7f436c454f0708e481373f105cb4e84",
        6472,
    ),
]


def _reference(active: List[Vehicle]) -> List[Tuple[str, str, float]]:
    """compute_ttc on every candidate pair, in scan order."""
    placed = [v for v in active if v.lane is not None]
    events = []
    for i, va in enumerate(placed):
        ax, ay = va.coords
        for vb in placed[i + 1 :]:
            if va.lane is vb.lane:
                continue
            bx, by = vb.coords
            if (bx - ax) ** 2 + (by - ay) ** 2 > SEARCH_RADIUS**2:
                continue
            ttc = compute_ttc(va, vb)
            if ttc is not None:
                events.append((va.vehicle_id, vb.vehicle_id, ttc))
    return events


@pytest.mark.parametrize(
    "case_id, document, strategy, pinned, pinned_events",
    CASES,
    ids=[c[0] for c in CASES],
)
def test_the_ttc_scan_reports_exactly_the_recorded_events(
    case_id: str,
    document: Dict[str, Any],
    strategy: str,
    pinned: str,
    pinned_events: int,
) -> None:
    parsed, errors = parse_scenario(document)
    assert not errors, errors
    config = compile_scenario(parsed, strategy)
    duration = float(document["simulation"]["duration"])
    clock = Clock(time_step=0.1)
    engine = SimulationEngine(clock, duration=duration, config=config)
    engine.controller = create_controller(config, engine.network)

    digest = hashlib.sha256()
    count = 0
    for tick in range(clock.ticks_for_duration(duration)):
        engine.step()
        active = engine.pool.active_vehicles
        events = find_ttc_events(active, SEARCH_RADIUS)
        assert events == _reference(active), f"{case_id}: tick {tick}"
        for a, b, ttc in events:
            digest.update(f"{tick}|{a}|{b}|{ttc:.6f}\n".encode("ascii"))
            count += 1

    assert count == pinned_events, f"{case_id}: {count} TTC events"
    assert digest.hexdigest() == pinned, f"{case_id}: TTC events changed"
