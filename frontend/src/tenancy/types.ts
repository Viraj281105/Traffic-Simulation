/** Shapes of /api/v2/tenancy/* (backend/src/tenancy/router.py, deps.py
 *  quota_snapshot, limits.py). Copied from the code; see
 *  src/CONTRACTS_P6.md. Both routes need an OIDC bearer token with a tenant
 *  claim: 401 or 403 without one, 503 when tenancy is not configured. */

export interface Identity {
  userId: string;
  email: string;
  issuer: string;
  /** Unix seconds; null when the token has no expiry claim. */
  tokenExpiresAt: number | null;
}

export interface RateBucket {
  burst: number;
  remaining: number;
}

export interface Quota {
  requests: {
    user: RateBucket;
    tenant: RateBucket;
    userPerMinute: number;
    tenantPerMinute: number;
  };
  dailyRuns: {
    limit: number;
    used: number;
    remaining: number;
    resetsInSeconds: number;
  };
  concurrentRuns: { limit: number; active: number; remaining: number };
}

/** GET /api/v2/tenancy/me */
export interface MeResponse {
  identity: Identity;
  tenant: { id: string };
  role: string | null;
  roles: string[];
  permissions: string[];
  quota: Quota;
}

export interface Counters {
  requestsTotal: number;
  rateLimitedTotal: number;
  runsToday: number;
  runsTotal: number;
  activeRuns: number;
}

/** GET /api/v2/tenancy/usage (needs the usage:read permission). */
export interface UsageResponse {
  day: string;
  tenant: Counters;
  user: Counters;
  /** Per-user breakdown, tenant admins only; null otherwise. */
  users: Record<string, Counters> | null;
}
