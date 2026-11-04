import { comparisonFixture } from "../comparison/fixtures";
import { metricsFixture } from "../kpis/fixtures";
import { sensitivityFixture } from "../sensitivity/fixtures";
import type { ReportDocument } from "./types";

export const reportFixture: ReportDocument = {
  experimentId: "exp1",
  title: "Peak hour: adaptive versus fixed-time signal",
  generatedAt: "2026-11-04T08:00:00Z",
  assumptions: [
    "Demand follows the stated arrival-rate distribution, not counted traffic.",
    "Drivers follow the simulator's car-following model.",
  ],
  limitations: [
    "One junction only; results do not transfer to a network.",
    "Safety and emissions numbers are model estimates.",
  ],
  summary: {
    text: "Adaptive signal beats Fixed-time signal on average delay by 4.2 s per vehicle.",
    grounded: true,
  },
  comparison: comparisonFixture,
  sensitivity: sensitivityFixture,
  metrics: metricsFixture,
  manifest: {
    seed: 42,
    configHash: "a1b2c3",
    codeVersion: "59f57cc",
    inputVersion: null,
  },
};
