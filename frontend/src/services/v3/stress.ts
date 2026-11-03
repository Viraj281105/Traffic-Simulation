/**
 * Stress lab client (backend src/stress/router.py, /api/v3/stress).
 */
import { getJson, postJson } from "./experiments";
import type { EntryQueueSpec } from "../../scenario/scenarioTypes";
import type { EntryModelUsed } from "../../metrics/entryModel";

const PREFIX = "/api/v3/stress";

export interface StressJob {
  id: string;
  kind: "suite" | "breakpoints";
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  createdAt: string;
  runs: number;
  resultAvailable: boolean;
  error: string | null;
}

export interface SuiteResult {
  format: "urbanflow-stress-suite";
  generator: string;
  seed: number;
  suiteFingerprint: string;
  strategies: string[];
  /** Absent in results saved before it (those ran "suspend"). */
  entryModel?: EntryModelUsed;
  rules: Record<string, string>;
  failureTotals: Partial<Record<string, Partial<Record<string, number>>>>;
  scenarios: {
    index: number;
    family: string;
    name: string;
    results: Partial<
      Record<
        string,
        | {
            failures: Record<string, number>;
            meanDelay: number | null;
            runErrors: number;
            admittedShareOfNominal?: number | null;
            unfinishedShare?: number | null;
          }
        | { skipped: string }
      >
    >;
    /** The lowest-delay strategy served less of the demand than another
     *  (absent in results saved before it). */
    lowestDelayServedLess?: boolean;
  }[];
  note: string;
}

export interface BreakpointResult {
  format: "urbanflow-breakpoints";
  factor: string;
  strategies: string[];
  seedsPerLevel: number;
  entryModel?: EntryModelUsed;
  table: {
    level: number | string;
    meanDelay: Record<string, number | null>;
    preferred: string | null;
    preferenceShare: Record<string, number>;
    /** The lowest-delay strategy served less of the demand than another
     *  (absent in results saved before it). */
    preferredServedLess?: boolean;
  }[];
  breakpoints: {
    between: [number | string, number | string];
    from: string;
    to: string;
    confidence: number;
  }[];
  tooFewToAssess: string[] | null;
  note: string;
}

export function startSuite(body: {
  seed: number;
  count: number;
  seedsPerRun: number;
  /** Sent only when the point queue is on. */
  entryQueue?: EntryQueueSpec;
}): Promise<StressJob> {
  return postJson(`${PREFIX}/suites`, body);
}

export function startBreakpoints(body: {
  factor: "demand_scale" | "aggression";
  levels: (number | string)[];
  seedsPerLevel: number;
  /** The default junction's entry model; sent only when the queue is on. */
  entryQueue?: EntryQueueSpec;
}): Promise<StressJob> {
  return postJson(`${PREFIX}/breakpoints`, body);
}

export function listJobs(): Promise<StressJob[]> {
  return getJson(`${PREFIX}/jobs`);
}

export function getJob(id: string): Promise<StressJob> {
  return getJson(`${PREFIX}/jobs/${encodeURIComponent(id)}`);
}

export function getJobResult(
  id: string,
): Promise<SuiteResult | BreakpointResult> {
  return getJson(`${PREFIX}/jobs/${encodeURIComponent(id)}/result`);
}

export function cancelJob(id: string): Promise<StressJob> {
  return postJson(`${PREFIX}/jobs/${encodeURIComponent(id)}/cancel`);
}
