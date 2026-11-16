import { V2, getJson, postJson } from "../netcommon/api";
import type { CostEstimate, EstimateInput, RunCost } from "./types";

const BASE = `${V2}/costing`;

/** POST /api/v2/costing/estimate */
export function estimateCost(input: EstimateInput): Promise<CostEstimate> {
  return postJson(`${BASE}/estimate`, input);
}

/** GET /api/v2/costing/runs/{runId} (404 when no job record is stored). */
export function getRunCost(runId: string, spot: boolean): Promise<RunCost> {
  const q = spot ? "?spot=true" : "";
  return getJson(`${BASE}/runs/${encodeURIComponent(runId)}${q}`);
}
