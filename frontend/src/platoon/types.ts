/** Shapes of POST /api/v2/platoon/experiment (backend/src/platoon/router.py,
 *  experiment.py, analysis.py). Copied from the code; see src/CONTRACTS_P7.md.
 *  Platoon is arm "A", human-driven (IDM) is arm "B". */
import type { PairedStat } from "../rescommon/types";

/** `PairedComparison.to_dict()`: the paired fields without a verdict. */
export type PairedCmp = Omit<PairedStat, "verdict">;

export type PlatoonMetricKey = "throughputVph" | "fuelLPer100Km" | "co2GPerKm";

export interface PlatoonMetric {
  platoonMean: number;
  humanMean: number;
  /** null when the human mean is zero. */
  changePct: number | null;
  comparison: PairedCmp;
  verdict: string;
}

export interface PlatoonSafety {
  platoonMinGapM: number;
  humanMinGapM: number;
  platoonCollisions: number;
  humanCollisions: number;
  platoonFallbackEvents: number;
}

export interface ChannelCell {
  latencySeconds: number;
  lossProbability: number;
  fuelChangePct: number | null;
  throughputChangePct: number | null;
  minGapM: number;
  collisions: number;
  fallbackEvents: number;
}

export interface StringStability {
  vehicles: number;
  timeGapSeconds: number;
  controller: string;
  peakSpeedDeviationMps: number[];
  stepRatioMax: number;
  amplification: number;
  stable: boolean;
  minGapM: number;
  collisions: number;
}

export interface PlatoonExperiment {
  seeds: number[];
  metrics: Record<PlatoonMetricKey, PlatoonMetric>;
  safety: PlatoonSafety;
  perSeed: {
    seed: number;
    platoon: Record<string, number | null>;
    human: Record<string, number | null>;
  }[];
  isEstimate: boolean;
  label: string;
  channelSweep?: ChannelCell[];
  stringStability: StringStability;
  throughputSteadyState: { cacc: number; idm: number };
}

export interface PlatoonInput {
  vehicles: number;
  durationSeconds: number;
  latencyMs: number;
  lossProbability: number;
  seedCount: number;
  withSweep: boolean;
}
