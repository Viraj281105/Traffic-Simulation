/** Shapes of POST /api/v2/aim/comparison (backend/src/aim/router.py and
 *  experiment.py). Copied from the code; see src/CONTRACTS_P7.md. Differences
 *  are AIM (arm "A") minus the fixed-time signal (arm "B"): negative delay and
 *  stops favour AIM, positive throughput favours AIM. */
import type { PairedStat } from "../rescommon/types";

export type AimMetricKey = "meanDelay" | "stopsPerVehicle" | "throughputVph";

export interface AimSafety {
  conflicts: number;
  /** null when no pair of vehicles shared the box. */
  minGapSeconds: number | null;
  deadlock: boolean;
  maxAccel: number;
  passed: boolean;
}

export interface AimSummary {
  meanDelay: number;
  stopsPerVehicle: number;
  throughputVph: number;
  p95Delay: number;
  lostMessages: number;
  safety: AimSafety;
}

/** `PairedComparison.to_dict()` plus the router's `verdict`. */
export type AimComparison = Record<AimMetricKey, PairedStat>;

export interface DemandRow {
  demandVehPerHourPerApproach: number;
  aim: AimSummary;
  signal: AimSummary;
  comparison: AimComparison;
}

export interface LossRow {
  lossProbability: number;
  aim: AimSummary;
  signal: AimSummary;
  comparison: AimComparison;
}

export interface AimResult {
  provenance: {
    seeds: number[];
    durationSeconds: number;
    turnMix: { left: number; right: number };
    signal: {
      greenSeconds: number;
      yellowSeconds: number;
      allRedSeconds: number;
    };
    confidence: number;
    method: string;
    stressDemandVehPerHourPerApproach: number | null;
    assumptions: string[];
    inModelBestCase: boolean;
  };
  sweep: DemandRow[];
  messageLossStress: LossRow[];
  gateGAim: { passed: boolean; description: string };
}

export interface AimInput {
  durationSeconds: number;
  seedCount: number;
  demands: number[];
  withLossStress: boolean;
}
