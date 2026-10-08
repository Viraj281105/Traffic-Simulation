import logging
import os
import time
from typing import Any, Dict, List, cast

import requests
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwk, jwt
from jose.utils import base64url_decode

from src.database.db import get_db_connection

security = HTTPBearer()

# Load from .env if variables are not set
# Load from .env if variables are not set
try:
    env_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "backend", ".env")
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

    if not USER_POOL_ID:
        # Local development without Cognito uses DEV_AUTH_BYPASS (above);
        # a real token always needs a configured pool.
        raise HTTPException(
            status_code=500, detail="Cognito User Pool ID not configured on server"
        )

    try:
        # Get the key ID from the header
        headers = jwt.get_unverified_headers(token)
        kid = headers.get("kid")

        # Find the public key matching the kid
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

        public_key = jwk.construct(keys[key_index])

        # Get the payload
        message, encoded_signature = str(token).rsplit(".", 1)
        decoded_signature = base64url_decode(encoded_signature.encode("utf-8"))

        # Verify signature
        if not public_key.verify(message.encode("utf8"), decoded_signature):
            raise HTTPException(status_code=401, detail="Signature verification failed")

        # Verify claims
        claims = jwt.get_unverified_claims(token)
        if time.time() > claims["exp"]:
            raise HTTPException(status_code=401, detail="Token is expired")

        # Optional: verify audience (client ID)
        if claims.get("aud") != CLIENT_ID and claims.get("client_id") != CLIENT_ID:
            raise HTTPException(
                status_code=401, detail="Token was not issued for this audience"
            )

        return cast(Dict[str, Any], claims)

    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Authentication error: {str(e)}")


def get_current_user_id(claims: Dict[str, Any] = Security(verify_token)) -> str:
    """Returns the Cognito username (sub) from the token."""
    return str(claims.get("sub", ""))


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
        claims.get("cognito:username")
        or claims.get("preferred_username")
        or sub
    )

    try:
        with get_db_connection() as conn:
            conn.execute(
                """
                INSERT INTO users (sub, email, username, first_seen, last_seen)
                VALUES (:sub, :email, :username, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(sub) DO UPDATE SET
                    email    = excluded.email,
                    username = excluded.username,
                    last_seen = CURRENT_TIMESTAMP
                """,
                {"sub": sub, "email": email, "username": username},
            )
            conn.commit()
    except Exception:
        logging.getLogger(__name__).warning("upsert_user failed", exc_info=True)


def is_admin(claims: Dict[str, Any]) -> bool:
    """Return True when the authenticated user's email is in ADMIN_EMAILS."""
    email = str(claims.get("email", "")).strip().lower()
    return bool(email and email in ADMIN_EMAILS)


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
