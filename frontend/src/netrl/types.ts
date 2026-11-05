/**
 * Contract: the network RL evaluation document (`urbanflow-rl-eval` v1,
 * kind "network"), written by backend/src/rl/network_eval.py
 * (compare_network) and wrapped by scripts/produce_rl_comparison.py. See
 * src/CONTRACTS_P5.md. Keys are snake_case, as the backend writes them.
 *
 * `policies[name][metric]` is one value per held-out seed; every policy ran
 * the same seeds, so the values pair up by position. `wall_seconds` is a
 * single number, not a per-seed list. `paired_comparisons` is RL minus each
 * baseline per compared metric, computed by the server
 * (src/uncertainty/comparison.py: compare_paired, verdict): the UI never
 * recomputes an interval or a p-value.
 *
 * Also read here: GET /api/v3/rl/comparisons/{id} (RlComparison, see
 * src/rlcompare/types.ts), the junction-level comparison.
 */

export interface PairedStats {
  method: string;
  n_pairs: number;
  mean_a: number;
  mean_b: number;
  /** mean(RL - baseline). */
  difference: number;
  ci_lower: number;
  ci_upper: number;
  /** 0.95 = a 95% interval. */
  confidence: number;
  p_value: number;
  alpha: number;
  significant: boolean;
  direction: "a_lower" | "a_higher" | "none";
  statistic: number | null;
  cautions: string[];
}

export interface PairedComparisonRow {
  rl: string;
  baseline: string;
  metric: string;
  lower_is_better: boolean;
  comparison: PairedStats;
  /** Plain-words verdict from the server, naming both policies. */
  verdict: string;
}

export type PolicyResults = Record<string, number[] | number>;

export interface RlEvalDocument {
  format: "urbanflow-rl-eval";
  version: number;
  kind: "network";
  seeds: number[];
  env: Record<string, unknown>;
  signal_nodes: string[];
  baseline_fixed_green_s: number;
  metrics: string[];
  lower_is_better: string[];
  policies: Record<string, PolicyResults>;
  paired_comparisons: PairedComparisonRow[];
  comparison_method: string;
  confidence: number;
  cautions: string[];
  environment: { python: string; platform: string };
}
