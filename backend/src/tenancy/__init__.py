"""Multi-tenant layer (F16 / package 2D): OIDC verification, roles and
permissions, tenant scoping, rate limits and quotas. Additive: existing
routers keep their own auth until they adopt it (docs/security/tenancy.md)."""

from src.tenancy.deps import (
    Principal,
    TenancyRuntime,
    TenantContext,
    acquire_run_slot,
    get_runtime,
    get_tenant_context,
    require_permission,
    require_role,
    set_runtime,
)
from src.tenancy.limits import (
    LimitExceededError,
    QuotaManager,
    QuotaPolicy,
    RateLimiter,
)
from src.tenancy.oidc import OidcConfig, OidcVerifier, TokenError, cognito_config
from src.tenancy.roles import PERMISSION_MATRIX, Role
from src.tenancy.scoping import InMemoryScopedStore, InvalidKeyError, TenantScope

__all__ = [
    "InMemoryScopedStore",
    "InvalidKeyError",
    "LimitExceededError",
    "OidcConfig",
    "OidcVerifier",
    "PERMISSION_MATRIX",
    "Principal",
    "QuotaManager",
    "QuotaPolicy",
    "RateLimiter",
    "Role",
    "TenancyRuntime",
    "TenantContext",
    "TenantScope",
    "TokenError",
    "acquire_run_slot",
    "cognito_config",
    "get_runtime",
    "get_tenant_context",
    "require_permission",
    "require_role",
    "set_runtime",
]
