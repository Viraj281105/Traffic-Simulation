/** Shapes of /api/v2/costing (backend/src/costing/router.py, estimator.py,
 *  runcost.py). Copied from the code; see src/CONTRACTS_P7.md. Every figure
 *  is "estimate, not a bill". */

export interface CostEstimate {
  items: { compute: number; storage: number; queue: number };
  total: number;
  currency: string;
  /** Always "estimate, not a bill". */
  confidence: string;
  assumptions: string[];
}

/** GET /runs/{id}: the estimate plus the run's own facts. */
export interface RunCost extends CostEstimate {
  runId: string;
  tenant: string;
  day: string | null;
  computeSeconds: number;
  costTags: Record<string, string>;
}

export interface EstimateInput {
  computeSeconds: number;
  vcpuWeight: number;
  spot: boolean;
  storedBytes: number;
  queueRequests: number;
  storageMonths: number;
}
