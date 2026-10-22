"""W3 descriptor defaults, engine-key resolution and identity pin (ADR-014 §4).

1. Descriptor defaults equal what the engine uses when a key is omitted, so a
   resolved parameter set is what the run actually used.
2. ``resolve_strategy_parameters`` reads the controller keys, in the controller's
   precedence order.
3. Built-in descriptor identity (fingerprints) only changes on purpose.
4. The ring-lane limit has a single source.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

from src.controllers.adaptive_signal import AdaptiveSignalController
from src.controllers.fixed_time_signal import FixedTimeSignalController
from src.controllers.roundabout import RoundaboutController
from src.roads.lane_config import MAX_CIRCULATING_LANES as ENGINE_MAX_CIRCULATING_LANES
from src.roads.network import RoadNetwork
from src.simulations.registry import register_simulation, simulations_db
from src.strategies import limits
from src.strategies.models import MAX_CIRCULATING_LANES
from src.strategies.registry import get_strategy_registry, reset_strategy_registry
from src.strategies.resolution import (
    compute_strategy_instance_fingerprint,
    resolve_strategy_parameters,
)

CONFIG_SCHEMA_PATH = (
    Path(__file__).resolve().parents[3] / "shared" / "schemas" / "config.schema.json"
)

# Pinned on purpose: see TestDescriptorIdentityPin.
PINNED_DESCRIPTOR_FINGERPRINTS = {
    "adaptive_signal": "9463e0b9e7a3619d",
    "conventional_roundabout": "b622164ad2527a01",
    "fixed_time_signal": "21b44f48677fff33",
    "metered_entry_roundabout": "32511c2e97ffc1bb",
}


@pytest.fixture(autouse=True)
def _reset_registry() -> None:
    reset_strategy_registry()


def _network() -> RoadNetwork:
    net = RoadNetwork()
    net.setup_default_intersection(
        approach_length=100.0, lane_width=3.5, lanes_per_approach=1
    )
    return net


def _signal_config() -> Dict[str, Any]:
    return {
        "simulation": {"duration": 10.0, "timeStep": 0.1, "randomSeed": 42},
        "geometry": {"intersectionType": "fixed_time_signal"},
        "controller": {},
    }


class TestDescriptorDefaultsAreEngineDefaults:
    def test_fixed_time_defaults_match_the_controller(self) -> None:
        ctrl = FixedTimeSignalController({"controller": {}}, _network())
        params = get_strategy_registry().get("fixed_time_signal").parameters
        assert params["green_time"].default_value == ctrl.straight_right_duration
        assert params["yellow_time"].default_value == ctrl.yellow_duration
        assert params["all_red_time"].default_value == ctrl.all_red_duration

    def test_adaptive_signal_timing_defaults_match_the_controller(self) -> None:
        ctrl = AdaptiveSignalController({"controller": {}}, _network())
        params = get_strategy_registry().get("adaptive_signal").parameters
        assert params["yellow_time"].default_value == ctrl.yellow_duration
        assert params["all_red_time"].default_value == ctrl.all_red_duration

    def test_roundabout_defaults_match_the_controller(self) -> None:
        ctrl = RoundaboutController({"controller": {}}, _network())
        params = get_strategy_registry().get("conventional_roundabout").parameters
        assert params["critical_gap"].default_value == ctrl.critical_gap
        assert params["inner_radius"].default_value == ctrl.inner_radius

    def test_metering_defaults_match_the_schema(self) -> None:
        schema = json.loads(CONFIG_SCHEMA_PATH.read_text(encoding="utf-8"))
        ctrl_props = schema["properties"]["controller"]["properties"]
        props = ctrl_props["entryMetering"]["properties"]
        params = get_strategy_registry().get("metered_entry_roundabout").parameters
        assert params["metering_yellow"].default_value == props["yellow"]["default"]
        assert params["metering_all_red"].default_value == props["allRed"]["default"]

    def test_derived_knobs_report_no_fabricated_default(self) -> None:
        reg = get_strategy_registry()
        fixed = reg.get("fixed_time_signal")
        assert fixed.parameters["cycle_time"].default_value is None
        assert (
            reg.get("adaptive_signal").parameters["passage_gap"].default_value is None
        )
        assert "cycle_time" not in resolve_strategy_parameters(fixed, {})

    def test_unset_timings_resolve_to_the_engine_defaults(self) -> None:
        desc = get_strategy_registry().get("fixed_time_signal")
        assert resolve_strategy_parameters(desc, {}) == {
            "green_time": 30.0,
            "yellow_time": 4.0,
            "all_red_time": 2.0,
        }


class TestEngineKeyResolution:
    """resolve_strategy_parameters reads the keys the controller reads."""

    @pytest.mark.parametrize(
        "controller,expected",
        [
            ({"straightRightDuration": 40, "greenTime": 20, "greenDuration": 10}, 40.0),
            ({"greenTime": 20, "greenDuration": 10}, 20.0),
            ({"greenDuration": 10}, 10.0),
        ],
    )
    def test_green_precedence_matches_the_controller(
        self, controller: Dict[str, Any], expected: float
    ) -> None:
        engine = FixedTimeSignalController({"controller": dict(controller)}, _network())
        desc = get_strategy_registry().get("fixed_time_signal")
        resolved = resolve_strategy_parameters(desc, {"controller": controller})
        assert resolved["green_time"] == expected == engine.straight_right_duration

    @pytest.mark.parametrize(
        "controller",
        [
            {
                "yellowDuration": 5,
                "yellowTime": 3,
                "allRedDuration": 1,
                "allRedTime": 4,
            },
            {"yellowTime": 3, "allRedTime": 4},
            {"yellowDuration": 6},
        ],
    )
    def test_clearance_precedence_matches_the_controller(
        self, controller: Dict[str, Any]
    ) -> None:
        engine = FixedTimeSignalController({"controller": dict(controller)}, _network())
        desc = get_strategy_registry().get("fixed_time_signal")
        resolved = resolve_strategy_parameters(desc, {"controller": controller})
        assert resolved["yellow_time"] == engine.yellow_duration
        assert resolved["all_red_time"] == engine.all_red_duration

    def test_engine_keys_are_bounds_checked(self) -> None:
        desc = get_strategy_registry().get("fixed_time_signal")
        with pytest.raises(ValueError, match="yellow_time"):
            resolve_strategy_parameters(desc, {"controller": {"yellowDuration": 9}})

    def test_register_simulation_records_the_values_it_runs(self) -> None:
        cfg = _signal_config()
        cfg["controller"] = {"yellowDuration": 5.0, "allRedDuration": 1.0}
        entry = register_simulation(cfg)
        simulations_db.pop(entry["sim_id"], None)
        assert entry["strategy_parameters"] == {
            "green_time": 30.0,
            "yellow_time": 5.0,
            "all_red_time": 1.0,
        }
        assert entry["controller"].yellow_duration == 5.0


class TestDescriptorIdentityPin:
    """Descriptor identity changes only on purpose (docs/simulation/strategies.md)."""

    def test_builtin_fingerprints_are_pinned(self) -> None:
        actual = {d.id: d.fingerprint for d in get_strategy_registry().list_all()}
        assert actual == PINNED_DESCRIPTOR_FINGERPRINTS, (
            "A built-in descriptor changed. If intended: update this pin and the "
            "frontend copies in strategySummaryModel.ts; once V3.0 has shipped, "
            "also bump the descriptor version."
        )

    def test_a_bound_change_changes_descriptor_and_instance_identity(self) -> None:
        desc = get_strategy_registry().get("fixed_time_signal")
        widened = desc.model_copy(deep=True)
        widened.parameters["green_time"].max_value += 1
        assert widened.compute_fingerprint() != desc.fingerprint
        params = {"green_time": 30.0}
        assert compute_strategy_instance_fingerprint(
            desc, params
        ) != compute_strategy_instance_fingerprint(widened, params)


class TestRingLaneLimitSingleSource:
    def test_descriptor_and_engine_share_one_value(self) -> None:
        assert MAX_CIRCULATING_LANES is limits.MAX_CIRCULATING_LANES
        assert ENGINE_MAX_CIRCULATING_LANES is limits.MAX_CIRCULATING_LANES
