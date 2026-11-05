import type { ComparisonResult } from "./types";

export const comparisonFixture: ComparisonResult = {
  experimentId: "exp1",
  metric: {
    id: "mean_delay",
    label: "Average delay",
    unit: "s per vehicle",
    lowerIsBetter: true,
  },
  a: { id: "adaptive", label: "Adaptive signal" },
  b: { id: "fixed", label: "Fixed-time signal" },
  pairs: 30,
  meanDifference: -4.2,
  ci: [-7.3, -1.1],
  confidenceLevel: 0.95,
  pValue: 0.012,
  method: {
    test: "Paired t-test",
    interval: "t-based interval on the mean of the paired differences",
    pairing: "Same seed and demand for both strategies",
  },
  effectSize: { name: "Paired Cohen d", value: -0.52 },
  verdict: "a_better",
  eligibility: "eligible",
};
