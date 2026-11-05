import { V2, getJson, postJson } from "../netcommon/api";
import type {
  IncidentCatalogue,
  ResilienceResponse,
  Scenario,
  SimulateResponse,
  Strategy,
} from "./types";

const BASE = `${V2}/incidents`;

export function getIncidentCatalogue(): Promise<IncidentCatalogue> {
  return getJson(`${BASE}/catalogue`);
}

export interface SimulateInput {
  preset: string;
  scenario: Scenario;
  duration: number;
  seed: number;
  strategy: Strategy;
}

/** POST /api/v2/incidents/simulate. The preset supplies the network; the
 *  scenario in the form replaces the preset's scenario. */
export function simulateIncident(
  input: SimulateInput,
): Promise<SimulateResponse> {
  return postJson(`${BASE}/simulate`, {
    preset: input.preset,
    scenario: input.scenario,
    duration: input.duration,
    seed: input.seed,
    strategy: input.strategy,
    compareBaseline: true,
    bucketSeconds: 30,
  });
}

export interface ResilienceInput {
  preset: string;
  scenario: Scenario;
  duration: number;
  seedCount: number;
  strategies: Strategy[];
}

/** The seeds 1..n of a resilience request. */
export function seedList(count: number): number[] {
  return Array.from({ length: count }, (_, i) => i + 1);
}

/** POST /api/v2/incidents/resilience. */
export function evaluateResilience(
  input: ResilienceInput,
): Promise<ResilienceResponse> {
  return postJson(`${BASE}/resilience`, {
    preset: input.preset,
    scenario: input.scenario,
    duration: input.duration,
    strategies: input.strategies,
    seeds: seedList(input.seedCount),
    bucketSeconds: 30,
    includeSeries: false,
  });
}
