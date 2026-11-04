import type { RunMetrics } from "./types";

export const metricsFixture: RunMetrics = {
  runId: "run1",
  vehiclesCompleted: 1840,
  delay: {
    mean: { value: 18.4, unit: "s", ci: [17.1, 19.7] },
    p95: { value: 52.9, unit: "s" },
    definition: "Time beyond free-flow travel time, per vehicle.",
  },
  travelTime: {
    mean: { value: 61.2, unit: "s", ci: [59.8, 62.6] },
    p95: { value: 101.5, unit: "s" },
    definition: "Time from entering to leaving the modelled area.",
  },
  safety: {
    minTtc: { value: 1.4, unit: "s" },
    conflicts: { value: 37, unit: "" },
    thresholdSeconds: 1.5,
    definition:
      "Time-to-collision from simulated vehicle positions and speeds.",
  },
  emissions: {
    fuel: { value: 212.6, unit: "L" },
    co2: { value: 493.2, unit: "kg" },
    co2PerVehicle: { value: null, unit: "g" },
    model: { name: "Speed-based emission factors", version: "1" },
    definition: "Fuel and CO2 estimated from speed and acceleration.",
  },
  notes: ["Light vehicles only; no cold-start effects."],
};
