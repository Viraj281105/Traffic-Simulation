/**
 * Scenario documents (V1.4): the portable, strategy-neutral description of a
 * junction and its traffic. Mirrors backend/src/scenario/documents.py
 * (ScenarioDocument); the backend validates and compiles it once per control
 * strategy, so every strategy runs the same approaches, lanes, traffic,
 * vehicles, duration and seed.
 */
import type { VehicleMix } from "../vehicles/vehicleClasses";

export const SCENARIO_FORMAT = "urbanflow-scenario";
export const SCENARIO_VERSION = 1;

export type Movement = "uturn" | "left" | "straight" | "right";
/** The V1.0-V1.4 movements, from which every default lane use is built. */
export const CORE_MOVEMENTS: Movement[] = ["left", "straight", "right"];
/** Every movement a lane can be marked with, left to right as a driver
 *  reads the arrows (V1.5 adds the U-turn, never part of a default). */
export const MOVEMENTS: Movement[] = ["uturn", "left", "straight", "right"];

export type ApproachName = "north" | "south" | "east" | "west";
export const APPROACHES: ApproachName[] = ["north", "east", "south", "west"];
/** Compass bearing (degrees clockwise from north) of each slot's own axis. */
export const SLOT_BEARING: Record<ApproachName, number> = {
  north: 0,
  east: 90,
  south: 180,
  west: 270,
};
/** How far an arm may lie from its slot (backend junction_geometry). */
export const MAX_SLOT_DEVIATION = 30;
/** The road each approach belongs to (opposite approaches share it). */
export const OPPOSITE: Record<ApproachName, ApproachName> = {
  north: "south",
  south: "north",
  east: "west",
  west: "east",
};

export type JunctionType =
  "fixed_time_signal" | "adaptive_signal" | "roundabout";
export type Strategy = "fixed_time" | "adaptive" | "roundabout";
export const STRATEGIES: Strategy[] = ["fixed_time", "adaptive", "roundabout"];
export const STRATEGY_TITLE: Record<Strategy, string> = {
  fixed_time: "Fixed-time signal",
  adaptive: "Adaptive signal",
  roundabout: "Roundabout",
};
/** The roundabout as it is named when its entries carry signals. */
export const METERED_ROUNDABOUT_TITLE = "Roundabout (metered entry)";

export type DriverAggression = "standard" | "moderate" | "high";
export const DRIVER_AGGRESSION_PROFILES: DriverAggression[] = [
  "standard",
  "moderate",
  "high",
];
export const DRIVER_AGGRESSION_DISCLAIMER =
  "driver aggression — a simulation assumption, not a measurement of real-world driver behaviour";

/** What each profile does, for the selectors (ADR-016). ``levers`` mirrors
 *  backend AGGRESSION_MULTIPLIERS; a backend contract test keeps them equal. */
export const DRIVER_AGGRESSION_INFO: Record<
  DriverAggression,
  { label: string; summary: string; levers: string }
> = {
  standard: {
    label: "Standard",
    summary: "The calibrated drivers every earlier result used",
    levers: "T ×1 · s₀ ×1 · a ×1",
  },
  moderate: {
    label: "Moderate",
    summary: "Closer following and quicker launches",
    levers: "T ×0.85 · s₀ ×0.875 · a ×1.075",
  },
  high: {
    label: "High",
    summary: "Short gaps, hard launches, assertive lane changes",
    levers: "T ×0.7 · s₀ ×0.75 · a ×1.15",
  },
};

/** The scenario's roundabout has signals on its entries (V3.0 W2). */
export function isMeteredEntry(doc: {
  roundabout: { entryControl?: "metered_entry" | "none" | null };
}): boolean {
  return doc.roundabout.entryControl === "metered_entry";
}

/** A strategy's display name for this scenario: a metered-entry roundabout is
 *  not the conventional one, so the two must never share a name. */
export function strategyTitle(
  strategy: Strategy,
  doc: Parameters<typeof isMeteredEntry>[0],
): string {
  return strategy === "roundabout" && isMeteredEntry(doc)
    ? METERED_ROUNDABOUT_TITLE
    : STRATEGY_TITLE[strategy];
}
export const JUNCTION_STRATEGY: Record<JunctionType, Strategy> = {
  fixed_time_signal: "fixed_time",
  adaptive_signal: "adaptive",
  roundabout: "roundabout",
};

export interface Turning {
  left: number;
  straight: number;
  right: number;
  /** V1.5: share making a U-turn; omitted = none. */
  uturn?: number | null;
}

export interface ApproachSpec {
  lanes: number;
  /** Metres from the edge of the simulated area to the junction. */
  length: number;
  /** Signal lane arrows, lane 1 (next to the centre line) first; omitted =
   *  the default policy. */
  laneUse?: Movement[][] | null;
  /** Roundabout entry lane markings; omitted = derived from the ring. */
  roundaboutLaneUse?: Movement[][] | null;
  vehiclesPerHour: number;
  turning: Turning;
  /** This approach's own vehicle mix; omitted = the scenario's. */
  vehicleMix?: VehicleMix | null;
  /** V1.5: compass bearing of the arm from the junction outwards (degrees
   *  clockwise from north); omitted = the slot's own bearing. */
  bearing?: number | null;
  /** V1.5: this arm's own lane width (m); omitted = roads.laneWidth. */
  laneWidth?: number | null;
}

export interface AdaptiveSpec {
  minGreen: number;
  maxGreen: number;
  extensionStep: number;
  detectionDistance: number;
  demandThreshold: number;
}

export interface MeteredPhaseSpec {
  entries: string[];
  green: number;
  minGreen?: number | null;
  maxGreen?: number | null;
}

export interface SpillbackGuardSpec {
  enabled: boolean;
  stoppedThreshold?: number;
  maxHold?: number;
}

export interface QueueCapSpec {
  enabled: boolean;
  vehicles?: number;
}

export interface EntryMeteringSpec {
  phases: MeteredPhaseSpec[];
  yellow: number;
  allRed: number;
  offset?: number;
  spillbackGuard?: SpillbackGuardSpec | null;
  queueCap?: QueueCapSpec | null;
}

export interface ScenarioDocument {
  format: typeof SCENARIO_FORMAT;
  version: typeof SCENARIO_VERSION;
  name: string;
  description: string;
  preset?: string | null;
  junction: { type: JunctionType };
  /** null: the junction has no arm in that slot (V1.5, three-arm junction). */
  approaches: Record<ApproachName, ApproachSpec | null>;
  roads: { laneWidth: number; speedLimit: number; laneChanging: boolean };
  /** mix omitted = the calibrated cars-only population. */
  vehicles: { mix?: VehicleMix | null };
  signal: {
    greenTime: number;
    nsGreenTime?: number | null;
    ewGreenTime?: number | null;
    yellowTime: number;
    allRedTime: number;
    adaptive: AdaptiveSpec;
  };
  roundabout: {
    /** omitted = as many as the widest approach. */
    circulatingLanes?: number | null;
    innerRadius: number;
    outerRadius: number;
    criticalGap: number;
    followUpTime: number;
    entrySpeed: number;
    circulatingSpeed: number;
    /** V3.0 W2: entry control mode. Omitted or "none" = conventional uncontrolled roundabout. */
    entryControl?: "metered_entry" | "none" | null;
    /** V3.0 W2: phase plan and optional guard/cap for metered entry. */
    entryMetering?: EntryMeteringSpec | null;
  };
  simulation: {
    duration: number;
    warmup: number;
    seed: number;
    arrivalPattern: "poisson" | "uniform";
    timeStep: number;
  };
  traffic?: {
    driverAggression?: DriverAggression | null;
  } | null;
}

/** What the backend says it will build (POST /api/v1/scenarios/validate). */
/** One arm as the backend lays it out (V1.5). */
export interface ArmDesign {
  bearing: number;
  lanes: number;
  laneWidth: number;
  length: number;
  /** Centre to the stop / give-way line (m). */
  stopLineDistance: number;
}

export interface StrategyDesign {
  laneUse: Partial<Record<ApproachName, Movement[][]>>;
  geometry?: Partial<Record<ApproachName, ArmDesign>>;
  circulatingLanes?: number;
  ringAssignment?: Partial<
    Record<
      ApproachName,
      {
        lane: number;
        movement: Movement;
        exitTo: ApproachName;
        /** 1 = innermost circulating lane. */
        ringLane: number | null;
        exitLane: number | null;
      }[]
    >
  >;
}

export interface ScenarioValidation {
  valid: boolean;
  errors: string[];
  warnings: string[];
  strategies: Strategy[];
  design?: Partial<Record<Strategy, StrategyDesign>>;
  fingerprint?: string;
}
