"""Tests for entry metering configuration validation and fuzzing (W2 S6).

Covers all 16 stable metering.* error codes (D-W2-8, Plan §5.2), bounds checks (§5.3),
integration with semantic_config_errors and validate_scenario, and a seeded
10,000-plan fuzz test verifying no unhandled crashes and valid code reporting.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List

import pytest

from src.controllers.entry_metering import (
    METERING_ERROR_CODES,
    MeteringValidationIssue,
    validate_entry_metering,
)
from src.core.enums import Direction
from src.scenario.config_validation import (
    _entry_control_errors,
    semantic_config_errors,
)
from src.scenario.documents import parse_scenario, validate_scenario


def _valid_base_config() -> Dict[str, Any]:
    return {
        "simulation": {
            "duration": 120.0,
            "timeStep": 0.1,
            "warmupTime": 10.0,
            "randomSeed": 42,
        },
        "geometry": {
            "intersectionType": "roundabout",
            "arms": ["north", "south", "east", "west"],
        },
        "roads": {
            "approachLength": 200.0,
            "laneWidth": 3.5,
            "speedLimit": 13.89,
            "lanesPerApproach": 2,
            "approaches": [
                {"direction": "north", "lanes": 2, "length": 200.0},
                {"direction": "south", "lanes": 2, "length": 200.0},
                {"direction": "east", "lanes": 2, "length": 200.0},
                {"direction": "west", "lanes": 2, "length": 200.0},
            ],
        },
        "traffic": {
            "arrivalRate": 0.5,
            "arrivalDistribution": "poisson",
            "totalVehicles": 200,
            "directionalSplit": {
                "north": 0.25,
                "south": 0.25,
                "east": 0.25,
                "west": 0.25,
            },
            "turnProbabilities": {"left": 0.2, "straight": 0.6, "right": 0.2},
        },
        "controller": {
            "innerRadius": 10.0,
            "outerRadius": 20.0,
            "criticalGap": 4.0,
            "followUpTime": 2.5,
            "entryControl": "metered_entry",
            "entryMetering": {
                "phases": [
                    {
                        "entries": ["north", "south"],
                        "green": 20.0,
                        "minGreen": 8.0,
                        "maxGreen": 40.0,
                    },
                    {
                        "entries": ["east", "west"],
                        "green": 20.0,
                        "minGreen": 8.0,
                        "maxGreen": 40.0,
                    },
                ],
                "yellow": 3.0,
                "allRed": 2.0,
                "offset": 0.0,
                "spillbackGuard": {
                    "enabled": True,
                    "stoppedThreshold": 2,
                    "maxHold": 10.0,
                },
                "queueCap": {
                    "enabled": True,
                    "vehicles": 8,
                },
            },
        },
    }


def _codes(issues: List[MeteringValidationIssue]) -> List[str]:
    return [issue.code for issue in issues]


# ---------------------------------------------------------------------------
# 1. Validation of all 16 stable metering.* codes
# ---------------------------------------------------------------------------


def test_code_mode_unknown() -> None:
    cfg = _valid_base_config()
    cfg["controller"]["entryControl"] = "unsupported_mode"
    issues = validate_entry_metering(cfg)
    assert "metering.mode_unknown" in _codes(issues)


def test_code_not_roundabout() -> None:
    cfg = _valid_base_config()
    cfg["geometry"]["intersectionType"] = "fixed_time_signal"
    issues = validate_entry_metering(cfg)
    assert "metering.not_roundabout" in _codes(issues)


def test_code_adaptive_conflict() -> None:
    cfg = _valid_base_config()
    cfg["controller"]["signalControl"] = "adaptive"
    issues = validate_entry_metering(cfg)
    assert "metering.adaptive_conflict" in _codes(issues)


def test_code_no_phases() -> None:
    cfg = _valid_base_config()
    cfg["controller"]["entryMetering"]["phases"] = []
    issues = validate_entry_metering(cfg)
    assert "metering.no_phases" in _codes(issues)

    del cfg["controller"]["entryMetering"]["phases"]
    issues2 = validate_entry_metering(cfg)
    assert "metering.no_phases" in _codes(issues2)


def test_code_empty_phase() -> None:
    cfg = _valid_base_config()
    cfg["controller"]["entryMetering"]["phases"][0]["entries"] = []
    issues = validate_entry_metering(cfg)
    assert "metering.empty_phase" in _codes(issues)


def test_code_unknown_entry() -> None:
    cfg = _valid_base_config()
    cfg["controller"]["entryMetering"]["phases"][0]["entries"] = ["northwest"]
    issues = validate_entry_metering(cfg)
    assert "metering.unknown_entry" in _codes(issues)


def test_code_missing_arm() -> None:
    cfg = _valid_base_config()
    cfg["geometry"]["arms"] = ["north", "south", "east"]
    cfg["roads"]["approaches"] = [
        {"direction": "north", "lanes": 2, "length": 200.0},
        {"direction": "south", "lanes": 2, "length": 200.0},
        {"direction": "east", "lanes": 2, "length": 200.0},
    ]
    # Phase 1 asks for west, which is not present
    cfg["controller"]["entryMetering"]["phases"][1]["entries"] = ["east", "west"]
    issues = validate_entry_metering(cfg)
    assert "metering.missing_arm" in _codes(issues)


def test_code_duplicate_in_phase() -> None:
    cfg = _valid_base_config()
    cfg["controller"]["entryMetering"]["phases"][0]["entries"] = ["north", "north"]
    issues = validate_entry_metering(cfg)
    assert "metering.duplicate_in_phase" in _codes(issues)


def test_code_zero_green() -> None:
    cfg = _valid_base_config()
    cfg["controller"]["entryMetering"]["phases"][0]["green"] = 0.0
    issues = validate_entry_metering(cfg)
    assert "metering.zero_green" in _codes(issues)

    cfg["controller"]["entryMetering"]["phases"][0]["green"] = -5.0
    issues2 = validate_entry_metering(cfg)
    assert "metering.zero_green" in _codes(issues2)


def test_code_green_below_min() -> None:
    cfg = _valid_base_config()
    cfg["controller"]["entryMetering"]["phases"][0]["green"] = 8.0
    cfg["controller"]["entryMetering"]["phases"][0]["minGreen"] = 12.0
    issues = validate_entry_metering(cfg)
    assert "metering.green_below_min" in _codes(issues)


def test_code_green_above_max() -> None:
    cfg = _valid_base_config()
    cfg["controller"]["entryMetering"]["phases"][0]["green"] = 50.0
    cfg["controller"]["entryMetering"]["phases"][0]["maxGreen"] = 30.0
    issues = validate_entry_metering(cfg)
    assert "metering.green_above_max" in _codes(issues)


def test_code_min_above_max() -> None:
    cfg = _valid_base_config()
    cfg["controller"]["entryMetering"]["phases"][0]["minGreen"] = 45.0
    cfg["controller"]["entryMetering"]["phases"][0]["maxGreen"] = 30.0
    issues = validate_entry_metering(cfg)
    assert "metering.min_above_max" in _codes(issues)


@pytest.mark.parametrize(
    "mutator",
    [
        lambda c: c["controller"]["entryMetering"]["phases"][0].update(
            green=5.0
        ),  # bound: 5 < green <= 120
        lambda c: c["controller"]["entryMetering"]["phases"][0].update(green=125.0),
        lambda c: c["controller"]["entryMetering"]["phases"][0].update(
            minGreen=4.0
        ),  # bound: 5 <= minGreen <= 60
        lambda c: c["controller"]["entryMetering"]["phases"][0].update(minGreen=65.0),
        lambda c: c["controller"]["entryMetering"]["phases"][0].update(
            maxGreen=9.0
        ),  # bound: 10 <= maxGreen <= 180
        lambda c: c["controller"]["entryMetering"]["phases"][0].update(maxGreen=185.0),
        lambda c: c["controller"]["entryMetering"].update(
            yellow=2.0
        ),  # bound: 2 < yellow <= 8
        lambda c: c["controller"]["entryMetering"].update(yellow=8.5),
        lambda c: c["controller"]["entryMetering"].update(
            allRed=-0.5
        ),  # bound: 0 <= allRed <= 5
        lambda c: c["controller"]["entryMetering"].update(allRed=5.5),
        lambda c: c["controller"]["entryMetering"].update(
            offset=-1.0
        ),  # bound: offset >= 0
        lambda c: c["controller"]["entryMetering"]["spillbackGuard"].update(
            stoppedThreshold=0
        ),  # 1..20
        lambda c: c["controller"]["entryMetering"]["spillbackGuard"].update(
            stoppedThreshold=21
        ),
        lambda c: c["controller"]["entryMetering"]["spillbackGuard"].update(
            maxHold=-1.0
        ),  # 0..60
        lambda c: c["controller"]["entryMetering"]["spillbackGuard"].update(
            maxHold=65.0
        ),
        lambda c: c["controller"]["entryMetering"]["queueCap"].update(
            vehicles=0
        ),  # 1..50
        lambda c: c["controller"]["entryMetering"]["queueCap"].update(vehicles=55),
        lambda c: c["controller"]["entryMetering"].update(
            phases=[
                {"entries": ["north"], "green": 20.0},
                {"entries": ["south"], "green": 20.0},
                {"entries": ["east"], "green": 20.0},
                {"entries": ["west"], "green": 20.0},
                {"entries": ["north"], "green": 20.0},
            ]
        ),  # max 4 phases
    ],
)
def test_code_out_of_bounds(mutator: Any) -> None:
    cfg = _valid_base_config()
    mutator(cfg)
    issues = validate_entry_metering(cfg)
    assert "metering.out_of_bounds" in _codes(issues)


def test_code_offset_beyond_cycle() -> None:
    cfg = _valid_base_config()
    # cycle duration = 20 + 3 + 2 + 20 + 3 + 2 = 50 s
    cfg["controller"]["entryMetering"]["offset"] = 50.0
    issues = validate_entry_metering(cfg)
    assert "metering.offset_beyond_cycle" in _codes(issues)

    cfg["controller"]["entryMetering"]["offset"] = 75.0
    issues2 = validate_entry_metering(cfg)
    assert "metering.offset_beyond_cycle" in _codes(issues2)


def test_code_unknown_field() -> None:
    cfg = _valid_base_config()
    cfg["controller"]["entryMetering"]["bogusField"] = 123
    issues = validate_entry_metering(cfg)
    assert "metering.unknown_field" in _codes(issues)

    cfg2 = _valid_base_config()
    cfg2["controller"]["entryMetering"]["phases"][0]["bogusPhaseField"] = 456
    issues2 = validate_entry_metering(cfg2)
    assert "metering.unknown_field" in _codes(issues2)

    cfg3 = _valid_base_config()
    cfg3["controller"]["entryMetering"]["spillbackGuard"]["bogusGuard"] = True
    issues3 = validate_entry_metering(cfg3)
    assert "metering.unknown_field" in _codes(issues3)

    cfg4 = _valid_base_config()
    cfg4["controller"]["entryMetering"]["queueCap"]["bogusCap"] = "x"
    issues4 = validate_entry_metering(cfg4)
    assert "metering.unknown_field" in _codes(issues4)


@pytest.mark.parametrize(
    "mutator",
    [
        lambda c: c["controller"]["entryMetering"]["phases"][0].update(
            green=float("nan")
        ),
        lambda c: c["controller"]["entryMetering"]["phases"][0].update(
            green=float("inf")
        ),
        lambda c: c["controller"]["entryMetering"]["phases"][0].update(
            green="not_a_number"
        ),
        lambda c: c["controller"]["entryMetering"].update(yellow="fast"),
        lambda c: c["controller"]["entryMetering"].update(allRed=float("nan")),
        lambda c: c["controller"]["entryMetering"].update(
            offset=True
        ),  # boolean is not a number
        lambda c: c["controller"]["entryMetering"]["spillbackGuard"].update(
            stoppedThreshold=float("nan")
        ),
        lambda c: c["controller"]["entryMetering"]["queueCap"].update(
            vehicles=float("inf")
        ),
    ],
)
def test_code_not_a_number(mutator: Any) -> None:
    cfg = _valid_base_config()
    mutator(cfg)
    issues = validate_entry_metering(cfg)
    assert "metering.not_a_number" in _codes(issues)


# ---------------------------------------------------------------------------
# 2. Stable error format and semantic_config_errors integration
# ---------------------------------------------------------------------------


def test_issue_messages_end_in_code() -> None:
    cfg = _valid_base_config()
    cfg["controller"]["entryMetering"]["phases"][0]["green"] = 0.0
    formatted_errors = _entry_control_errors(cfg)
    assert len(formatted_errors) > 0
    for err in formatted_errors:
        assert err.endswith("(metering.zero_green)") or any(
            err.endswith(f"({code})") for code in METERING_ERROR_CODES
        )


def test_semantic_config_errors_includes_metering_issues() -> None:
    cfg = _valid_base_config()
    cfg["controller"]["entryMetering"]["phases"][0]["green"] = -10.0
    errors = semantic_config_errors(cfg)
    assert any("metering.zero_green" in e for e in errors)


def test_valid_config_produces_zero_errors() -> None:
    cfg = _valid_base_config()
    assert validate_entry_metering(cfg) == []
    assert _entry_control_errors(cfg) == []
    assert semantic_config_errors(cfg) == []


# ---------------------------------------------------------------------------
# 3. validate_scenario integration
# ---------------------------------------------------------------------------


def _valid_scenario_document_dict() -> Dict[str, Any]:
    return {
        "format": "urbanflow-scenario",
        "version": 1,
        "name": "Metered Roundabout Test",
        "description": "Valid metered roundabout",
        "junction": {"type": "roundabout"},
        "approaches": {
            "north": {"lanes": 2, "length": 200.0, "vehiclesPerHour": 400.0},
            "south": {"lanes": 2, "length": 200.0, "vehiclesPerHour": 400.0},
            "east": {"lanes": 2, "length": 200.0, "vehiclesPerHour": 400.0},
            "west": {"lanes": 2, "length": 200.0, "vehiclesPerHour": 400.0},
        },
        "roads": {"laneWidth": 3.5, "speedLimit": 13.89, "laneChanging": True},
        "roundabout": {
            "innerRadius": 10.0,
            "outerRadius": 20.0,
            "criticalGap": 4.0,
            "followUpTime": 2.5,
            "entryControl": "metered_entry",
            "entryMetering": {
                "phases": [
                    {
                        "entries": ["north", "south"],
                        "green": 20.0,
                        "minGreen": 8.0,
                        "maxGreen": 40.0,
                    },
                    {
                        "entries": ["east", "west"],
                        "green": 20.0,
                        "minGreen": 8.0,
                        "maxGreen": 40.0,
                    },
                ],
                "yellow": 3.0,
                "allRed": 2.0,
                "offset": 0.0,
                "spillbackGuard": {
                    "enabled": True,
                    "stoppedThreshold": 2,
                    "maxHold": 10.0,
                },
                "queueCap": {"enabled": True, "vehicles": 8},
            },
        },
        "simulation": {"duration": 120.0, "warmup": 10.0, "seed": 42},
    }


def test_validate_scenario_with_valid_metering() -> None:
    doc_dict = _valid_scenario_document_dict()
    result = validate_scenario(doc_dict, ["roundabout"])
    assert result["valid"] is True, result["errors"]


def test_validate_scenario_with_invalid_metering_returns_error_code() -> None:
    doc_dict = _valid_scenario_document_dict()
    # green time 0 is invalid
    doc_dict["roundabout"]["entryMetering"]["phases"][0]["green"] = 0.0
    parsed, _ = parse_scenario(doc_dict)
    # Even if parsed or rejected by Pydantic, validate_scenario reports it
    result = validate_scenario(doc_dict, ["roundabout"])
    assert result["valid"] is False
    assert any("metering." in e or "green" in e for e in result["errors"])


# ---------------------------------------------------------------------------
# 4. Fuzz test of >= 10,000 random plans (seeded random.Random)
# ---------------------------------------------------------------------------


def test_fuzz_entry_metering_validator_10000_plans() -> None:
    """Fuzz the entry metering validator with >= 10,000 diverse random configurations.

    Guarantees:
    1. Validator never raises an unhandled exception or crashes on arbitrary structures.
    2. Every emitted issue has a recognised code in METERING_ERROR_CODES.
    3. Fully valid generated plans return 0 issues.
    """
    rng = random.Random(42)
    directions = ["north", "south", "east", "west", "northwest", "southeast", "up", ""]

    iterations = 10_000

    for _ in range(iterations):
        # Decide plan structure
        scenario_shape = rng.choice(["dict", "raw_metering", "garbage_type"])
        if scenario_shape == "garbage_type":
            bad_input = rng.choice([None, 42, "string", [], True, 3.14])
            issues = validate_entry_metering(bad_input)  # type: ignore[arg-type]
            assert isinstance(issues, list)
            for issue in issues:
                assert issue.code in METERING_ERROR_CODES
            continue

        num_phases = rng.randint(0, 6)
        phases: List[Any] = []
        for _ in range(num_phases):
            phase_type = rng.choice(["dict", "non_dict"])
            if phase_type == "non_dict":
                phases.append(rng.choice(["invalid_phase", 123, None, []]))
                continue

            num_entries = rng.randint(0, 5)
            entries = [rng.choice(directions) for _ in range(num_entries)]

            green = rng.choice(
                [
                    rng.uniform(-10.0, 150.0),
                    0.0,
                    5.0,
                    20.0,
                    120.0,
                    float("nan"),
                    float("inf"),
                    "not_num",
                    None,
                ]
            )

            p_dict: Dict[str, Any] = {"entries": entries}
            if green is not None:
                p_dict["green"] = green

            if rng.random() < 0.5:
                p_dict["minGreen"] = rng.choice(
                    [rng.uniform(0.0, 80.0), float("nan"), "str", None]
                )
            if rng.random() < 0.5:
                p_dict["maxGreen"] = rng.choice(
                    [rng.uniform(5.0, 200.0), float("nan"), "str", None]
                )
            if rng.random() < 0.2:
                p_dict["unknown_phase_field"] = rng.randint(1, 100)

            phases.append(p_dict)

        yellow = rng.choice([rng.uniform(-1.0, 12.0), 3.0, float("nan"), "y", None])
        all_red = rng.choice([rng.uniform(-1.0, 8.0), 2.0, float("inf"), None])
        offset = rng.choice([rng.uniform(-5.0, 100.0), 0.0, float("nan"), None])

        metering_dict: Dict[str, Any] = {"phases": phases}
        if yellow is not None:
            metering_dict["yellow"] = yellow
        if all_red is not None:
            metering_dict["allRed"] = all_red
        if offset is not None:
            metering_dict["offset"] = offset

        # Spillback guard
        if rng.random() < 0.5:
            if rng.random() < 0.1:
                metering_dict["spillbackGuard"] = "invalid_sg"
            else:
                sg: Dict[str, Any] = {}
                if rng.random() < 0.8:
                    sg["enabled"] = rng.choice([True, False, "not_bool"])
                if rng.random() < 0.8:
                    sg["stoppedThreshold"] = rng.choice(
                        [rng.randint(-2, 25), 2.5, float("nan"), "bad"]
                    )
                if rng.random() < 0.8:
                    sg["maxHold"] = rng.choice(
                        [rng.uniform(-5.0, 70.0), float("inf"), "bad"]
                    )
                if rng.random() < 0.2:
                    sg["unexpected"] = 1
                metering_dict["spillbackGuard"] = sg

        # Queue cap
        if rng.random() < 0.5:
            if rng.random() < 0.1:
                metering_dict["queueCap"] = 12345
            else:
                qc: Dict[str, Any] = {}
                if rng.random() < 0.8:
                    qc["enabled"] = rng.choice([True, False, 1])
                if rng.random() < 0.8:
                    qc["vehicles"] = rng.choice(
                        [rng.randint(-2, 60), 3.5, float("nan"), "bad"]
                    )
                if rng.random() < 0.2:
                    qc["unexpected"] = 2
                metering_dict["queueCap"] = qc

        if rng.random() < 0.2:
            metering_dict["unknown_top_field"] = "bad"

        if scenario_shape == "raw_metering":
            test_config = metering_dict
        else:
            intersection_type = rng.choice(["roundabout", "fixed_time_signal", None])
            signal_control = rng.choice(["fixed_time", "adaptive", None])
            entry_control = rng.choice(["metered_entry", "none", "unknown", None])
            test_config = {
                "geometry": {"intersectionType": intersection_type},
                "controller": {
                    "entryControl": entry_control,
                    "entryMetering": metering_dict,
                },
            }
            if signal_control is not None:
                test_config["controller"]["signalControl"] = signal_control

        # Run validator: must NOT crash
        issues = validate_entry_metering(test_config)
        assert isinstance(issues, list)
        for issue in issues:
            assert isinstance(issue, MeteringValidationIssue)
            assert issue.code in METERING_ERROR_CODES
            assert isinstance(issue.message, str)
            assert isinstance(issue.path, str)


def test_fuzz_known_valid_plans_never_emit_errors() -> None:
    """Generate 500 valid permutations and verify none return any issues."""
    rng = random.Random(1337)
    valid_entries = [
        [Direction.NORTH, Direction.SOUTH],
        [Direction.EAST, Direction.WEST],
        [Direction.NORTH],
        [Direction.SOUTH],
    ]

    for _ in range(500):
        k = rng.randint(1, 4)
        chosen_entries = valid_entries[:k]
        phases = []
        for e in chosen_entries:
            green = round(rng.uniform(6.0, 119.0), 1)
            min_green = round(rng.uniform(5.0, min(green, 60.0)), 1)
            max_green = round(rng.uniform(max(green, 10.0), 180.0), 1)
            phases.append(
                {
                    "entries": [d.value for d in e],
                    "green": green,
                    "minGreen": min_green,
                    "maxGreen": max_green,
                }
            )

        yellow = round(rng.uniform(2.1, 7.9), 1)
        all_red = round(rng.uniform(0.0, 5.0), 1)
        cycle_len = sum(p["green"] + yellow + all_red for p in phases)
        offset = round(rng.uniform(0.0, cycle_len - 0.1), 1)

        cfg: Dict[str, Any] = {
            "geometry": {"intersectionType": "roundabout"},
            "controller": {
                "entryControl": "metered_entry",
                "entryMetering": {
                    "phases": phases,
                    "yellow": yellow,
                    "allRed": all_red,
                    "offset": offset,
                    "spillbackGuard": {
                        "enabled": rng.choice([True, False]),
                        "stoppedThreshold": rng.randint(1, 20),
                        "maxHold": round(rng.uniform(0.0, 60.0), 1),
                    },
                    "queueCap": {
                        "enabled": rng.choice([True, False]),
                        "vehicles": rng.randint(1, 50),
                    },
                },
            },
        }

        issues = validate_entry_metering(cfg)
        assert issues == [], f"Unexpected issues on valid config: {issues}"
