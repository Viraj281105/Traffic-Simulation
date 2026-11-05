/**
 * Contract: /api/v2/calibration/network-fit (network calibration report).
 * Source of truth: backend/src/calibration/network_fit.py (calibrate_network),
 * network_metrics.py (fit metrics, gate G-CAL), network_recalibration.py and
 * network_calibration_router.py. See src/CONTRACTS_P5.md.
 *
 * Flows are vehicles per hour on a link. GEH = sqrt(2 (M - C)^2 / (M + C))
 * for modelled flow M and counted flow C. The default G-CAL rule (GEH < 5 on
 * at least 85% of links) is a placeholder for the agreed error (decision D1);
 * the criteria that were applied come back in every report.
 */

export interface FitMetrics {
  links: number;
  rmseVph: number | null;
  /** Percent; null when no link had a count above `minObservedVph`. */
  mapePercent: number | null;
  /** Null when the counts do not vary. */
  r2: number | null;
  meanGeh: number | null;
  gehUnderLimitFraction: number | null;
  mapeLinks: number;
  mapeSkippedLinks: number;
  minObservedVph: number;
}

export interface GCalCriteria {
  geh_limit: number;
  min_fraction: number;
  max_mape: number | null;
  max_rmse: number | null;
}

export interface GCalCheck {
  passed: boolean;
  criteria: GCalCriteria;
  linksChecked: number;
  linksPassingGeh: number;
  gehFraction: number | null;
  /** Plain-language reasons the gate failed; empty when it passed. */
  reasons: string[];
}

export interface FitSide {
  metrics: FitMetrics;
  gCal: GCalCheck;
  objective: number;
}

export interface LinkFit {
  simulatedVph: number;
  residualVph: number;
  geh: number;
  /** Null when the counted flow is below the minimum. */
  percentError: number | null;
}

export interface PerLinkFit {
  linkId: string;
  observedVph: number;
  before: LinkFit;
  after: LinkFit;
}

export interface CountsProvenance {
  source: string;
  sha256: string;
  rows: number;
  links: number;
  sensors: number;
  intervals: number;
  intervalSeconds: number;
  intervalSecondsInferred: boolean;
  firstIntervalStart: string | null;
  lastIntervalStart: string | null;
  warnings: string[];
}

export interface CalibrationReport {
  format: "urbanflow-network-calibration";
  version: number;
  status: "PASS" | "FAIL";
  gate: "G-CAL";
  before: FitSide;
  after: FitSide;
  parameters: {
    /** Scale factors by name: "demand:ORIGIN->DEST" and speed-group names. */
    fitted: Record<string, number>;
    start: Record<string, number>;
    bounds: Record<string, [number, number]>;
    speedGroups: Record<string, string[]>;
    fittedDemandVph: Record<string, number>;
  };
  perLink: PerLinkFit[];
  optimiser: {
    method: string;
    seed: number;
    budget: number;
    evaluations: number;
    sweeps: number;
    stopReason: string;
    finalStep: number;
    trace: { evaluations: number; step: number; objective: number }[];
  };
  simulation: { duration: number; seed: number; [key: string]: unknown };
  provenance: {
    counts: CountsProvenance;
    network: {
      name: string;
      source?: string | null;
      nodes: number;
      links: number;
    };
    countedLinks: number;
    linksWithoutCounts: number;
  };
  thresholds: {
    gCal: GCalCriteria;
    minObservedVph: number;
    gehNote: string;
  };
  manifest: {
    version: number;
    /** sha256 of every input: equal hash and code give an equal report. */
    hash: string;
    graphSha256: string;
    note: string;
  };
  notes: string[];
  /** Only on a recalibration report. */
  recalibration?: Recalibration;
}

export interface DriftRow {
  name: string;
  previous: number | null;
  current: number | null;
  /** Fraction (0.2 = 20%); null when the parameter is new or was zero. */
  relativeChange: number | null;
  flag: boolean;
}

export interface Recalibration {
  windowIntervals: number;
  windowFirstIntervalStart: string | null;
  windowLastIntervalStart: string | null;
  warmStartFrom: Record<string, number>;
  /** Did the previous parameters still pass G-CAL on the new window? */
  previousParametersGCalPassed: boolean;
  drift: {
    threshold: number;
    maxAbsRelativeChange: number | null;
    flagged: string[];
    drifted: boolean;
    parameters: DriftRow[];
  };
}

/** POST /api/v2/calibration/network-fit/validate-counts */
export interface CountsValidation {
  valid: boolean;
  errors: string[];
  warnings: string[];
  provenance: CountsProvenance;
  linkFlowsVph: Record<string, number>;
}

export interface FlowInput {
  origin: string;
  destination: string;
  vehiclesPerHour: number;
}

export interface FitInputs {
  graph: Record<string, unknown>;
  flows: FlowInput[];
  countsCsv: string;
  budget?: number;
  duration?: number;
  seed?: number;
}
