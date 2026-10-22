"""W3 integration-hardening regression tests (ADR-014).

Pins defects found in the independent review of W3-T1..T5:
1. Descriptor parameter bounds/defaults must agree with the config schema and the
   controllers, or ``register_simulation`` rejects schema-valid configurations.
2. Registry alias integrity (no shadowing of canonical ids, no silent re-targeting)
   and isolation of registered descriptors from callers.
3. Strict numeric typing in ``resolve_strategy_parameters``.
4. Adaptive control on a metered-entry roundabout is rejected at every entry point.
5. Frontend strategy model parity (descriptor fingerprints, diagnostic identifiers).
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterator, List, Tuple

import pytest

from src.controllers.adaptive_signal import DEFAULT_ADAPTIVE
from src.scenario.config_validation import semantic_config_errors
from src.simulations.registry import (
    InvalidSimulationConfigError,
    register_simulation,
    simulations_db,
)
from src.strategies.builtins import BUILTIN_STRATEGIES
from src.strategies.registry import (
    StrategyRegistry,
    get_strategy_registry,
    reset_strategy_registry,
)
from src.strategies.resolution import resolve_strategy_parameters
from src.strategies.validator import (
    COMPATIBILITY_ERROR_CODES,
    validate_scenario_strategy_compatibility,
)
from tests.controllers.test_signalised_roundabout import (
    _make_metered_roundabout_config,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_SCHEMA_PATH = REPO_ROOT / "shared" / "schemas" / "config.schema.json"
FRONTEND_MODEL_PATH = (
    REPO_ROOT / "frontend" / "src" / "scenario" / "strategySummaryModel.ts"
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


def _register_then_discard(config: Dict[str, Any]) -> Dict[str, Any]:
    entry = register_simulation(config)
    simulations_db.pop(entry["sim_id"], None)
    return entry


def _schema_range(prop: Dict[str, Any]) -> Tuple[float, float]:
    low = prop["minimum"] if "minimum" in prop else prop["exclusiveMinimum"]
    return float(low), float(prop["maximum"])


def _camel(snake: str) -> str:
    head, *rest = snake.split("_")
    return head + "".join(word.capitalize() for word in rest)


def _schema_backed_parameters() -> Iterator[Tuple[str, str, str, Dict[str, Any]]]:
    """(strategy id, parameter, config path, schema property) for mapped parameters."""
    schema = json.loads(CONFIG_SCHEMA_PATH.read_text(encoding="utf-8"))
    ctrl_props = schema["properties"]["controller"]["properties"]
    adaptive_props = ctrl_props["adaptive"]["properties"]
    for desc in BUILTIN_STRATEGIES:
        for name in desc.parameters:
            camel = _camel(name)
            for path, props in (
                (f"controller.{camel}", ctrl_props),
                (f"controller.adaptive.{camel}", adaptive_props),
            ):
                prop = props.get(camel)
                if prop is not None and (
                    "minimum" in prop or "exclusiveMinimum" in prop
                ):
                    yield desc.id, name, path, prop
                    break


class TestParameterSchemaParity:
    def test_mapped_parameters_exist(self) -> None:
        mapped = {(sid, name) for sid, name, _, _ in _schema_backed_parameters()}
        # Guards the discovery logic itself: these are known to map onto the schema.
        assert ("fixed_time_signal", "yellow_time") in mapped
        assert ("adaptive_signal", "min_green") in mapped

    @pytest.mark.parametrize(
        "strategy_id,name,path,prop",
        list(_schema_backed_parameters()),
        ids=lambda v: v if isinstance(v, str) else "",
    )
    def test_descriptor_bounds_cover_schema_bounds(
        self, strategy_id: str, name: str, path: str, prop: Dict[str, Any]
    ) -> None:
        """A schema-valid value must never be rejected by the descriptor bounds."""
        bound = get_strategy_registry().get(strategy_id).parameters[name]
        low, high = _schema_range(prop)
        assert bound.min_value <= low, f"{path}: descriptor min above schema min"
        assert bound.max_value >= high, f"{path}: descriptor max below schema max"

    def test_adaptive_descriptor_defaults_match_controller_defaults(self) -> None:
        params = get_strategy_registry().get("adaptive_signal").parameters
        assert params["min_green"].default_value == DEFAULT_ADAPTIVE["minGreen"]
        assert params["max_green"].default_value == DEFAULT_ADAPTIVE["maxGreen"]
        assert (
            params["extension_step"].default_value == DEFAULT_ADAPTIVE["extensionStep"]
        )

    @pytest.mark.parametrize(
        "controller",
        [
            {"allRedTime": 0},
            {"yellowTime": 2.5},
            {"yellowTime": 8},
            {
                "signalControl": "adaptive",
                "adaptive": {"minGreen": 60, "maxGreen": 100},
            },
            {"signalControl": "adaptive", "adaptive": {"maxGreen": 180}},
            {"signalControl": "adaptive", "adaptive": {"extensionStep": 10}},
        ],
    )
    def test_register_simulation_accepts_schema_valid_timings(
        self, controller: Dict[str, Any]
    ) -> None:
        cfg = _signal_config()
        cfg["controller"].update(controller)
        _register_then_discard(cfg)


class TestRegistryAliasIntegrity:
    def test_alias_cannot_shadow_canonical_id(self) -> None:
        reg = StrategyRegistry()
        with pytest.raises(ValueError, match="shadow"):
            reg.register_alias("fixed_time_signal", "adaptive_signal")
        assert reg.resolve_id("fixed_time_signal") == "fixed_time_signal"

    def test_alias_cannot_be_retargeted(self) -> None:
        reg = StrategyRegistry()
        with pytest.raises(ValueError, match="Re-targeting"):
            reg.register_alias("fixed_time", "adaptive_signal")
        assert reg.resolve_id("fixed_time") == "fixed_time_signal"

    def test_identical_alias_registration_is_idempotent(self) -> None:
        reg = StrategyRegistry()
        reg.register_alias("fixed_time", "fixed_time_signal")
        assert reg.resolve_id("fixed_time") == "fixed_time_signal"

    def test_strategy_id_cannot_collide_with_alias(self) -> None:
        reg = StrategyRegistry()
        clash = reg.get("fixed_time_signal").model_copy(update={"id": "roundabout"})
        with pytest.raises(ValueError, match="collides with an existing alias"):
            reg.register(clash)

    def test_registry_returns_isolated_copies(self) -> None:
        reg = get_strategy_registry()
        reg.get("fixed_time_signal").name = "tampered"
        reg.get("fixed_time_signal").parameters.pop("cycle_time")
        reg.list_all()[0].parameters.clear()
        fresh = reg.get("fixed_time_signal")
        assert fresh.name == "Fixed-Time Signal"
        assert "cycle_time" in fresh.parameters
        reg.self_check()

    def test_registered_descriptor_is_detached_from_callers_reference(self) -> None:
        reg = StrategyRegistry(load_builtins=False)
        original = BUILTIN_STRATEGIES[0].model_copy(deep=True)
        reg.register(original)
        original.name = "mutated after registration"
        assert reg.get(original.id).name != "mutated after registration"


class TestParameterTyping:
    @pytest.mark.parametrize("bad", ["abc", "30", [1], {"v": 1}, True])
    def test_non_numeric_parameter_rejected(self, bad: Any) -> None:
        desc = get_strategy_registry().get("fixed_time_signal")
        with pytest.raises(ValueError, match="must be a number"):
            resolve_strategy_parameters(desc, {"controller": {"greenTime": bad}})

    def test_non_numeric_parameter_fails_registration_cleanly(self) -> None:
        cfg = _signal_config()
        cfg["controller"]["yellowTime"] = "3"
        before = len(simulations_db)
        with pytest.raises(InvalidSimulationConfigError, match="must be a number"):
            register_simulation(cfg)
        assert len(simulations_db) == before

    def test_integer_parameter_resolves_as_float(self) -> None:
        desc = get_strategy_registry().get("fixed_time_signal")
        resolved = resolve_strategy_parameters(desc, {"controller": {"greenTime": 30}})
        assert resolved["green_time"] == 30.0
        assert isinstance(resolved["green_time"], float)


class TestMeteredAdaptiveRejection:
    @staticmethod
    def _metered_adaptive() -> Dict[str, Any]:
        cfg = _make_metered_roundabout_config()
        cfg["controller"]["signalControl"] = "adaptive"
        return cfg

    def test_validator_flags_adaptive_on_metered_roundabout(self) -> None:
        issues = validate_scenario_strategy_compatibility(self._metered_adaptive())
        assert "compat.adaptive_unsupported_policy" in [i.code for i in issues]
        assert all(i.code in COMPATIBILITY_ERROR_CODES for i in issues)

    def test_metered_roundabout_without_adaptive_stays_valid(self) -> None:
        cfg = _make_metered_roundabout_config()
        assert validate_scenario_strategy_compatibility(cfg) == []

    def test_register_simulation_rejects_instead_of_dropping_adaptive(self) -> None:
        before = len(simulations_db)
        with pytest.raises(
            InvalidSimulationConfigError, match="compat.adaptive_unsupported_policy"
        ):
            register_simulation(self._metered_adaptive())
        assert len(simulations_db) == before

    def test_semantic_message_does_not_call_metered_ring_unmetered(self) -> None:
        errors = semantic_config_errors(copy.deepcopy(self._metered_adaptive()))
        adaptive = [e for e in errors if "compat.adaptive_unsupported_policy" in e]
        assert len(adaptive) == 1
        assert "unmetered" not in adaptive[0]
        assert "metered-entry roundabout" in adaptive[0]


def _frontend_model_source() -> str:
    return FRONTEND_MODEL_PATH.read_text(encoding="utf-8")


def _frontend_fingerprints() -> Dict[str, str]:
    pairs = re.findall(
        r'id: "([a-z_]+)",.*?fingerprint: "([0-9a-f]{16})"',
        _frontend_model_source(),
        flags=re.DOTALL,
    )
    return dict(pairs)


class TestFrontendBackendParity:
    def test_frontend_descriptor_fingerprints_match_registry(self) -> None:
        frontend = _frontend_fingerprints()
        backend = {d.id: d.fingerprint for d in get_strategy_registry().list_all()}
        assert frontend == backend

    def test_frontend_diagnostic_codes_exist_in_backend(self) -> None:
        emitted = set(
            re.findall(r'code: "(compat\.[a-z_]+)"', _frontend_model_source())
        )
        assert emitted, "frontend model emits no compat.* codes"
        unknown: List[str] = sorted(emitted - COMPATIBILITY_ERROR_CODES)
        assert not unknown, (
            f"frontend emits codes the backend does not define: {unknown}"
        )
