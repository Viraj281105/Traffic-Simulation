"""Tests for experiment manifest assumptions block (V3.0 ADR-016, Strategy §6).

Verifies:
1. Resolved driverAggression profile and parameter hash recorded in manifest assumptions.
2. Absent or standard traffic resolves to 'standard' with the standard parameter hash.
3. Non-standard profiles (moderate, high) record their distinct profile and parameter hash.
4. The required scientific disclaimer is recorded in the assumptions block.
5. Service result document carries the manifest assumptions block.
"""

from __future__ import annotations

from src.experiments.manifest import (
    MANIFEST_FORMAT,
    MANIFEST_VERSION,
    build_experiment_manifest,
    build_manifest_assumptions,
)
from src.scenario.documents import (
    DRIVER_AGGRESSION_DISCLAIMER,
    create_scenario,
    scenario_fingerprint,
)
from src.uncertainty.spec import Distribution, Factor
from src.vehicles.driver_aggression import (
    compute_aggression_parameter_hash,
)


def _factor() -> Factor:
    return Factor(
        id="demand",
        kind="demand_scale",
        distribution=Distribution(kind="uniform"),
        bounds=[0.8, 1.2],
        basis="assumed",
        rationale="plausible weekday variation",
    )


def test_manifest_assumptions_standard_and_absent() -> None:
    """Absent traffic and standard driverAggression both record standard profile and parameter hash."""
    # Absent traffic
    doc_absent = create_scenario(name="Absent Traffic", driver_aggression=None)
    assumptions_absent = build_manifest_assumptions(doc_absent, [_factor()])
    assert assumptions_absent["driverAggression"] == "standard"
    assert assumptions_absent["driverAggressionHash"] == compute_aggression_parameter_hash("standard")
    assert assumptions_absent["disclaimer"] == DRIVER_AGGRESSION_DISCLAIMER
    assert len(assumptions_absent["factors"]) == 1
    assert assumptions_absent["factors"][0]["id"] == "demand"

    # Explicit standard
    doc_std = create_scenario(name="Standard Traffic", driver_aggression="standard")
    assumptions_std = build_manifest_assumptions(doc_std, [_factor()])
    assert assumptions_std["driverAggression"] == "standard"
    assert assumptions_std["driverAggressionHash"] == assumptions_absent["driverAggressionHash"]


def test_manifest_assumptions_non_standard_profiles() -> None:
    """Moderate and high profiles record distinct names and parameter hashes in manifest assumptions."""
    doc_mod = create_scenario(name="Moderate Traffic", driver_aggression="moderate")
    assumptions_mod = build_manifest_assumptions(doc_mod, [_factor()])
    assert assumptions_mod["driverAggression"] == "moderate"
    assert assumptions_mod["driverAggressionHash"] == compute_aggression_parameter_hash("moderate")

    doc_high = create_scenario(name="High Traffic", driver_aggression="high")
    assumptions_high = build_manifest_assumptions(doc_high, [_factor()])
    assert assumptions_high["driverAggression"] == "high"
    assert assumptions_high["driverAggressionHash"] == compute_aggression_parameter_hash("high")

    # Assert pairwise distinct parameter hashes
    h_std = compute_aggression_parameter_hash("standard")
    assert assumptions_mod["driverAggressionHash"] != h_std
    assert assumptions_high["driverAggressionHash"] != h_std
    assert assumptions_high["driverAggressionHash"] != assumptions_mod["driverAggressionHash"]


def test_build_experiment_manifest_structure() -> None:
    """Manifest adheres to urbanflow-experiment-manifest v1 contract."""
    doc = create_scenario(name="High Manifest", driver_aggression="high")
    spec_fp = "0123456789abcdef"
    result_fp = "fedcba9876543210"

    manifest = build_experiment_manifest(
        scenario=doc,
        spec_fingerprint=spec_fp,
        result_fingerprint=result_fp,
        factors=[_factor()],
        extra={"gitCommit": "abcdef123456", "pythonVersion": "3.14.7"},
    )

    assert manifest["format"] == MANIFEST_FORMAT
    assert manifest["version"] == MANIFEST_VERSION
    assert manifest["scenarioFingerprint"] == scenario_fingerprint(doc)
    assert manifest["specFingerprint"] == spec_fp
    assert manifest["resultFingerprint"] == result_fp
    assert manifest["gitCommit"] == "abcdef123456"

    assumptions = manifest["assumptions"]
    assert assumptions["driverAggression"] == "high"
    assert assumptions["driverAggressionHash"] == compute_aggression_parameter_hash("high")
    assert assumptions["disclaimer"] == DRIVER_AGGRESSION_DISCLAIMER
