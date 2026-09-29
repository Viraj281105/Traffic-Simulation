import { API_BASE_URL } from "../config";
import type { DashboardScenarioPayload } from "../types/config";
import { ensureLiveSession } from "./liveSession";

const BASE = API_BASE_URL;

/** A non-2xx API response; `status` lets callers tell "not found" apart. */
export class ApiError extends Error {
  readonly status: number;
  constructor(status: number, statusText: string) {
    super(`HTTP ${status.toString()}: ${statusText}`);
    this.name = "ApiError";
    this.status = status;
  }
}

import { getAuthToken } from "../auth/cognito";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  // Live/comparison calls must land in the same backend session as the
  // stream (see liveSession.ts).
  if (path.startsWith("/api/simulation")) await ensureLiveSession();

  const token = await getAuthToken();
  const headers = new Headers(init?.headers);

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${BASE}${path}`, {
    ...init,
    headers,
  });

  if (!response.ok) {
    throw new ApiError(response.status, response.statusText);
  }
  return response.json() as Promise<T>;
}

export async function post<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    ...(body === undefined
      ? {}
      : {
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }),
  });
}

export async function get<T>(path: string): Promise<T> {
  return request<T>(path);
}

/** Start / resume the live simulation engine. */
export async function playSimulation(): Promise<void> {
  await post("/api/simulation/play");
}

/** Pause the live simulation engine. */
export async function pauseSimulation(): Promise<void> {
  await post("/api/simulation/pause");
}

/** Stop the live simulation engine. */
export async function stopSimulation(): Promise<void> {
  await post("/api/simulation/stop");
}

/** Start / resume the dual simulation engine. */
export async function playDualSimulation(): Promise<void> {
  await post("/api/simulation/dual/play");
}

/** Pause the dual simulation engine. */
export async function pauseDualSimulation(): Promise<void> {
  await post("/api/simulation/dual/pause");
}

/** Send new configuration to backend. */
export async function updateSimulationConfig(
  config: DashboardScenarioPayload,
): Promise<void> {
  await post("/api/simulation/config", config);
}

/** Reset/stop lockstep dual simulation. */
export async function stopDualSimulation(): Promise<void> {
  await post("/api/simulation/dual/reset");
}

// ── Study / Analytics API ──────────────────────────────────────────────────

/** List saved sweep sessions. */
export async function listSweeps<T>(limit = 20): Promise<T> {
  return get(`/api/v1/study/sweeps?limit=${limit.toString()}`);
}

/** Get a specific sweep session by ID. */
export async function getSweep(id: string): Promise<unknown> {
  return get(`/api/v1/study/sweeps/${encodeURIComponent(id)}`);
}

/** Compact reproducibility record of a saved run
 *  (backend describe_reproducibility, include_payload=False). Fields a run
 *  never recorded — runs saved before provenance tracking — are null. */
export interface RunReproducibility {
  runId: string;
  /** User-entered labels (V1.1); null/empty until someone sets them. */
  name: string | null;
  notes: string | null;
  tags: string[];
  /** "replay" for runs saved from the dashboard; a sweep id for sweep runs. */
  batchId: string | null;
  createdAt: string | null;
  status: string | null;
  intersectionType: string | null;
  provenanceRecorded: boolean;
  runMode: "single" | "dual" | null;
  seed: number | null;
  /** "unknown" when the backend could not read its git state. */
  gitCommitHash: string | null;
  pythonVersion: string | null;
  /** "engine": the exact config the simulation ran with;
   *  "client": the dashboard's own summary of it. */
  configSource: "engine" | "client" | null;
  configAvailable: boolean;
  exactConfig: boolean;
  timing: {
    timeStep: number | null;
    duration: number | null;
    warmupTime: number | null;
    elapsed: number | null;
  };
}

export async function saveReplay(payload: {
  name: string;
  config: Record<string, unknown>;
  metrics: Record<string, unknown>;
  mode?: "single" | "dual";
}): Promise<{
  status: string;
  replay_id: string;
  runId?: string;
  reproducibility?: RunReproducibility | null;
}> {
  return post("/api/v1/replays", payload);
}

export async function listReplays<T>(): Promise<T> {
  return get<T>("/api/v1/replays");
}

export async function deleteReplay(id: string): Promise<{ status: string }> {
  return request(`/api/v1/replays/${id}`, { method: "DELETE" });
}

/** Full stored record of one run (GET …/runs/{id}/reproducibility). */
export interface RunRecord extends RunReproducibility {
  /** Stored configuration with simulation.randomSeed pinned to `seed`;
   *  null when the run recorded none. */
  config: Record<string, unknown> | null;
  /** Metrics as stored: one metrics object, or {signal, roundabout} for a
   *  comparison run. Empty when none were recorded. */
  summaryMetrics: Record<string, unknown>;
  /** A History (dashboard) save exists, so its settings can be restored. */
  savedReplay: boolean;
}

function runUrl(runId: string): string {
  return `/api/v1/study/history/runs/${encodeURIComponent(runId)}`;
}

export async function getRunRecord(runId: string): Promise<RunRecord> {
  return get(`${runUrl(runId)}/reproducibility`);
}

export async function updateRunMetadata(
  runId: string,
  changes: { name?: string; notes?: string | null; tags?: string[] },
): Promise<RunRecord> {
  return request(runUrl(runId), {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(changes),
  });
}

/** Result of POST …/runs/{id}/reproduce. `isDeterministic` is null when the
 *  stored run had nothing to compare against. */
export interface ReproductionResult {
  runId: string;
  mode: "single" | "dual";
  seed: number;
  reproducedElapsed: number;
  isDeterministic: boolean | null;
  comparedMetrics: string[];
  tolerances: { averageDelaySeconds: number; throughputVehicles: number };
  discrepancies: string[];
  limitations: string[];
  recordedGitCommitHash: string | null;
  provenance: { gitCommitHash: string; pythonVersion: string };
}

export async function reproduceRun(runId: string): Promise<ReproductionResult> {
  return post(`${runUrl(runId)}/reproduce`);
}

/** Download URL of a run export (served as an attachment). */
export function runExportUrl(runId: string, format: "json" | "csv"): string {
  return `${BASE}${runUrl(runId)}/export?format=${format}`;
}

export async function getReplay<T>(id: string): Promise<T> {
  return get<T>(`/api/v1/replays/${encodeURIComponent(id)}`);
}
