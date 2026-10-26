import datetime
import json
import logging
import os
import threading
import time
from datetime import timezone
from typing import Any, Callable, Dict, List, Literal, Optional, Sequence, cast

import requests
from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwk, jwt
from jose.utils import base64url_decode
from pydantic import BaseModel, ConfigDict, Field

from src.api.request_limits import client_key
from src.api.token_store import AuditStore, TokenStore, hash_token_secret
from src.database.dao import UserDAO
from src.database.db import get_db_connection

# ── Personal Access Token (PAT) Scopes and Unified Identity (W7 / ADR-013) ───
PAT_SCOPES: frozenset[str] = frozenset(
    {
        "experiments:read",
        "experiments:run",
        "packages:read",
        "packages:write",
        "tokens:read",
        "tokens:manage",
    }
)
PatScope = Literal[
    "experiments:read",
    "experiments:run",
    "packages:read",
    "packages:write",
    "tokens:read",
    "tokens:manage",
]


def validate_scopes(requested_scopes: Sequence[str]) -> List[str]:
    """Validate requested PAT scopes against the allowed vocabulary."""
    invalid = set(requested_scopes) - PAT_SCOPES
    if invalid:
        raise ValueError(
            f"Invalid PAT scope(s): {', '.join(sorted(invalid))}. "
            f"Allowed scopes: {', '.join(sorted(PAT_SCOPES))}"
        )
    return list(requested_scopes)


class UserIdentity(BaseModel):
    """Unified caller identity across Cognito JWT, dev bypass, and PAT auth."""

    model_config = ConfigDict(extra="forbid")

    user_id: str
    auth_type: Literal["dev", "cognito", "pat"]
    token_id: Optional[str] = None
    scopes: frozenset[str] = Field(default_factory=frozenset)

    def has_scope(self, scope: str) -> bool:
        """Browser sessions (dev and cognito) hold full interactive permissions; PATs must match scope."""
        if self.auth_type in ("dev", "cognito"):
            return True
        return scope in self.scopes


security = HTTPBearer()
# Same scheme, but an absent Authorization header yields None instead of 401.
optional_security = HTTPBearer(auto_error=False)

# Load from .env if variables are not set
try:
    env_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "backend", ".env")
    )
    if not os.path.exists(env_path):
        env_path = ".env"
    with open(env_path) as f:
        for line in f:
            if line.strip() and not line.startswith("#"):
                key, val = line.strip().split("=", 1)
                if key not in os.environ:
                    os.environ[key] = val
except Exception:
    pass

REGION = os.getenv("AWS_REGION", "us-east-1")
USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID", "")
CLIENT_ID = os.getenv("COGNITO_CLIENT_ID", "")

# Comma-separated list of emails that are treated as admins, e.g.
# ADMIN_EMAILS=alice@example.com,bob@example.com
# All comparisons are lower-cased so casing doesn't matter.
_ADMIN_EMAILS_RAW = os.getenv("ADMIN_EMAILS", "")
ADMIN_EMAILS: frozenset[str] = frozenset(
    e.strip().lower() for e in _ADMIN_EMAILS_RAW.split(",") if e.strip()
)

# The only algorithm a Cognito user-pool token is accepted with.
_TOKEN_ALGORITHM = "RS256"

# Cache the keys so we don't fetch them on every request
_JWKS_CACHE = None

# ── Local development auth bypass ──────────────────────────────────────────
# Cognito is not connected in local development. The Vite dev server sends
# DEV_AUTH_TOKEN as its bearer token (frontend/src/auth/cognito.ts); it is
# accepted here only when the backend is started with DEV_AUTH_BYPASS=1
# (docker-compose.dev.yml does; docker-compose.yml, the
# production stack, does not), and then stands for one clearly local
# identity, DEV_AUTH_CLAIMS. Every other token takes the Cognito path
# unchanged, and without the flag the marker is refused.
DEV_AUTH_TOKEN = "urbanflow-local-dev"
DEV_AUTH_CLAIMS: Dict[str, Any] = {"sub": "local-dev", "email": ""}


def dev_auth_bypass_enabled() -> bool:
    """True only when DEV_AUTH_BYPASS is explicitly switched on. Read per
    request, so nothing at import time can leave it on."""
    return os.getenv("DEV_AUTH_BYPASS", "").strip().lower() in {"1", "true", "yes"}


def get_jwks() -> List[Dict[str, Any]]:
    global _JWKS_CACHE
    if _JWKS_CACHE is None:
        if not USER_POOL_ID or not REGION:
            raise ValueError("COGNITO_USER_POOL_ID or AWS_REGION is not set")

        keys_url = f"https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}/.well-known/jwks.json"
        response = requests.get(keys_url, timeout=10)
        response.raise_for_status()
        _JWKS_CACHE = response.json()["keys"]
    return cast(List[Dict[str, Any]], _JWKS_CACHE)


# ── Failed authentication rate limiting ──────────────────────────────────────
_AUTH_FAILURES_LOCK = threading.Lock()
_AUTH_FAILURES: Dict[str, List[float]] = {}
MAX_AUTH_FAILURES = 10
AUTH_FAILURE_WINDOW_SECONDS = 60.0


def record_auth_failure(key: str) -> int:
    """Record a failed authentication attempt for brute-force mitigation.

    Returns the number of failures now inside the window."""
    now = time.time()
    with _AUTH_FAILURES_LOCK:
        failures = _AUTH_FAILURES.setdefault(key, [])
        cutoff = now - AUTH_FAILURE_WINDOW_SECONDS
        pruned = [t for t in failures if t > cutoff]
        pruned.append(now)
        _AUTH_FAILURES[key] = pruned
        return len(pruned)


def _fail_auth(
    key: str,
    reason: str,
    detail: str,
    *,
    user_id: Optional[str] = None,
    token_id: Optional[str] = None,
) -> HTTPException:
    """Count a failed authentication, audit it, and return the 401 to raise.

    A failure that names a real token (revoked, expired) is audited against its
    owner. Anything else carries no trustworthy identity and is unbounded
    attacker-controlled input, so it is audited once per lockout, when the
    client reaches the failure limit, instead of per request. No credential
    value is ever written.
    """
    count = record_auth_failure(key)
    if user_id is not None or count == MAX_AUTH_FAILURES:
        try:
            AuditStore.record_event(
                user_id=user_id or "unknown",
                event_type="auth_failed",
                token_id=token_id,
                details={
                    "reason": reason if user_id is not None else "rate_limit_reached",
                    "client_ip": key,
                },
            )
        except Exception:
            logging.getLogger(__name__).warning("auth audit failed", exc_info=True)
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def is_auth_rate_limited(key: str) -> bool:
    """Check if the client has exceeded the failed authentication limit."""
    now = time.time()
    with _AUTH_FAILURES_LOCK:
        failures = _AUTH_FAILURES.get(key, [])
        cutoff = now - AUTH_FAILURE_WINDOW_SECONDS
        recent = [t for t in failures if t > cutoff]
        _AUTH_FAILURES[key] = recent
        return len(recent) >= MAX_AUTH_FAILURES


def reset_auth_failures() -> None:
    """Clear failed authentication tracking. Intended for test fixtures."""
    with _AUTH_FAILURES_LOCK:
        _AUTH_FAILURES.clear()


def verify_cognito_jwt(token: str) -> Dict[str, Any]:
    """Verify an RS256 Cognito user pool JWT and return its claims."""
    if not USER_POOL_ID:
        raise HTTPException(
            status_code=500, detail="Cognito User Pool ID not configured on server"
        )

    try:
        headers = jwt.get_unverified_headers(token)
        if headers.get("alg") != _TOKEN_ALGORITHM:
            raise HTTPException(status_code=401, detail="Unsupported token algorithm")
        kid = headers.get("kid")

        keys = get_jwks()
        key_index = -1
        for i in range(len(keys)):
            if kid == keys[i]["kid"]:
                key_index = i
                break

        if key_index == -1:
            raise HTTPException(
                status_code=401, detail="Public key not found in jwks.json"
            )

        public_key = jwk.construct(keys[key_index], algorithm=_TOKEN_ALGORITHM)

        message, encoded_signature = str(token).rsplit(".", 1)
        decoded_signature = base64url_decode(encoded_signature.encode("utf-8"))

        if not public_key.verify(message.encode("utf8"), decoded_signature):
            raise HTTPException(status_code=401, detail="Signature verification failed")

        claims = jwt.get_unverified_claims(token)
        if time.time() > claims["exp"]:
            raise HTTPException(status_code=401, detail="Token is expired")

        if claims.get("aud") != CLIENT_ID and claims.get("client_id") != CLIENT_ID:
            raise HTTPException(
                status_code=401, detail="Token was not issued for this audience"
            )

        return cast(Dict[str, Any], claims)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Authentication error: {str(e)}")


def verify_token(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> Dict[str, Any]:
    token = credentials.credentials
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing"
        )

    if token == DEV_AUTH_TOKEN:
        if dev_auth_bypass_enabled():
            return dict(DEV_AUTH_CLAIMS)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Development auth token rejected: DEV_AUTH_BYPASS is not "
            "enabled on this server",
        )

    return verify_cognito_jwt(token)


def get_current_identity(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(optional_security),
) -> UserIdentity:
    """Unified user authentication resolving into UserIdentity (W7 Stage 1).

    Extracts bearer token from Authorization: Bearer <TOKEN>.
    Resolves caller into:
    - dev bypass: UserIdentity(user_id='local-dev', auth_type='dev', scopes=all)
    - PAT (uf_pat_...): UserIdentity(user_id=row['user_id'], auth_type='pat', token_id=row['id'], scopes=row['scopes'])
    - Cognito JWT: UserIdentity(user_id=sub, auth_type='cognito', scopes=all)
    """
    key = client_key(request)
    if is_auth_rate_limited(key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many invalid authentication attempts; try again later",
        )

    # This dependency is the protected authentication boundary, so a request
    # that reaches it without a credential is a failed attempt like any other.
    if credentials is None or not credentials.credentials.strip():
        raise _fail_auth(key, "missing_credentials", "Token missing")

    token = credentials.credentials.strip()

    # 1. Dev auth bypass
    if token == DEV_AUTH_TOKEN:
        if dev_auth_bypass_enabled():
            return UserIdentity(
                user_id="local-dev",
                auth_type="dev",
                token_id=None,
                scopes=PAT_SCOPES,
            )
        raise _fail_auth(
            key,
            "dev_token_rejected",
            "Development auth token rejected: DEV_AUTH_BYPASS is not enabled on this server",
        )

    # 2. Personal Access Token (PAT)
    if token.startswith("uf_pat_"):
        token_hash = hash_token_secret(token)
        row = TokenStore.get_by_hash(token_hash)
        if row is None:
            raise _fail_auth(key, "unknown_token", "Invalid token")

        owner = {"user_id": row["user_id"], "token_id": row["id"]}
        if row.get("revoked_at") is not None:
            raise _fail_auth(
                key, "revoked_token", "Token has been revoked", **owner
            )

        try:
            expires_at = datetime.datetime.fromisoformat(row["expires_at"])
            expired = datetime.datetime.now(timezone.utc) > expires_at
        except Exception:
            raise _fail_auth(
                key,
                "expiry_invalid",
                "Token expiry validation failed",
                **owner,
            )
        if expired:
            raise _fail_auth(key, "expired_token", "Token is expired", **owner)

        TokenStore.touch_last_used(row["id"])
        scopes = json.loads(row["scopes_json"])
        return UserIdentity(
            user_id=row["user_id"],
            auth_type="pat",
            token_id=row["id"],
            scopes=frozenset(scopes),
        )

    # 3. Cognito JWT
    try:
        claims = verify_cognito_jwt(token)
    except HTTPException as err:
        if err.status_code == status.HTTP_401_UNAUTHORIZED:
            raise _fail_auth(key, "invalid_jwt", str(err.detail)) from err
        raise
    except Exception as e:
        raise _fail_auth(
            key, "invalid_jwt", f"Authentication error: {str(e)}"
        ) from e

    sub = _subject(claims)
    upsert_user(claims)
    return UserIdentity(
        user_id=sub,
        auth_type="cognito",
        token_id=None,
        scopes=PAT_SCOPES,
    )


def require_scope(scope: PatScope) -> Callable[..., UserIdentity]:
    """FastAPI dependency factory asserting that caller identity holds the required scope."""

    def _scope_guard(
        identity: UserIdentity = Depends(get_current_identity),
    ) -> UserIdentity:
        if not identity.has_scope(scope):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient token scope",
            )
        return identity

    return _scope_guard


def require_browser_session(
    identity: UserIdentity = Depends(get_current_identity),
) -> UserIdentity:
    """FastAPI dependency restricting an operation to interactive browser sessions (dev or Cognito).

    A request presenting a PAT is rejected with HTTP 403 ('A PAT cannot create a PAT').
    """
    if identity.auth_type == "pat":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A PAT cannot create a PAT",
        )
    return identity


def _subject(claims: Dict[str, Any]) -> str:
    """The token's ``sub``. A verified token without one names nobody, and an
    empty id would match every unowned record, so it is refused."""
    sub = str(claims.get("sub") or "").strip()
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has no subject"
        )
    return sub


def get_current_user_id(claims: Dict[str, Any] = Security(verify_token)) -> str:
    """Returns the Cognito username (sub) from the token."""
    return _subject(claims)


def get_current_user_email(claims: Dict[str, Any] = Security(verify_token)) -> str:
    """Returns the user's email from the token."""
    return str(claims.get("email", ""))


def upsert_user(claims: Dict[str, Any]) -> None:
    """Upsert the authenticated user into the local ``users`` table.

    Called after every successful token verification so the DB always
    reflects who has logged in.  The ``sub`` claim is the immutable
    Cognito identifier and acts as the primary key.

    This is a no-op for the local dev bypass (sub == 'local-dev').
    """
    sub = str(claims.get("sub", ""))
    if not sub or sub == "local-dev":
        return

    email = str(claims.get("email", ""))
    # Cognito stores the human login name in ``cognito:username``; fall back to
    # ``preferred_username`` then the sub itself.
    username = str(
        claims.get("cognito:username") or claims.get("preferred_username") or sub
    )

    try:
        with get_db_connection() as conn:
            UserDAO.upsert(conn, sub, email, username)
    except Exception:
        logging.getLogger(__name__).warning("upsert_user failed", exc_info=True)


def is_admin(claims: Dict[str, Any]) -> bool:
    """Return True when the authenticated user's *verified* email is in
    ADMIN_EMAILS. An unverified address proves nothing about who holds it."""
    email = str(claims.get("email", "")).strip().lower()
    verified = claims.get("email_verified") in (True, "true")
    return bool(email and verified and email in ADMIN_EMAILS)


def get_current_user_is_admin(claims: Dict[str, Any] = Security(verify_token)) -> bool:
    """True when the signed-in user is an admin (``ADMIN_EMAILS``). Owner-scoped
    routes use it to let admins see every record, including legacy rows that
    were stored before they had an owner."""
    return is_admin(claims)


def get_optional_claims(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(optional_security),
) -> Optional[Dict[str, Any]]:
    """Claims of the caller when a bearer token is presented, None for an
    anonymous request. A token that is presented but invalid is still a 401:
    a bad token must never silently fall back to anonymous access."""
    if credentials is None:
        return None
    return verify_token(credentials)


def get_optional_user_id(
    claims: Optional[Dict[str, Any]] = Depends(get_optional_claims),
) -> Optional[str]:
    """The signed-in user's id, or None for an anonymous caller. For routes
    whose public records stay public but whose owned records are private."""
    return None if claims is None else _subject(claims)


def get_optional_user_is_admin(
    claims: Optional[Dict[str, Any]] = Depends(get_optional_claims),
) -> bool:
    return claims is not None and is_admin(claims)


def get_verified_claims(
    claims: Dict[str, Any] = Security(verify_token),
) -> Dict[str, Any]:
    """Return verified token claims, register the user in the DB, and stamp
    ``_is_admin`` so endpoints don't have to re-check."""
    upsert_user(claims)
    # Stamp admin flag on a copy so the original JWT claims are not mutated.
    result = dict(claims)
    result["_is_admin"] = is_admin(claims)
    return result
