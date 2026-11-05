# Multi-tenant layer (F16, package 2D)

`backend/src/tenancy/` adds OIDC login, roles, tenant scoping, rate limits and
quotas. It is **additive**: no existing router uses it yet, and the current
Cognito, API-key and personal-access-token paths (`src/api/auth.py`,
`src/api/security.py`, `src/access.py`) are unchanged.

## What is in it

| Module | Purpose |
|---|---|
| `oidc.py` | `OidcVerifier`: RS256 only, checks signature, `iss`, audience (`aud`, or `client_id` for Cognito access tokens), `exp`, `nbf`. `JwksCache` finds keys by `kid`; an unknown `kid` refetches once per cooldown (rotation); a failed refetch keeps the last good set; the fetcher is injectable. `cognito_config(region, pool, client)`. |
| `roles.py` | Roles `admin`, `analyst`, `viewer`, `service`; `PERMISSION_MATRIX`; `roles_from_claims` (claim `cognito:groups` by default, list or comma/space string, optional exhaustive `group_map`). |
| `scoping.py` | `TenantScope(tenant_id)`: `key(*segments)`, `key_for(path)`, `owns`, `relative`, `sql_filter(column)`; `InMemoryScopedStore` as the reference store. |
| `limits.py` | `TokenBucket`, `RateLimiter` (per user and per tenant), `QuotaManager` (daily runs and concurrent runs, per user and per tenant, per-tenant overrides, usage counters). Injectable clock. |
| `deps.py` | `TenancyRuntime`, `get_tenant_context`, `require_role(...)`, `require_permission(...)`, `acquire_run_slot`. |
| `router.py` | `GET /api/v2/tenancy/me`, `GET /api/v2/tenancy/usage`. |

## Permission matrix

| Permission | admin | analyst | viewer | service |
|---|:-:|:-:|:-:|:-:|
| `resources:read` | x | x | x | x |
| `resources:write` | x | x |  | x |
| `resources:delete` | x | x |  |  |
| `runs:read` | x | x | x | x |
| `runs:create` | x | x |  | x |
| `usage:read` | x | x | x |  |
| `tenant:admin` | x |  |  |  |

No role crosses tenants; `admin` is admin of its own tenant only. A user with
several groups gets the union of their permissions; `role` in `/me` is the
highest by precedence admin, analyst, service, viewer. A token with no
recognised role has no permissions (403).

## Configuration (environment)

The runtime is built lazily from the environment; without an issuer the
tenancy routes answer 503.

- `TENANCY_OIDC_ISSUER`, `TENANCY_OIDC_AUDIENCE`, optional `TENANCY_OIDC_JWKS_URL`
  (default `<issuer>/.well-known/jwks.json`, https only);
- or the existing `COGNITO_USER_POOL_ID`, `COGNITO_CLIENT_ID`, `AWS_REGION`;
- `TENANCY_TENANT_CLAIM` (default `custom:tenant_id`), `TENANCY_ROLE_CLAIM`
  (default `cognito:groups`).

Tenant ids must match `[a-z0-9][a-z0-9_-]{0,62}` (the claim is lower-cased);
anything else is a 403. Cognito needs a custom attribute `tenant_id` added to
the pool and put in the token (pre-token-generation trigger for access tokens).
Limits and quotas default to: 30 burst / 120 per minute per user, 300 / 1200
per tenant; 50 runs per day and 2 concurrent per user, 500 and 10 per tenant.
Change them by building the `TenancyRuntime` yourself (`set_runtime`).

## Adopting it in a router

```python
from fastapi import Depends
from src.tenancy import TenantContext, acquire_run_slot, require_permission
from src.tenancy.roles import RESOURCES_READ

@router.get("/things")
def list_things(ctx: TenantContext = Depends(require_permission(RESOURCES_READ))):
    sql, params = ctx.scope.sql_filter("tenant_id")      # DB: WHERE tenant_id = ?
    key = ctx.scope.key_for(thing_id)                     # object store: tenants/<id>/<thing_id>
    ...

@router.post("/runs")
def start(lease: RunLease = Depends(acquire_run_slot)):   # 429 + Retry-After when over quota
    ...
```

Rules for every adopter:

1. Never build a storage key by hand. Use `ctx.scope.key(...)` / `key_for(...)`;
   they reject `..`, separators, `%` (so `%2e%2e`, `%2f`, double encoding), control
   characters and empty segments (`InvalidKeyError`, map it to 400).
2. Never build a tenant condition by hand. Use `sql_filter`; add a `tenant_id`
   column and index to the table.
3. Answer "another tenant's resource" exactly like "missing" (404).
4. A handler that runs work in the background sets `lease.keep = True` and calls
   `lease.release()` when the run ends; otherwise the slot is freed when the
   request returns.
5. Every `/api/v2` and `/api/v3` router must still carry
   `require_api_key` and the signed-in-user dependency (`tests/api/test_v*_route_auth.py`);
   the tenancy dependency is added next to them, not instead of them.

`tests/tenancy/test_tenancy_isolation.py` is the isolation sweep: two tenants
over list, read, overwrite and delete, plus 15 traversal and encoding attempts,
through the real dependencies. Add a route of your own to its app when you
adopt the layer.

## 429 responses

```
HTTP 429  Retry-After: <seconds>
{"detail": {"code": "rate_limited | tenant_rate_limited | daily_quota_exceeded |
            tenant_daily_quota_exceeded | concurrent_quota_exceeded |
            tenant_concurrent_quota_exceeded",
            "message": "...", "limit": 50, "retryAfterSeconds": 3600}}
```

Daily quotas reset at UTC midnight (`Retry-After` is the time to it); concurrent
quotas hint 10 s; rate limits give the time until a token exists.

## TypeScript client

`python scripts/generate_ts_client.py [--snapshot P] [--out P]` turns
`shared/schemas/v3/openapi.v3.snapshot.json` into a typed fetch client
(default `clients/typescript/urbanflow.ts`): a type per schema, a function per
operation, `ClientConfig {baseUrl, token, apiKey}` and `ApiError`. Deterministic;
regenerate when the snapshot changes. The `/api/v2/tenancy` routes are not in the
v3 snapshot, so they are not in this client.

## What is NOT done

- **No existing router is migrated.** `/api/v2/*` and `/api/v3/*` keep their
  per-user ownership (`src/access.py`); saved runs, suites and calibrations have
  no `tenant_id` column. Migration needs a column, a backfill, and an ADR.
- **Real Cognito is not wired or tested.** Only a local RSA mock issuer is
  exercised; the pool has no `tenant_id` attribute or groups yet
  (`scripts/setup_cognito.py` is unchanged), and no live JWKS fetch has run.
- **Quotas, usage counters and rate-limit buckets are in memory**, per process:
  lost on restart, not shared between workers or hosts. Redis (named in F16) or a
  table is the follow-up; `QuotaManager` / `RateLimiter` are the seam.
- The tenancy router is registered in `main.py` (`/api/v2/tenancy/me`, `/api/v2/tenancy/usage`) and covered by test suites (`tests/tenancy/test_tenancy_isolation.py`). Tenancy routes are excluded from the v3 public snapshot as enterprise internal APIs.
- No tenant management API (create tenant, invite user, change role): roles and
  tenant come only from the identity provider.
- No audit trail of denied requests, and no per-tenant quota configuration
  outside code (`tenant_overrides`).
- The security review of W53 (#16) is not done; this layer has not been reviewed.
- PATs and the dev-auth bypass are not tenant-aware.
