"""Experiment reproducibility manifest (V3.0 Product Strategy §6, ADR-013, ADR-016).

Every experiment result, and every .ufpkg, carries an urbanflow-experiment-manifest (v1).
The manifest's assumptions block records:
- Resolved driverAggression profile name (e.g. 'standard', 'moderate', 'high').
- The parameter set hash (16-hex SHA-256) of the resolved multipliers and invariants.
- The required scientific disclaimer.
- The declared uncertainty factor assumptions with their distributions, bounds, basis, and rationales.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Sequence

from src.scenario.documents import ScenarioDocument, scenario_fingerprint
from src.uncertainty.spec import Factor
from src.vehicles.driver_aggression import (
    DRIVER_AGGRESSION_DISCLAIMER,
    compute_aggression_parameter_hash,
    resolve_aggression_name,
)

MANIFEST_FORMAT = "urbanflow-experiment-manifest"
MANIFEST_VERSION = 1


def build_manifest_assumptions(
    scenario: ScenarioDocument,
    factors: Sequence[Factor] = (),
) -> Dict[str, Any]:
    """Build the assumptions block for an experiment manifest.

    Records the resolved driver aggression profile and its parameter hash,
    the scientific disclaimer, and factor assumptions.
    """
    profile = resolve_aggression_name(scenario.model_dump())
    param_hash = compute_aggression_parameter_hash(profile)
    return {
        "driverAggression": profile,
        "driverAggressionHash": param_hash,
        "disclaimer": DRIVER_AGGRESSION_DISCLAIMER,
        "factors": [
            {
                "id": f.id,
                "kind": f.kind,
                "distribution": f.distribution.model_dump(
                    mode="json", exclude_none=True
                ),
                "bounds": f.bounds,
                "basis": f.basis,
                "rationale": f.rationale,
            }
            for f in factors
        ],
    }


def build_experiment_manifest(
    *,
    scenario: ScenarioDocument,
    spec_fingerprint: str,
    result_fingerprint: str,
    factors: Sequence[Factor] = (),
    extra: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Build an urbanflow-experiment-manifest v1 document."""
    doc: Dict[str, Any] = {
        "format": MANIFEST_FORMAT,
        "version": MANIFEST_VERSION,
        "scenarioFingerprint": scenario_fingerprint(scenario),
        "specFingerprint": spec_fingerprint,
        "resultFingerprint": result_fingerprint,
        "assumptions": build_manifest_assumptions(scenario, factors),
    }
    if extra:
        doc.update(extra)
    return doc
