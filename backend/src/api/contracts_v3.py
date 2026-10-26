"""API Route Signatures and Contract Models for UrbanFlow V3 Stages 1–4.

Codifies route paths, HTTP methods, status codes, request/response models,
and OpenAPI metadata per W7 Readiness Audit & Execution Plan (Stage 0).

Routes codified here are implemented in Stages 1–4; this module acts as the
shared contract source of truth ensuring alignment across backend services,
OpenAPI contracts, and the Python SDK.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Tuple, Type

from pydantic import BaseModel, ConfigDict, Field

from src.api.auth import PatScope

# ── Stage 1: Personal Access Tokens (PATs) ───────────────────────────────────


class CreateTokenRequest(BaseModel):
    """Request payload for POST /api/v3/tokens."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        ..., min_length=1, max_length=120, description="Human-readable token name"
    )
    scopes: List[PatScope] = Field(
        ..., min_length=1, description="Requested permissions"
    )
    expiresInDays: int = Field(
        30, ge=1, le=90, description="Validity period (default 30d, max 90d)"
    )


class TokenCreatedResponse(BaseModel):
    """Response returned once upon POST /api/v3/tokens containing the secret token."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., description="Short token identifier (pat_xxx)")
    name: str
    token: str = Field(
        ..., description="256-bit cryptographically secure secret (shown once)"
    )
    scopes: List[PatScope]
    createdAt: str
    expiresAt: str


class TokenMetadata(BaseModel):
    """Masked token metadata returned by GET /api/v3/tokens."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    scopes: List[PatScope]
    createdAt: str
    expiresAt: str
    lastUsedAt: Optional[str] = None


class TokenListResponse(BaseModel):
    """Response payload for GET /api/v3/tokens."""

    model_config = ConfigDict(extra="forbid")

    tokens: List[TokenMetadata]


class TokenRevokedResponse(BaseModel):
    """Response payload for DELETE /api/v3/tokens/{token_id}."""

    model_config = ConfigDict(extra="forbid")

    id: str
    revoked: Literal[True] = True


# ── Stage 2: Quota Contracts & Capability Definitions ────────────────────────

PER_TOKEN_REQUESTS_PER_MINUTE_QUOTA = 60
DAILY_SIMULATED_SECONDS_PER_USER_QUOTA = 86_400  # 24 hours of simulated time
MAX_PACKAGE_BYTES_QUOTA = 10 * 1024 * 1024  # 10 MB maximum package size


# ── Stage 3: Cancel and Resume Contracts ─────────────────────────────────────

# Status transitions:
# queued/running -> cancelled
# cancelled -> queued/running (on resume)
# cancelled -> deleted (on delete)
CANCEL_STATUS = "cancelled"


# ── Stage 4: Package Export, Import, and Verification ────────────────────────

ReplayClass = Literal["exact", "comparable", "differs (engine or runtime changed)"]

NORMATIVE_INTEGRITY_STATEMENT = (
    "Integrity is not authenticity: checksums show a package is internally "
    "consistent, not who made it."
)

MAX_UNCOMPRESSED_PACKAGE_BYTES = 50 * 1024 * 1024  # 50 MB decompression bomb limit
MAX_PACKAGE_ENTRY_COUNT = 50  # 50 files max


class PackageVerificationReport(BaseModel):
    """Report returned by POST /api/v3/packages/verify."""

    model_config = ConfigDict(extra="forbid")

    format: Literal["urbanflow-package-verification"] = "urbanflow-package-verification"
    version: Literal[1] = 1
    kind: str
    replayClass: ReplayClass
    internallyConsistent: bool
    integrityNote: str = NORMATIVE_INTEGRITY_STATEMENT
    manifestSummary: Dict[str, Any]
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


# ── Codified Stage 1–4 Route Signatures ──────────────────────────────────────


class RouteSignature(BaseModel):
    """Defines the signature and specification for a planned route."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    method: Literal["GET", "POST", "DELETE", "PUT", "PATCH"]
    path: str
    stage: int
    expected_status: int
    summary: str
    description: str
    required_scope: Optional[PatScope]
    browser_only: bool = False
    request_model: Optional[Type[BaseModel]] = None
    response_model: Optional[Type[BaseModel]] = None


V3_STAGE_ROUTE_SIGNATURES: Tuple[RouteSignature, ...] = (
    # Stage 1: PATs
    RouteSignature(
        method="POST",
        path="/api/v3/tokens",
        stage=1,
        expected_status=201,
        summary="Create a personal access token",
        description="Creates a PAT. Restricted to browser sessions (dev or Cognito JWT). A PAT cannot create a PAT.",
        required_scope=None,
        browser_only=True,
        request_model=CreateTokenRequest,
        response_model=TokenCreatedResponse,
    ),
    RouteSignature(
        method="GET",
        path="/api/v3/tokens",
        stage=1,
        expected_status=200,
        summary="List active personal access tokens",
        description="Returns caller's active, non-revoked PATs with masked secrets and usage timestamps.",
        required_scope=None,
        browser_only=False,
        request_model=None,
        response_model=TokenListResponse,
    ),
    RouteSignature(
        method="DELETE",
        path="/api/v3/tokens/{token_id}",
        stage=1,
        expected_status=200,
        summary="Revoke a personal access token",
        description="Immediately revokes a PAT owned by the caller.",
        required_scope=None,
        browser_only=False,
        request_model=None,
        response_model=TokenRevokedResponse,
    ),
    # Stage 3: Cancel & Resume
    RouteSignature(
        method="POST",
        path="/api/v3/experiments/{experiment_id}/cancel",
        stage=3,
        expected_status=200,
        summary="Cancel a queued or running experiment",
        description="Signals running tasks to stop and marks the experiment cancelled, preserving partial results.",
        required_scope="experiments:run",
        browser_only=False,
        request_model=None,
        response_model=None,
    ),
    RouteSignature(
        method="POST",
        path="/api/v3/experiments/{experiment_id}/resume",
        stage=3,
        expected_status=202,
        summary="Resume a cancelled experiment",
        description="Resumes remaining conditions using deterministic seed rules, reproducing uninterrupted fingerprints.",
        required_scope="experiments:run",
        browser_only=False,
        request_model=None,
        response_model=None,
    ),
    # Stage 4: Package Export and Verification
    RouteSignature(
        method="GET",
        path="/api/v3/experiments/{experiment_id}/package",
        stage=4,
        expected_status=200,
        summary="Export portable experiment package",
        description="Exports experiment archive (.ufpkg ZIP) containing manifest, data, results, and SHA256 checksums.",
        required_scope="packages:read",
        browser_only=False,
        request_model=None,
        response_model=None,
    ),
    RouteSignature(
        method="POST",
        path="/api/v3/packages/verify",
        stage=4,
        expected_status=200,
        summary="Verify uploaded experiment package",
        description="Inspects package integrity and evaluates replay classification without executing simulation code.",
        required_scope="packages:write",
        browser_only=False,
        request_model=None,
        response_model=PackageVerificationReport,
    ),
)
