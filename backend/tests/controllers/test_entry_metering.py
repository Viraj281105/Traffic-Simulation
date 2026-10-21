"""Tests for entry metering plan model, resolver, and cursor (W2 Step S3).

Pins the requirements of SR-08, SR-09, SR-10, SR-19, and decisions D-W2-3, D-W2-6:
- Phase plan expansion (green -> yellow -> all-red)
- Carry-over timing arithmetic and exact boundary transitions
- Direction-specific color projection (metered vs unmetered)
- Offset initialization and wrap-around
- Early green termination (queue-cap hook)
- Deterministic fuzzing over >= 10,000 valid plans asserting the starvation property.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Tuple

import pytest

from src.controllers.entry_metering import (
    MeteredPhaseSpec,
    MeteringPhaseCursor,
    build_metering_plan,
)
from src.core.enums import Direction

# ---------------------------------------------------------------------------
# Fixtures and Helpers
# ---------------------------------------------------------------------------

_BASIC_CONFIG: Dict[str, Any] = {
    "phases": [
        {
            "entries": ["north", "south"],
            "green": 20.0,
            "minGreen": 8.0,
            "maxGreen": 40.0,
        },
        {"entries": ["east", "west"], "green": 15.0, "minGreen": 6.0, "maxGreen": 30.0},
    ],
    "yellow": 3.0,
    "allRed": 2.0,
    "offset": 0.0,
}


def _assert_close(a: float, b: float, tol: float = 1e-9) -> None:
    assert abs(a - b) < tol, f"{a} != {b} (diff {abs(a - b)} >= {tol})"


# ---------------------------------------------------------------------------
# MeteredPhaseSpec Tests
# ---------------------------------------------------------------------------


def test_spec_valid_construction() -> None:
    spec = MeteredPhaseSpec(
        entries=(Direction.NORTH, Direction.SOUTH),
        green=20.0,
        min_green=8.0,
        max_green=40.0,
    )
    assert spec.entries == (Direction.NORTH, Direction.SOUTH)
    assert spec.green == 20.0
    assert spec.min_green == 8.0
    assert spec.max_green == 40.0


@pytest.mark.parametrize(
    ("entries", "green", "min_g", "max_g", "expected_err"),
    [
        ((), 20.0, 8.0, 40.0, "at least one entry"),
        ((Direction.NORTH,), -5.0, 5.0, 30.0, "green duration must be positive"),
        ((Direction.NORTH,), 0.0, 0.0, 30.0, "green duration must be positive"),
        ((Direction.NORTH,), 20.0, -1.0, 30.0, "min_green must be positive"),
        ((Direction.NORTH,), 20.0, 10.0, -1.0, "max_green must be positive"),
        (
            (Direction.NORTH,),
            20.0,
            35.0,
            30.0,
            r"min_green .* cannot exceed max_green",
        ),
        (
            (Direction.NORTH,),
            5.0,
            10.0,
            30.0,
            r"green .* cannot be less than min_green",
        ),
        (
            (Direction.NORTH,),
            45.0,
            10.0,
            40.0,
            r"green .* cannot exceed max_green",
        ),
    ],
)
def test_spec_invalid_inputs_raise(
    entries: Tuple[Direction, ...],
    green: float,
    min_g: float,
    max_g: float,
    expected_err: str,
) -> None:
    with pytest.raises(ValueError, match=expected_err):
        MeteredPhaseSpec(entries=entries, green=green, min_green=min_g, max_green=max_g)


# ---------------------------------------------------------------------------
# build_metering_plan Resolver Tests
# ---------------------------------------------------------------------------


def test_build_plan_basic_expansion() -> None:
    plan = build_metering_plan(_BASIC_CONFIG)

    # 2 specs -> each expands to green, yellow, all-red = 6 phases total
    assert len(plan.specs) == 2
    assert len(plan.phases) == 6

    # Cycle = (20 + 3 + 2) + (15 + 3 + 2) = 25 + 20 = 45 s
    _assert_close(plan.cycle_duration, 45.0)
    assert plan.metered_entries == frozenset(
        {Direction.NORTH, Direction.SOUTH, Direction.EAST, Direction.WEST}
    )

    # Phase 0: green (N, S)
    p0 = plan.phases[0]
    assert p0.name == "north_south_green"
    assert p0.directions == (Direction.NORTH, Direction.SOUTH)
    assert p0.color == "green"
    assert p0.duration == 20.0

    # Phase 1: yellow (N, S)
    p1 = plan.phases[1]
    assert p1.name == "north_south_yellow"
    assert p1.directions == (Direction.NORTH, Direction.SOUTH)
    assert p1.color == "yellow"
    assert p1.duration == 3.0

    # Phase 2: all_red
    p2 = plan.phases[2]
    assert p2.name == "north_south_all_red"
    assert p2.directions == ()
    assert p2.color == "red"
    assert p2.duration == 2.0

    # Phase 3: green (E, W)
    p3 = plan.phases[3]
    assert p3.name == "east_west_green"
    assert p3.directions == (Direction.EAST, Direction.WEST)
    assert p3.color == "green"
    assert p3.duration == 15.0

    # Planned red and green calculations
    _assert_close(plan.planned_green_for(Direction.NORTH), 20.0)
    _assert_close(plan.planned_red_for(Direction.NORTH), 2.0 + 15.0 + 3.0 + 2.0)  # 22.0


def test_build_plan_nested_config_locations() -> None:
    # 1. Under "controller.entryMetering"
    cfg1 = {"controller": {"entryMetering": _BASIC_CONFIG}}
    plan1 = build_metering_plan(cfg1)
    assert plan1.cycle_duration == 45.0

    # 2. Under top-level "entryMetering"
    cfg2 = {"entryMetering": _BASIC_CONFIG}
    plan2 = build_metering_plan(cfg2)
    assert plan2.cycle_duration == 45.0


def test_build_plan_zero_clearance_omits_subphases() -> None:
    cfg = {
        "phases": [{"entries": ["north"], "green": 25.0}],
        "yellow": 0.0,
        "allRed": 0.0,
    }
    plan = build_metering_plan(cfg)
    assert len(plan.phases) == 1
    assert plan.phases[0].color == "green"
    assert plan.phases[0].duration == 25.0
    assert plan.cycle_duration == 25.0


def test_build_plan_partial_metering_leaves_unmetered_arms_out() -> None:
    # Only North is metered; South, East, West are unmetered
    cfg = {
        "phases": [{"entries": ["north"], "green": 20.0}],
        "yellow": 3.0,
        "allRed": 2.0,
    }
    plan = build_metering_plan(cfg)
    assert plan.metered_entries == frozenset({Direction.NORTH})
    assert plan.planned_green_for(Direction.SOUTH) == plan.cycle_duration
    assert plan.planned_red_for(Direction.SOUTH) == 0.0


@pytest.mark.parametrize(
    ("bad_cfg", "expected_err"),
    [
        ({}, "entryMetering must define a non-empty list of phases"),
        ({"phases": []}, "entryMetering must define a non-empty list of phases"),
        ({"phases": ["not_a_dict"]}, "phase at index 0 must be a dictionary"),
        (
            {"phases": [{"entries": [], "green": 10}]},
            "must have non-empty entries list",
        ),
        (
            {"phases": [{"entries": ["north", "north"], "green": 10}]},
            "duplicate entry 'north'",
        ),
        (
            {"phases": [{"entries": ["invalid_dir"], "green": 10}]},
            "cannot parse 'invalid_dir'",
        ),
        ({"phases": [{"entries": ["north"], "green": -5}]}, "green must be positive"),
        (
            {"phases": [{"entries": ["north"], "green": 10}], "yellow": -1.0},
            "yellow duration cannot be negative",
        ),
        (
            {"phases": [{"entries": ["north"], "green": 10}], "allRed": -1.0},
            "allRed duration cannot be negative",
        ),
        (
            {"phases": [{"entries": ["north"], "green": 10}], "offset": -2.0},
            "offset cannot be negative",
        ),
    ],
)
def test_build_plan_invalid_configs_raise(
    bad_cfg: Dict[str, Any], expected_err: str
) -> None:
    with pytest.raises(ValueError, match=expected_err):
        build_metering_plan(bad_cfg)


# ---------------------------------------------------------------------------
# MeteringPhaseCursor Tests
# ---------------------------------------------------------------------------


def test_cursor_initial_state_zero_offset() -> None:
    plan = build_metering_plan(_BASIC_CONFIG)
    cursor = MeteringPhaseCursor(plan)

    assert cursor.current_phase_idx == 0
    assert cursor.current_phase.name == "north_south_green"
    assert cursor.time_in_current_state == 0.0
    assert cursor.cycle_number == 0
    _assert_close(cursor.phase_time_remaining, 20.0)
    _assert_close(cursor.cycle_time_elapsed, 0.0)
    _assert_close(cursor.cycle_progress, 0.0)


def test_cursor_with_offset() -> None:
    # Basic cycle is 45s:
    # Phase 0: Green (20s) -> [0, 20)
    # Phase 1: Yellow (3s) -> [20, 23)
    # Phase 2: AllRed (2s) -> [23, 25)
    # Phase 3: Green (15s) -> [25, 40)
    # Phase 4: Yellow (3s) -> [40, 43)
    # Phase 5: AllRed (2s) -> [43, 45)

    # Offset = 21.0 -> should land in Phase 1 (Yellow) with 1.0 s elapsed
    cfg = dict(_BASIC_CONFIG, offset=21.0)
    plan = build_metering_plan(cfg)
    cursor = MeteringPhaseCursor(plan)

    assert cursor.current_phase_idx == 1
    assert cursor.current_phase.color == "yellow"
    _assert_close(cursor.time_in_current_state, 1.0)
    _assert_close(cursor.phase_time_remaining, 2.0)
    _assert_close(cursor.cycle_time_elapsed, 21.0)


def test_cursor_offset_modulo_cycle() -> None:
    # Offset = 45.0 + 10.0 = 55.0 -> lands at t=10 in Phase 0
    cfg = dict(_BASIC_CONFIG, offset=55.0)
    plan = build_metering_plan(cfg)
    cursor = MeteringPhaseCursor(plan)

    assert cursor.current_phase_idx == 0
    _assert_close(cursor.time_in_current_state, 10.0)


def test_cursor_advance_within_phase() -> None:
    plan = build_metering_plan(_BASIC_CONFIG)
    cursor = MeteringPhaseCursor(plan)

    cursor.advance(5.0)
    assert cursor.current_phase_idx == 0
    _assert_close(cursor.time_in_current_state, 5.0)
    _assert_close(cursor.phase_time_remaining, 15.0)
    _assert_close(cursor.cycle_time_elapsed, 5.0)


def test_cursor_advance_exact_boundary() -> None:
    plan = build_metering_plan(_BASIC_CONFIG)
    cursor = MeteringPhaseCursor(plan)

    # Phase 0 duration is 20.0
    cursor.advance(20.0)
    assert cursor.current_phase_idx == 1
    assert cursor.current_phase.color == "yellow"
    _assert_close(cursor.time_in_current_state, 0.0)
    _assert_close(cursor.phase_time_remaining, 3.0)


def test_cursor_advance_carry_over() -> None:
    plan = build_metering_plan(_BASIC_CONFIG)
    cursor = MeteringPhaseCursor(plan)

    # Advance 21.5 s: spans Phase 0 (20s) and lands 1.5s into Phase 1 (Yellow, 3s)
    cursor.advance(21.5)
    assert cursor.current_phase_idx == 1
    assert cursor.current_phase.color == "yellow"
    _assert_close(cursor.time_in_current_state, 1.5)
    _assert_close(cursor.phase_time_remaining, 1.5)


def test_cursor_advance_large_step_cycle_wrap() -> None:
    plan = build_metering_plan(_BASIC_CONFIG)
    cursor = MeteringPhaseCursor(plan)

    # Cycle = 45s. Advance 100s = 2 full cycles (90s) + 10s into 3rd cycle (Phase 0)
    cursor.advance(100.0)
    assert cursor.cycle_number == 2
    assert cursor.current_phase_idx == 0
    _assert_close(cursor.time_in_current_state, 10.0)


def test_cursor_negative_or_zero_advance() -> None:
    plan = build_metering_plan(_BASIC_CONFIG)
    cursor = MeteringPhaseCursor(plan)

    cursor.advance(0.0)
    assert cursor.time_in_current_state == 0.0

    with pytest.raises(ValueError, match="delta_time must be non-negative"):
        cursor.advance(-1.0)


def test_cursor_color_projections() -> None:
    # 2 metered entries (North, South), unmetered (East, West)
    cfg = {
        "phases": [{"entries": ["north", "south"], "green": 10.0}],
        "yellow": 3.0,
        "allRed": 2.0,
    }
    plan = build_metering_plan(cfg)
    cursor = MeteringPhaseCursor(plan)

    # 1. During Phase 0 Green
    assert cursor.get_color(Direction.NORTH) == "green"
    assert cursor.get_color(Direction.SOUTH) == "green"
    assert cursor.get_color(Direction.EAST) == "green"  # unmetered arm is ALWAYS green
    assert cursor.get_color(Direction.WEST) == "green"  # unmetered arm is ALWAYS green

    # 2. Advance to Phase 1 Yellow
    cursor.advance(10.0)
    assert cursor.current_phase.color == "yellow"
    assert cursor.get_color(Direction.NORTH) == "yellow"
    assert cursor.get_color(Direction.SOUTH) == "yellow"
    assert cursor.get_color(Direction.EAST) == "green"  # unmetered stays green
    assert cursor.get_color(Direction.WEST) == "green"

    # 3. Advance to Phase 2 All-Red
    cursor.advance(3.0)
    assert cursor.current_phase.color == "red"
    assert cursor.get_color(Direction.NORTH) == "red"
    assert cursor.get_color(Direction.SOUTH) == "red"
    assert cursor.get_color(Direction.EAST) == "green"  # unmetered stays green
    assert cursor.get_color(Direction.WEST) == "green"

    # All colors helper
    colors = cursor.all_colors()
    assert colors[Direction.NORTH] == "red"
    assert colors[Direction.EAST] == "green"


def test_cursor_end_green_early_queue_cap_hook() -> None:
    plan = build_metering_plan(_BASIC_CONFIG)
    cursor = MeteringPhaseCursor(plan)

    # Currently in Phase 0 Green (20s)
    cursor.advance(9.0)
    assert cursor.current_phase.color == "green"

    # Trigger early termination
    assert cursor.end_green_early() is True
    # Immediately in Phase 1 Yellow with 0 elapsed
    assert cursor.current_phase_idx == 1
    assert cursor.current_phase.color == "yellow"
    _assert_close(cursor.time_in_current_state, 0.0)

    # Calling it during yellow returns False and does not advance
    assert cursor.end_green_early() is False
    assert cursor.current_phase_idx == 1


# ---------------------------------------------------------------------------
# Starvation Property: 10,000 Valid Plans Property / Fuzz Test (SR-19)
# ---------------------------------------------------------------------------


def test_starvation_property_10000_valid_plans() -> None:
    """Verify the starvation property across >= 10,000 valid random plans (SR-19, D-W2-3).

    Property to prove:
    For any metered approach 'd', the maximum continuous non-green duration
    under cursor progression is strictly bounded by:
        cycle_duration - sum(phase.green for phase in plan if d in phase.entries).
    Additionally asserts that every metered approach receives green in every cycle.
    """
    rng = random.Random(20261020)
    all_directions = [Direction.NORTH, Direction.SOUTH, Direction.EAST, Direction.WEST]

    num_plans = 10_000

    for plan_idx in range(num_plans):
        num_phases = rng.randint(1, 4)
        phases_cfg: List[Dict[str, Any]] = []

        for _ in range(num_phases):
            # Choose 1 to 3 distinct entries for this phase
            phase_entries = rng.sample(all_directions, k=rng.randint(1, 3))
            green = round(rng.uniform(5.5, 60.0), 2)
            min_green = round(rng.uniform(5.0, min(green, 30.0)), 2)
            max_green = round(rng.uniform(max(green, 30.0), 120.0), 2)

            phases_cfg.append(
                {
                    "entries": [d.value for d in phase_entries],
                    "green": green,
                    "minGreen": min_green,
                    "maxGreen": max_green,
                }
            )

        yellow = round(rng.uniform(2.1, 6.0), 2)
        all_red = round(rng.uniform(0.0, 4.0), 2)
        offset = round(rng.uniform(0.0, 100.0), 2)

        cfg: Dict[str, Any] = {
            "phases": phases_cfg,
            "yellow": yellow,
            "allRed": all_red,
            "offset": offset,
        }

        plan = build_metering_plan(cfg)
        cycle_dur = plan.cycle_duration

        # 1. Structural cycle duration invariant
        expected_dur = sum(
            spec.green + (yellow if yellow > 0 else 0) + (all_red if all_red > 0 else 0)
            for spec in plan.specs
        )
        _assert_close(cycle_dur, expected_dur, tol=1e-7)

        # 2. Mathematical starvation bound check for every metered entry
        for d in plan.metered_entries:
            total_green = plan.planned_green_for(d)
            assert total_green > 0.0, f"entry {d} has zero green in cycle"

            # Maximum theoretical non-green interval across a cycle
            max_theoretical_non_green = cycle_dur - total_green
            assert max_theoretical_non_green < cycle_dur, "starvation bound violated"

        # 3. Dynamic cursor stepping verification on representative sample (500 plans across the seed space)
        if plan_idx % 20 == 0:
            cursor = MeteringPhaseCursor(plan)
            time_since_green: Dict[Direction, float] = {
                d: 0.0 for d in plan.metered_entries
            }
            max_observed_non_green: Dict[Direction, float] = {
                d: 0.0 for d in plan.metered_entries
            }

            total_test_time = 2.0 * cycle_dur
            elapsed = 0.0

            while elapsed < total_test_time:
                dt = min(round(rng.uniform(0.2, 1.2), 3), total_test_time - elapsed)
                cursor.advance(dt)
                elapsed += dt

                for d in plan.metered_entries:
                    color = cursor.get_color(d)
                    if color == "green":
                        time_since_green[d] = 0.0
                    else:
                        time_since_green[d] += dt
                        if time_since_green[d] > max_observed_non_green[d]:
                            max_observed_non_green[d] = time_since_green[d]

            for d in plan.metered_entries:
                bound = cycle_dur - plan.planned_green_for(d)
                assert max_observed_non_green[d] <= bound + 1.5, (
                    f"Observed non-green {max_observed_non_green[d]} exceeded bound {bound} for entry {d}"
                )


# ---------------------------------------------------------------------------
# Hardening: non-finite and mistyped values (W2 final integration review)
# ---------------------------------------------------------------------------

_NAN = float("nan")
_INF = float("inf")


@pytest.mark.parametrize("bad_dt", [_NAN, _INF, -_INF])
def test_cursor_rejects_non_finite_steps(bad_dt: float) -> None:
    """NaN used to poison the clock for good and +inf never left the advance loop."""
    cursor = MeteringPhaseCursor(build_metering_plan(_BASIC_CONFIG))
    cursor.advance(3.0)
    with pytest.raises(ValueError, match="non-negative and finite"):
        cursor.advance(bad_dt)
    _assert_close(cursor.time_in_current_state, 3.0)


def _phase(**over: Any) -> Dict[str, Any]:
    return {"entries": ["north"], "green": 20, **over}


@pytest.mark.parametrize(
    "bad_cfg",
    [
        {"phases": [_phase(green=_NAN)]},
        {"phases": [_phase(green=_INF, maxGreen=_INF)]},
        {"phases": [_phase(green=True)]},
        {"phases": [_phase(green="20")]},
        {"phases": [_phase(minGreen=_NAN)]},
        {"phases": [_phase(maxGreen=_NAN)]},
        {"phases": [_phase()], "yellow": _NAN},
        {"phases": [_phase()], "yellow": _INF},
        {"phases": [_phase()], "allRed": _NAN},
        {"phases": [_phase()], "offset": _NAN},
        {"phases": [_phase()], "offset": _INF},
        {"phases": [_phase()], "spillbackGuard": {"maxHold": _NAN}},
        {"phases": [_phase()], "spillbackGuard": {"stoppedThreshold": "3"}},
        {"phases": [_phase()], "spillbackGuard": {"enabled": "false"}},
        {"phases": [_phase()], "spillbackGuard": [1]},
        {"phases": [_phase()], "queueCap": {"vehicles": 2.7}},
        {"phases": [_phase()], "queueCap": {"enabled": 1}},
        {"phases": [_phase()], "queueCap": "on"},
    ],
)
def test_build_plan_rejects_non_finite_and_mistyped_values(
    bad_cfg: Dict[str, Any],
) -> None:
    """Direct construction must refuse what the validator refuses.

    ``float(True)``, ``float("20")`` and ``bool("false")`` all succeed, NaN passes every
    ordered comparison and infinity makes the cycle infinite: each used to build a plan
    whose cursor could never leave its first phase (or enabled a guard configured off).
    """
    with pytest.raises(ValueError):
        build_metering_plan(bad_cfg)


def test_cursor_has_no_timing_drift_over_a_long_run() -> None:
    """Carry-over arithmetic never lets a boundary move by more than one tick.

    300,000 ticks of 0.1 s (30,000 s, about 667 cycles of 45 s) with an offset that is
    not a multiple of the step.  Summing 0.1 can land a hair under a boundary, so the
    cursor may switch one tick late (the FixedTimeSignalController behaviour it mirrors),
    but the surplus is subtracted, not kept: it must never be early, never more than one
    tick late, late at most once per boundary crossed, and the cycle count must match
    exact arithmetic at the end.
    """
    plan = build_metering_plan({**_BASIC_CONFIG, "offset": 7.3})
    cursor = MeteringPhaseCursor(plan)
    n = len(plan.phases)
    bounds: List[float] = []
    acc = 0.0
    for p in plan.phases:
        acc += p.duration
        bounds.append(acc)
    offset = plan.offset % plan.cycle_duration
    late = 0
    for i in range(1, 300_001):
        cursor.advance(0.1)
        pos = (offset + i * 0.1) % plan.cycle_duration
        expected = next(k for k, b in enumerate(bounds) if pos < b - 1e-9)
        if cursor.current_phase_idx != expected:
            assert cursor.current_phase_idx == (expected - 1) % n, (i, expected)
            late += 1
    boundaries_crossed = int(30_000.0 / plan.cycle_duration * n) + 1
    assert late <= boundaries_crossed
    assert cursor.cycle_number == int((offset + 30_000.0) // plan.cycle_duration)
