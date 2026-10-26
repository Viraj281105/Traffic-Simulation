"""Tests for Stage 0 contracts and integration seams (W7, ADR-013, ADR-018).

Verifies:
1. Package manifest extension is backward-compatible with pre-W7 manifests (no version bump, version: 1).
2. Manifest tolerates null for optional fields (kind, sidecars) and applies safe defaults.
3. Strict schema validation (extra='forbid') on known kinds and sidecars.
4. Two-tier verification: structural integrity checks for all kinds; semantic verification for known kinds only.
5. PAT scope vocabulary and scope validation rules.
6. Unified UserIdentity permission model.
7. Audit event vocabulary and detail sanitization (payload and credential redaction).
8. Extensible quota registration seam.
9. Codified Stage 1–4 route signatures.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.api.audit import (
    AUDIT_EVENT_TYPES,
    AuditEvent,
    sanitize_audit_details,
)
from src.api.auth import (
    PAT_SCOPES,
    UserIdentity,
    validate_scopes,
)
from src.api.contracts_v3 import (
    DAILY_SIMULATED_SECONDS_PER_USER_QUOTA,
    MAX_PACKAGE_BYTES_QUOTA,
    NORMATIVE_INTEGRITY_STATEMENT,
    PER_TOKEN_REQUESTS_PER_MINUTE_QUOTA,
    V3_STAGE_ROUTE_SIGNATURES,
    CreateTokenRequest,
    PackageVerificationReport,
    TokenCreatedResponse,
)
from src.experiments import limits
from src.experiments.manifest import (
    DEFAULT_PACKAGE_KIND,
    MANIFEST_FORMAT,
    MANIFEST_VERSION,
    ExperimentManifest,
    SidecarMetadata,
    build_experiment_manifest,
    validate_manifest_semantic,
    validate_manifest_structure,
)
from src.scenario.documents import (
    DRIVER_AGGRESSION_DISCLAIMER,
    create_scenario,
    scenario_fingerprint,
)
from src.vehicles.driver_aggression import compute_aggression_parameter_hash


def _sample_scenario():
    return create_scenario(name="Stage 0 Scenario", driver_aggression="standard")


# ── 1. Manifest Extension & Backward Compatibility ───────────────────────────


def test_manifest_builder_produces_kind_and_sidecars_by_default() -> None:
    doc = _sample_scenario()
    manifest = build_experiment_manifest(
        scenario=doc,
        spec_fingerprint="spec_0123456789abcdef",
        result_fingerprint="res_fedcba9876543210",
    )
    assert manifest["format"] == MANIFEST_FORMAT
    assert manifest["version"] == 1
    assert manifest["kind"] == DEFAULT_PACKAGE_KIND
    assert manifest["sidecars"] == []
    # Fully validates against the schema
    validated = ExperimentManifest.model_validate(manifest)
    assert validated.kind == "robustness_experiment"
    assert validated.sidecars == []


def test_pre_w7_manifest_without_kind_or_sidecars_deserializes_cleanly() -> None:
    """Pre-W7 manifests (no 'kind', no 'sidecars') must deserialize cleanly without error."""
    doc = _sample_scenario()
    pre_w7 = {
        "format": MANIFEST_FORMAT,
        "version": MANIFEST_VERSION,
        "scenarioFingerprint": scenario_fingerprint(doc),
        "specFingerprint": "spec_1111",
        "resultFingerprint": "res_2222",
        "assumptions": {
            "driverAggression": "standard",
            "driverAggressionHash": compute_aggression_parameter_hash("standard"),
            "disclaimer": DRIVER_AGGRESSION_DISCLAIMER,
            "factors": [],
        },
    }
    # Deserializes cleanly and applies defaults
    manifest = ExperimentManifest.model_validate(pre_w7)
    assert manifest.kind == "robustness_experiment"
    assert manifest.sidecars == []
    assert manifest.version == 1

    sem_validated = validate_manifest_semantic(pre_w7)
    assert sem_validated.kind == "robustness_experiment"
    assert sem_validated.sidecars == []


def test_manifest_tolerates_null_optional_fields() -> None:
    """Explicit null/None values for kind and sidecars are accepted and normalized."""
    doc = _sample_scenario()
    payload = {
        "format": MANIFEST_FORMAT,
        "version": MANIFEST_VERSION,
        "kind": None,
        "sidecars": None,
        "scenarioFingerprint": scenario_fingerprint(doc),
        "specFingerprint": "spec_1111",
        "resultFingerprint": "res_2222",
        "assumptions": {
            "driverAggression": "standard",
            "driverAggressionHash": compute_aggression_parameter_hash("standard"),
            "disclaimer": DRIVER_AGGRESSION_DISCLAIMER,
            "factors": [],
        },
    }
    manifest = ExperimentManifest.model_validate(payload)
    assert manifest.kind == "robustness_experiment"
    assert manifest.sidecars == []


def test_manifest_sidecars_validation() -> None:
    """Valid sidecars parse correctly; invalid sidecars or extra properties are rejected."""
    valid_sidecar = {
        "name": "sensitivity_data",
        "kind": "tabular_metrics",
        "path": "sidecars/sensitivity.csv",
        "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    }
    parsed = SidecarMetadata.model_validate(valid_sidecar)
    assert parsed.name == "sensitivity_data"
    assert (
        parsed.sha256
        == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )

    # Reject non-hex or invalid-length sha256
    with pytest.raises(ValidationError):
        SidecarMetadata.model_validate(
            {**valid_sidecar, "sha256": "not-a-valid-sha256"}
        )

    # Reject extra fields on sidecar (extra='forbid')
    with pytest.raises(ValidationError):
        SidecarMetadata.model_validate(
            {**valid_sidecar, "extra_unexpected_field": True}
        )


def test_manifest_rejects_extra_fields_on_known_kind() -> None:
    """Known kinds strictly enforce extra='forbid' per ADR-013."""
    doc = _sample_scenario()
    payload = {
        "format": MANIFEST_FORMAT,
        "version": MANIFEST_VERSION,
        "scenarioFingerprint": scenario_fingerprint(doc),
        "specFingerprint": "spec_1111",
        "resultFingerprint": "res_2222",
        "assumptions": {
            "driverAggression": "standard",
            "driverAggressionHash": compute_aggression_parameter_hash("standard"),
            "disclaimer": DRIVER_AGGRESSION_DISCLAIMER,
            "factors": [],
        },
        "unauthorizedExtraProperty": 12345,
    }
    with pytest.raises(ValidationError):
        ExperimentManifest.model_validate(payload)


# ── 2. Two-Tier Verification: Known vs Unknown Kinds ─────────────────────────


def test_two_tier_verification_structural_accepts_unknown_kind() -> None:
    """Tier 1: Structural checks pass for unknown package kinds without semantic validation."""
    unknown_kind_manifest = {
        "format": MANIFEST_FORMAT,
        "version": MANIFEST_VERSION,
        "kind": "ai_copilot_proposal_v1",  # Unregistered future kind
        "scenarioFingerprint": "fp_scen_123",
        "specFingerprint": "fp_spec_123",
        "resultFingerprint": "fp_res_123",
        "assumptions": {"anything": "arbitrary"},
        "sidecars": [
            {
                "name": "proposal_prompt",
                "kind": "prompt_text",
                "path": "sidecars/prompt.txt",
                "sha256": "a" * 64,
            }
        ],
    }
    # Structural check succeeds
    valid, err = validate_manifest_structure(unknown_kind_manifest)
    assert valid is True
    assert err is None

    # Semantic check fails: unknown kind cannot undergo semantic validation without a registered schema
    with pytest.raises(
        ValueError, match="Unknown package kind 'ai_copilot_proposal_v1'"
    ):
        validate_manifest_semantic(unknown_kind_manifest)


def test_two_tier_verification_structural_catches_corrupted_manifest() -> None:
    """Tier 1: Structural checks reject corrupted formats, missing fingerprints, or bad sidecars."""
    assert validate_manifest_structure("not a dict")[0] is False
    assert validate_manifest_structure({"format": "wrong-format"})[0] is False
    assert (
        validate_manifest_structure({"format": MANIFEST_FORMAT, "version": 99})[0]
        is False
    )
    assert (
        validate_manifest_structure(
            {
                "format": MANIFEST_FORMAT,
                "version": 1,
                "scenarioFingerprint": "fp",
                # missing specFingerprint and resultFingerprint
            }
        )[0]
        is False
    )


# ── 3. PAT Scope Vocabulary & UserIdentity ───────────────────────────────────


def test_pat_scopes_vocabulary() -> None:
    """PAT scopes vocabulary matches exact V3 Product Strategy §7 specification."""
    expected = {
        "experiments:read",
        "experiments:run",
        "packages:read",
        "packages:write",
        "tokens:read",
        "tokens:manage",
    }
    assert PAT_SCOPES == expected
    # Validate valid list
    assert validate_scopes(["experiments:read", "packages:write"]) == [
        "experiments:read",
        "packages:write",
    ]
    # Rejects unauthorized scopes
    with pytest.raises(ValueError, match="Invalid PAT scope"):
        validate_scopes(["admin"])
    with pytest.raises(ValueError, match="Invalid PAT scope"):
        validate_scopes(["experiments:delete"])


def test_unified_user_identity_permissions() -> None:
    """UserIdentity handles dev, cognito, and PAT permission scoping."""
    # Dev and Cognito have full access (all scopes pass)
    dev_user = UserIdentity(user_id="local-dev", auth_type="dev")
    assert dev_user.has_scope("experiments:run") is True
    assert dev_user.has_scope("packages:write") is True

    cognito_user = UserIdentity(user_id="user-uuid-123", auth_type="cognito")
    assert cognito_user.has_scope("experiments:run") is True
    assert cognito_user.has_scope("arbitrary:scope") is True

    # PAT strictly checks granted scopes
    pat_user = UserIdentity(
        user_id="user-uuid-123",
        auth_type="pat",
        token_id="pat_abc123",
        scopes=frozenset({"experiments:read", "packages:read"}),
    )
    assert pat_user.has_scope("experiments:read") is True
    assert pat_user.has_scope("packages:read") is True
    assert pat_user.has_scope("experiments:run") is False
    assert pat_user.has_scope("packages:write") is False


# ── 4. Audit Vocabulary & Redaction ──────────────────────────────────────────


def test_audit_event_types_vocabulary() -> None:
    """Audit event types match exact normative vocabulary."""
    expected = {
        "token_created",
        "token_revoked",
        "experiment_submitted",
        "experiment_cancelled",
        "quota_rejected",
        "auth_failed",
        "package_exported",
        "package_verified",
    }
    assert AUDIT_EVENT_TYPES == expected

    # AuditEvent model validates correctly
    event = AuditEvent(
        timestamp="2026-10-23T12:00:00Z",
        userId="user-123",
        eventType="token_created",
        tokenId="pat_123",
        details={"name": "CLI token", "scopes": ["experiments:read"]},
    )
    assert event.eventType == "token_created"

    with pytest.raises(ValidationError):
        AuditEvent(
            timestamp="2026-10-23T12:00:00Z",
            userId="user-123",
            eventType="invalid_event_type",  # type: ignore[arg-type]
        )


def test_sanitize_audit_details_redacts_credentials_and_payloads() -> None:
    """Audit details sanitize secrets, keys, and payload bodies."""
    raw_details = {
        "quotaName": "maxActiveExperiments",
        "count": 2,
        "token": "uf_pat_secret1234567890",
        "apiKey": "infra-key-xyz",
        "scenario": {"huge": "payload"},
        "nested": {
            "secret_key": "sensitive",
            "safe_property": 42,
        },
    }
    sanitized = sanitize_audit_details(raw_details)
    assert sanitized["quotaName"] == "maxActiveExperiments"
    assert sanitized["count"] == 2
    assert sanitized["token"] == "[REDACTED]"
    assert sanitized["apiKey"] == "[REDACTED]"
    assert sanitized["scenario"] == "[REDACTED]"
    assert sanitized["nested"]["secret_key"] == "[REDACTED]"
    assert sanitized["nested"]["safe_property"] == 42


# ── 5. Extensible Quota Seam ─────────────────────────────────────────────────


def test_extensible_quota_seam() -> None:
    """Base quotas remain unchanged, and extension quotas register dynamically."""
    current_quotas = limits.quotas()
    assert current_quotas["maxActiveExperiments"] == limits.MAX_ACTIVE_EXPERIMENTS
    assert current_quotas["maxAlternatives"] == limits.MAX_ALTERNATIVES

    # Register an extension quota (e.g. simulated future W5 AI quota)
    limits.register_quota("maxDailyAiProposals", 50, "aiProposals")
    updated = limits.quotas()
    assert updated["maxDailyAiProposals"] == 50
    assert limits.QUOTA_NAMES["aiProposals"] == "maxDailyAiProposals"
    # Clean up test registration
    limits._EXTENSION_QUOTAS.pop("maxDailyAiProposals", None)
    limits.QUOTA_NAMES.pop("aiProposals", None)


# ── 6. Codified Route Signatures for Stages 1–4 ──────────────────────────────


def test_codified_stage_route_signatures() -> None:
    """Route signatures for Stages 1–4 are codified with status codes and models."""
    routes = {(r.method, r.path): r for r in V3_STAGE_ROUTE_SIGNATURES}

    # Verify Stage 1 PAT routes
    assert ("POST", "/api/v3/tokens") in routes
    tokens_post = routes[("POST", "/api/v3/tokens")]
    assert tokens_post.method == "POST"
    assert tokens_post.stage == 1
    assert tokens_post.expected_status == 201
    assert tokens_post.browser_only is True
    assert tokens_post.request_model is CreateTokenRequest
    assert tokens_post.response_model is TokenCreatedResponse

    assert ("GET", "/api/v3/tokens") in routes
    tokens_get = routes[("GET", "/api/v3/tokens")]
    assert tokens_get.stage == 1
    assert tokens_get.expected_status == 200

    assert ("DELETE", "/api/v3/tokens/{token_id}") in routes
    tokens_delete = routes[("DELETE", "/api/v3/tokens/{token_id}")]
    assert tokens_delete.stage == 1
    assert tokens_delete.expected_status == 200

    # Verify Stage 3 Cancel & Resume routes
    assert ("POST", "/api/v3/experiments/{experiment_id}/cancel") in routes
    cancel_route = routes[("POST", "/api/v3/experiments/{experiment_id}/cancel")]
    assert cancel_route.method == "POST"
    assert cancel_route.stage == 3
    assert cancel_route.expected_status == 200
    assert cancel_route.required_scope == "experiments:run"

    assert ("POST", "/api/v3/experiments/{experiment_id}/resume") in routes
    resume_route = routes[("POST", "/api/v3/experiments/{experiment_id}/resume")]
    assert resume_route.method == "POST"
    assert resume_route.stage == 3
    assert resume_route.expected_status == 202
    assert resume_route.required_scope == "experiments:run"

    # Verify Stage 4 Package routes
    assert ("GET", "/api/v3/experiments/{experiment_id}/package") in routes
    pkg_route = routes[("GET", "/api/v3/experiments/{experiment_id}/package")]
    assert pkg_route.method == "GET"
    assert pkg_route.stage == 4
    assert pkg_route.expected_status == 200
    assert pkg_route.required_scope == "packages:read"

    assert ("POST", "/api/v3/packages/verify") in routes
    verify_route = routes[("POST", "/api/v3/packages/verify")]
    assert verify_route.method == "POST"
    assert verify_route.stage == 4
    assert verify_route.expected_status == 200
    assert verify_route.required_scope == "packages:write"
    assert verify_route.response_model is PackageVerificationReport

    # Verify Stage 2 Quota constants
    assert PER_TOKEN_REQUESTS_PER_MINUTE_QUOTA == 60
    assert DAILY_SIMULATED_SECONDS_PER_USER_QUOTA == 86_400
    assert MAX_PACKAGE_BYTES_QUOTA == 10 * 1024 * 1024
    assert "Integrity is not authenticity" in NORMATIVE_INTEGRITY_STATEMENT
