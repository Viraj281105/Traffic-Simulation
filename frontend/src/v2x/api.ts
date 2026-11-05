import { V2, postJson } from "../netcommon/api";
import type { V2xExperiment } from "./types";

export interface V2xInput {
  rows: number;
  cols: number;
  vehiclesPerHour: number;
  duration: number;
  seedCount: number;
  latencyMs: number;
  lossProbability: number;
  withSensitivity: boolean;
}

export const PENETRATIONS = [0, 0.25, 0.5, 0.75, 1];

/** POST /api/v2/v2x/experiment (seeds 1..n; the server needs at least two). */
export function runV2xExperiment(input: V2xInput): Promise<V2xExperiment> {
  return postJson(`${V2}/v2x/experiment`, {
    grid: {
      rows: input.rows,
      cols: input.cols,
      vehiclesPerHour: input.vehiclesPerHour,
    },
    duration: input.duration,
    seeds: Array.from({ length: input.seedCount }, (_, i) => i + 1),
    penetrations: PENETRATIONS,
    channel: {
      latencyKind: "constant",
      latencyMs: input.latencyMs,
      lossProbability: input.lossProbability,
    },
    ...(input.withSensitivity
      ? {
          sensitivity: {
            penetration: 1,
            latenciesMs: [0, 100, 500, 2000, 5000],
            lossProbabilities: [0, 0.1, 0.3, 0.6, 0.9],
          },
        }
      : {}),
    confidence: 0.95,
    method: "paired_t",
  });
}
