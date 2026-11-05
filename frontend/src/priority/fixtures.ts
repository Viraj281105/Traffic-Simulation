/** Contract fixtures for /api/v2/priority/*: shapes from
 *  backend/src/priority with small invented numbers. Not real results. */
import type { PriorityStat } from "../rescommon/types";
import type {
  EmergencyComparison,
  PriorityCatalogue,
  Safety,
  TransitComparison,
} from "./types";

export const priorityCatalogueFixture: PriorityCatalogue = {
  inModelOnly: true,
  label:
    "In-model only: results describe this simulation model and its assumed parameters, not observed emergency-response or transit performance.",
  emergencyKinds: [
    { id: "ambulance", label: "Ambulance" },
    { id: "fire_truck", label: "Fire truck" },
  ],
  approaches: ["north", "south", "east", "west"],
  turns: ["left", "straight", "right"],
  methods: ["paired_t", "paired_bootstrap"],
  limits: {
    durationSeconds: [60, 900],
    seeds: [2, 20],
    seedsTimesDurationSeconds: 2000,
    emergencyVehicles: 8,
    transitLines: 4,
    tripsPerLine: 30,
  },
  assumptions: [
    "Single four-arm fixed-time signalised junction.",
    "Yielding is clearing, not pulling over.",
  ],
};

export function stat(
  metric: string,
  label: string,
  meanWith: number,
  meanBase: number,
  extra: Partial<PriorityStat> = {},
): PriorityStat {
  const diff = meanWith - meanBase;
  return {
    method: "paired_t",
    n_pairs: 4,
    mean_a: meanWith,
    mean_b: meanBase,
    difference: diff,
    ci_lower: diff - 2,
    ci_upper: diff + 2,
    confidence: 0.95,
    p_value: 0.012,
    alpha: 0.05,
    significant: true,
    direction: diff < 0 ? "a_lower" : "a_higher",
    statistic: -4.1,
    cautions: [],
    verdict: `A beats B: ${diff.toFixed(2)} (A minus B, 95% interval, p = 0.012, paired_t, n = 4)`,
    metric,
    label,
    lowerIsBetter: true,
    meanBaseline: meanBase,
    meanWithPriority: meanWith,
    changePercent: Math.round((10000 * diff) / meanBase) / 100,
    ...extra,
  };
}

const safe = (collisions: number[], ok = true): Safety => ({
  collisions,
  vehiclesConserved: true,
  signalAuditOk: ok,
  signalViolations: ok ? [] : ["minimum green violated"],
  preemptions: [1, 1, 1, 1],
});

export const emergencyFixture: EmergencyComparison = {
  kind: "emergency-comparison",
  inModelOnly: true,
  label: priorityCatalogueFixture.label,
  method: "paired_t",
  confidence: 0.95,
  seeds: [1, 2, 3, 4],
  droppedSeeds: [],
  perSeed: {
    withPreemption: {
      travelTime: [14, 15, 13.5, 14.5],
      delay: [1, 1.5, 0.8, 1.2],
      waitTime: [0, 0, 0, 0.5],
      collateralDelay: [6.2, 6.4, 6.1, 6.3],
    },
    baseline: {
      travelTime: [22, 25, 19, 24],
      delay: [9, 11, 6, 10],
      waitTime: [8, 10, 5, 9],
      collateralDelay: [5.8, 6, 5.7, 5.9],
    },
  },
  comparison: {
    emergencyTravelTime: stat(
      "emergencyTravelTime",
      "Emergency vehicle travel time (s)",
      14.25,
      22.5,
    ),
    emergencyDelay: stat(
      "emergencyDelay",
      "Emergency vehicle delay versus free flow (s)",
      1.125,
      9.0,
    ),
    emergencyWaitTime: stat(
      "emergencyWaitTime",
      "Emergency vehicle time stopped (s)",
      0.125,
      8.0,
    ),
    collateralDelay: stat(
      "collateralDelay",
      "Mean time lost by other vehicles (s per vehicle)",
      6.25,
      5.85,
      {
        significant: false,
        direction: "none",
        p_value: 0.21,
        verdict:
          "No reliable difference between A and B: 0.4 (A minus B, 95% interval -0.3 to 1.1, p = 0.21, paired_t, n = 4)",
      },
    ),
  },
  safety: {
    withPreemption: safe([0, 0, 0, 0]),
    baseline: safe([0, 0, 0, 0]),
  },
};

export const transitFixture: TransitComparison = {
  kind: "transit-comparison",
  inModelOnly: true,
  label: priorityCatalogueFixture.label,
  method: "paired_t",
  confidence: 0.95,
  seeds: [1, 2, 3, 4],
  droppedSeeds: [
    { seed: 5, reason: "no bus reached the stop line in one arm" },
  ],
  perSeed: {
    withPriority: {
      busScheduleLateness: [10, 12, 9, 11],
      busTimeLost: [8, 9, 7, 8],
      personDelayPerPerson: [20, 21, 19, 20],
      vehicleDelay: [18, 19, 17, 18],
      otherVehicleDelay: [17, 18, 16, 17],
    },
    baseline: {
      busScheduleLateness: [18, 20, 15, 19],
      busTimeLost: [14, 15, 12, 14],
      personDelayPerPerson: [22, 23, 21, 22],
      vehicleDelay: [17, 18, 16, 17],
      otherVehicleDelay: [16, 17, 15, 16],
    },
  },
  comparison: {
    busScheduleLateness: stat(
      "busScheduleLateness",
      "Bus lateness at the stop line (s)",
      10.5,
      18,
    ),
    busTimeLost: stat(
      "busTimeLost",
      "Bus time lost excluding dwell (s)",
      8,
      13.75,
    ),
    personDelayPerPerson: stat(
      "personDelayPerPerson",
      "Person delay (s per person)",
      20,
      22,
    ),
    vehicleDelay: stat(
      "vehicleDelay",
      "Vehicle delay (s per vehicle)",
      18,
      17,
      {
        significant: false,
        direction: "none",
      },
    ),
    otherVehicleDelay: stat(
      "otherVehicleDelay",
      "Delay of non-line vehicles (s per vehicle)",
      17,
      16,
      { significant: false, direction: "none" },
    ),
  },
  safety: {
    withPriority: safe([0, 0, 0, 0, 0]),
    baseline: safe([0, 0, 0, 0, 0], false),
  },
};
