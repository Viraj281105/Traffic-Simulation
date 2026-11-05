import { V3, getJson } from "../insights/http";
import type { RlComparison } from "./types";

export function getRlComparison(comparisonId: string): Promise<RlComparison> {
  return getJson(`${V3}/rl/comparisons/${encodeURIComponent(comparisonId)}`);
}
