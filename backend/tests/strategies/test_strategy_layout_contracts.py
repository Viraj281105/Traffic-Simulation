"""W3 contract-consistency regression tests (ADR-014).

1. Roundabout descriptor parameters resolve from the real config keys.
2. Strategy inference and compatibility validation read one junction layout.
3. ``strategy: adaptive`` contradicting an explicit ``signalControl: fixed_time``.
4. Supported ring lane counts on ``GeometryConstraint.circulating_lanes``.
5. The diagnostic code -> layer contract shared with the frontend.
"""

from __future__ import annotations

import itertools
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest

from src.roads.lane_config import MAX_CIRCULATING_LANES as ENGINE_MAX_CIRCULATING_LANES
from src.simulations.registry import (
    InvalidSimulationConfigError,
    register_simulation,
    simulations_db,
)
from src.strategies.models import MAX_CIRCULATING_LANES, GeometryConstraint
from src.strategies.registry import get_strategy_registry, reset_strategy_registry
from src.strategies.resolution import (
    extract_geometry_type,
    resolve_strategy,
    resolve_strategy_parameters,
)
from src.strategies.validator import (
    COMPATIBILITY_CODE_LAYERS,
    COMPATIBILITY_ERROR_CODES,
    validate_layer_combination,
    validate_scenario_strategy_compatibility,
)
from tests.controllers.test_signalised_roundabout import (
    _make_metered_roundabout_config,
)

FRONTEND_MODEL_PATH = (
    Path(__file__).resolve().parents[3]
    / "frontend"
    / "src"
    / "scenario"
    / "strategySummaryModel.ts"
)


@pytest.fixture(autouse=True)
def _reset_registry() -> None:
    reset_strategy_registry()


def _signal_config() -> Dict[str, Any]:
    return {
        "simulation": {"duration": 10.0, "timeStep": 0.1, "randomSeed": 42},
        "geometry": {"intersectionType": "fixed_time_signal"},
        "controller": {},
    }


def _codes(config: Dict[str, Any]) -> List[str]:
    return [i.code for i in validate_scenario_strategy_compatibility(config)]


class TestRoundaboutParameterResolution:
    def test_critical_gap_is_read_from_the_real_config_key(self) -> None:
        desc = get_strategy_registry().get("conventional_roundabout")
        resolved = resolve_strategy_parameters(desc, {"controller": {"criticalGap": 6}})
        assert resolved == {"critical_gap": 6.0, "inner_radius": 10.0}

    def test_inner_radius_is_read_from_the_real_config_key(self) -> None:
        desc = get_strategy_registry().get("conventional_roundabout")
        resolved = resolve_strategy_parameters(
            desc, {"controller": {"innerRadius": 12}}
        )
        assert resolved["inner_radius"] == 12.0

    def test_metering_timings_are_read_from_entry_metering(self) -> None:
        desc = get_strategy_registry().get("metered_entry_roundabout")
        cfg = _make_metered_roundabout_config()
        cfg["controller"]["entryMetering"].update(yellow=4.0, allRed=0)
        assert resolve_strategy_parameters(desc, cfg) == {
            "metering_yellow": 4.0,
            "metering_all_red": 0.0,
        }

    def test_metering_defaults_when_unset(self) -> None:
        desc = get_strategy_registry().get("metered_entry_roundabout")
        assert resolve_strategy_parameters(desc, {"controller": {}}) == {
            "metering_yellow": 3.0,
            "metering_all_red": 2.0,
        }

    def test_out_of_range_metering_yellow_is_rejected(self) -> None:
        desc = get_strategy_registry().get("metered_entry_roundabout")
        cfg = {"controller": {"entryMetering": {"yellow": 9}}}
        with pytest.raises(ValueError, match="metering_yellow"):
            resolve_strategy_parameters(desc, cfg)

    @pytest.mark.parametrize(
        "entry_metering", [{"yellow": 2.5, "allRed": 0}, {"yellow": 8, "allRed": 5}]
    )
    def test_schema_valid_metering_timings_register(
        self, entry_metering: Dict[str, Any]
    ) -> None:
        cfg = _make_metered_roundabout_config()
        cfg["controller"]["entryMetering"].update(entry_metering)
        entry = register_simulation(cfg)
        simulations_db.pop(entry["sim_id"], None)


class TestGeometryDeclarationConsistency:
    """Strategy inference and compatibility validation read one layout."""

    def test_junction_type_fallback_rules(self) -> None:
        assert (
            extract_geometry_type({"junction": {"type": "roundabout"}}) == "roundabout"
        )
        engine = {"geometry": {"intersectionType": "roundabout"}}
        assert extract_geometry_type(engine) == "roundabout"
        null_geometry = {
            "geometry": {"intersectionType": None},
            "junction": {"type": "roundabout"},
        }
        assert extract_geometry_type(null_geometry) == "roundabout"
        geometry_wins = {
            "geometry": {"intersectionType": "fixed_time_signal"},
            "junction": {"type": "roundabout"},
        }
        assert extract_geometry_type(geometry_wins) == "fixed_time_signal"
        assert extract_geometry_type({}) is None
        assert extract_geometry_type("not a dict") is None

    def test_adaptive_on_a_roundabout_junction_is_rejected_like_geometry(self) -> None:
        controller = {"signalControl": "adaptive"}
        by_junction = {"junction": {"type": "roundabout"}, "controller": controller}
        by_geometry = {
            "geometry": {"intersectionType": "roundabout"},
            "controller": controller,
        }
        assert _codes(by_junction) == _codes(by_geometry)
        assert "compat.adaptive_unsupported_policy" in _codes(by_junction)

    @pytest.mark.parametrize(
        "junction,expected",
        [
            ("fixed_time_signal", "fixed_time_signal"),
            ("adaptive_signal", "adaptive_signal"),
            ("roundabout", "conventional_roundabout"),
        ],
    )
    def test_valid_junction_documents_resolve_and_validate(
        self, junction: str, expected: str
    ) -> None:
        cfg = {"junction": {"type": junction}}
        assert _codes(cfg) == []
        assert resolve_strategy(cfg).id == expected

    def test_explicit_strategy_is_checked_against_junction_type(self) -> None:
        cfg = {
            "strategy": "conventional_roundabout",
            "junction": {"type": "fixed_time_signal"},
        }
        assert _codes(cfg) == ["compat.strategy_config_mismatch"]


class TestAdaptiveStrategyContradiction:
    @staticmethod
    def _cfg(**controller: Any) -> Dict[str, Any]:
        cfg = _signal_config()
        cfg["strategy"] = "adaptive_signal"
        cfg["controller"] = dict(controller)
        return cfg

    def test_explicit_fixed_time_contradicts_adaptive_strategy(self) -> None:
        issues = validate_scenario_strategy_compatibility(
            self._cfg(signalControl="fixed_time")
        )
        assert [i.code for i in issues] == ["compat.strategy_config_mismatch"]
        assert "signalControl='fixed_time'" in issues[0].message

    def test_register_simulation_rejects_instead_of_running_adaptive(self) -> None:
        before = len(simulations_db)
        with pytest.raises(InvalidSimulationConfigError, match="fixed_time"):
            register_simulation(self._cfg(signalControl="fixed_time"))
        assert len(simulations_db) == before

    @pytest.mark.parametrize(
        "controller", [{}, {"signalControl": "adaptive"}, {"signalControl": None}]
    )
    def test_absent_or_matching_signal_control_is_not_a_contradiction(
        self, controller: Dict[str, Any]
    ) -> None:
        assert _codes(self._cfg(**controller)) == []

    def test_compiled_adaptive_scenario_is_unaffected(self) -> None:
        cfg = _signal_config()
        cfg["controller"] = {"signalControl": "adaptive"}
        cfg["scenario"] = {"strategy": "adaptive"}
        assert _codes(cfg) == []
        assert resolve_strategy(cfg).id == "adaptive_signal"


class TestCirculatingLanesRange:
    def test_limit_matches_the_engine(self) -> None:
        # One source (strategies/limits.py); see test_strategy_defaults_and_identity.
        assert MAX_CIRCULATING_LANES == ENGINE_MAX_CIRCULATING_LANES == 2

    @pytest.mark.parametrize("lanes", [[0], [3], [-1], [1, 1], [1, 2, 3]])
    def test_unsupported_ring_lane_counts_are_rejected(self, lanes: List[int]) -> None:
        with pytest.raises(ValueError, match="circulating_lanes"):
            GeometryConstraint(intersection_type="roundabout", circulating_lanes=lanes)

    @pytest.mark.parametrize("lanes", [None, [1], [2], [1, 2]])
    def test_supported_ring_lane_counts_are_accepted(
        self, lanes: Optional[List[int]]
    ) -> None:
        GeometryConstraint(intersection_type="roundabout", circulating_lanes=lanes)

    def test_empty_list_still_surfaces_as_a_coded_diagnostic(self) -> None:
        geometry = GeometryConstraint(
            intersection_type="roundabout", circulating_lanes=[]
        )
        issues = validate_layer_combination(
            geometry,
            {"topology_type": "zone_based_conflicts"},
            {"rule": "yield_to_ring"},
            {"policy": "uncontrolled"},
            {"logic": "none"},
        )
        assert [i.code for i in issues] == [
            "compat.roundabout_requires_circulating_lanes"
        ]


def _sweep_layer_issues() -> List[Tuple[str, Tuple[str, ...]]]:
    """Every (code, layers) the layer validator can emit across its input space."""
    emitted: List[Tuple[str, Tuple[str, ...]]] = []
    space = itertools.product(
        ("fixed_time_signal", "roundabout"),
        (None, [], [1]),
        ((3, 4), (4, 3)),
        ("point_based_conflicts", "zone_based_conflicts"),
        ("signal", "yield_to_ring", "signal_over_yield", "phased_priority"),
        ("fixed_time_phase_plan", "metering", "uncontrolled"),
        (False, True),
        ("none", "gap_out_extension"),
        ("none", "emergency_preemption"),
    )
    for geom, lanes, arms, topo, rule, policy, cycle, logic, overlay in space:
        for issue in validate_layer_combination(
            {
                "intersection_type": geom,
                "circulating_lanes": lanes,
                "min_arms": arms[0],
                "max_arms": arms[1],
            },
            {"topology_type": topo},
            {"rule": rule},
            {"policy": policy, "cycle_aware": cycle},
            {"logic": logic},
            {"overlay": overlay},
        ):
            emitted.append((issue.code, issue.layers))
    return emitted


class TestDiagnosticLayerContract:
    def test_codes_are_exactly_the_layer_map_keys(self) -> None:
        assert COMPATIBILITY_ERROR_CODES == frozenset(COMPATIBILITY_CODE_LAYERS)

    def test_every_layer_rule_is_exercised_with_its_declared_layers(self) -> None:
        emitted = _sweep_layer_issues()
        scenario_level = {"compat.unknown_strategy", "compat.strategy_config_mismatch"}
        assert {code for code, _ in emitted} == (
            set(COMPATIBILITY_CODE_LAYERS) - scenario_level
        )
        for code, layers in emitted:
            assert layers == COMPATIBILITY_CODE_LAYERS[code], code

    def test_scenario_level_issues_stay_within_declared_layers(self) -> None:
        roundabout = {"intersectionType": "roundabout"}
        cases: List[Dict[str, Any]] = [
            {"strategy": "nope"},
            {"strategy": "conventional_roundabout"},
            {"strategy": "fixed_time_signal", "geometry": roundabout},
            {"strategy": "metered_entry_roundabout", "geometry": roundabout},
            {
                "strategy": "fixed_time_signal",
                "controller": {"signalControl": "adaptive"},
            },
            {
                "strategy": "adaptive_signal",
                "controller": {"signalControl": "fixed_time"},
            },
        ]
        seen = set()
        for cfg in cases:
            for issue in validate_scenario_strategy_compatibility(cfg):
                seen.add(issue.code)
                allowed = set(COMPATIBILITY_CODE_LAYERS[issue.code])
                assert set(issue.layers) <= allowed, (cfg, issue.code)
        assert {"compat.unknown_strategy", "compat.strategy_config_mismatch"} <= seen

    def test_frontend_layer_table_matches_backend_contract(self) -> None:
        layer_order = [
            "geometry",
            "movement_topology",
            "right_of_way",
            "control_policy",
            "adaptation_logic",
            "priority_overlay",
        ]
        source = FRONTEND_MODEL_PATH.read_text(encoding="utf-8")
        table = source.split("export const COMPAT_CODE_LAYER_INDEX")[1].split("};")[0]
        frontend = {
            code: int(index)
            for code, index in re.findall(r'"(compat\.[a-z_]+)":\s*(\d)', table)
        }
        assert set(frontend) == set(COMPATIBILITY_CODE_LAYERS)
        for code, index in frontend.items():
            assert layer_order[index - 1] in COMPATIBILITY_CODE_LAYERS[code], code
