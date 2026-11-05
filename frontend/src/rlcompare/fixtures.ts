import type { RlComparison } from "./types";

export const rlFixture: RlComparison = {
  id: "rl1",
  junction: "Four-way junction, peak demand",
  metric: {
    id: "mean_delay",
    label: "Average delay",
    unit: "s per vehicle",
    lowerIsBetter: true,
  },
  fixedTime: { label: "Fixed-time signal" },
  rl: {
    label: "RL policy",
    policyId: "dqn-7",
    algorithm: "DQN",
    trainingSteps: 500000,
  },
  difference: { mean: -3.4, ci: [-5.9, -0.9], pValue: 0.009 },
  confidenceLevel: 0.95,
  verdict: "rl_better",
  scenarios: [
    {
      scenarioId: "peak",
      label: "Peak demand",
      fixedTime: { mean: 31.2, ci: [29.8, 32.6], n: 20 },
      rl: { mean: 27.1, ci: [25.9, 28.3], n: 20 },
    },
    {
      scenarioId: "offpeak",
      label: "Off-peak demand",
      fixedTime: { mean: 12.4, ci: [11.9, 12.9], n: 20 },
      rl: { mean: 12.9, ci: [12.3, 13.5], n: 20 },
    },
  ],
  caveats: [
    "Trained and tested on the same junction; not shown to transfer.",
    "The fixed-time plan is a standard Webster plan, not a tuned one.",
  ],
};
