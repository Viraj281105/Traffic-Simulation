/** Contract fixture for POST /api/v2/aim/comparison: shapes from
 *  backend/src/aim/experiment.py with small invented numbers. Not real. */
import type { PairedStat } from "../rescommon/types";
import type { AimComparison, AimResult, AimSummary } from "./types";

function stat(a: number, b: number, higherBetter = false): PairedStat {
  const diff = a - b;
  return {
    method: "paired_t",
    n_pairs: 3,
    mean_a: a,
    mean_b: b,
    difference: diff,
    ci_lower: diff - 0.4,
    ci_upper: diff + 0.4,
    confidence: 0.95,
    p_value: 0.01,
    alpha: 0.05,
    significant: true,
    direction: diff < 0 ? "a_lower" : "a_higher",
    statistic: -4,
    cautions: [],
    verdict: `${diff < 0 !== higherBetter ? "A beats B" : "B beats A"}: ${String(diff)} (A minus B, 95% interval, p = 0.01, paired_t, n = 3)`,
  };
}

function summary(delay: number, passed = true): AimSummary {
  return {
    meanDelay: delay,
    stopsPerVehicle: delay / 10,
    throughputVph: 1000,
    p95Delay: delay * 2,
    lostMessages: 0,
    safety: {
      conflicts: passed ? 0 : 2,
      minGapSeconds: 0.8,
      deadlock: false,
      maxAccel: 2.5,
      passed,
    },
  };
}

function comparison(aim: number, signal: number): AimComparison {
  return {
    meanDelay: stat(aim, signal),
    stopsPerVehicle: stat(aim / 10, signal / 10),
    throughputVph: stat(1000, 990, true),
  };
}

export const aimFixture: AimResult = {
  provenance: {
    seeds: [1, 2, 3],
    durationSeconds: 300,
    turnMix: { left: 0.15, right: 0.15 },
    signal: { greenSeconds: 25, yellowSeconds: 3, allRedSeconds: 2 },
    confidence: 0.95,
    method: "paired_t",
    stressDemandVehPerHourPerApproach: 450,
    assumptions: [
      "In-model, all-vehicles-connected best case: every vehicle is automated and connected.",
      "One isolated 4-way intersection.",
    ],
    inModelBestCase: true,
  },
  sweep: [
    {
      demandVehPerHourPerApproach: 150,
      aim: summary(1.5),
      signal: summary(9),
      comparison: comparison(1.5, 9),
    },
    {
      demandVehPerHourPerApproach: 450,
      aim: summary(3),
      signal: summary(20),
      comparison: comparison(3, 20),
    },
  ],
  messageLossStress: [
    {
      lossProbability: 0,
      aim: summary(3),
      signal: summary(20),
      comparison: comparison(3, 20),
    },
    {
      lossProbability: 0.95,
      aim: summary(40),
      signal: summary(20),
      comparison: comparison(40, 20),
    },
  ],
  gateGAim: {
    passed: true,
    description:
      "independent replay checker: no tile overlap, no deadlock, minimum gap, speed and acceleration bounds",
  },
};
