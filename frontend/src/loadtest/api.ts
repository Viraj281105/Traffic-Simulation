import { V3, getJson } from "../netcommon/api";
import type { LoadTestSummary } from "./types";

/** GET /api/v3/loadtests/latest: the newest load-test summary (contract in
 *  loadtest/types.ts). A 404 means no result has been published yet. */
export function getLatestLoadTest(): Promise<LoadTestSummary> {
  return getJson(`${V3}/loadtests/latest`);
}

/** True when `value` has the fields the dashboard reads. */
export function isLoadTestSummary(value: unknown): value is LoadTestSummary {
  if (typeof value !== "object" || value === null) return false;
  const v = value as Record<string, unknown>;
  return (
    v.format === "urbanflow-loadtest-summary" &&
    typeof v.requests === "object" &&
    v.requests !== null &&
    typeof v.latencyMs === "object" &&
    v.latencyMs !== null &&
    typeof v.vus === "object" &&
    v.vus !== null &&
    Array.isArray(v.thresholds)
  );
}

/** Parse a summary file; throws a plain sentence when it is not one. */
export function parseLoadTest(text: string): LoadTestSummary {
  let doc: unknown;
  try {
    doc = JSON.parse(text);
  } catch {
    throw new Error("That is not valid JSON.");
  }
  if (!isLoadTestSummary(doc)) {
    throw new Error(
      "That is not a load-test summary (format urbanflow-loadtest-summary).",
    );
  }
  return doc;
}
