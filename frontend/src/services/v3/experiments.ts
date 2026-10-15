/**
 * V3.0 Robustness Lab API client (backend src/experiments/router.py, /api/v3).
 *
 * Types mirror the documents the server sends: the status (ExperimentStatus in
 * experiments/models.py) and the result (experiments/service.py,
 * _result_document, which embeds the analysis of uncertainty/analysis.py). The
 * contract files are in shared/schemas/v3/. Nothing here computes a statistic:
 * every number shown comes from the server, and a field the server leaves out
 * is shown as unavailable, never as zero.
 *
 * Like services/v2/planning.ts this client keeps the server's own error
 * message so a refused request shows its reasons.
 */
import { API_BASE_URL } from "../../config";
import { getAuthToken } from "../../auth/cognito";

const PREFIX = "/api/v3";

// ── Status ─────────────────────────────────────────────────────────────────

export type ExperimentState = "queued" | "running" | "completed" | "failed";

export interface RunCounts {
  conditions: number;
  alternatives: number;
  replications: number;
  totalRuns: number;
}

export interface ExperimentProgress {
  phase: string;
  total: number;
  completed: number;
  fraction: number;
  elapsedSeconds: number;
}

export interface ExperimentStatus {
  id: string;
  name: string;
  status: ExperimentState;
  error: string | null;
  createdAt: string;
  counts: RunCounts | null;
  specFingerprint: string | null;
  resultAvailable: boolean;
  progress: ExperimentProgress | null;
}

export const isActive = (status: ExperimentState): boolean =>
  status === "queued" || status === "running";

// ── Result ─────────────────────────────────────────────────────────────────

export interface Interval {
  value: number;
  ci: [number, number];
}

export interface Proportion {
  count: number;
  p: number;
  ci: [number, number];
}

export interface Comparison {
  win: Proportion;
  tie: Proportion;
  loss: Proportion;
  difference: Record<"mean" | "median" | "p5" | "p95", Interval>;
}

export interface AlternativeAnalysis {
  isBaseline: boolean;
  meanOutcome?: number;
  regret?: { mean: number; p95: number; sampleMax: number };
  preferenceShare?: number;
  comparison: Comparison | null;
}

export interface EligibilityCriterion {
  id: string;
  /** true = met, false = not met, null = not assessed in this version. */
  passed: boolean | null;
  detail: string;
}

export type EligibilityClass = "exploratory" | "indicative" | "eligible";

export interface Tolerance {
  kind: "rule" | "absolute";
  absSeconds?: number;
  relative?: number;
  value?: number;
}

export interface Analysis {
  primaryIndicator: string;
  lowerIsBetter: boolean;
  tolerance: Tolerance;
  confidenceLevel: number;
  baseline: string;
  counts: RunCounts & { validConditions: number };
  exclusions: {
    excluded: number;
    overallShare: number;
    byReason: Record<string, number>;
    worstStratumShare: number;
  };
  alternatives: Record<string, AlternativeAnalysis>;
  eligibility: {
    class: EligibilityClass;
    validConditions: number;
    criteria: EligibilityCriterion[];
  };
  realWorldValidity: string;
  limitations: string[];
}

export interface ResultAlternative {
  id: string;
  label: string;
  strategy: string;
  isBaseline: boolean;
  fingerprint: string | null;
  changesFromBase: string[];
}

export interface Assumption {
  id: string;
  kind: string;
  distribution: { kind: string } & Record<string, number | string>;
  bounds: [number, number];
  basis: "assumed" | "observed" | "user";
  rationale: string;
}

export interface ExperimentResult {
  experimentId: string;
  name: string;
  scenario: { name: string; fingerprint: string };
  alternatives: ResultAlternative[];
  baseline: string;
  specFingerprint: string;
  assumptions: Assumption[];
  analysis: Analysis;
  resultFingerprint: string;
  provenance: {
    gitCommit: string;
    pythonVersion: string;
    sampling: string;
    commonRandomNumbers: boolean;
    seedRule: string;
    note: string;
  };
  execution: {
    runsPlanned: number;
    runsExecuted: number;
    workers: number;
    wallSeconds: number;
  };
}

// ── Errors and transport ───────────────────────────────────────────────────

export class ExperimentsApiError extends Error {
  readonly status: number;
  readonly reasons: string[];
  constructor(status: number, reasons: string[]) {
    super(reasons.join("; ") || `HTTP ${status.toString()}`);
    this.name = "ExperimentsApiError";
    this.status = status;
    this.reasons = reasons;
  }
}

/** The reasons in the backend's error envelope: ``error.details.errors`` when
 *  the server gave a list, otherwise ``error.message``. */
function reasonsFrom(body: unknown): string[] {
  if (!body || typeof body !== "object") return [];
  const error = (body as { error?: unknown }).error;
  if (!error || typeof error !== "object") return [];
  const { message, details } = error as {
    message?: unknown;
    details?: { errors?: unknown } | null;
  };
  if (Array.isArray(details?.errors)) return details.errors.map(String);
  return typeof message === "string" && message ? [message] : [];
}

async function json<T>(path: string): Promise<T> {
  const token = await getAuthToken();
  const headers = new Headers();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { headers });
  } catch {
    throw new ExperimentsApiError(0, ["The server could not be reached."]);
  }
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null);
    const reasons = reasonsFrom(body);
    throw new ExperimentsApiError(
      response.status,
      reasons.length ? reasons : [response.statusText || "Request failed"],
    );
  }
  return (await response.json()) as T;
}

// ── Endpoints ──────────────────────────────────────────────────────────────

export function getExperiment(id: string): Promise<ExperimentStatus> {
  return json(`${PREFIX}/experiments/${encodeURIComponent(id)}`);
}

export function getExperimentResult(id: string): Promise<ExperimentResult> {
  return json(`${PREFIX}/experiments/${encodeURIComponent(id)}/result`);
}
