/** Contract fixtures for /api/v2/costing: shapes from
 *  backend/src/costing/estimator.py and runcost.py. Invented values. */
import type { CostEstimate, RunCost } from "./types";

export const estimateFixture: CostEstimate = {
  items: { compute: 0.012, storage: 0.0003, queue: 0.000001 },
  total: 0.012301,
  currency: "USD",
  confidence: "estimate, not a bill",
  assumptions: ["On-demand price for the default instance, approximate."],
};

export const runCostFixture: RunCost = {
  ...estimateFixture,
  runId: "run_1",
  tenant: "acme",
  day: "2026-11-01",
  computeSeconds: 42,
  costTags: { project: "demo", env: "dev" },
};
