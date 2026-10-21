"""Tests for Strategy Resolution, Parity, and Simulation Initialization Contracts (V3.0 W3, ADR-014 §4).

Covers:
1. Strategy resolution contract (canonical IDs, legacy aliases, descriptors, config dicts).
2. Contract violations: unknown strategies, contradictory configurations, and pre-simulation guards.
3. Configuration equivalence: equivalent configurations instantiate identical controllers and produce
   100% bit-identical simulation results and fingerprints.
4. Fixture scenario fingerprint parity across frontend presets and golden baselines.
5. Strategy instance fingerprinting incorporating descriptor ID, version, and resolved parameters (ADR-014 §4).
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict

import pytest

from src.controllers.adaptive_signal import AdaptiveSignalController
from src.controllers.factory import create_controller
from src.controllers.fixed_time_signal import FixedTimeSignalController
from src.controllers.roundabout import RoundaboutController
from src.controllers.signalised_roundabout import SignalisedRoundaboutController
from src.core.clock import Clock
from src.engine.simulation_engine import SimulationEngine
from src.metrics.collector import MetricCollector
from src.planning.models import canonical_json
from src.scenario.documents import (
    compile_scenario,
    parse_scenario,
    scenario_fingerprint,
)
from src.simulations.registry import InvalidSimulationConfigError, register_simulation
from src.strategies.builtins import (
    ADAPTIVE_SIGNAL,
    CONVENTIONAL_ROUNDABOUT,
    FIXED_TIME_SIGNAL,
    METERED_ENTRY_ROUNDABOUT,
)
from src.strategies.registry import reset_strategy_registry
from src.strategies.resolution import (
    compute_strategy_instance_fingerprint,
    extract_explicit_strategy,
    infer_strategy_id_from_config,
    resolve_strategy,
    resolve_strategy_id,
    resolve_strategy_parameters,
)
from src.strategies.validator import (
    StrategyCompatibilityError,
    check_scenario_strategy_compatibility,
    validate_scenario_strategy_compatibility,
)

PRESETS_PATH = (
    Path(__file__).resolve().parents[3]
    / "frontend"
    / "src"
    / "scenario"
    / "presets.json"
)


@pytest.fixture(autouse=True)
def _reset_registry() -> None:
    reset_strategy_registry()


# --- Sample Scenario Configurations for Testing ---
def _base_signal_config() -> Dict[str, Any]:
    return {
        "simulation": {"duration": 10.0, "timeStep": 0.1, "randomSeed": 42},
        "geometry": {
            "intersectionType": "fixed_time_signal",
            "intersectionCenter": {"x": 0.0, "y": 0.0},
        },
        "roads": {
            "approachLength": 200.0,
            "laneWidth": 3.5,
            "speedLimit": 13.89,
            "lanesPerApproach": 2,
        },
        "traffic": {
            "arrivalRate": 0.5,
            "directionalSplit": {"north": 0.25, "south": 0.25, "east": 0.25, "west": 0.25},
            "turnProbabilities": {"left": 0.2, "straight": 0.6, "right": 0.2},
        },
        "controller": {
            "straightRightDuration": 25.0,
            "yellowDuration": 3.0,
            "allRedDuration": 2.0,
        },
    }


def _base_roundabout_config() -> Dict[str, Any]:
    return {
        "simulation": {"duration": 10.0, "timeStep": 0.1, "randomSeed": 42},
        "geometry": {
            "intersectionType": "roundabout",
            "circulatingLanes": 2,
            "intersectionCenter": {"x": 0.0, "y": 0.0},
        },
        "roads": {
            "approachLength": 200.0,
            "laneWidth": 3.5,
            "speedLimit": 13.89,
            "lanesPerApproach": 2,
        },
        "traffic": {
            "arrivalRate": 0.5,
            "directionalSplit": {"north": 0.25, "south": 0.25, "east": 0.25, "west": 0.25},
            "turnProbabilities": {"left": 0.2, "straight": 0.6, "right": 0.2},
        },
        "controller": {
            "innerRadius": 12.0,
            "outerRadius": 22.0,
            "criticalGap": 3.5,
            "followUpTime": 2.0,
        },
    }


class TestStrategyResolutionContract:
    """Explicit contracts for resolving strategy IDs, aliases, descriptors, and configurations."""

    def test_resolve_canonical_identifiers(self) -> None:
        assert resolve_strategy("fixed_time_signal") == FIXED_TIME_SIGNAL
        assert resolve_strategy("adaptive_signal") == ADAPTIVE_SIGNAL
        assert resolve_strategy("conventional_roundabout") == CONVENTIONAL_ROUNDABOUT
        assert resolve_strategy("metered_entry_roundabout") == METERED_ENTRY_ROUNDABOUT

    def test_resolve_legacy_aliases(self) -> None:
        assert resolve_strategy("fixed_time") == FIXED_TIME_SIGNAL
        assert resolve_strategy("adaptive") == ADAPTIVE_SIGNAL
        assert resolve_strategy("roundabout") == CONVENTIONAL_ROUNDABOUT
        assert resolve_strategy("signalised_roundabout") == METERED_ENTRY_ROUNDABOUT

    def test_resolve_strategy_descriptor_instance(self) -> None:
        desc = FIXED_TIME_SIGNAL
        assert resolve_strategy(desc) is desc

    def test_resolve_invalid_source_type_raises_type_error(self) -> None:
        with pytest.raises(TypeError, match="Expected str, Dict"):
            resolve_strategy(12345)  # type: ignore[arg-type]
        with pytest.raises(TypeError, match="Expected str, Dict"):
            resolve_strategy(None)  # type: ignore[arg-type]
        with pytest.raises(TypeError, match="Expected str, Dict"):
            resolve_strategy(["fixed_time"])  # type: ignore[arg-type]

    def test_resolve_from_config_explicit_and_inferred(self) -> None:
        # Implicit signal
        cfg_sig = _base_signal_config()
        assert extract_explicit_strategy(cfg_sig) is None
        assert infer_strategy_id_from_config(cfg_sig) == "fixed_time_signal"
        assert resolve_strategy(cfg_sig) == FIXED_TIME_SIGNAL
        assert resolve_strategy_id(cfg_sig) == "fixed_time_signal"

        # Explicit root strategy
        cfg_explicit = copy.deepcopy(cfg_sig)
        cfg_explicit["strategy"] = "fixed_time_signal"
        assert extract_explicit_strategy(cfg_explicit) == "fixed_time_signal"
        assert resolve_strategy(cfg_explicit) == FIXED_TIME_SIGNAL

        # Explicit alias in controller
        cfg_ctrl_alias = copy.deepcopy(cfg_sig)
        cfg_ctrl_alias["controller"]["strategy"] = "fixed_time"
        assert extract_explicit_strategy(cfg_ctrl_alias) == "fixed_time"
        assert resolve_strategy(cfg_ctrl_alias) == FIXED_TIME_SIGNAL

        # Implicit adaptive
        cfg_adaptive = copy.deepcopy(cfg_sig)
        cfg_adaptive["controller"]["signalControl"] = "adaptive"
        cfg_adaptive["controller"]["adaptive"] = {"minGreen": 5.0, "maxGreen": 45.0}
        assert infer_strategy_id_from_config(cfg_adaptive) == "adaptive_signal"
        assert resolve_strategy(cfg_adaptive) == ADAPTIVE_SIGNAL

        # Implicit conventional roundabout
        cfg_rb = _base_roundabout_config()
        assert infer_strategy_id_from_config(cfg_rb) == "conventional_roundabout"
        assert resolve_strategy(cfg_rb) == CONVENTIONAL_ROUNDABOUT

        # Implicit metered roundabout
        cfg_metered = copy.deepcopy(cfg_rb)
        cfg_metered["controller"]["entryControl"] = "metered_entry"
        cfg_metered["controller"]["entryMetering"] = {
            "phases": [{"entries": ["north"], "green": 20.0}]
        }
        assert infer_strategy_id_from_config(cfg_metered) == "metered_entry_roundabout"
        assert resolve_strategy(cfg_metered) == METERED_ENTRY_ROUNDABOUT


class TestContractViolationsAndDiagnostics:
    """Validation contract catches invalid strategies, contradictions, and guards initialization."""

    def test_unknown_strategy_rejected_with_compat_unknown_strategy(self) -> None:
        cfg = _base_signal_config()
        cfg["strategy"] = "super_quantum_controller"

        issues = validate_scenario_strategy_compatibility(cfg)
        codes = [i.code for i in issues]
        assert "compat.unknown_strategy" in codes
        issue = next(i for i in issues if i.code == "compat.unknown_strategy")
        assert "Unknown strategy 'super_quantum_controller'" in issue.message
        assert issue.suggestion is not None
        assert "Choose a registered strategy from" in issue.suggestion

        with pytest.raises(StrategyCompatibilityError) as exc_info:
            check_scenario_strategy_compatibility(cfg)
        assert exc_info.value.code == "compat.unknown_strategy"

    def test_strategy_geometry_mismatch_rejected(self) -> None:
        # Roundabout strategy on signal geometry
        cfg_signal = _base_signal_config()
        cfg_signal["strategy"] = "conventional_roundabout"
        issues = validate_scenario_strategy_compatibility(cfg_signal)
        codes = [i.code for i in issues]
        assert "compat.strategy_config_mismatch" in codes
        issue = next(i for i in issues if i.code == "compat.strategy_config_mismatch")
        assert "requires 'roundabout' geometry" in issue.message

        # Signal strategy on roundabout geometry
        cfg_rb = _base_roundabout_config()
        cfg_rb["strategy"] = "fixed_time_signal"
        issues_rb = validate_scenario_strategy_compatibility(cfg_rb)
        assert "compat.strategy_config_mismatch" in [i.code for i in issues_rb]

    def test_strategy_controller_mismatch_rejected(self) -> None:
        # conventional_roundabout strategy with metered_entry control
        cfg = _base_roundabout_config()
        cfg["strategy"] = "conventional_roundabout"
        cfg["controller"]["entryControl"] = "metered_entry"
        issues = validate_scenario_strategy_compatibility(cfg)
        assert "compat.strategy_config_mismatch" in [i.code for i in issues]
        issue = next(i for i in issues if i.code == "compat.strategy_config_mismatch")
        assert "requires unmetered roundabout control" in issue.message

        # metered_entry_roundabout without entryControl='metered_entry'
        cfg_metered = _base_roundabout_config()
        cfg_metered["strategy"] = "metered_entry_roundabout"
        issues_m = validate_scenario_strategy_compatibility(cfg_metered)
        assert "compat.strategy_config_mismatch" in [i.code for i in issues_m]
        issue_m = next(i for i in issues_m if i.code == "compat.strategy_config_mismatch")
        assert "requires entryControl='metered_entry'" in issue_m.message

        # fixed_time_signal with signalControl='adaptive'
        cfg_fts = _base_signal_config()
        cfg_fts["strategy"] = "fixed_time_signal"
        cfg_fts["controller"]["signalControl"] = "adaptive"
        issues_fts = validate_scenario_strategy_compatibility(cfg_fts)
        assert "compat.strategy_config_mismatch" in [i.code for i in issues_fts]

    def test_register_simulation_guards_against_invalid_strategy(self) -> None:
        """register_simulation must reject contradictory configurations before engine build."""
        cfg = _base_signal_config()
        cfg["strategy"] = "conventional_roundabout"

        with pytest.raises(InvalidSimulationConfigError) as exc_info:
            register_simulation(cfg)
        assert "compat.strategy_config_mismatch" in str(exc_info.value)


class TestConfigurationEquivalenceAndSimulationBitIdentity:
    """Equivalent strategy configurations produce identical controllers, simulation runs, and metrics."""

    def _simulate(self, config: Dict[str, Any], ticks: int = 50) -> Dict[str, Any]:
        """Run engine synchronously and return final metrics digest and vehicle states."""
        clock = Clock(time_step=config.get("simulation", {}).get("timeStep", 0.1))
        duration = config.get("simulation", {}).get("duration", 300)
        engine = SimulationEngine(clock, duration=duration, config=config)
        controller = create_controller(config, engine.network)
        engine.controller = controller
        collector = MetricCollector(config)

        for _ in range(ticks):
            engine.step()

        metrics = collector.get_metrics(
            clock.get_elapsed_time(),
            engine.pool.active_vehicles,
            engine.pool.exited_vehicles,
            engine.spawner.spawned_count if engine.spawner else 0,
            engine.pool.collision_count,
        )
        trajectory = [
            (
                v.vehicle_id,
                v.lane.lane_id if v.lane is not None else "",
                round(float(v.position), 6),
                round(float(v.speed), 6),
            )
            for v in sorted(engine.pool.active_vehicles, key=lambda x: x.vehicle_id)
        ]
        return {
            "metrics": metrics,
            "metrics_json": canonical_json(metrics),
            "trajectory": trajectory,
            "trajectory_json": canonical_json(trajectory),
        }

    def test_fixed_time_signal_equivalence(self) -> None:
        """Fixed-time signal: implicit, legacy alias, and canonical ID run bit-identically."""
        cfg_implicit = _base_signal_config()

        cfg_alias = copy.deepcopy(cfg_implicit)
        cfg_alias["strategy"] = "fixed_time"

        cfg_canonical = copy.deepcopy(cfg_implicit)
        cfg_canonical["strategy"] = "fixed_time_signal"

        # 1. Controller factory contract
        clock = Clock(time_step=0.1)
        eng = SimulationEngine(clock, duration=10, config=cfg_implicit)
        ctrl_impl = create_controller(cfg_implicit, eng.network)
        ctrl_alias = create_controller(cfg_alias, eng.network)
        ctrl_canon = create_controller(cfg_canonical, eng.network)

        assert isinstance(ctrl_impl, FixedTimeSignalController)
        assert isinstance(ctrl_alias, FixedTimeSignalController)
        assert isinstance(ctrl_canon, FixedTimeSignalController)

        # 2. Simulation bit-identity
        res_impl = self._simulate(cfg_implicit)
        res_alias = self._simulate(cfg_alias)
        res_canon = self._simulate(cfg_canonical)

        assert res_impl["metrics_json"] == res_alias["metrics_json"] == res_canon["metrics_json"]
        assert res_impl["trajectory_json"] == res_alias["trajectory_json"] == res_canon["trajectory_json"]

    def test_adaptive_signal_equivalence(self) -> None:
        """Adaptive signal: implicit and canonical ID run bit-identically."""
        cfg_implicit = _base_signal_config()
        cfg_implicit["controller"]["signalControl"] = "adaptive"
        cfg_implicit["controller"]["adaptive"] = {"minGreen": 5.0, "maxGreen": 45.0}

        cfg_alias = copy.deepcopy(cfg_implicit)
        cfg_alias["strategy"] = "adaptive"

        cfg_canonical = copy.deepcopy(cfg_implicit)
        cfg_canonical["strategy"] = "adaptive_signal"

        clock = Clock(time_step=0.1)
        eng = SimulationEngine(clock, duration=10, config=cfg_implicit)
        assert isinstance(create_controller(cfg_implicit, eng.network), AdaptiveSignalController)
        assert isinstance(create_controller(cfg_alias, eng.network), AdaptiveSignalController)
        assert isinstance(create_controller(cfg_canonical, eng.network), AdaptiveSignalController)

        res_impl = self._simulate(cfg_implicit)
        res_alias = self._simulate(cfg_alias)
        res_canon = self._simulate(cfg_canonical)

        assert res_impl["metrics_json"] == res_alias["metrics_json"] == res_canon["metrics_json"]
        assert res_impl["trajectory_json"] == res_alias["trajectory_json"] == res_canon["trajectory_json"]

    def test_conventional_roundabout_equivalence(self) -> None:
        """Conventional roundabout: implicit, alias, and canonical ID run bit-identically."""
        cfg_implicit = _base_roundabout_config()

        cfg_alias = copy.deepcopy(cfg_implicit)
        cfg_alias["strategy"] = "roundabout"

        cfg_canonical = copy.deepcopy(cfg_implicit)
        cfg_canonical["strategy"] = "conventional_roundabout"

        clock = Clock(time_step=0.1)
        eng = SimulationEngine(clock, duration=10, config=cfg_implicit)
        assert isinstance(create_controller(cfg_implicit, eng.network), RoundaboutController)
        assert isinstance(create_controller(cfg_alias, eng.network), RoundaboutController)
        assert isinstance(create_controller(cfg_canonical, eng.network), RoundaboutController)

        res_impl = self._simulate(cfg_implicit)
        res_alias = self._simulate(cfg_alias)
        res_canon = self._simulate(cfg_canonical)

        assert res_impl["metrics_json"] == res_alias["metrics_json"] == res_canon["metrics_json"]
        assert res_impl["trajectory_json"] == res_alias["trajectory_json"] == res_canon["trajectory_json"]

    def test_metered_entry_roundabout_equivalence(self) -> None:
        """Metered roundabout: implicit, alias, and canonical ID run bit-identically."""
        cfg_implicit = _base_roundabout_config()
        cfg_implicit["controller"]["entryControl"] = "metered_entry"
        cfg_implicit["controller"]["entryMetering"] = {
            "phases": [{"entries": ["north"], "green": 20.0}],
            "yellow": 3.0,
            "allRed": 2.0,
        }

        cfg_alias = copy.deepcopy(cfg_implicit)
        cfg_alias["strategy"] = "signalised_roundabout"

        cfg_canonical = copy.deepcopy(cfg_implicit)
        cfg_canonical["strategy"] = "metered_entry_roundabout"

        clock = Clock(time_step=0.1)
        eng = SimulationEngine(clock, duration=10, config=cfg_implicit)
        assert isinstance(create_controller(cfg_implicit, eng.network), SignalisedRoundaboutController)
        assert isinstance(create_controller(cfg_alias, eng.network), SignalisedRoundaboutController)
        assert isinstance(create_controller(cfg_canonical, eng.network), SignalisedRoundaboutController)

        res_impl = self._simulate(cfg_implicit)
        res_alias = self._simulate(cfg_alias)
        res_canon = self._simulate(cfg_canonical)

        assert res_impl["metrics_json"] == res_alias["metrics_json"] == res_canon["metrics_json"]
        assert res_impl["trajectory_json"] == res_alias["trajectory_json"] == res_canon["trajectory_json"]


class TestFixtureParityAndScenarioCompilation:
    """Verifies that all pre-existing fixture presets maintain 100% bit-identical fingerprints."""

    def test_presets_produce_identical_scenario_fingerprints(self) -> None:
        """Every frontend preset must produce identical scenario fingerprint before and after compilation."""
        assert PRESETS_PATH.is_file(), f"Presets file not found at {PRESETS_PATH}"
        presets_data = json.loads(PRESETS_PATH.read_text(encoding="utf-8"))["presets"]

        for preset_item in presets_data:
            preset_id = preset_item.get("id", "unknown")
            preset_doc = preset_item.get("scenario", preset_item)
            doc, errors = parse_scenario(preset_doc)
            assert doc is not None, f"Preset '{preset_id}' failed parsing: {errors}"

            fp_base = scenario_fingerprint(doc)

            # Compile under legacy vs canonical strategy
            cfg_legacy = compile_scenario(doc, "fixed_time")
            cfg_canonical = compile_scenario(doc, "fixed_time_signal")

            # Scenario block fingerprints must match
            assert cfg_legacy["scenario"]["fingerprint"] == fp_base
            assert cfg_canonical["scenario"]["fingerprint"] == fp_base

            # Physical simulation configuration sections must be identical
            for section in ("simulation", "geometry", "roads", "traffic", "vehicleGeneration"):
                assert cfg_legacy[section] == cfg_canonical[section]

            # Controller parameters must be identical
            assert cfg_legacy["controller"] == cfg_canonical["controller"]


class TestStrategyInstanceFingerprinting:
    """Deterministic strategy instance fingerprinting (ADR-014 §4)."""

    def test_instance_fingerprint_deterministic_and_stable(self) -> None:
        desc = FIXED_TIME_SIGNAL
        params = {"cycle_time": 60.0, "green_time": 25.0}

        fp1 = compute_strategy_instance_fingerprint(desc, params)
        fp2 = compute_strategy_instance_fingerprint(desc, params)
        assert fp1 == fp2
        assert len(fp1) == 16
        assert all(c in "0123456789abcdef" for c in fp1)

    def test_instance_fingerprint_sensitivities(self) -> None:
        desc = FIXED_TIME_SIGNAL
        fp_base = compute_strategy_instance_fingerprint(desc, {"cycle_time": 60.0})

        # Changed parameter changes fingerprint
        fp_param = compute_strategy_instance_fingerprint(desc, {"cycle_time": 90.0})
        assert fp_param != fp_base

        # Changed descriptor changes fingerprint
        fp_desc = compute_strategy_instance_fingerprint(ADAPTIVE_SIGNAL, {"cycle_time": 60.0})
        assert fp_desc != fp_base

    def test_resolve_parameters_from_config(self) -> None:
        cfg = _base_signal_config()
        cfg["controller"]["cycle_time"] = 75.0
        resolved = resolve_strategy_parameters(FIXED_TIME_SIGNAL, cfg)
        assert resolved["cycle_time"] == 75.0
        # Default value populated for unset parameter with default
        assert resolved["yellow_time"] == 3.0
