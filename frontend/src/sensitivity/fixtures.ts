import type { SensitivityResult } from "./types";

export const sensitivityFixture: SensitivityResult = {
  experimentId: "exp1",
  metric: { id: "mean_delay", label: "Average delay", unit: "s per vehicle" },
  method: { name: "Sobol indices", seed: 42, samples: 2048 },
  inputs: [
    {
      id: "arrival_rate",
      label: "Arrival rate",
      firstOrder: 0.18,
      total: 0.22,
      ci: [0.14, 0.22],
    },
    {
      id: "demand_scale",
      label: "Demand scale",
      firstOrder: 0.61,
      total: 0.68,
      ci: [0.55, 0.67],
    },
    {
      id: "heavy_share",
      label: "Heavy vehicle share",
      firstOrder: 0.05,
      total: 0.08,
      ci: [0.02, 0.08],
    },
  ],
};
