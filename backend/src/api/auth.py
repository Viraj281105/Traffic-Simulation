import datetime
import json
import logging
import os
import threading
import time
from collections import deque
from datetime import timezone
from typing import Any, Callable, Dict, List, Literal, Optional, Sequence, cast

import jwt
import requests
from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field

from src.api.request_limits import client_key
from src.api.store import AuditStore, TokenStore, hash_token_secret
from src.database.dao import UserDAO
from src.database.db import get_db_connection
from src.experiments.limits import PER_TOKEN_REQUESTS_PER_MINUTE
from src.observability.metrics import AUTH_FAILURES

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


def _load_env_file(env_path: str) -> None:
    """Set KEY=VALUE lines from ``env_path`` that the environment lacks.

    A line without ``=`` is skipped; it used to raise and silently drop every
    setting after it.
    """
    try:
        with open(env_path) as f:
            for line in f:
                if line.strip() and not line.startswith("#") and "=" in line:
                    key, val = line.strip().split("=", 1)
                    if key not in os.environ:
                        os.environ[key] = val
    except OSError:
        pass


# Load from .env if variables are not set
_env_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "backend", ".env")
)
_load_env_file(_env_path if os.path.exists(_env_path) else ".env")

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


def _pool_issuer() -> str:
    """The ``iss`` every token of this user pool carries."""
    return f"https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}"


# Cache the keys so we don't fetch them on every request. A token signed with
# a key not in the cache (Cognito rotated its signing keys) triggers one
# refetch, at most once per JWKS_REFRESH_COOLDOWN_SECONDS, so tokens with
# made-up kids cannot turn every request into a fetch (F-22).
_JWKS_CACHE: Optional[List[Dict[str, Any]]] = None
_JWKS_FETCHED_AT: Optional[float] = None  # time.monotonic() of the last fetch
_JWKS_LOCK = threading.Lock()
JWKS_REFRESH_COOLDOWN_SECONDS = 300.0
# A key the pool has withdrawn must stop verifying even if no token with an
# unknown kid ever arrives, so the set is also refetched once it is this old.
# If that refetch fails the cached set stays in use (it was the pool's
# published set; failing closed would lock every user out during an
# outage); the clock restarts at the attempt, so the next one comes after
# another max age, or after a cooldown if an unknown kid arrives.
JWKS_MAX_AGE_SECONDS = 3600.0
# With no keys held yet (a cold start while the pool is unreachable), a
# failed fetch is not retried for this long: every token is refused either
# way, and without the pause each request waited behind its own 10 s fetch
# under the lock.
JWKS_INITIAL_FAILURE_BACKOFF_SECONDS = 15.0
_JWKS_FAILED_AT: Optional[float] = None

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


def _fetch_jwks() -> List[Dict[str, Any]]:
    if not USER_POOL_ID or not REGION:
        raise ValueError("COGNITO_USER_POOL_ID or AWS_REGION is not set")

    keys_url = f"https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}/.well-known/jwks.json"
    response = requests.get(keys_url, timeout=10)
    response.raise_for_status()
    return cast(List[Dict[str, Any]], response.json()["keys"])


def get_jwks() -> List[Dict[str, Any]]:
    global _JWKS_CACHE, _JWKS_FETCHED_AT, _JWKS_FAILED_AT
    with _JWKS_LOCK:
        if _JWKS_CACHE is None:
            if (
                _JWKS_FAILED_AT is not None
                and time.monotonic() - _JWKS_FAILED_AT
                < JWKS_INITIAL_FAILURE_BACKOFF_SECONDS
            ):
                raise RuntimeError("JWKS unavailable; retrying after a backoff")
            try:
                _JWKS_CACHE = _fetch_jwks()
            except Exception:
                _JWKS_FAILED_AT = time.monotonic()
                raise
            _JWKS_FETCHED_AT = time.monotonic()
            _JWKS_FAILED_AT = None
        elif (
            _JWKS_FETCHED_AT is not None
            and time.monotonic() - _JWKS_FETCHED_AT >= JWKS_MAX_AGE_SECONDS
        ):
            _refetch_locked()
        return _JWKS_CACHE


def _refetch_locked() -> bool:
    """Replace the cached set with a fresh fetch; caller holds _JWKS_LOCK.

    The attempt restarts the clock whether or not it succeeds, so a failing
    endpoint is retried at most once per cooldown. A failed fetch keeps the
    keys already held. True when new keys were stored.
    """
    global _JWKS_CACHE, _JWKS_FETCHED_AT
    _JWKS_FETCHED_AT = time.monotonic()
    try:
        _JWKS_CACHE = _fetch_jwks()
    except Exception:
        # Old keys kept: a token still needs a valid signature from a key the
        # pool published; nothing is accepted without one.
        logging.getLogger(__name__).warning(
            "JWKS refetch failed; keeping the cached keys", exc_info=True
        )
        return False
    return True


def _refresh_jwks_for_unknown_kid() -> bool:
    """Refetch the key set once a token names a kid the cache lacks.

    Only when the cached set is older than the cooldown, so tokens with
    made-up kids cause at most one fetch per cooldown, however many arrive
    concurrently (the check and the fetch run under one lock).
    """
    with _JWKS_LOCK:
        if _JWKS_FETCHED_AT is None:
            return False
        if time.monotonic() - _JWKS_FETCHED_AT < JWKS_REFRESH_COOLDOWN_SECONDS:
            return False
        return _refetch_locked()


def reset_jwks_cache() -> None:
    """Forget the cached key set. Intended for test fixtures."""
    global _JWKS_CACHE, _JWKS_FETCHED_AT, _JWKS_FAILED_AT
    with _JWKS_LOCK:
        _JWKS_CACHE = None
        _JWKS_FETCHED_AT = None
        _JWKS_FAILED_AT = None


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
    AUTH_FAILURES.inc(reason)
    # The reason is a fixed vocabulary; no credential, token or claim is logged.
    logging.getLogger(__name__).warning(
        "authentication failed: %s",
        reason,
        extra={"event": "auth_failed", "reason": reason, "failures_in_window": count},
    )
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


# ── Per-token request rate (W7 Stage 2) ──────────────────────────────────────
# Sliding 60 s window of request times per PAT id. Process-local like the failure
# counters above: with several workers each would allow its own 60 requests.
TOKEN_RATE_WINDOW_SECONDS = 60.0
_TOKEN_REQUESTS_LOCK = threading.Lock()
_TOKEN_REQUESTS: Dict[str, "deque[float]"] = {}


def check_token_rate(token_id: str) -> None:
    """Count one request for ``token_id``; 429 (naming the quota) once it exceeds the limit."""
    now = time.monotonic()
    with _TOKEN_REQUESTS_LOCK:
        window = _TOKEN_REQUESTS.setdefault(token_id, deque())
        while window and window[0] <= now - TOKEN_RATE_WINDOW_SECONDS:
            window.popleft()
        if len(window) >= PER_TOKEN_REQUESTS_PER_MINUTE:
            retry_after = max(1, int(window[0] + TOKEN_RATE_WINDOW_SECONDS - now) + 1)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    "quota perTokenRequestsPerMinute: this token has made "
                    f"{PER_TOKEN_REQUESTS_PER_MINUTE} requests in the last minute"
                ),
                headers={"Retry-After": str(retry_after)},
            )
        window.append(now)


def reset_token_rate() -> None:
    """Clear per-token request tracking. Intended for test fixtures."""
    with _TOKEN_REQUESTS_LOCK:
        _TOKEN_REQUESTS.clear()


def reset_auth_failures() -> None:
    """Clear failed authentication and per-token request tracking. Intended for test fixtures."""
    with _AUTH_FAILURES_LOCK:
        _AUTH_FAILURES.clear()
    reset_token_rate()


def verify_cognito_jwt(token: str) -> Dict[str, Any]:
    """Verify an RS256 Cognito user pool JWT and return its claims.

    The key is the pool's published JWK named by the token's ``kid``; the
    token cannot choose the algorithm (RS256 only, checked on the header
    and again by PyJWT). ``exp`` is required, ``iss`` must be this pool,
    and the token must be for this app client (``aud`` on ID tokens,
    ``client_id`` on access tokens). Verified with PyJWT (F-33): python-jose
    and its ecdsa dependency carried unfixed advisories.
    """
    if not USER_POOL_ID:
        raise HTTPException(
            status_code=500, detail="Cognito User Pool ID not configured on server"
        )

    try:
        headers = jwt.get_unverified_header(token)
        if headers.get("alg") != _TOKEN_ALGORITHM:
            raise HTTPException(status_code=401, detail="Unsupported token algorithm")
        kid = headers.get("kid")

        keys = get_jwks()
        key_index = next((i for i, k in enumerate(keys) if k["kid"] == kid), -1)
        if key_index == -1 and _refresh_jwks_for_unknown_kid():
            keys = get_jwks()
            key_index = next((i for i, k in enumerate(keys) if k["kid"] == kid), -1)

        if key_index == -1:
            raise HTTPException(
                status_code=401, detail="Public key not found in jwks.json"
            )

        public_key = jwt.PyJWK(keys[key_index], algorithm=_TOKEN_ALGORITHM)
        try:
            claims = jwt.decode(
                token,
                key=public_key,
                algorithms=[_TOKEN_ALGORITHM],
                issuer=_pool_issuer(),
                # The audience is checked below (ID and access tokens name the
                # client differently). iat is not checked, as before: a
                # server clock slightly behind Cognito's must not refuse a
                # fresh token.
                options={
                    "require": ["exp", "iss"],
                    "verify_aud": False,
                    "verify_iat": False,
                },
            )
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token is expired")
        except jwt.InvalidSignatureError:
            raise HTTPException(status_code=401, detail="Signature verification failed")
        except jwt.InvalidIssuerError:
            raise HTTPException(
                status_code=401, detail="Token was not issued by this user pool"
            )

        if claims.get("aud") != CLIENT_ID and claims.get("client_id") != CLIENT_ID:
            raise HTTPException(
                status_code=401, detail="Token was not issued for this audience"
            )

        return claims

    except HTTPException:
        raise
    except Exception:
        # Malformed tokens, missing claims and JWKS fetch failures. The cause
        # is logged; the client gets no internal exception text.
        logging.getLogger(__name__).info("token verification failed", exc_info=True)
        raise HTTPException(status_code=401, detail="Invalid token")


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
            raise _fail_auth(key, "revoked_token", "Token has been revoked", **owner)

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

        check_token_rate(row["id"])
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
        raise _fail_auth(key, "invalid_jwt", "Invalid token") from e

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
