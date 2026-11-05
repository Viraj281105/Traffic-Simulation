/**
 * Contract: /api/v2/twin/compare and /api/v2/twin/whatif (stateless digital
 * twin). Source of truth: backend/src/twin/router.py, runner.py (state),
 * compare.py (scoring) and whatif.py. See src/CONTRACTS_P5.md.
 *
 * Counts are vehicles that left a link during one interval. Time is cut into
 * windows of `intervalSeconds` from `start`. MAE and bias are in vehicles per
 * window; MAPE is a percent over windows with an observation above zero (null
 * when there are none). Bias is the mean of predicted minus observed.
 */

export interface TwinObservation {
  linkId: string;
  /** Seconds on the feed's own clock: the start of the interval. */
  timestamp: number;
  count: number;
  /** Metres per second, optional. */
  meanSpeed?: number;
}

export interface TwinFlowInput {
  origin: string;
  destination: string;
  vehiclesPerHour: number;
}

/** Body of POST /api/v2/twin/compare. `graph` and `flows` default to the
 *  two-junction corridor when left out. */
export interface TwinRequest {
  observations: TwinObservation[];
  graph?: Record<string, unknown>;
  flows?: TwinFlowInput[];
  intervalSeconds?: number;
  warmupSeconds?: number;
  start?: number;
  seed?: number;
  alertThresholdPct?: number;
}

export interface TwinScenario {
  closeLinks: string[];
  demandScale: number;
  lanes?: Record<string, number>;
  speedFactors?: Record<string, number>;
}

export interface SeriesScore {
  n: number;
  mae: number | null;
  mape: number | null;
  bias: number | null;
}

export interface NetworkScore extends SeriesScore {
  /** Windows by which the observations lag (+) or lead (-) the prediction. */
  lagWindows: number;
  lagSeconds: number;
}

export interface NetworkPoint {
  window: number;
  predicted: number;
  observed: number;
  error: number;
  /** Null when the observation was zero. */
  errorPct: number | null;
}

export interface TwinAlert {
  /** Null for the overall (whole-series) alert. */
  window: number | null;
  kind: "window" | "overall";
  errorPct: number;
  thresholdPct: number;
}

export interface TwinComparison {
  network: NetworkScore;
  perLink: Record<string, SeriesScore>;
  series: NetworkPoint[];
  alertThresholdPct: number;
  alert: boolean;
  alerts: TwinAlert[];
}

export interface TimelineWindow {
  window: number;
  /** Start of the window, seconds. */
  time: number;
  predicted: Record<string, number>;
  observed: Record<string, number>;
  observedSpeed: Record<string, number>;
}

export interface TwinState {
  format: "urbanflow-twin-state";
  version: number;
  /** Name of the road graph. */
  graph: string;
  intervalSeconds: number;
  warmupSeconds: number;
  seed: number;
  start: number;
  latestWindow: number | null;
  currentFlows: TwinFlowInput[];
  timeline: TimelineWindow[];
  comparison: TwinComparison;
}

/** Body of POST /api/v2/twin/whatif. */
export interface WhatIfRequest extends TwinRequest {
  scenario: TwinScenario;
  /** 1 to 12 windows to forecast. */
  horizonWindows?: number;
}

export interface ScenarioOutcome {
  completed: number;
  /** Null when no vehicle completed. */
  meanDelaySeconds: number | null;
  meanTravelSeconds: number | null;
}

export interface WhatIfLink {
  baseline: number;
  /** Null when the link is closed in the variant. */
  variant: number | null;
  delta: number | null;
  peakOccupancyDelta: number | null;
}

export interface WhatIfResult {
  /** The first forecast window. */
  window: number;
  horizonWindows: number;
  scenario: {
    closeLinks: string[];
    demandScale: number;
    lanes: Record<string, number>;
    speedFactors: Record<string, number>;
  };
  baseline: ScenarioOutcome;
  variant: ScenarioOutcome & { unroutable: number };
  delta: {
    completed: number;
    meanDelaySeconds: number | null;
    meanTravelSeconds: number | null;
  };
  perLink: Record<string, WhatIfLink>;
}
