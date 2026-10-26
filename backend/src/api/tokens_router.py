"""Personal Access Token (PAT) routes (W7 Stage 1 / ADR-013 / ADR-018).

Provides:
- POST /api/v3/tokens: Create a PAT (restricted to browser sessions).
- GET /api/v3/tokens: List active PATs for current user.
- DELETE /api/v3/tokens/{token_id}: Immediately revoke a PAT.

Adheres to ADR-018: routers hold no SQL; persistence belongs in TokenStore / AuditStore.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Body, Depends, HTTPException, status

from src.api.auth import (
    UserIdentity,
    require_browser_session,
    require_scope,
    validate_scopes,
)
from src.api.contracts_v3 import (
    CreateTokenRequest,
    TokenCreatedResponse,
    TokenListResponse,
    TokenMetadata,
    TokenRevokedResponse,
)
from src.api.store import (
    MAX_ACTIVE_TOKENS_PER_USER,
    AuditStore,
    TokenStore,
)

logger = logging.getLogger(__name__)

PREFIX = "/api/v3"
router = APIRouter(prefix=PREFIX, tags=["tokens-v3"])


@router.post(
    "/tokens",
    status_code=status.HTTP_201_CREATED,
    response_model=TokenCreatedResponse,
    summary="Create a personal access token",
    description="Creates a PAT. Restricted to browser sessions (dev or Cognito JWT). A PAT cannot create a PAT.",
)
def create_token(
    payload: CreateTokenRequest = Body(...),
    identity: UserIdentity = Depends(require_browser_session),
) -> TokenCreatedResponse:
    """Create a new personal access token with cryptographically secure secret shown once."""
    try:
        validate_scopes(payload.scopes)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e

    try:
        metadata, raw_secret = TokenStore.create_token(
            user_id=identity.user_id,
            name=payload.name,
            scopes=payload.scopes,
            expires_in_days=payload.expiresInDays,
        )
    except RuntimeError as err:
        AuditStore.record_event(
            user_id=identity.user_id,
            event_type="quota_rejected",
            token_id=None,
            details={"quota": "active_pats", "limit": MAX_ACTIVE_TOKENS_PER_USER},
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(err)
        ) from err
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(err)
        ) from err

    AuditStore.record_event(
        user_id=identity.user_id,
        event_type="token_created",
        token_id=metadata["id"],
        details={
            "token_id": metadata["id"],
            "name": metadata["name"],
            "scopes": metadata["scopes"],
            "expires_in_days": payload.expiresInDays,
        },
    )

    return TokenCreatedResponse(
        id=metadata["id"],
        name=metadata["name"],
        token=raw_secret,
        scopes=metadata["scopes"],
        createdAt=metadata["createdAt"],
        expiresAt=metadata["expiresAt"],
    )


@router.get(
    "/tokens",
    status_code=status.HTTP_200_OK,
    response_model=TokenListResponse,
    summary="List active personal access tokens",
    description="Returns caller's active, non-revoked PATs with usage timestamps. Browser sessions, or a PAT with the tokens:read scope.",
)
def list_tokens(
    identity: UserIdentity = Depends(require_scope("tokens:read")),
) -> TokenListResponse:
    """List caller's active tokens with metadata (no raw secrets)."""
    tokens = TokenStore.list_active(identity.user_id)
    return TokenListResponse(tokens=[TokenMetadata(**t) for t in tokens])


@router.delete(
    "/tokens/{token_id}",
    status_code=status.HTTP_200_OK,
    response_model=TokenRevokedResponse,
    summary="Revoke a personal access token",
    description="Immediately revokes a PAT owned by the caller. Browser sessions, or a PAT with the tokens:manage scope.",
)
def revoke_token(
    token_id: str,
    identity: UserIdentity = Depends(require_scope("tokens:manage")),
) -> TokenRevokedResponse:
    """Revoke a token immediately. Returns 404 if not found or not owned."""
    revoked = TokenStore.revoke(token_id=token_id, user_id=identity.user_id)
    if revoked is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Token not found"
        )

    AuditStore.record_event(
        user_id=identity.user_id,
        event_type="token_revoked",
        token_id=token_id,
        details={"token_id": token_id, "name": revoked["name"]},
    )

    return TokenRevokedResponse(id=token_id, revoked=True)
