import { V3, getJson } from "../insights/http";
import type { RunMetrics } from "./types";

export function getRunMetrics(runId: string): Promise<RunMetrics> {
  return getJson(`${V3}/runs/${encodeURIComponent(runId)}/metrics`);
}
