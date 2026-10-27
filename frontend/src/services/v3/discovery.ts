/**
 * Discovery Lab client (backend src/discovery/router.py, /api/v3/discovery).
 * Every number shown comes from the server; candidates are EXPERIMENTAL.
 */
import { downloadFile, getJson, postJson } from "./experiments";

const PREFIX = "/api/v3/discovery";

export interface Regime {
  name: string;
  vehiclesPerHour: number;
  unevenDemand: boolean;
  lanesPerArm: number;
  aggression: "standard" | "moderate" | "high" | null;
  mix: "default" | "heavy_vehicles" | "two_wheelers";
  duration: number;
  warmup: number;
}

export interface SearchBudget {
  population: number;
  generations: number;
  tuningSeeds: number;
  selectionSeeds: number;
  heldOutSeeds: number;
  paretoCap: number;
  shortlist: number;
  unseenGrid: boolean;
}

export interface SearchSpec {
  name: string;
  regime: Regime;
  budget: SearchBudget;
  seed: number;
}

export interface SearchStatus {
  id: string;
  name: string;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  phase: string;
  createdAt: string;
  runs: { planned: number; used: number };
  resultAvailable: boolean;
  error: string | null;
}

export type ObjectiveRow = Record<string, number> | null;

export interface Versus {
  meanDifference: number | null;
  ci95: [number, number] | null;
  n: number;
  lowerDelayInSeeds?: number;
}

export interface SearchResult {
  status: string;
  complete: boolean;
  experimental: string;
  method: string;
  specFingerprint: string;
  traceFingerprint: string;
  runs: { planned: number; used: number };
  rejected: Record<string, number>;
  seedPools: {
    tuning: number;
    selection: number;
    heldOut: number;
    heldOutHashCommittedBeforeSearch: string;
  };
  pareto: {
    candidate: string;
    generation: number;
    genome: Record<string, unknown>;
    tuningObjectives: ObjectiveRow;
  }[];
  heldOut: {
    seeds: number;
    differenceMeaning: string;
    candidates: Record<
      string,
      {
        genome: Record<string, unknown>;
        objectives: ObjectiveRow;
        infeasible: string | null;
        versusBaselines: Record<string, Versus>;
      }
    >;
    baselines: Record<
      string,
      { objectives: ObjectiveRow; infeasible: string | null }
    >;
  } | null;
  bestOnTuningLosesOnHeldOut: boolean | null;
  preferenceChanges:
    | {
        demandScale: number;
        aggression: string;
        meanDelay: Record<string, number | null>;
        lowestDelay: string | null;
        seeds: number;
      }[]
    | null;
}

export function estimate(
  spec: SearchSpec,
): Promise<{ runs: number; simulatedSeconds: number }> {
  return postJson(`${PREFIX}/estimate`, spec);
}

export function startSearch(spec: SearchSpec): Promise<SearchStatus> {
  return postJson(`${PREFIX}/searches`, spec);
}

export function listSearches(): Promise<SearchStatus[]> {
  return getJson(`${PREFIX}/searches`);
}

export function getSearch(id: string): Promise<SearchStatus> {
  return getJson(`${PREFIX}/searches/${encodeURIComponent(id)}`);
}

export function getSearchResult(id: string): Promise<SearchResult> {
  return getJson(`${PREFIX}/searches/${encodeURIComponent(id)}/result`);
}

export function cancelSearch(id: string): Promise<SearchStatus> {
  return postJson(`${PREFIX}/searches/${encodeURIComponent(id)}/cancel`);
}

export function downloadSearchPackage(
  id: string,
): Promise<{ filename: string; blob: Blob }> {
  return downloadFile(
    `${PREFIX}/searches/${encodeURIComponent(id)}/package`,
    `urbanflow-discovery-${id.slice(0, 12)}.ufpkg`,
  );
}
