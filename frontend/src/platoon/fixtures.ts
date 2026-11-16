/** Contract fixture for POST /api/v2/platoon/experiment: shapes from
 *  backend/src/platoon/experiment.py with small invented numbers. Not real. */
import type { PairedCmp, PlatoonExperiment, PlatoonMetric } from "./types";

function cmp(a: number, b: number): PairedCmp {
  return {
    method: "paired_t",
    n_pairs: 3,
    mean_a: a,
    mean_b: b,
    difference: a - b,
    ci_lower: a - b - 0.5,
    ci_upper: a - b + 0.5,
    confidence: 0.95,
    p_value: 0.01,
    alpha: 0.05,
    significant: true,
    direction: a < b ? "a_lower" : "a_higher",
    statistic: 5,
    cautions: [],
  };
}

function metric(a: number, b: number, verdict: string): PlatoonMetric {
  return {
    platoonMean: a,
    humanMean: b,
    changePct: ((a - b) / b) * 100,
    comparison: cmp(a, b),
    verdict,
  };
}

export const platoonFixture: PlatoonExperiment = {
  seeds: [1, 2, 3],
  metrics: {
    throughputVph: metric(
      2400,
      1800,
      "A beats B: 600 (A minus B, 95% interval 599.5 to 600.5, p = 0.01, paired_t, n = 3)",
    ),
    fuelLPer100Km: metric(
      7.6,
      8.4,
      "A beats B: -0.8 (A minus B, 95% interval -1.3 to -0.3, p = 0.01, paired_t, n = 3)",
    ),
    co2GPerKm: metric(
      176,
      195,
      "A beats B: -19 (A minus B, 95% interval -19.5 to -18.5, p = 0.01, paired_t, n = 3)",
    ),
  },
  safety: {
    platoonMinGapM: 4.2,
    humanMinGapM: 9.1,
    platoonCollisions: 0,
    humanCollisions: 0,
    platoonFallbackEvents: 2,
  },
  perSeed: [
    {
      seed: 1,
      platoon: { throughputVph: 2400, fuelLPer100Km: 7.6 },
      human: { throughputVph: 1800, fuelLPer100Km: 8.4 },
    },
  ],
  isEstimate: true,
  label:
    "Simulation estimates from a single-lane 1-D model with a relative fuel proxy; not a field measurement.",
  channelSweep: [
    {
      latencySeconds: 0,
      lossProbability: 0,
      fuelChangePct: -9.5,
      throughputChangePct: 33,
      minGapM: 4.2,
      collisions: 0,
      fallbackEvents: 0,
    },
    {
      latencySeconds: 0.5,
      lossProbability: 0.5,
      fuelChangePct: -2,
      throughputChangePct: 10,
      minGapM: 3.1,
      collisions: 0,
      fallbackEvents: 14,
    },
  ],
  stringStability: {
    vehicles: 10,
    timeGapSeconds: 0.6,
    controller: "cacc",
    peakSpeedDeviationMps: [1, 0.8, 0.6],
    stepRatioMax: 0.9,
    amplification: 0.6,
    stable: true,
    minGapM: 8,
    collisions: 0,
  },
  throughputSteadyState: { cacc: 3100, idm: 1900 },
};
