/** Shapes of /api/v2/priority/* (backend/src/priority/router.py and
 *  comparison.py). Copied from the code; see src/CONTRACTS_P6.md. */
import type { PriorityStat } from "../rescommon/types";

export type Approach = "north" | "south" | "east" | "west";
export type Turn = "left" | "straight" | "right";
export type Method = "paired_t" | "paired_bootstrap";

/** GET /api/v2/priority/catalogue (the parts the screen uses). */
export interface PriorityCatalogue {
  inModelOnly: boolean;
  label: string;
  emergencyKinds: { id: string; label: string }[];
  approaches: Approach[];
  turns: Turn[];
  methods: Method[];
  limits: {
    durationSeconds: [number, number];
    seeds: [number, number];
    seedsTimesDurationSeconds: number;
    emergencyVehicles: number;
    transitLines: number;
    tripsPerLine: number;
  };
  assumptions: string[];
}

export interface Safety {
  /** One count per seed, including dropped seeds. */
  collisions: number[];
  vehiclesConserved: boolean;
  signalAuditOk: boolean;
  signalViolations: unknown[];
  preemptions: number[];
}

export interface DroppedSeed {
  seed: number;
  reason: string;
}

interface ComparisonBase {
  inModelOnly: boolean;
  label: string;
  method: Method;
  confidence: number;
  /** Seeds used in the paired comparison. */
  seeds: number[];
  droppedSeeds: DroppedSeed[];
  comparison: Record<string, PriorityStat>;
}

/** POST /api/v2/priority/emergency-comparison */
export interface EmergencyComparison extends ComparisonBase {
  kind: "emergency-comparison";
  perSeed: Record<
    "withPreemption" | "baseline",
    {
      travelTime: number[];
      delay: number[];
      waitTime: number[];
      collateralDelay: number[];
    }
  >;
  safety: Record<"withPreemption" | "baseline", Safety>;
}

/** POST /api/v2/priority/transit-comparison */
export interface TransitComparison extends ComparisonBase {
  kind: "transit-comparison";
  perSeed: Record<
    "withPriority" | "baseline",
    {
      busScheduleLateness: number[];
      busTimeLost: number[];
      personDelayPerPerson: number[];
      vehicleDelay: number[];
      otherVehicleDelay: number[];
    }
  >;
  safety: Record<"withPriority" | "baseline", Safety>;
}
