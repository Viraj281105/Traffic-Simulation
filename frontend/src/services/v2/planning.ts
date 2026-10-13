/**
 * V2.0 planning API client (backend src/planning/router.py, /api/v2/planning).
 *
 * Types mirror the backend's request model (planning/models.py) and the parts
 * of the result the planner page reads (planning/runner.py; full schema in
 * shared/schemas/v2/planning-report.schema.json). Nothing here computes a
 * statistic: every number shown comes from the server.
 *
 * Unlike services/api.ts this client keeps the server's error message, so a
 * rejected study shows its reasons and the two-study limit (HTTP 429) is
 * explained rather than reported as a bare status code.
 */
import { API_BASE_URL } from "../../config";
import { getAuthToken } from "../../auth/cognito";
import type { ScenarioDocument, Strategy } from "../../scenario/scenarioTypes";

const PREFIX = "/api/v2/planning";

/** Server limits (planning/models.py); the server re-checks every one. */
export const PLANNING_LIMITS = {
  maxAlternatives: 6,
  maxScales: 5,
  maxSeeds: 30,
  maxTotalRuns: 240,
  minScale: 0.1,
  maxScale: 3.0,
} as const;

// ── Request ────────────────────────────────────────────────────────────────

export interface AlternativeSpec {
  id: string;
  label?: string;
  strategy: Strategy;
}

export interface PlanningStudyRequest {
  format: "urbanflow-planning-study";
  version: 1;
  name: string;
  objective?: string;
  subject: { scenario: ScenarioDocument };
  /** First entry is the baseline. */
  alternatives: AlternativeSpec[];
  demand: { scales: number[] };
  repetitions: { seeds: number; baseSeed?: number; confidenceLevel?: number };
}

// ── Responses ──────────────────────────────────────────────────────────────

export interface ValidateResponse {
  valid: boolean;
  errors: string[];
  warnings: string[];
  /** Total simulations the study would run (alternatives x scales x seeds). */
  simulations?: number | null;
  scenarioFingerprint?: string | null;
  alternatives: {
    id: string;
    label: string;
    strategy: string;
    fingerprint: string;
    changesFromBase: unknown[];
  }[];
}

export type StudyStatus = "queued" | "running" | "completed" | "failed";

export interface StudyProgress {
  phase: string;
  total: number;
  completed: number;
  fraction: number;
  elapsedSeconds: number;
}

export interface IndicatorValue {
  mean: number | null;
  std?: number | null;
  ciLow?: number | null;
  ciHigh?: number | null;
  n?: number;
  label: string;
  unit?: string;
  direction?: "lower_is_better" | "higher_is_better";
}

export interface IndicatorGroup {
  status: string;
  values: Record<string, IndicatorValue>;
  unavailable: { key: string; label: string; reason: string }[];
  note?: string;
}

export interface ResultRow {
  alternativeId: string;
  demandScale: number;
  demandVph: number;
  vehicleLimitReached: boolean;
  performance?: IndicatorGroup;
  safety?: IndicatorGroup;
  environmental?: IndicatorGroup;
  reliability?: IndicatorGroup;
}

export type Verdict =
  "better" | "worse" | "tie" | "inconclusive" | "unavailable";

export interface BaselineComparison {
  alternativeId: string;
  baselineId: string;
  demandScale: number;
  metric: string;
  direction?: string;
  baselineMean?: number | null;
  alternativeMean?: number | null;
  delta?: number | null;
  deltaPct?: number | null;
  ciLow?: number | null;
  ciHigh?: number | null;
  n: number;
  reading: string;
  verdict: Verdict;
}

export interface Finding {
  id: string;
  kind: string;
  statement: string;
  confidence: string;
  evidence: { path: string }[];
  caveats: string[];
}

export interface PlanningResult {
  format: "urbanflow-planning-result";
  name: string;
  scenario: { name: string; fingerprint: string };
  alternatives: {
    id: string;
    label: string;
    strategy: string;
    strategyTitle: string;
    isBaseline: boolean;
    fingerprint: string;
  }[];
  summary: {
    baseline: string;
    alternatives: number;
    scales: number[];
    seeds: number;
    findings: number;
    recommendationBasis: string;
  };
  results: ResultRow[];
  comparison: { baselineId: string; vsBaseline: BaselineComparison[] };
  reliability: {
    repetitions: number;
    seeds: number[];
    confidenceLevel: number;
    sampleAdequacy: string;
    flags: { code: string; severity: string; message: string }[];
  };
  findings: Finding[];
  limitations: string[];
  validity: {
    fieldCalibration: string;
    fieldCalibrationDetail?: unknown;
    exploratory: boolean;
    vehicleLimitReached: boolean;
    caveats: string[];
  };
  meta: {
    gitCommit: string;
    scenarioFingerprint: string;
    inputFingerprint: string;
    resultFingerprint: string;
    networkFingerprint?: string | null;
    seeds: number[];
    createdAt: string;
  };
}

export interface StudyRecord {
  id: string;
  name: string;
  status: StudyStatus;
  error: string | null;
  createdAt: string;
  result: PlanningResult | null;
  progress?: StudyProgress | null;
}

export interface ReproduceResponse {
  id: string;
  reproduced: boolean;
  originalResultFingerprint: string;
  rerunResultFingerprint: string;
  gitCommitOriginal: string;
  gitCommitRerun: string;
}

export type ReportFormat = "json" | "md" | "csv";

// ── Transport ──────────────────────────────────────────────────────────────

/** A failed planning call: the HTTP status (0 when the server could not be
 *  reached) and the server's own explanation. */
export class PlanningApiError extends Error {
  readonly status: number;
  readonly reasons: string[];
  constructor(status: number, reasons: string[]) {
    super(reasons.join("; ") || `HTTP ${status.toString()}`);
    this.name = "PlanningApiError";
    this.status = status;
    this.reasons = reasons;
  }
}

/** The reasons in the backend's error envelope: the list in
 *  ``error.details.errors`` when the server gave one (a rejected study),
 *  otherwise ``error.message``. */
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

async function send(path: string, init: RequestInit = {}): Promise<Response> {
  const token = await getAuthToken();
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
  } catch {
    throw new PlanningApiError(0, ["The server could not be reached."]);
  }
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null);
    const reasons = reasonsFrom(body);
    throw new PlanningApiError(
      response.status,
      reasons.length ? reasons : [response.statusText || "Request failed"],
    );
  }
  return response;
}

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  return (await send(path, init)).json() as Promise<T>;
}

function postJson(body?: unknown): RequestInit {
  return {
    method: "POST",
    ...(body === undefined
      ? {}
      : {
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }),
  };
}

// ── Endpoints ──────────────────────────────────────────────────────────────

export function validateStudy(
  study: PlanningStudyRequest,
): Promise<ValidateResponse> {
  return json(`${PREFIX}/validate`, postJson(study));
}

/** Start the study as a background job (HTTP 202). */
export function startStudy(study: PlanningStudyRequest): Promise<StudyRecord> {
  return json(`${PREFIX}/jobs`, postJson(study));
}

export function getStudy(id: string): Promise<StudyRecord> {
  return json(`${PREFIX}/${encodeURIComponent(id)}`);
}

export function reproduceStudy(id: string): Promise<ReproduceResponse> {
  return json(`${PREFIX}/${encodeURIComponent(id)}/reproduce`, postJson());
}

/** The report as the server wrote it, plus the file name it suggests. */
export async function fetchReport(
  id: string,
  format: ReportFormat,
): Promise<{ filename: string; content: string; type: string }> {
  const response = await send(
    `${PREFIX}/${encodeURIComponent(id)}/report?format=${format}`,
  );
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const named = /filename="([^"]+)"/.exec(disposition);
  return {
    filename: named?.[1] ?? `planning-${id}.${format}`,
    content: await response.text(),
    type: response.headers.get("Content-Type") ?? "text/plain",
  };
}
