/** Contract fixture for POST /api/v2/v2x/experiment: shapes from
 *  backend/src/v2x/experiment.py with small invented numbers. Not real. */
import type { PairedStat } from "../rescommon/types";
import type {
  MetricRow,
  SensitivityCell,
  SweepRow,
  V2xExperiment,
} from "./types";

function paired(diff: number): PairedStat {
  return {
    method: "paired_t",
    n_pairs: 3,
    mean_a: 10 + diff,
    mean_b: 10,
    difference: diff,
    ci_lower: diff - 0.5,
    ci_upper: diff + 0.5,
    confidence: 0.95,
    p_value: 0.02,
    alpha: 0.05,
    significant: diff !== 0,
    direction: diff < 0 ? "a_lower" : "none",
    statistic: -3,
    cautions: [],
    verdict: `A beats B: ${String(diff)} (A minus B, 95% interval, p = 0.02, paired_t, n = 3)`,
  };
}

function row(base: number, change: number): MetricRow {
  return {
    baseline: base,
    cooperative: base + change,
    change,
    changePct: base ? (100 * change) / base : null,
    paired: change === 0 ? null : paired(change),
  };
}

function sweep(p: number, scale: number): SweepRow {
  return {
    penetration: p,
    metrics: {
      delaySeconds: row(20, -4 * scale),
      stops: row(1.5, -0.3 * scale),
      fuelLitres: row(0.05, -0.004 * scale),
      co2Kg: row(0.12, -0.01 * scale),
    },
    connectedVehicles: Math.round(100 * p),
    vehicles: 100,
    stopsAvoided: Math.round(30 * p),
    reroutes: 0,
    messageDeliveryRatio: p === 0 ? null : 0.9,
    meanMessageAgeAtUseSeconds: p === 0 ? null : 0.4,
    messagesAttempted: Math.round(1000 * p),
    messagesDelivered: Math.round(900 * p),
    messagesUsed: Math.round(700 * p),
  };
}

const cell = (
  latencyMs: number,
  lossProbability: number,
  benefit: number,
): SensitivityCell => ({
  latencyMs,
  lossProbability,
  delayBenefitSeconds: benefit,
  delayBenefitPct: benefit * 5,
  stopsAvoidedPerVehicle: benefit / 10,
  stopsReductionPct: benefit * 4,
  deliveryRatio: 1 - lossProbability,
  meanAgeAtUseSeconds: latencyMs / 1000,
  delayPaired: null,
});

export const v2xFixture: V2xExperiment = {
  format: "urbanflow-v2x-experiment",
  version: 1,
  baseline: {
    perSeed: [
      { seed: 1, vehicles: 100, completedByNetwork: 90, delaySeconds: 20 },
    ],
    mean: { delaySeconds: 20, stops: 1.5, fuelLitres: 0.05, co2Kg: 0.12 },
  },
  sweep: [
    sweep(0, 0),
    sweep(0.25, 1),
    sweep(0.5, 2),
    sweep(0.75, 3),
    sweep(1, 4),
  ],
  provenance: {
    seeds: [1, 2, 3],
    durationSeconds: 600,
    penetrations: [0, 0.25, 0.5, 0.75, 1],
    channel: {
      latencyKind: "constant",
      latencyMs: 100,
      jitterMs: 0,
      lossProbability: 0.1,
      rangeM: null,
    },
    behaviour: { advisoryHorizonSeconds: 15 },
    hazard: null,
    confidence: 0.95,
    method: "paired_t",
    constants: { co2KgPerLitre: 2.31 },
    assumptions: [
      "Baseline is the unmodified mesoscopic run; the cooperative outcome is an overlay on its vehicle traces, not a re-simulation.",
      "Fuel and CO2 are relative proxies of excess over free flow, not calibrated emissions.",
    ],
  },
  sensitivity: {
    penetration: 1,
    latenciesMs: [0, 500, 5000],
    lossProbabilities: [0, 0.3, 0.9],
    note: "benefit = baseline minus cooperative (positive is better)",
    cells: [
      cell(0, 0, 4),
      cell(0, 0.3, 3),
      cell(0, 0.9, 0.5),
      cell(500, 0, 3.5),
      cell(500, 0.3, 2.5),
      cell(500, 0.9, 0.4),
      cell(5000, 0, 1),
      cell(5000, 0.3, 0.7),
      cell(5000, 0.9, 0),
    ],
  },
};
