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

export type Movement = "left" | "straight" | "right";
export const MOVEMENTS: Movement[] = ["left", "straight", "right"];

export type ApproachName = "north" | "south" | "east" | "west";
export const APPROACHES: ApproachName[] = ["north", "east", "south", "west"];
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
  approaches: Record<ApproachName, ApproachSpec>;
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
export interface StrategyDesign {
  laneUse: Partial<Record<ApproachName, Movement[][]>>;
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
