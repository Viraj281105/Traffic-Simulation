"""FastAPI dependencies of the tenancy layer.

``get_tenant_context`` verifies the bearer token (OIDC, RS256), derives the
tenant and roles from claims, spends rate-limit tokens and returns a
``TenantContext``. ``require_role`` / ``require_permission`` build on it::

    @router.get("/things")
    def things(ctx: TenantContext = Depends(require_permission(RESOURCES_READ))):
        return store.list(ctx.scope)

The runtime (verifier, limiter, quotas, claim names) is process-wide and built
lazily from the environment; tests replace it with
``app.dependency_overrides[get_runtime]`` or ``set_runtime``.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, FrozenSet, Iterator, Mapping, Optional

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.tenancy.limits import LimitExceededError, QuotaManager, RateLimiter, RunLease
from src.tenancy.oidc import (
    JwksUnavailableError,
    OidcConfig,
    OidcVerifier,
    TokenError,
    cognito_config,
)
from src.tenancy.roles import (
    Role,
    permissions_for,
    primary_role,
    roles_from_claims,
)
from src.tenancy.scoping import TENANT_ID_PATTERN, TenantScope

_bearer = HTTPBearer(auto_error=False)


@dataclass
class TenancyRuntime:
    verifier: OidcVerifier
    limiter: RateLimiter = field(default_factory=RateLimiter)
    quotas: QuotaManager = field(default_factory=QuotaManager)
    tenant_claim: str = "custom:tenant_id"
    role_claim: str = "cognito:groups"
    group_map: Optional[Mapping[str, Role]] = None


def runtime_from_env(
    env: Optional[Mapping[str, str]] = None,
) -> Optional[TenancyRuntime]:
    """Build the runtime from TENANCY_* variables, falling back to the
    Cognito variables the API already uses. None when no issuer is set."""
    e = os.environ if env is None else env
    issuer = e.get("TENANCY_OIDC_ISSUER", "").strip()
    audience = e.get("TENANCY_OIDC_AUDIENCE", "").strip()
    config: Optional[OidcConfig] = None
    if issuer and audience:
        config = OidcConfig(
            issuer=issuer,
            audience=audience,
            jwks_url=e.get("TENANCY_OIDC_JWKS_URL", "").strip(),
        )
    elif e.get("COGNITO_USER_POOL_ID") and e.get("COGNITO_CLIENT_ID"):
        config = cognito_config(
            e.get("AWS_REGION", "us-east-1"),
            e["COGNITO_USER_POOL_ID"],
            e["COGNITO_CLIENT_ID"],
        )
    if config is None:
        return None
    return TenancyRuntime(
        verifier=OidcVerifier(config),
        tenant_claim=e.get("TENANCY_TENANT_CLAIM", "custom:tenant_id").strip(),
        role_claim=e.get("TENANCY_ROLE_CLAIM", "cognito:groups").strip(),
    )


_runtime: Optional[TenancyRuntime] = None
_runtime_lock = threading.Lock()


def set_runtime(runtime: Optional[TenancyRuntime]) -> None:
    global _runtime
    with _runtime_lock:
        _runtime = runtime


def get_runtime() -> TenancyRuntime:
    global _runtime
    with _runtime_lock:
        if _runtime is None:
            _runtime = runtime_from_env()
        runtime = _runtime
    if runtime is None:
        raise HTTPException(status_code=503, detail="Tenancy is not configured")
    return runtime


@dataclass(frozen=True)
class Principal:
    user_id: str
    tenant_id: str
    roles: FrozenSet[Role]
    permissions: FrozenSet[str]
    role: Optional[Role]
    email: str = ""
    issuer: str = ""
    expires_at: Optional[int] = None


@dataclass(frozen=True)
class TenantContext:
    principal: Principal
    scope: TenantScope
    runtime: TenancyRuntime

    @property
    def tenant_id(self) -> str:
        return self.principal.tenant_id

    @property
    def user_id(self) -> str:
        return self.principal.user_id

    def has_permission(self, permission: str) -> bool:
        return permission in self.principal.permissions


def _unauthorized(message: str = "Invalid or expired token") -> HTTPException:
    return HTTPException(
        status_code=401, detail=message, headers={"WWW-Authenticate": "Bearer"}
    )


def principal_from_claims(claims: Mapping[str, Any], rt: TenancyRuntime) -> Principal:
    tenant = claims.get(rt.tenant_claim)
    if not isinstance(tenant, str) or not TENANT_ID_PATTERN.fullmatch(tenant.lower()):
        raise HTTPException(status_code=403, detail="No valid tenant on this token")
    roles = roles_from_claims(claims, claim=rt.role_claim, group_map=rt.group_map)
    exp = claims.get("exp")
    return Principal(
        user_id=str(claims["sub"]),
        tenant_id=tenant.lower(),
        roles=roles,
        permissions=permissions_for(roles),
        role=primary_role(roles),
        email=str(claims.get("email", "")),
        issuer=str(claims.get("iss", "")),
        expires_at=int(exp) if isinstance(exp, (int, float)) else None,
    )


def get_principal(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    rt: TenancyRuntime = Depends(get_runtime),
) -> Principal:
    if credentials is None or not credentials.credentials:
        raise _unauthorized("Missing bearer token")
    try:
        claims = rt.verifier.verify(credentials.credentials)
    except TokenError as exc:
        raise _unauthorized(exc.message) from exc
    except JwksUnavailableError as exc:
        raise HTTPException(
            status_code=503, detail="Identity provider keys unavailable"
        ) from exc
    return principal_from_claims(claims, rt)


def too_many(exc: LimitExceededError) -> HTTPException:
    return HTTPException(
        status_code=429,
        detail=exc.detail(),
        headers={"Retry-After": str(exc.retry_after_seconds)},
    )


def get_tenant_context(
    principal: Principal = Depends(get_principal),
    rt: TenancyRuntime = Depends(get_runtime),
) -> TenantContext:
    """Authenticated, tenant-scoped and within the request rate limit."""
    try:
        rt.limiter.check(principal.tenant_id, principal.user_id)
    except LimitExceededError as exc:
        rt.quotas.record_request(principal.tenant_id, principal.user_id, limited=True)
        raise too_many(exc) from exc
    rt.quotas.record_request(principal.tenant_id, principal.user_id)
    return TenantContext(principal, TenantScope(principal.tenant_id), rt)


def require_role(*roles: Role) -> Callable[..., TenantContext]:
    """Dependency: the caller holds at least one of ``roles`` (else 403)."""
    allowed = frozenset(roles)

    def dependency(ctx: TenantContext = Depends(get_tenant_context)) -> TenantContext:
        if not (ctx.principal.roles & allowed):
            raise HTTPException(status_code=403, detail="Role not permitted")
        return ctx

    return dependency


def require_permission(*permissions: str) -> Callable[..., TenantContext]:
    """Dependency: the caller holds every one of ``permissions`` (else 403)."""
    needed = frozenset(permissions)

    def dependency(ctx: TenantContext = Depends(get_tenant_context)) -> TenantContext:
        if not needed <= ctx.principal.permissions:
            raise HTTPException(status_code=403, detail="Permission denied")
        return ctx

    return dependency


def acquire_run_slot(
    ctx: TenantContext = Depends(require_permission("runs:create")),
) -> Iterator[RunLease]:
    """Dependency: take a run slot (429 + Retry-After when a quota is used up)
    and release it when the request ends. A handler that hands the run to a
    background task sets ``lease.keep = True`` and releases it itself."""
    try:
        lease = ctx.runtime.quotas.acquire_run(ctx.tenant_id, ctx.user_id)
    except LimitExceededError as exc:
        raise too_many(exc) from exc
    try:
        yield lease
    finally:
        if not lease.keep:
            lease.release()


def quota_snapshot(ctx: TenantContext) -> Dict[str, Any]:
    user_rate, tenant_rate = ctx.runtime.limiter.remaining(ctx.tenant_id, ctx.user_id)
    lim = ctx.runtime.limiter.limits
    return {
        "requests": {
            "user": {"burst": lim.user_burst, "remaining": user_rate},
            "tenant": {"burst": lim.tenant_burst, "remaining": tenant_rate},
            "userPerMinute": lim.user_per_minute,
            "tenantPerMinute": lim.tenant_per_minute,
        },
        **ctx.runtime.quotas.remaining(ctx.tenant_id, ctx.user_id),
    }
