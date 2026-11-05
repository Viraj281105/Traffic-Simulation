/** Contract: GET /api/v3/rl/comparisons/{comparisonId}. See src/CONTRACTS.md.
 *  RL policy against the fixed-time plan on the same junction and seeds. */

export interface Estimate {
  mean: number;
  ci: [number, number];
  /** Number of seeds behind the estimate. */
  n: number;
}

export interface ScenarioResult {
  scenarioId: string;
  label: string;
  fixedTime: Estimate;
  rl: Estimate;
}

export interface RlComparison {
  id: string;
  junction: string;
  metric: { id: string; label: string; unit: string; lowerIsBetter: boolean };
  fixedTime: { label: string };
  rl: {
    label: string;
    policyId: string;
    algorithm: string;
    trainingSteps: number;
  };
  /** Overall, across scenarios: (RL minus fixed-time). */
  difference: { mean: number; ci: [number, number]; pValue: number };
  confidenceLevel: number;
  verdict: "rl_better" | "fixed_better" | "no_clear_difference";
  scenarios: ScenarioResult[];
  /** Plain statements the server wants shown with the result. */
  caveats: string[];
}
