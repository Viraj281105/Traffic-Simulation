/** Shapes of POST /api/v2/v2x/experiment (backend/src/v2x/router.py and
 *  experiment.py). Copied from the code; see src/CONTRACTS_P6.md. The
 *  cooperative side is "a": a negative change is a benefit. */
import type { PairedStat } from "../rescommon/types";

export type MetricKey = "delaySeconds" | "stops" | "fuelLitres" | "co2Kg";

export interface MetricRow {
  baseline: number;
  cooperative: number;
  change: number;
  /** null when the baseline is zero. */
  changePct: number | null;
  /** null with fewer than two vehicles. */
  paired: PairedStat | null;
}

export interface SweepRow {
  penetration: number;
  metrics: Record<MetricKey, MetricRow>;
  connectedVehicles: number;
  vehicles: number;
  stopsAvoided: number;
  reroutes: number;
  /** null when no message was sent. */
  messageDeliveryRatio: number | null;
  meanMessageAgeAtUseSeconds: number | null;
  messagesAttempted: number;
  messagesDelivered: number;
  messagesUsed: number;
}

export interface SensitivityCell {
  latencyMs: number;
  lossProbability: number;
  delayBenefitSeconds: number;
  delayBenefitPct: number | null;
  stopsAvoidedPerVehicle: number;
  stopsReductionPct: number | null;
  deliveryRatio: number | null;
  meanAgeAtUseSeconds: number | null;
  delayPaired: PairedStat | null;
}

export interface Sensitivity {
  penetration: number;
  latenciesMs: number[];
  lossProbabilities: number[];
  note: string;
  cells: SensitivityCell[];
}

export interface Provenance {
  seeds: number[];
  durationSeconds: number;
  penetrations: number[];
  channel: {
    latencyKind: string;
    latencyMs: number;
    jitterMs: number;
    lossProbability: number;
    rangeM: number | null;
  };
  behaviour: Record<string, number>;
  hazard: { linkId: string; startSeconds: number; delaySeconds: number } | null;
  confidence: number;
  method: string;
  constants: Record<string, number>;
  assumptions: string[];
}

export interface V2xExperiment {
  format: string;
  version: number;
  baseline: {
    perSeed: Record<string, number>[];
    mean: Record<string, number>;
  };
  sweep: SweepRow[];
  provenance: Provenance;
  /** Present when the request asked for a sensitivity grid. */
  sensitivity?: Sensitivity;
}
