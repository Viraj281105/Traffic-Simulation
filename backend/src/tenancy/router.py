"""``/api/v2/tenancy``: who am I, and how much of my quota is left.

Register in ``main.py`` (same dependencies as the other v2 routers)::

    from src.tenancy.router import router as tenancy_router
    app.include_router(
        tenancy_router,
        dependencies=[Depends(require_api_key), Depends(get_current_user_id)],
    )

Both routes also need a valid OIDC bearer token with a tenant claim
(``src.tenancy.deps``); they read, and change nothing.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.tenancy.deps import (
    TenantContext,
    get_tenant_context,
    quota_snapshot,
    require_permission,
)
from src.tenancy.roles import TENANT_ADMIN, USAGE_READ

router = APIRouter(prefix="/api/v2/tenancy", tags=["tenancy"])


class IdentityOut(BaseModel):
    userId: str
    email: str
    issuer: str
    tokenExpiresAt: Optional[int]


class TenantOut(BaseModel):
    id: str


class MeResponse(BaseModel):
    identity: IdentityOut
    tenant: TenantOut
    role: Optional[str]
    roles: List[str]
    permissions: List[str]
    quota: Dict[str, Any]


class UsageResponse(BaseModel):
    day: str
    tenant: Dict[str, int]
    user: Dict[str, int]
    users: Optional[Dict[str, Dict[str, int]]]  # per-user breakdown: admins only


@router.get("/me", response_model=MeResponse)
def me(ctx: TenantContext = Depends(get_tenant_context)) -> MeResponse:
    p = ctx.principal
    return MeResponse(
        identity=IdentityOut(
            userId=p.user_id,
            email=p.email,
            issuer=p.issuer,
            tokenExpiresAt=p.expires_at,
        ),
        tenant=TenantOut(id=p.tenant_id),
        role=p.role.value if p.role else None,
        roles=sorted(r.value for r in p.roles),
        permissions=sorted(p.permissions),
        quota=quota_snapshot(ctx),
    )


@router.get("/usage", response_model=UsageResponse)
def usage(
    ctx: TenantContext = Depends(require_permission(USAGE_READ)),
) -> UsageResponse:
    data = ctx.runtime.quotas.usage(ctx.tenant_id, ctx.user_id)
    users = (
        ctx.runtime.quotas.usage_by_user(ctx.tenant_id)
        if ctx.has_permission(TENANT_ADMIN)
        else None
    )
    return UsageResponse(
        day=data["day"], tenant=data["tenant"], user=data["user"], users=users
    )
