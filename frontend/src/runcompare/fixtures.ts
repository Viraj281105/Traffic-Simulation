import type { RunDiff } from "./types";

export const runDiffFixture: RunDiff = {
  a: { runId: "run-a", label: "Baseline", createdAt: "2026-11-02T09:00:00Z" },
  b: { runId: "run-b", label: "Adaptive", createdAt: "2026-11-02T10:00:00Z" },
  sameInputs: false,
  manifest: [
    { field: "seed", label: "Seed", a: "42", b: "42", same: true },
    {
      field: "config_hash",
      label: "Configuration",
      a: "a1b2c3",
      b: "d4e5f6",
      same: false,
    },
    {
      field: "code_version",
      label: "Code version",
      a: "59f57cc",
      b: "59f57cc",
      same: true,
    },
  ],
  metrics: [
    {
      id: "mean_delay",
      label: "Average delay",
      unit: "s",
      lowerIsBetter: true,
      a: 22.5,
      b: 18.4,
      delta: -4.1,
      deltaFraction: -0.182,
    },
    {
      id: "throughput",
      label: "Vehicles served",
      unit: "veh",
      lowerIsBetter: false,
      a: 1800,
      b: 1840,
      delta: 40,
      deltaFraction: 0.022,
    },
    {
      id: "co2",
      label: "CO2",
      unit: "kg",
      lowerIsBetter: true,
      a: null,
      b: 493.2,
      delta: null,
      deltaFraction: null,
    },
  ],
};
