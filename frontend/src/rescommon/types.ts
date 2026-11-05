/** Shapes shared by the resilience screens (/app/resilience). Copied from
 *  backend/src/uncertainty/comparison.py (PairedComparison.to_dict) and the
 *  fields priority/comparison.py (_compare) adds. See src/CONTRACTS_P6.md. */

/** One paired comparison. The keys are snake_case because the server returns
 *  `dataclasses.asdict` output; `metric`, `label`, `verdict` and the camelCase
 *  keys are added by the priority router. */
export interface PairedStat {
  method: string;
  n_pairs: number;
  mean_a: number;
  mean_b: number;
  /** mean(a - b). */
  difference: number;
  ci_lower: number;
  ci_upper: number;
  confidence: number;
  p_value: number;
  alpha: number;
  significant: boolean;
  /** "a_lower", "a_higher" or "none". */
  direction: string;
  statistic: number | null;
  cautions: string[];
  verdict: string;
}

/** The priority router's extra keys on a PairedStat. */
export interface PriorityStat extends PairedStat {
  metric: string;
  label: string;
  lowerIsBetter: boolean;
  meanBaseline: number;
  meanWithPriority: number;
  changePercent: number | null;
}
