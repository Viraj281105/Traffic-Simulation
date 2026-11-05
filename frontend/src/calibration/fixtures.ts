/** Contract fixtures for the network calibration report (shape of
 *  calibrate_network and recalibrate). Not real measurements. */
import type {
  CalibrationReport,
  CountsProvenance,
  CountsValidation,
  Recalibration,
} from "./types";

const criteria = {
  geh_limit: 5,
  min_fraction: 0.85,
  max_mape: null,
  max_rmse: null,
};

export const countsProvenance: CountsProvenance = {
  source: "upload",
  sha256: "9f2c1d0a7b",
  rows: 24,
  links: 4,
  sensors: 4,
  intervals: 6,
  intervalSeconds: 900,
  intervalSecondsInferred: false,
  firstIntervalStart: "2026-03-10T07:00:00Z",
  lastIntervalStart: "2026-03-10T08:15:00Z",
  warnings: [],
};

export const reportFixture: CalibrationReport = {
  format: "urbanflow-network-calibration",
  version: 1,
  status: "PASS",
  gate: "G-CAL",
  before: {
    metrics: {
      links: 4,
      rmseVph: 142.3,
      mapePercent: 24.8,
      r2: 0.71,
      meanGeh: 6.1,
      gehUnderLimitFraction: 0.5,
      mapeLinks: 4,
      mapeSkippedLinks: 0,
      minObservedVph: 10,
    },
    gCal: {
      passed: false,
      criteria,
      linksChecked: 4,
      linksPassingGeh: 2,
      gehFraction: 0.5,
      reasons: ["GEH < 5 on 50.0% of links; 85% required"],
    },
    objective: 0.3012,
  },
  after: {
    metrics: {
      links: 4,
      rmseVph: 31.4,
      mapePercent: 6.2,
      r2: 0.97,
      meanGeh: 1.9,
      gehUnderLimitFraction: 1,
      mapeLinks: 4,
      mapeSkippedLinks: 0,
      minObservedVph: 10,
    },
    gCal: {
      passed: true,
      criteria,
      linksChecked: 4,
      linksPassingGeh: 4,
      gehFraction: 1,
      reasons: [],
    },
    objective: 0.0412,
  },
  parameters: {
    fitted: { "demand:W->E": 1.18, "demand:N1->S2": 0.92, "speed:all": 1.05 },
    start: { "demand:W->E": 1, "demand:N1->S2": 1, "speed:all": 1 },
    bounds: {
      "demand:W->E": [0.2, 3],
      "demand:N1->S2": [0.2, 3],
      "speed:all": [0.5, 1.5],
    },
    speedGroups: { all: ["J1>J2", "J2>E", "N1>J1", "W>J1"] },
    fittedDemandVph: { "W->E": 708, "N1->S2": 138 },
  },
  perLink: [
    {
      linkId: "J1>J2",
      observedVph: 640,
      before: {
        simulatedVph: 540,
        residualVph: -100,
        geh: 4.1,
        percentError: -15.6,
      },
      after: {
        simulatedVph: 652,
        residualVph: 12,
        geh: 0.5,
        percentError: 1.9,
      },
    },
    {
      linkId: "J2>E",
      observedVph: 610,
      before: {
        simulatedVph: 480,
        residualVph: -130,
        geh: 5.6,
        percentError: -21.3,
      },
      after: {
        simulatedVph: 590,
        residualVph: -20,
        geh: 0.8,
        percentError: -3.3,
      },
    },
    {
      linkId: "N1>J1",
      observedVph: 150,
      before: {
        simulatedVph: 195,
        residualVph: 45,
        geh: 3.4,
        percentError: 30,
      },
      after: {
        simulatedVph: 140,
        residualVph: -10,
        geh: 0.8,
        percentError: -6.7,
      },
    },
    {
      linkId: "W>J1",
      observedVph: 720,
      before: {
        simulatedVph: 540,
        residualVph: -180,
        geh: 7.2,
        percentError: -25,
      },
      after: {
        simulatedVph: 702,
        residualVph: -18,
        geh: 0.7,
        percentError: -2.5,
      },
    },
  ],
  optimiser: {
    method: "coordinate-search",
    seed: 1,
    budget: 150,
    evaluations: 64,
    sweeps: 7,
    stopReason: "converged",
    finalStep: 0.0125,
    trace: [
      { evaluations: 1, step: 0.2, objective: 0.3012 },
      { evaluations: 64, step: 0.0125, objective: 0.0412 },
    ],
  },
  simulation: { duration: 600, seed: 1 },
  provenance: {
    counts: countsProvenance,
    network: {
      name: "Two-junction corridor",
      source: "corridor",
      nodes: 8,
      links: 4,
    },
    countedLinks: 4,
    linksWithoutCounts: 0,
  },
  thresholds: {
    gCal: criteria,
    minObservedVph: 10,
    gehNote:
      "GEH < 5 on >= 85% of links (UK DMRB/TfL guidance); placeholder for the agreed G-CAL error (D1)",
  },
  manifest: {
    version: 1,
    hash: "3b7e0c5d9a41f2e86c0d1a7b5e93f4a2c8d6b0e1f7a3c9d5b2e8f4a6c0d1e7b3",
    graphSha256:
      "a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90",
    note: "sha256 of the canonical JSON of every input; equal hash and code version give an equal report",
  },
  notes: [],
};

export const failingReportFixture: CalibrationReport = {
  ...reportFixture,
  status: "FAIL",
  after: {
    ...reportFixture.after,
    gCal: {
      passed: false,
      criteria,
      linksChecked: 4,
      linksPassingGeh: 2,
      gehFraction: 0.5,
      reasons: ["GEH < 5 on 50.0% of links; 85% required"],
    },
  },
  notes: [
    "G-CAL not met: GEH < 5 on 50.0% of links; 85% required",
    "The evaluation budget ran out before the search converged",
  ],
};

export const recalibration: Recalibration = {
  windowIntervals: 4,
  windowFirstIntervalStart: "2026-03-10T07:30:00Z",
  windowLastIntervalStart: "2026-03-10T08:15:00Z",
  warmStartFrom: {
    "demand:W->E": 1.18,
    "demand:N1->S2": 0.92,
    "speed:all": 1.05,
  },
  previousParametersGCalPassed: false,
  drift: {
    threshold: 0.15,
    maxAbsRelativeChange: 0.22,
    flagged: ["demand:N1->S2"],
    drifted: true,
    parameters: [
      {
        name: "demand:N1->S2",
        previous: 0.92,
        current: 1.122,
        relativeChange: 0.2196,
        flag: true,
      },
      {
        name: "demand:W->E",
        previous: 1.18,
        current: 1.2,
        relativeChange: 0.0169,
        flag: false,
      },
      {
        name: "speed:all",
        previous: 1.05,
        current: 1.04,
        relativeChange: -0.0095,
        flag: false,
      },
    ],
  },
};

export const recalibratedFixture: CalibrationReport = {
  ...reportFixture,
  recalibration,
};

export const countsValidFixture: CountsValidation = {
  valid: true,
  errors: [],
  warnings: [],
  provenance: countsProvenance,
  linkFlowsVph: { "J1>J2": 640, "J2>E": 610, "N1>J1": 150, "W>J1": 720 },
};

export const countsInvalidFixture: CountsValidation = {
  valid: false,
  errors: ["Line 3: link_id 'X>Y' is not in the network"],
  warnings: [],
  provenance: { ...countsProvenance, rows: 0, links: 0, intervals: 0 },
  linkFlowsVph: {},
};
