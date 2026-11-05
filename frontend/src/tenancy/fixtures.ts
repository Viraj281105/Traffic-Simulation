/** Contract fixtures for /api/v2/tenancy/*. Invented values. */
import type { MeResponse, UsageResponse } from "./types";

export const meFixture: MeResponse = {
  identity: {
    userId: "user-1",
    email: "ana@example.test",
    issuer: "https://idp.example.test",
    tokenExpiresAt: 1800000000,
  },
  tenant: { id: "acme" },
  role: "analyst",
  roles: ["analyst", "viewer"],
  permissions: ["runs:create", "runs:read", "usage:read"],
  quota: {
    requests: {
      user: { burst: 60, remaining: 55 },
      tenant: { burst: 300, remaining: 290 },
      userPerMinute: 30,
      tenantPerMinute: 120,
    },
    dailyRuns: { limit: 50, used: 12, remaining: 38, resetsInSeconds: 7200 },
    concurrentRuns: { limit: 2, active: 1, remaining: 1 },
  },
};

export const usageFixture: UsageResponse = {
  day: "2026-11-05",
  tenant: {
    requestsTotal: 400,
    rateLimitedTotal: 3,
    runsToday: 20,
    runsTotal: 90,
    activeRuns: 1,
  },
  user: {
    requestsTotal: 120,
    rateLimitedTotal: 0,
    runsToday: 12,
    runsTotal: 40,
    activeRuns: 1,
  },
  users: null,
};
