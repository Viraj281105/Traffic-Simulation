import { V2, postJson } from "../netcommon/api";
import type { PlatoonExperiment, PlatoonInput } from "./types";

/** POST /api/v2/platoon/experiment (seeds 1..n; the server needs two). */
export function runPlatoonExperiment(
  input: PlatoonInput,
): Promise<PlatoonExperiment> {
  return postJson(`${V2}/platoon/experiment`, {
    vehicles: input.vehicles,
    durationSeconds: input.durationSeconds,
    latencyMs: input.latencyMs,
    lossProbability: input.lossProbability,
    seeds: Array.from({ length: input.seedCount }, (_, i) => i + 1),
    method: "paired_t",
    confidence: 0.95,
    ...(input.withSweep
      ? {
          channelSweep: {
            latenciesMs: [0, 200, 500],
            lossProbabilities: [0, 0.2, 0.5],
          },
        }
      : {}),
  });
}
