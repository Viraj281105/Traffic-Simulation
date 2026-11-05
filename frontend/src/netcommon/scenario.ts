/** The scenario the simulated-network screens run: a grid, as the network-metrics
 *  endpoints accept it (backend/src/netmetrics/router.py, RunRequest). */

export type GridPreset = "3x3" | "12-junction" | "custom";

export interface ScenarioInput {
  preset: GridPreset;
  rows: number;
  cols: number;
  vehiclesPerHour: number;
  duration: number;
  seed: number;
}

export const DEFAULT_SCENARIO: ScenarioInput = {
  preset: "3x3",
  rows: 3,
  cols: 3,
  vehiclesPerHour: 300,
  duration: 600,
  seed: 1,
};

/** The `grid` object of a request body. */
export function gridBody(s: ScenarioInput): Record<string, unknown> {
  return s.preset === "custom"
    ? { rows: s.rows, cols: s.cols, vehiclesPerHour: s.vehiclesPerHour }
    : { preset: s.preset, vehiclesPerHour: s.vehiclesPerHour };
}

/** The shared fields of a RunRequest body. */
export function runBody(
  s: ScenarioInput,
  extra: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    grid: gridBody(s),
    duration: s.duration,
    seed: s.seed,
    bucketSeconds: 30,
    includeMap: true,
    ...extra,
  };
}

/** Server limits (RunRequest / GridSpec), used to keep the form inside them. */
export const LIMITS = {
  rows: [1, 12],
  cols: [1, 12],
  vehiclesPerHour: [0, 3600],
  duration: [30, 3600],
} as const;

export function clampTo(
  value: number,
  [lo, hi]: readonly [number, number],
): number {
  if (!Number.isFinite(value)) return lo;
  return Math.min(hi, Math.max(lo, value));
}
