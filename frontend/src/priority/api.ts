import { V2, getJson, postJson } from "../netcommon/api";
import type {
  Approach,
  EmergencyComparison,
  Method,
  PriorityCatalogue,
  TransitComparison,
  Turn,
} from "./types";

const BASE = `${V2}/priority`;

export function getPriorityCatalogue(): Promise<PriorityCatalogue> {
  return getJson(`${BASE}/catalogue`);
}

export interface CommonInput {
  durationSeconds: number;
  arrivalRate: number;
  numSeeds: number;
  method: Method;
}

export interface EmergencyInput extends CommonInput {
  kind: string;
  approach: Approach;
  turn: Turn;
  timeSeconds: number;
}

/** POST /api/v2/priority/emergency-comparison */
export function compareEmergency(
  input: EmergencyInput,
): Promise<EmergencyComparison> {
  return postJson(`${BASE}/emergency-comparison`, {
    scenario: {
      durationSeconds: input.durationSeconds,
      arrivalRate: input.arrivalRate,
    },
    numSeeds: input.numSeeds,
    baseSeed: 1,
    method: input.method,
    confidence: 0.95,
    emergencyVehicles: [
      {
        kind: input.kind,
        approach: input.approach,
        turn: input.turn,
        timeSeconds: input.timeSeconds,
      },
    ],
  });
}

export interface TransitInput extends CommonInput {
  approach: Approach;
  turn: Turn;
  headwaySeconds: number;
  trips: number;
}

/** POST /api/v2/priority/transit-comparison */
export function compareTransit(
  input: TransitInput,
): Promise<TransitComparison> {
  return postJson(`${BASE}/transit-comparison`, {
    scenario: {
      durationSeconds: input.durationSeconds,
      arrivalRate: input.arrivalRate,
    },
    numSeeds: input.numSeeds,
    baseSeed: 1,
    method: input.method,
    confidence: 0.95,
    lines: [
      {
        lineId: "L1",
        approach: input.approach,
        turn: input.turn,
        headwaySeconds: input.headwaySeconds,
        trips: input.trips,
      },
    ],
  });
}
