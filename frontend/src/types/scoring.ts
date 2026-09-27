import type { RunningMetrics } from "./simulation";
import { METRICS, metricState, type MetricContext } from "../metrics/catalog";

/** The five metrics the weighted score reads. */
const SCORE_INPUT_KEYS = [
  "averageWaitTime",
  "throughputRate",
  "averageQueueLength",
  "directionalFairnessIndex",
  "averageStopsPerVehicle",
] as const;

/** True only when every input is a real measurement for this side: after
 *  warm-up, with at least one vehicle exited. Before that the backend holds
 *  best-case placeholders (no waiting, no stops, fairness 1.0), which would
 *  otherwise score high before anything has been measured. */
export function weightedScoreReady(ctx: MetricContext): boolean {
  return SCORE_INPUT_KEYS.every((key) => {
    const def = METRICS.find((m) => m.key === key);
    return def !== undefined && metricState(def, ctx).kind === "value";
  });
}

export interface ScoringWeights {
  weightWaitTime: number;
  weightThroughput: number;
  weightQueue: number;
  weightFairness: number;
  weightStops: number;
}

export const DEFAULT_WEIGHTS: ScoringWeights = {
  weightWaitTime: 30,
  weightThroughput: 30,
  weightQueue: 15,
  weightFairness: 15,
  weightStops: 10,
};

/** How each metric is mapped onto 0-1 before weighting (shown to users). */
export const SCORE_NORMALISATION: Array<[string, string]> = [
  ["Average queued time", "1 at 0 s, falling linearly to 0 at 60 s or more"],
  ["Throughput rate", "0 at 0 veh/min, rising linearly to 1 at 120 veh/min"],
  [
    "Average queue per approach",
    "1 at 0 vehicles, falling linearly to 0 at 15 or more",
  ],
  ["Directional fairness", "Jain's index as reported (0.25-1)"],
  ["Stops per vehicle", "1 at 0 stops, falling linearly to 0 at 5 or more"],
];

export function computeWeightedScore(
  metrics: RunningMetrics | undefined,
  weights: ScoringWeights,
): number {
  if (!metrics) return 0;

  const totalWeights =
    weights.weightWaitTime +
    weights.weightThroughput +
    weights.weightQueue +
    weights.weightFairness +
    weights.weightStops;

  const wTotal = totalWeights > 0 ? totalWeights : 100;

  // Normalized components (0.0 to 1.0). See SCORE_NORMALISATION below.
  const waitNorm = Math.max(0, 1 - metrics.averageWaitTime / 60.0);
  // throughputRate is always vehicles per minute (backend metric contract).
  // It was previously treated as vehicles per second whenever it was <= 2,
  // inflating low-throughput runs' scores by up to 60x.
  const tpPerSec = metrics.throughputRate / 60.0;
  const tpNorm = Math.min(1, tpPerSec / 2.0);
  const queueNorm = Math.max(0, 1 - metrics.averageQueueLength / 15.0);
  const fairnessNorm = Math.max(
    0,
    Math.min(1, metrics.directionalFairnessIndex),
  );
  const stopsNorm = Math.max(0, 1 - metrics.averageStopsPerVehicle / 5.0);

  const weightedSum =
    waitNorm * weights.weightWaitTime +
    tpNorm * weights.weightThroughput +
    queueNorm * weights.weightQueue +
    fairnessNorm * weights.weightFairness +
    stopsNorm * weights.weightStops;

  return Math.round((weightedSum / wTotal) * 1000) / 10;
}
