/** Contract: GET /api/v3/experiments/{experimentId}/comparison?a=&b=&metric=
 *  (all three query parameters optional; the server picks the experiment's
 *  baseline, best alternative and primary metric). See src/CONTRACTS.md. */

export type Eligibility = "eligible" | "indicative" | "exploratory";

/** Server's call on the pair. Decided from the interval and p-value on the
 *  server; the screen only words it. */
export type Verdict = "a_better" | "b_better" | "no_clear_difference";

export interface ComparisonResult {
  experimentId: string;
  metric: {
    id: string;
    label: string;
    unit: string;
    lowerIsBetter: boolean;
  };
  a: { id: string; label: string };
  b: { id: string; label: string };
  /** Number of paired observations (seeds or sampled conditions). */
  pairs: number;
  /** Mean of (A minus B) per pair, in the metric's unit. */
  meanDifference: number;
  /** Interval for that mean difference. */
  ci: [number, number];
  /** 0.95 for a 95% interval. */
  confidenceLevel: number;
  pValue: number;
  method: {
    /** e.g. "Paired t-test" or "Paired bootstrap". */
    test: string;
    /** e.g. "Percentile bootstrap, 10,000 resamples". */
    interval: string;
    pairing: string;
  };
  effectSize?: { name: string; value: number } | null;
  verdict: Verdict;
  eligibility: Eligibility;
}
