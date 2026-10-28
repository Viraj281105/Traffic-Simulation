/**
 * The Monte Carlo validation study as the dashboard reads it: the backend's
 * result (study/validation.py run_statistical_validation), the settings of
 * the next run and how they become a request, the per-seed tallies, chart
 * rows and CSV the views show, and the display rules for effect sizes.
 * No React.
 */
import { DEFAULT_CONFIG_VALUES } from "../../types/config";
import { SIMILARITY, compare } from "../../metrics/plainLanguage";
import { SERIES } from "../../theme/chart";

export interface StatResult {
  mean: number;
  std: number;
  min: number;
  max: number;
  /** Student-t half-width at the run's confidence level. */
  ci?: number;
  /** Student-t half-width at 95 % (always present). */
  ci95: number;
  ciConfidence?: number;
  ciDegreesOfFreedom?: number;
  ciCriticalValue?: number;
}

export interface SeedRun {
  seed: number;
  signal: { delay: number; throughput: number; queue: number };
  roundabout: { delay: number; throughput: number; queue: number };
}

/** Welch's t-test result from the backend (_compare_groups). */
export interface GroupComparison {
  pValue: number | null;
  significant: boolean;
  /** Null when no test statistic is defined (see untestableReason). */
  cohensD: number | null;
  /** Welch-Satterthwaite degrees of freedom (absent for degenerate cases). */
  degreesOfFreedom?: number;
  /** Why there is no p-value: too few seeds, an invalid value, or no
   *  seed-to-seed variation in either control. */
  untestableReason?: "insufficient_data" | "invalid_data" | "no_variation";
}

export interface ValidationResult {
  numSeeds: number;
  /** Level the intervals and significance flags were computed at; alpha is
   *  1 - level. Both come from the backend, which is what ran the test. */
  confidenceLevel?: number;
  alpha?: number;
  calibration?: { calibrated: boolean; note: string };
  vehicleLimitReachedSeeds?: number[];
  signal: {
    delay: StatResult;
    throughput: StatResult;
    queue: StatResult;
  };
  roundabout: {
    delay: StatResult;
    throughput: StatResult;
    queue: StatResult;
  };
  comparison: {
    delay: GroupComparison;
    throughput: GroupComparison;
    queue: GroupComparison;
  };
  seedRuns: SeedRun[];
}

export const METRIC_KEYS = ["delay", "throughput", "queue"] as const;
export type MetricKey = (typeof METRIC_KEYS)[number];

export const METRIC_LABELS: Record<MetricKey, string> = {
  delay: "Avg Delay (s)",
  throughput: "Throughput (veh)",
  queue: "Avg Queue (veh)",
};

export const METRIC_UNITS: Record<MetricKey, string> = {
  delay: "seconds",
  throughput: "vehicles",
  queue: "vehicles",
};

// ── Settings of the next run ────────────────────────────────────────────────

export interface ValidationSettings {
  numSeeds: number;
  duration: number;
  lanesCount: 1 | 2 | 3;
  arrivalRate: number;
  arrivalDistribution: "poisson" | "uniform";
  warmupTime: number;
  timeStep: number;
  approachLength: number;
  confidenceLevel: 0.9 | 0.95 | 0.99;
}

/** What "Reset defaults" restores, and where the studio starts. */
export const DEFAULT_VALIDATION_SETTINGS: ValidationSettings = {
  numSeeds: 5,
  duration: 240,
  lanesCount: 1,
  arrivalRate: DEFAULT_CONFIG_VALUES.arrivalRate,
  arrivalDistribution: "poisson",
  warmupTime: 30.0,
  timeStep: 0.1,
  approachLength: 200.0,
  confidenceLevel: 0.95,
};

/** The study's own engine configuration (customConfig of the Monte Carlo
 *  request) for a run of `duration` seconds per seed. */
export function validationCustomConfig(
  settings: ValidationSettings,
  duration: number,
) {
  const lanes = settings.lanesCount;
  return {
    simulation: {
      timeStep: settings.timeStep,
      duration,
      warmupTime: settings.warmupTime,
    },
    roads: {
      approachLength: settings.approachLength,
      laneWidth: 3.5,
      lanesPerApproach: {
        north: lanes,
        south: lanes,
        east: lanes,
        west: lanes,
      },
    },
    traffic: {
      arrivalRate: settings.arrivalRate,
      arrivalDistribution: settings.arrivalDistribution,
    },
  };
}

// ── Reading a result ────────────────────────────────────────────────────────

/** Which control had the lower delay on one seed, by the app-wide "about the
 *  same" rule (plainLanguage SIMILARITY.delay = backend study/tolerances.py). */
export function lowerDelayOf(run: SeedRun): "signal" | "roundabout" | "tie" {
  return (
    compare(run.signal.delay, run.roundabout.delay, SIMILARITY.delay)?.lower ??
    "tie"
  );
}

/** Seeds by which control had the lower delay, so a fraction of a second is
 *  never counted as one control "winning". */
export function lowerDelayTally(result: ValidationResult | null) {
  const tally = { roundabout: 0, signal: 0, same: 0, total: 0 };
  if (!result) return tally;
  for (const r of result.seedRuns) {
    const lower = lowerDelayOf(r);
    tally.total += 1;
    if (lower === "roundabout") tally.roundabout += 1;
    else if (lower === "signal") tally.signal += 1;
    else tally.same += 1;
  }
  return tally;
}

/** One bar pair per seed for the chosen metric. */
export function seedChartRows(
  result: ValidationResult | null,
  metric: MetricKey,
) {
  if (!result) return [];
  return result.seedRuns.map((r) => ({
    seed: r.seed.toString(),
    signal: Number(r.signal[metric].toFixed(2)),
    roundabout: Number(r.roundabout[metric].toFixed(2)),
    delta: Number((r.roundabout[metric] - r.signal[metric]).toFixed(2)),
  }));
}

/** The per-seed dataset as CSV text (header row first). */
export function validationCsv(result: ValidationResult): string {
  const headers = [
    "Seed",
    "Signal Delay (s)",
    "Roundabout Delay (s)",
    "Delta Delay (s)",
    "Signal Throughput (veh)",
    "Roundabout Throughput (veh)",
    "Signal Queue (veh)",
    "Roundabout Queue (veh)",
    "Lower delay",
  ];
  const rows = result.seedRuns.map((r) => {
    const lower = lowerDelayOf(r);
    return [
      r.seed.toString(),
      r.signal.delay.toFixed(2),
      r.roundabout.delay.toFixed(2),
      (r.roundabout.delay - r.signal.delay).toFixed(2),
      r.signal.throughput.toFixed(1),
      r.roundabout.throughput.toFixed(1),
      r.signal.queue.toFixed(2),
      r.roundabout.queue.toFixed(2),
      lower === "roundabout"
        ? "Roundabout"
        : lower === "signal"
          ? "Signal"
          : "About the same",
    ];
  });
  return [headers.join(","), ...rows.map((e) => e.join(","))].join("\n");
}

// ── Display rules ───────────────────────────────────────────────────────────

export const SIGNAL_COLOR = "#3b82f6"; // Vibrant blue
export const ROUND_COLOR = "#10b981"; // Emerald green

export function getCohensDLabel(d: number | null): {
  label: string;
  color: string;
  bg: string;
} {
  // No effect size is defined (too few seeds, or no variation to scale by).
  if (d === null)
    return {
      label: "No test applies",
      color: "#64748b",
      bg: "rgba(100, 116, 139, 0.12)",
    };
  const absD = Math.abs(d);
  if (absD >= 0.8)
    return {
      label: "Large Effect",
      color: SERIES.signal,
      bg: "rgba(245, 158, 11, 0.12)",
    };
  if (absD >= 0.5)
    return {
      label: "Medium Effect",
      color: "#3b82f6",
      bg: "rgba(59, 130, 246, 0.12)",
    };
  if (absD >= 0.2)
    return {
      label: "Small Effect",
      color: "#8b5cf6",
      bg: "rgba(139, 92, 246, 0.12)",
    };
  return {
    label: "Negligible",
    color: "#64748b",
    bg: "rgba(100, 116, 139, 0.12)",
  };
}
