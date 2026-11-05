"""Roles, permissions and the matrix between them.

Roles come from a token claim (``cognito:groups`` by default; a list, or a
comma/space separated string). A deployment can map its own group names to
roles. A caller with no recognised role has no permissions.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, FrozenSet, Iterable, Mapping, Optional, Tuple


class Role(str, Enum):
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"
    SERVICE = "service"


# Highest first: the primary role of a user holding several.
ROLE_PRECEDENCE: Tuple[Role, ...] = (
    Role.ADMIN,
    Role.ANALYST,
    Role.SERVICE,
    Role.VIEWER,
)

RESOURCES_READ = "resources:read"
RESOURCES_WRITE = "resources:write"
RESOURCES_DELETE = "resources:delete"
RUNS_READ = "runs:read"
RUNS_CREATE = "runs:create"
USAGE_READ = "usage:read"
TENANT_ADMIN = "tenant:admin"

ALL_PERMISSIONS: FrozenSet[str] = frozenset(
    {
        RESOURCES_READ,
        RESOURCES_WRITE,
        RESOURCES_DELETE,
        RUNS_READ,
        RUNS_CREATE,
        USAGE_READ,
        TENANT_ADMIN,
    }
)

# Every grant applies inside the caller's own tenant; no role crosses tenants.
PERMISSION_MATRIX: Dict[Role, FrozenSet[str]] = {
    Role.ADMIN: ALL_PERMISSIONS,
    Role.ANALYST: frozenset(
        {
            RESOURCES_READ,
            RESOURCES_WRITE,
            RESOURCES_DELETE,
            RUNS_READ,
            RUNS_CREATE,
            USAGE_READ,
        }
    ),
    Role.VIEWER: frozenset({RESOURCES_READ, RUNS_READ, USAGE_READ}),
    Role.SERVICE: frozenset({RESOURCES_READ, RESOURCES_WRITE, RUNS_READ, RUNS_CREATE}),
}


def permissions_for(roles: Iterable[Role]) -> FrozenSet[str]:
    granted: FrozenSet[str] = frozenset()
    for role in roles:
        granted |= PERMISSION_MATRIX[role]
    return granted


def primary_role(roles: Iterable[Role]) -> Optional[Role]:
    held = set(roles)
    for role in ROLE_PRECEDENCE:
        if role in held:
            return role
    return None


def _as_names(value: Any) -> Tuple[str, ...]:
    if isinstance(value, str):
        return tuple(p for p in value.replace(",", " ").split() if p)
    if isinstance(value, (list, tuple)):
        return tuple(v for v in value if isinstance(v, str))
    return ()


def roles_from_claims(
    claims: Mapping[str, Any],
    *,
    claim: str = "cognito:groups",
    group_map: Optional[Mapping[str, Role]] = None,
) -> FrozenSet[Role]:
    """The roles a token claim grants; unknown group names are ignored."""
    found = set()
    for name in _as_names(claims.get(claim)):
        if group_map is not None:  # a map is exhaustive: unmapped names grant nothing
            if name in group_map:
                found.add(group_map[name])
            continue
        try:
            found.add(Role(name.lower()))
        except ValueError:
            continue
    return frozenset(found)
