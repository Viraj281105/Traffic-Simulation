/**
 * Discovery Lab client (backend src/discovery/router.py, /api/v3/discovery).
 * Every number shown comes from the server; candidates are EXPERIMENTAL.
 */
import { downloadFile, getJson, postJson } from "./experiments";
import type { EntryQueueSpec } from "../../scenario/scenarioTypes";
import type { EntryModelUsed } from "../../metrics/entryModel";

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
  /** The entry model every candidate and baseline runs; null/absent = the
   *  default. With the queue, the delay objective is the delay from arrival. */
  entryQueue?: EntryQueueSpec | null;
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
  /** The candidate's lower delay came with less of the demand served
   *  (absent in results saved before it). */
  lowerDelayServedLess?: boolean;
}

/** Served-demand means beside the objectives (reported, never optimised). */
export interface ServedDemandMeans {
  averageEntryWait?: number;
  admittedShareOfNominal?: number;
  unfinishedShare?: number;
  /** Present under the queue model, where averageDelay is from arrival. */
  inNetworkDelay?: number;
}

export interface SearchResult {
  status: string;
  complete: boolean;
  experimental: string;
  method: string;
  specFingerprint: string;
  traceFingerprint: string;
  /** Absent in results saved before it (those ran "suspend"). */
  entryModel?: EntryModelUsed;
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
        servedDemand?: ServedDemandMeans | null;
        infeasible: string | null;
        versusBaselines: Record<string, Versus>;
      }
    >;
    baselines: Record<
      string,
      {
        objectives: ObjectiveRow;
        servedDemand?: ServedDemandMeans | null;
        infeasible: string | null;
      }
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
