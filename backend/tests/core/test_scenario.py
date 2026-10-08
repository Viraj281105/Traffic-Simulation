"""V1.4 scenario documents (core/scenario.py) and lane-configuration validation."""

import copy
import json
from pathlib import Path
from typing import Any, Dict

import pytest

from src.core.config_validation import semantic_config_errors
from src.core.scenario import (
    STRATEGIES,
    compile_scenario,
    parse_scenario,
    scenario_fingerprint,
    validate_scenario,
)

PRESETS_PATH = (
    Path(__file__).resolve().parents[3]
    / "frontend"
    / "src"
    / "scenario"
    / "presets.json"
)


def _arm(lanes: int, vph: float, **extra: Any) -> Dict[str, Any]:
    return {
        "lanes": lanes,
        "vehiclesPerHour": vph,
        "turning": {"left": 0.2, "straight": 0.6, "right": 0.2},
        **extra,
    }


def _doc(**overrides: Any) -> Dict[str, Any]:
    doc: Dict[str, Any] = {
        "format": "urbanflow-scenario",
        "version": 1,
        "name": "Test",
        "junction": {"type": "fixed_time_signal"},
        "approaches": {
            "north": _arm(3, 900),
            "south": _arm(3, 400),
            "east": _arm(2, 300),
            "west": _arm(2, 300),
        },
        "vehicles": {"mix": {"car": 0.8, "bus": 0.1, "motorcycle": 0.1}},
        "roundabout": {"circulatingLanes": 2},
        "simulation": {"duration": 120, "warmup": 30, "seed": 7},
    }
    doc.update(overrides)
    return doc


def test_the_v14_success_criterion_scenario_is_valid_for_all_three_strategies() -> None:
    """A 3-lane road and a 2-lane road, mostly cars with buses and motorcycles,
    heavy traffic from the north, compared as fixed / adaptive / 2-lane ring."""
    result = validate_scenario(_doc(), list(STRATEGIES))
    assert result["valid"], result["errors"]
    assert result["design"]["roundabout"]["circulatingLanes"] == 2


def test_compiled_strategies_differ_only_in_their_control() -> None:
    document, errors = parse_scenario(_doc())
    assert document is not None, errors
    configs = {s: compile_scenario(document, s) for s in STRATEGIES}
    for s in STRATEGIES:
        for key in ("simulation", "roads", "traffic", "vehicleGeneration"):
            assert configs[s][key] == configs["fixed_time"][key] or (
                # Lane markings belong to each junction's design.
                key == "roads" and s == "roundabout"
            )
    assert configs["roundabout"]["geometry"]["circulatingLanes"] == 2
    assert configs["adaptive"]["controller"]["signalControl"] == "adaptive"
    assert "signalControl" not in configs["fixed_time"]["controller"]
    assert configs["fixed_time"]["traffic"]["arrivalRate"] == pytest.approx(1900 / 3600)
    split = configs["fixed_time"]["traffic"]["directionalSplit"]
    assert split["north"] == pytest.approx(900 / 1900)


def test_compiled_configs_pass_the_engine_contract() -> None:
    document, _ = parse_scenario(_doc())
    assert document is not None
    for strategy in STRATEGIES:
        assert semantic_config_errors(compile_scenario(document, strategy)) == []


def test_fingerprint_ignores_name_but_not_content() -> None:
    a, _ = parse_scenario(_doc())
    b, _ = parse_scenario(_doc(name="Renamed"))
    c, _ = parse_scenario(_doc(simulation={"duration": 120, "warmup": 30, "seed": 8}))
    assert a and b and c
    assert scenario_fingerprint(a) == scenario_fingerprint(b)
    assert scenario_fingerprint(a) != scenario_fingerprint(c)


@pytest.mark.parametrize(
    "mutate,fragment",
    [
        (lambda d: d["vehicles"].update(mix={"car": 0.7, "bus": 0.1}), "sum to 1.0"),
        (
            lambda d: d["approaches"]["north"].update(
                turning={"left": 0.5, "straight": 0.6, "right": 0.2}
            ),
            "turnProbabilities must sum to 1.0",
        ),
        (lambda d: d.update(simulation={"duration": 60, "warmup": 60}), "warmup"),
        (
            lambda d: [
                d["approaches"][a].update(vehiclesPerHour=0) for a in d["approaches"]
            ],
            "No traffic",
        ),
        (lambda d: d["approaches"]["north"].update(lanes=0), "lanes"),
        (lambda d: d["approaches"]["north"].update(length=20), "length"),
        (lambda d: d.update(colour="blue"), "not a scenario field"),
        (lambda d: d.update(version=2), "version"),
    ],
)
def test_invalid_scenarios_are_rejected_with_a_reason(
    mutate: Any, fragment: str
) -> None:
    doc = _doc()
    mutate(doc)
    result = validate_scenario(doc, list(STRATEGIES))
    assert not result["valid"]
    assert any(fragment in e for e in result["errors"]), result["errors"]


def test_a_signal_needs_equal_opposite_lanes_but_a_roundabout_does_not() -> None:
    doc = _doc()
    doc["approaches"]["south"]["lanes"] = 2
    signal = validate_scenario(doc, ["fixed_time"])
    roundabout = validate_scenario(doc, ["roundabout"])
    assert not signal["valid"]
    assert any("same number of lanes" in e for e in signal["errors"])
    assert roundabout["valid"], roundabout["errors"]
    both = validate_scenario(doc, ["fixed_time", "roundabout"])
    assert any(e.startswith("Fixed-time signal:") for e in both["errors"])


def test_crossing_lane_arrows_are_rejected_for_a_signal() -> None:
    doc = _doc()
    doc["approaches"]["north"]["laneUse"] = [["straight"], ["left"], ["right"]]
    result = validate_scenario(doc, ["fixed_time"])
    assert not result["valid"]
    assert any("cross" in e for e in result["errors"])


def test_unserved_demand_is_rejected() -> None:
    doc = _doc()
    doc["approaches"]["north"]["laneUse"] = [["straight"], ["straight"], ["straight"]]
    result = validate_scenario(doc, ["fixed_time"])
    assert any("no lane allows it" in e for e in result["errors"]), result["errors"]
    doc["approaches"]["north"]["turning"] = {"left": 0, "straight": 1, "right": 0}
    assert validate_scenario(doc, ["fixed_time"])["valid"]


def test_dual_left_turn_lanes_need_receiving_lanes() -> None:
    doc = _doc()
    doc["approaches"]["north"]["laneUse"] = [["left"], ["left"], ["straight", "right"]]
    doc["approaches"]["north"]["turning"] = {"left": 0.4, "straight": 0.4, "right": 0.2}
    assert validate_scenario(doc, ["fixed_time"])["valid"]
    doc["approaches"]["east"]["lanes"] = 1
    doc["approaches"]["west"]["lanes"] = 1
    result = validate_scenario(doc, ["fixed_time"])
    assert any("receiving lane" in e for e in result["errors"]), result["errors"]


def test_roundabout_lane_markings_are_checked_against_the_designation() -> None:
    doc = _doc()
    doc["approaches"]["east"]["roundaboutLaneUse"] = [
        ["left", "straight", "right"],
        ["right"],
    ]
    result = validate_scenario(doc, ["roundabout"])
    assert not result["valid"]
    assert any("cannot turn right" in e for e in result["errors"]), result["errors"]


def test_three_circulating_lanes_are_rejected_as_unsupported() -> None:
    doc = _doc()
    doc["roundabout"] = {"circulatingLanes": 3, "innerRadius": 10, "outerRadius": 25}
    result = validate_scenario(doc, ["roundabout"])
    assert not result["valid"]
    assert any("not supported yet" in e for e in result["errors"])


def test_a_ring_too_narrow_for_its_lanes_is_rejected_with_the_radius_needed() -> None:
    doc = _doc()
    doc["roundabout"] = {"circulatingLanes": 2, "innerRadius": 10, "outerRadius": 15}
    result = validate_scenario(doc, ["roundabout"])
    assert any("too narrow" in e and "outerRadius" in e for e in result["errors"])


def test_an_approach_two_lanes_wider_than_the_ring_is_rejected() -> None:
    doc = _doc()
    doc["roundabout"] = {"circulatingLanes": 1}
    result = validate_scenario(doc, ["roundabout"])
    assert any("entry lanes can feed it" in e for e in result["errors"])


def test_per_approach_vehicle_mix_must_total_one() -> None:
    doc = _doc()
    doc["approaches"]["east"]["vehicleMix"] = {"car": 0.5, "truck": 0.4}
    result = validate_scenario(doc, ["fixed_time"])
    assert any("traffic.approaches[east].vehicleMix" in e for e in result["errors"])


def test_mix_is_never_normalised() -> None:
    doc = _doc()
    doc["vehicles"]["mix"] = {"car": 0.45, "suv": 0.45}
    assert not validate_scenario(doc, ["fixed_time"])["valid"]


def test_an_exported_document_round_trips() -> None:
    document, _ = parse_scenario(_doc())
    assert document is not None
    again, errors = parse_scenario(json.loads(json.dumps(document.model_dump())))
    assert again is not None, errors
    assert scenario_fingerprint(again) == scenario_fingerprint(document)
    # A wrapped export ({"scenario": {...}}) is read too.
    wrapped, _ = parse_scenario({"scenario": document.model_dump()})
    assert wrapped is not None


def test_every_frontend_preset_is_valid_for_every_strategy() -> None:
    presets = json.loads(PRESETS_PATH.read_text(encoding="utf-8"))["presets"]
    assert len(presets) >= 5
    for preset in presets:
        result = validate_scenario(copy.deepcopy(preset["scenario"]), list(STRATEGIES))
        assert result["valid"], (preset["id"], result["errors"])
