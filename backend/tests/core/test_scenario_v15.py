"""Real-world junction scenarios (V1.5): document fields, compilation,
validation and compatibility with V1.4 documents."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from src.core.scenario import (
    compile_scenario,
    parse_scenario,
    scenario_fingerprint,
    validate_scenario,
)

PRESETS = json.loads(
    (
        Path(__file__).resolve().parents[3]
        / "frontend"
        / "src"
        / "scenario"
        / "presets.json"
    ).read_text(encoding="utf-8")
)["presets"]

ALL = ["fixed_time", "adaptive", "roundabout"]

# Fingerprints and compiled configurations of every preset, recorded by
# running the V1.4 code (commit dcf7461) on them. V1.5 only adds optional
# fields, so a document that does not use them must compile and fingerprint
# exactly as it did.
V14_PRESETS = {
    "calibrated-baseline": ("12a4e686edffa0db", "c84904830c2eff0b"),
    "typical-urban": ("d2a4a7ea3cb097ff", "62ef4577903ba933"),
    "heavy-commuter": ("90318ac036de16a3", "54d852af48233b8f"),
    "bus-corridor": ("05a9fe58485aca5b", "828c01f13c4f5b24"),
    "mixed-urban": ("cc51df691d48d9d0", "f0f085cc1e7a4e95"),
    "motorcycle-heavy": ("de34c6b769aca36d", "227e879066ffeb49"),
}


def arm(
    lanes: int = 1,
    vph: float = 300,
    turning: Optional[Dict[str, float]] = None,
    **extra: Any,
) -> Dict[str, Any]:
    item: Dict[str, Any] = {
        "lanes": lanes,
        "vehiclesPerHour": vph,
        "turning": turning or {"left": 0.25, "straight": 0.5, "right": 0.25},
    }
    item.update(extra)
    return item


def t_junction() -> Dict[str, Any]:
    """A T-junction: no north arm, east-west main road, south stem."""
    return {
        "junction": {"type": "fixed_time_signal"},
        "approaches": {
            "north": None,
            "south": arm(1, 300, {"left": 0.5, "straight": 0, "right": 0.5}),
            "east": arm(1, 450, {"left": 0.3, "straight": 0.7, "right": 0}),
            "west": arm(1, 450, {"left": 0, "straight": 0.7, "right": 0.3}),
        },
        "simulation": {"duration": 120, "warmup": 20, "seed": 4},
    }


def four_arm(**overrides: Dict[str, Any]) -> Dict[str, Any]:
    doc: Dict[str, Any] = {
        "junction": {"type": "fixed_time_signal"},
        "approaches": {d: arm() for d in ("north", "south", "east", "west")},
        "simulation": {"duration": 120, "warmup": 20, "seed": 4},
    }
    for d, change in overrides.items():
        doc["approaches"][d].update(change)
    return doc


def errors_of(doc: Dict[str, Any], strategies: List[str] = ALL) -> List[str]:
    result = validate_scenario(doc, strategies)
    assert not result["valid"], "expected the scenario to be rejected"
    return list(result["errors"])


# -- compatibility ------------------------------------------------------------------


@pytest.mark.parametrize("preset", PRESETS, ids=lambda p: p["id"])
def test_v14_documents_compile_and_fingerprint_exactly_as_before(preset) -> None:
    document, errors = parse_scenario(preset["scenario"])
    assert document is not None, errors
    configs = {s: compile_scenario(document, s) for s in ALL}
    digest = hashlib.sha256(json.dumps(configs, sort_keys=True).encode()).hexdigest()
    assert (scenario_fingerprint(document), digest[:16]) == V14_PRESETS[preset["id"]]


def test_unset_v15_fields_do_not_change_the_fingerprint() -> None:
    plain, _ = parse_scenario(four_arm())
    explicit_doc = four_arm(
        north={"bearing": None, "laneWidth": None},
    )
    explicit_doc["approaches"]["north"]["turning"]["uturn"] = None
    explicit, _ = parse_scenario(explicit_doc)
    assert plain is not None and explicit is not None
    assert scenario_fingerprint(plain) == scenario_fingerprint(explicit)
    bent, _ = parse_scenario(four_arm(north={"bearing": 10.0}))
    assert bent is not None
    assert scenario_fingerprint(bent) != scenario_fingerprint(plain)


# -- compilation ------------------------------------------------------------------


def test_a_three_arm_junction_compiles_without_the_missing_arm() -> None:
    document, errors = parse_scenario(t_junction())
    assert document is not None, errors
    for strategy in ALL:
        config = compile_scenario(document, strategy)
        assert config["geometry"]["arms"] == ["south", "east", "west"]
        assert config["traffic"]["directionalSplit"]["north"] == 0.0
        assert sum(config["traffic"]["directionalSplit"].values()) == pytest.approx(1)
        assert {i["direction"] for i in config["roads"]["approaches"]} == {
            "south",
            "east",
            "west",
        }


def test_geometry_fields_compile_into_the_engine_contract() -> None:
    doc = four_arm(north={"bearing": 15.0, "laneWidth": 3.2})
    document, _ = parse_scenario(doc)
    assert document is not None
    config = compile_scenario(document, "fixed_time")
    north = next(i for i in config["roads"]["approaches"] if i["direction"] == "north")
    assert north["bearing"] == 15.0 and north["laneWidth"] == 3.2
    south = next(i for i in config["roads"]["approaches"] if i["direction"] == "south")
    assert "bearing" not in south and "laneWidth" not in south


def test_compilation_is_deterministic() -> None:
    document, _ = parse_scenario(t_junction())
    assert document is not None
    for strategy in ALL:
        assert compile_scenario(document, strategy) == compile_scenario(
            document, strategy
        )


def test_a_real_world_document_round_trips_through_export() -> None:
    doc = t_junction()
    doc["approaches"]["east"]["bearing"] = 80.0
    doc["approaches"]["west"]["laneWidth"] = 3.3
    document, _ = parse_scenario(doc)
    assert document is not None
    exported = json.loads(json.dumps(document.model_dump()))
    again, errors = parse_scenario(exported)
    assert again is not None, errors
    assert scenario_fingerprint(again) == scenario_fingerprint(document)
    assert compile_scenario(again, "roundabout") == compile_scenario(
        document, "roundabout"
    )


def test_resolved_design_reports_the_laid_out_geometry() -> None:
    doc = four_arm(north={"bearing": 20.0})
    result = validate_scenario(doc, ["fixed_time", "roundabout"])
    assert result["valid"], result["errors"]
    signal = result["design"]["fixed_time"]["geometry"]
    assert signal["north"]["bearing"] == 20.0
    assert (
        signal["north"]["stopLineDistance"] > signal["south"]["stopLineDistance"] - 1e-9
    )
    ring = result["design"]["roundabout"]["geometry"]
    assert ring["north"]["stopLineDistance"] == pytest.approx(24.0)


# -- valid real-world scenarios -----------------------------------------------------


def test_a_t_junction_is_valid_for_every_strategy() -> None:
    result = validate_scenario(t_junction(), ALL)
    assert result["valid"], result["errors"]
    assert any("Real-world geometry" in w for w in result["warnings"])


def test_an_asymmetric_skewed_four_arm_junction_is_valid() -> None:
    doc = four_arm(
        north={"lanes": 2, "vehiclesPerHour": 600, "bearing": 20.0},
        south={"lanes": 2, "vehiclesPerHour": 500, "bearing": 190.0, "length": 320},
        east={"bearing": 75.0, "laneWidth": 3.2, "length": 150},
        west={"bearing": 255.0},
    )
    doc["vehicles"] = {"mix": {"car": 0.8, "bus": 0.1, "truck": 0.1}}
    result = validate_scenario(doc, ALL)
    assert result["valid"], result["errors"]


def test_a_uturn_is_served_by_a_roundabout() -> None:
    doc = four_arm(
        north={
            "turning": {"left": 0.2, "straight": 0.5, "right": 0.2, "uturn": 0.1},
            "roundaboutLaneUse": [["uturn", "left", "straight", "right"]],
        }
    )
    result = validate_scenario(doc, ["roundabout"])
    assert result["valid"], result["errors"]
    rows = result["design"]["roundabout"]["ringAssignment"]["north"]
    assert {"movement": "uturn", "exitTo": "north"}.items() <= next(
        r for r in rows if r["movement"] == "uturn"
    ).items()


def test_a_uturn_at_a_wide_signal_is_valid() -> None:
    doc = four_arm(
        north={
            "lanes": 3,
            "laneWidth": 4.5,
            "turning": {"left": 0.2, "straight": 0.5, "right": 0.2, "uturn": 0.1},
            "laneUse": [["uturn", "left"], ["straight"], ["straight", "right"]],
        },
        south={"lanes": 3},
    )
    result = validate_scenario(doc, ["fixed_time", "adaptive"])
    assert result["valid"], result["errors"]


# -- rejected scenarios: what, where, why and what is valid -------------------------


def test_two_arms_are_rejected() -> None:
    doc = t_junction()
    doc["approaches"]["south"] = None
    errors = errors_of(doc)
    assert errors == [
        "approaches: 2 arm(s) given (east, west); a junction needs 3 or 4 arms. "
        "Two arms are a bend in one road, not a junction: give a three-arm "
        "(T or Y) or a four-arm junction"
    ]


def test_traffic_into_the_missing_arm_is_rejected() -> None:
    doc = t_junction()
    doc["approaches"]["south"]["turning"] = {"left": 0.4, "straight": 0.2, "right": 0.4}
    errors = errors_of(doc)
    assert any(
        "south approach has traffic turning straight, into a slot this junction "
        "has no arm in"
        in e
        and "go left/right" in e
        for e in errors
    )


def test_a_lane_marked_for_the_missing_arm_is_rejected() -> None:
    doc = t_junction()
    doc["approaches"]["south"]["laneUse"] = [["left", "straight", "right"]]
    errors = errors_of(doc, ["fixed_time"])
    assert any(
        "south approach's lane 1 allows straight, which would leave by the north "
        "slot, where this junction has no arm" in e
        for e in errors
    )


def test_a_stem_lane_left_without_a_movement_asks_for_lane_arrows() -> None:
    doc = t_junction()
    doc["approaches"]["south"]["lanes"] = 3
    errors = errors_of(doc, ["fixed_time"])
    assert any(
        "south approach's lane 2 has no movement under the default lane use" in e
        for e in errors
    )


def test_an_arm_out_of_its_slot_is_rejected() -> None:
    errors = errors_of(four_arm(east={"bearing": 140.0}))
    assert any("roads.approaches[east].bearing (140°)" in e for e in errors)


def test_a_uturn_from_a_narrow_signal_is_physically_impossible() -> None:
    doc = four_arm(
        north={
            "turning": {"left": 0.2, "straight": 0.5, "right": 0.2, "uturn": 0.1},
            "laneUse": [["uturn", "left", "straight", "right"]],
        }
    )
    errors = errors_of(doc, ["fixed_time"])
    assert any(
        "A U-turn from the north approach is not physically possible here" in e
        and "1.75 m radius" in e
        and "needs at least 6.4 m" in e
        and "Valid options: at least 4 lanes each way" in e
        for e in errors
    )


def test_a_uturn_needs_more_room_for_a_bus() -> None:
    doc = four_arm(
        north={
            "lanes": 4,
            "turning": {"left": 0.2, "straight": 0.5, "right": 0.2, "uturn": 0.1},
            "laneUse": [["uturn", "left"], ["straight"], ["straight"], ["right"]],
            "vehicleMix": {"car": 0.9, "bus": 0.1},
        },
        south={"lanes": 4},
    )
    errors = errors_of(doc, ["fixed_time"])
    assert any(
        "a bus needs at least 11.5 m" in e and "a vehicle mix without buses" in e
        for e in errors
    )


def test_a_uturn_may_only_start_from_lane_one_at_a_signal() -> None:
    doc = four_arm(
        north={
            "lanes": 4,
            "turning": {"left": 0.2, "straight": 0.5, "right": 0.2, "uturn": 0.1},
            "laneUse": [["left"], ["uturn", "straight"], ["straight"], ["right"]],
        },
        south={"lanes": 4},
    )
    errors = errors_of(doc, ["fixed_time"])
    assert any("may only start from lane 1" in e for e in errors)


def test_uturn_demand_needs_a_uturn_lane() -> None:
    doc = four_arm(
        north={"turning": {"left": 0.2, "straight": 0.5, "right": 0.2, "uturn": 0.1}}
    )
    errors = errors_of(doc)
    assert any("traffic turning uturn but no lane allows it" in e for e in errors)


def test_turning_shares_including_uturn_must_sum_to_one() -> None:
    doc = four_arm(
        north={
            "turning": {"left": 0.25, "straight": 0.5, "right": 0.25, "uturn": 0.1},
            "roundaboutLaneUse": [["uturn", "left", "straight", "right"]],
        }
    )
    errors = errors_of(doc, ["roundabout"])
    assert any("turnProbabilities must sum to 1.0" in e for e in errors)


def test_overlapping_roundabout_mouths_are_rejected_for_the_roundabout_only() -> None:
    doc = four_arm(
        north={"lanes": 3, "bearing": 25.0},
        east={"lanes": 3, "bearing": 72.0},
        south={"lanes": 3},
        west={"lanes": 3},
    )
    doc["roundabout"] = {"circulatingLanes": 2, "innerRadius": 10, "outerRadius": 18}
    result = validate_scenario(doc, ["fixed_time", "roundabout"])
    assert not result["valid"]
    overlap = [e for e in result["errors"] if "overlap where they meet the ring" in e]
    assert overlap and all(e.startswith("Roundabout: ") for e in overlap)


def test_engine_configs_describing_a_missing_arm_are_rejected() -> None:
    from src.core.config_validation import semantic_config_errors

    document, _ = parse_scenario(t_junction())
    assert document is not None
    config = compile_scenario(document, "fixed_time")
    broken = copy.deepcopy(config)
    broken["traffic"]["directionalSplit"] = {
        "north": 0.1,
        "south": 0.3,
        "east": 0.3,
        "west": 0.3,
    }
    assert any(
        "directionalSplit gives the north slot 0.1" in e
        for e in semantic_config_errors(broken)
    )
    no_split = copy.deepcopy(config)
    del no_split["traffic"]["directionalSplit"]
    assert any(
        "needs traffic.directionalSplit" in e for e in semantic_config_errors(no_split)
    )
    stray = copy.deepcopy(config)
    stray["roads"]["approaches"].append({"direction": "north", "lanes": 1})
    assert any(
        "roads.approaches describes the north approach" in e
        for e in semantic_config_errors(stray)
    )
