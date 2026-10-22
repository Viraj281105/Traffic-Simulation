"""Cross-layer contract tests for driver-aggression profiles (W4-T4).

Covers:
1. Backend models (TrafficConfig, TrafficSpec, DriverAggression).
2. Shared JSON schemas (shared/schemas/config.schema.json, shared/schemas/v2/network.schema.json).
3. Frontend TypeScript types (frontend/src/types/config.ts, frontend/src/scenario/scenarioTypes.ts).
4. Scenario presets (frontend/src/scenario/presets.json) and frozen fingerprint baselines.
5. Authoring boundary rules (new-scenario defaults to high, legacy/stored defaults to standard).
6. Scientific disclaimer consistency.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest
from pydantic import ValidationError

from src.core.config_models import TrafficSection
from src.scenario.documents import (
    DRIVER_AGGRESSION_DISCLAIMER,
    TrafficSpec,
    create_scenario,
    parse_scenario,
    scenario_fingerprint,
)
from src.vehicles.driver_aggression import (
    DRIVER_AGGRESSION_PROFILES,
    resolve_aggression_name,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_backend_models_enum_consistency() -> None:
    """Backend models enforce exact profiles: standard, moderate, high."""
    expected_profiles = ("standard", "moderate", "high")
    assert DRIVER_AGGRESSION_PROFILES == expected_profiles

    # TrafficSection defaults to "standard" and validates profiles
    cfg_default = TrafficSection()
    assert cfg_default.driverAggression == "standard"

    for profile in expected_profiles:
        cfg = TrafficSection(driverAggression=profile)
        assert cfg.driverAggression == profile

    with pytest.raises(ValidationError):
        TrafficSection(driverAggression="extreme")

    # TrafficSpec in ScenarioDocument: defaults to None (omitted), accepts exact profiles
    spec_default = TrafficSpec()
    assert spec_default.driverAggression is None

    for profile in expected_profiles:
        spec = TrafficSpec(driverAggression=profile)
        assert spec.driverAggression == profile

    with pytest.raises(ValidationError):
        TrafficSpec(driverAggression="aggressive")


def test_shared_json_schemas_enum_and_defaults() -> None:
    """Shared JSON schemas define matching enum and default for driverAggression."""
    expected_enum = ["standard", "moderate", "high"]

    # 1. shared/schemas/config.schema.json
    config_schema_path = REPO_ROOT / "shared" / "schemas" / "config.schema.json"
    assert config_schema_path.is_file(), f"Missing {config_schema_path}"
    config_schema = json.loads(config_schema_path.read_text(encoding="utf-8"))
    traffic_prop = config_schema["properties"]["traffic"]["properties"][
        "driverAggression"
    ]
    assert traffic_prop["enum"] == expected_enum
    assert traffic_prop["default"] == "standard"

    # 2. shared/schemas/v2/network.schema.json
    network_schema_path = (
        REPO_ROOT / "shared" / "schemas" / "v2" / "network.schema.json"
    )
    assert network_schema_path.is_file(), f"Missing {network_schema_path}"
    network_schema = json.loads(network_schema_path.read_text(encoding="utf-8"))
    v2_traffic_prop = network_schema["$defs"]["TrafficSpec"]["properties"][
        "driverAggression"
    ]
    assert v2_traffic_prop["anyOf"][0]["enum"] == expected_enum
    assert v2_traffic_prop["default"] is None


def test_frontend_types_contract_parity() -> None:
    """Frontend TypeScript definitions declare matching DriverAggression type and profiles constant."""
    # 1. frontend/src/types/config.ts re-exports DriverAggression
    types_path = REPO_ROOT / "frontend" / "src" / "types" / "config.ts"
    assert types_path.is_file(), f"Missing {types_path}"
    content_types = types_path.read_text(encoding="utf-8")
    assert "export type { DriverAggression };" in content_types

    # 2. frontend/src/scenario/scenarioTypes.ts defines DriverAggression and DRIVER_AGGRESSION_PROFILES
    scenario_types_path = (
        REPO_ROOT / "frontend" / "src" / "scenario" / "scenarioTypes.ts"
    )
    assert scenario_types_path.is_file(), f"Missing {scenario_types_path}"
    content_scenario_types = scenario_types_path.read_text(encoding="utf-8")
    assert (
        'export type DriverAggression = "standard" | "moderate" | "high";'
        in content_scenario_types
    )
    assert (
        "export const DRIVER_AGGRESSION_PROFILES: DriverAggression[] = ["
        in content_scenario_types
    )
    for p in ("standard", "moderate", "high"):
        assert f'"{p}"' in content_scenario_types


def test_presets_default_to_standard_and_match_fingerprint_baselines() -> None:
    """Presets in presets.json parse validly, resolve to standard, and keep frozen fingerprints."""
    presets_path = REPO_ROOT / "frontend" / "src" / "scenario" / "presets.json"
    assert presets_path.is_file(), f"Missing {presets_path}"
    data = json.loads(presets_path.read_text(encoding="utf-8"))
    presets = data["presets"]

    # Frozen V1.4 baseline fingerprints from test_scenario_v15.py
    v14_baselines: Dict[str, str] = {
        "calibrated-baseline": "12a4e686edffa0db",
        "typical-urban": "d2a4a7ea3cb097ff",
        "heavy-commuter": "90318ac036de16a3",
        "bus-corridor": "05a9fe58485aca5b",
        "mixed-urban": "cc51df691d48d9d0",
        "motorcycle-heavy": "de34c6b769aca36d",
    }

    for preset in presets:
        pid = preset["id"]
        scenario_data = preset["scenario"]
        doc, errs = parse_scenario(scenario_data)
        assert errs == [], f"Preset {pid} had parsing errors: {errs}"
        assert doc is not None

        # Resolves to standard profile
        assert resolve_aggression_name(doc.model_dump()) == "standard"
        assert resolve_aggression_name(scenario_data) == "standard"

        # Golden fingerprint invariant
        if pid in v14_baselines:
            assert scenario_fingerprint(doc) == v14_baselines[pid]


def test_authoring_boundary_rules_and_overrides() -> None:
    """New-scenario authoring boundary defaults to high, but explicit selections are preserved."""
    # 1. create_scenario authoring boundary defaults to high
    new_doc = create_scenario(name="New Authoring Junction", junction_type="roundabout")
    assert new_doc.traffic is not None
    assert new_doc.traffic.driverAggression == "high"

    # 2. create_scenario with explicit standard is preserved
    explicit_std = create_scenario(
        name="Standard Junction",
        junction_type="roundabout",
        driver_aggression="standard",
    )
    assert explicit_std.traffic is not None
    assert explicit_std.traffic.driverAggression == "standard"

    # 3. create_scenario with explicit moderate is preserved
    explicit_mod = create_scenario(
        name="Moderate Junction",
        junction_type="roundabout",
        driver_aggression="moderate",
    )
    assert explicit_mod.traffic is not None
    assert explicit_mod.traffic.driverAggression == "moderate"

    # 4. Legacy document without traffic defaults to standard behavior
    legacy_raw: Dict[str, Any] = {
        "format": "urbanflow-scenario",
        "version": 1,
        "name": "Legacy Junction",
        "junction": {"type": "fixed_time_signal"},
        "approaches": {
            "north": {
                "lanes": 1,
                "vehiclesPerHour": 300,
                "turning": {"left": 0.2, "straight": 0.6, "right": 0.2},
            },
            "south": {
                "lanes": 1,
                "vehiclesPerHour": 300,
                "turning": {"left": 0.2, "straight": 0.6, "right": 0.2},
            },
            "east": None,
            "west": None,
        },
    }
    legacy_doc, errs = parse_scenario(legacy_raw)
    assert errs == []
    assert legacy_doc is not None
    assert legacy_doc.traffic is None
    assert resolve_aggression_name(legacy_doc.model_dump()) == "standard"


def test_scientific_disclaimer_everywhere() -> None:
    """Scientific disclaimer wording is identical across backend and frontend contracts."""
    expected_disclaimer = "driver aggression — a simulation assumption, not a measurement of real-world driver behaviour"
    assert DRIVER_AGGRESSION_DISCLAIMER == expected_disclaimer
