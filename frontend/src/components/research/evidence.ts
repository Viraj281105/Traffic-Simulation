/**
 * The comparison rule the Research Lab teaches, plus the *illustrative* data
 * its diagrams use.
 *
 * The rule mirrors backend/src/study/control_comparison.py (`_paired_delay`),
 * study/tolerances.py and study/validation.py (`DEFAULT_CONFIDENCE_LEVEL`);
 * evidence.test.ts reads those files and fails if a constant drifts. The
 * example numbers below are made up for teaching. Every diagram that uses
 * them says so on the page; they are never presented as a study result.
 */
import { SIMILARITY } from "../../metrics/plainLanguage";

/** Confidence level of every interval a study reports. */
export const CONFIDENCE_LEVEL = 0.95;

/** "About the same": within `abs` seconds or `rel` of the larger mean. A
 *  presentation tolerance, not a significance test. */
export const TIE = SIMILARITY.delay;

/** Two-sided 95 % Student-t multipliers, t(n-1), for the seed counts the
 *  studies offer (3, 5 and 10 seeds). */
export const T_95: Readonly<Record<number, number>> = {
  2: 4.303,
  4: 2.776,
  9: 2.262,
};

export type Reading = "lower" | "higher" | "tie" | "inconclusive";

export interface PairedReading {
  n: number;
  meanA: number;
  meanB: number;
  /** Mean of the per-seed differences, A minus B. */
  meanDifference: number;
  ciLow: number;
  ciHigh: number;
  /** Sample standard deviation of the per-seed differences. */
  sd: number;
  /** Half-width of the interval, t(n-1) * sd / sqrt(n). */
  half: number;
  /** Half-width of the "about the same" band for these two means. */
  tieBand: number;
  reading: Reading;
}

const mean = (xs: readonly number[]) =>
  xs.reduce((s, x) => s + x, 0) / xs.length;

/** The implemented decision: ties are checked first, on the two means; then
 *  the interval of the paired differences must exclude zero. */
export function pairedReading(
  a: readonly number[],
  b: readonly number[],
): PairedReading {
  const n = a.length;
  const diffs = a.map((x, i) => x - b[i]);
  const meanA = mean(a);
  const meanB = mean(b);
  const meanDifference = mean(diffs);
  const sd = Math.sqrt(
    diffs.reduce((s, d) => s + (d - meanDifference) ** 2, 0) / (n - 1),
  );
  const half = (T_95[n - 1] * sd) / Math.sqrt(n);
  const ciLow = meanDifference - half;
  const ciHigh = meanDifference + half;
  const gap = Math.abs(meanA - meanB);
  const larger = Math.max(Math.abs(meanA), Math.abs(meanB));
  const tieBand = Math.max(TIE.abs, TIE.rel * larger);
  let reading: Reading;
  if (gap <= tieBand) reading = "tie";
  else if (ciHigh < 0 || ciLow > 0)
    reading = meanDifference < 0 ? "lower" : "higher";
  else reading = "inconclusive";
  return {
    n,
    meanA,
    meanB,
    meanDifference,
    ciLow,
    ciHigh,
    sd,
    half,
    tieBand,
    reading,
  };
}

/** ── Illustrative data: two controls over ten runs (ComparisonExplainer). ── */
export const EXAMPLE_TWO = {
  a: [34, 41, 29, 38, 36, 44, 31, 39, 35, 40],
  b: [30, 33, 31, 31, 32, 35, 28, 34, 33, 34],
} as const;

/** ── Illustrative data: three controls, five matched seeds (methods page). ── */
export const EXAMPLE_THREE = {
  seeds: [1, 2, 3, 4, 5],
  fixed_time: [38, 45, 33, 41, 40],
  adaptive: [31, 37, 30, 34, 33],
  roundabout: [32, 30, 36, 33, 35],
} as const;

export type ExampleControl = "fixed_time" | "adaptive" | "roundabout";

export const EXAMPLE_PAIRS: {
  key: string;
  a: ExampleControl;
  b: ExampleControl;
}[] = [
  { key: "adaptive_vs_fixed_time", a: "adaptive", b: "fixed_time" },
  { key: "adaptive_vs_roundabout", a: "adaptive", b: "roundabout" },
  { key: "fixed_time_vs_roundabout", a: "fixed_time", b: "roundabout" },
];

export const CONTROL_NAME: Record<ExampleControl, string> = {
  fixed_time: "Fixed-time",
  adaptive: "Adaptive",
  roundabout: "Roundabout",
};

/** The words a study uses for a reading of "a versus b". */
export function readingWords(reading: Reading, a: string, b: string): string {
  switch (reading) {
    case "lower":
      return `${a} lower`;
    case "higher":
      return `${b} lower`;
    case "tie":
      return "About the same";
    case "inconclusive":
      return "Inconclusive";
  }
}
