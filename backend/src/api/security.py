"""Minimal API-key protection for mutating / compute-heavy endpoints.

Disabled (no-op) when API_KEY is unset/empty — the intended local-dev
default, so nothing needs to change to keep developing without auth. Set
the API_KEY environment variable to require the key on protected routes.

The key travels in its own header, `X-API-Key`, which is what nginx injects
for browser traffic (frontend/templates/default.conf.template). That leaves
`Authorization` free for the signed-in user's Cognito token: the proxy used
to overwrite Authorization with the key, so with API_KEY set the user's
token never reached the backend and the live-session middleware rejected
the key itself as an invalid JWT. `Authorization: Bearer <API_KEY>` is still
accepted for scripts and proxies configured the old way.

Every /api/v2 and /api/v3 route needs the API key AND a signed-in user.
nginx attaches the key to every browser request, so the key identifies the
proxy, not a person; a route guarded by the key alone is public.
tests/api/test_v2_route_auth.py checks every mounted route.
"""

import os
import secrets
from typing import Optional

from fastapi import Header, HTTPException

# Read at call time by every function below, so tests can monkeypatch it.
API_KEY = os.environ.get("API_KEY", "").strip()


def is_api_key(value: Optional[str]) -> bool:
    """Constant-time check of a presented value against the configured key."""
    if not API_KEY or not value:
        return False
    return secrets.compare_digest(value.encode("utf-8"), API_KEY.encode("utf-8"))


def bearer_value(authorization: Optional[str]) -> Optional[str]:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    return authorization[len("Bearer ") :].strip() or None


def require_api_key(
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None),
) -> None:
    if not API_KEY:
        return
    if is_api_key(x_api_key) or is_api_key(bearer_value(authorization)):
        return
    raise HTTPException(
        status_code=401,
        detail="Missing or invalid API key",
        headers={"WWW-Authenticate": "Bearer"},
    )
