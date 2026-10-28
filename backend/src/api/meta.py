"""Service-level routes: health, build provenance, the caller's profile and
the admin user list."""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from src.api.auth import get_verified_claims
from src.core.provenance import GIT_COMMIT_HASH, PYTHON_VERSION
from src.database.dao import UserDAO
from src.database.db import get_db_connection

router = APIRouter()


# Used by Docker HEALTHCHECK.
@router.get("/health")
def health_check() -> Dict[str, str]:
    return {"status": "healthy"}


@router.get("/api/version")
def version() -> Dict[str, str]:
    """Build provenance of the running backend: the commit its code came from
    (the one recorded with saved runs; "unknown" when the image was built from
    uncommitted changes or without GIT_COMMIT) and the Python runtime.
    start.ps1 compares it with the source it just built."""
    return {"gitCommit": GIT_COMMIT_HASH, "pythonVersion": PYTHON_VERSION}


@router.get("/api/me")
def get_me(
    claims: Dict[str, Any] = Depends(get_verified_claims),
) -> Dict[str, Any]:
    """Return the current user's profile and admin status.

    The frontend calls this on login to know whether to show the Admin panel.
    """
    return {
        "sub": claims.get("sub", ""),
        "email": claims.get("email", ""),
        "username": (
            claims.get("cognito:username")
            or claims.get("preferred_username")
            or claims.get("sub", "")
        ),
        "isAdmin": bool(claims.get("_is_admin")),
    }


@router.get("/api/users")
def list_users(
    claims: Dict[str, Any] = Depends(get_verified_claims),
) -> Dict[str, Any]:
    """Return the list of users who have ever logged in via Cognito.

    Admin-only — returns 403 for non-admin callers.
    Each row also includes the number of simulation runs the user has saved.
    """
    if not claims.get("_is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")

    with get_db_connection() as conn:
        rows = UserDAO.list_with_run_counts(conn)

    users = [
        {
            "sub": row["sub"],
            "email": row["email"],
            "username": row["username"],
            "firstSeen": row["first_seen"],
            "lastSeen": row["last_seen"],
            "runCount": row["run_count"],
        }
        for row in rows
    ]
    return {"users": users, "count": len(users)}
