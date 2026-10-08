/**
 * Scenario documents (V1.4): the portable, strategy-neutral description of a
 * junction and its traffic. Mirrors backend/src/core/scenario.py
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
  };
  simulation: {
    duration: number;
    warmup: number;
    seed: number;
    arrivalPattern: "poisson" | "uniform";
    timeStep: number;
  };
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
