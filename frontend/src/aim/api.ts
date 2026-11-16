import { V2, postJson } from "../netcommon/api";
import type { AimInput, AimResult } from "./types";

/** POST /api/v2/aim/comparison (seeds 1..n; the server needs two). */
export function runAimComparison(input: AimInput): Promise<AimResult> {
  return postJson(`${V2}/aim/comparison`, {
    durationSeconds: input.durationSeconds,
    seeds: Array.from({ length: input.seedCount }, (_, i) => i + 1),
    demandsVehPerHourPerApproach: input.demands,
    method: "paired_t",
    confidence: 0.95,
    ...(input.withLossStress
      ? {
          messageLoss: {
            demandVehPerHourPerApproach: 450,
            lossProbabilities: [0, 0.25, 0.5, 0.8, 0.95],
          },
        }
      : {}),
  });
}
