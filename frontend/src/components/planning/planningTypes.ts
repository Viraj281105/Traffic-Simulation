/**
 * Types for the Scenario Planning & Comparison dashboard.
 *
 * Every metric here is measured by the simulation (the control-comparison
 * study's per-strategy means); nothing is estimated or filled in on the client.
 */
import type { Strategy } from "../../scenario/scenarioTypes";

export interface ScenarioItemConfig {
  id: string;
  name: string;
  isBaseline: boolean;
  strategy: Strategy;
  /** Demand multiplier applied by the study to every approach (e.g. 1.0, 1.25, 0.75) */
  volumeScale: number;
  /** Signal green time in seconds (for fixed-time and adaptive) */
  greenTime: number;
  /** Yellow time in seconds */
  yellowTime: number;
  /** Simulation duration in seconds */
  duration: number;
  /** Vehicle mix shares */
  vehicleMix: {
    car: number;
    suv: number;
    bus: number;
    truck: number;
    motorcycle: number;
  };
  /** Driver / follower behaviour parameters */
  driverBehavior: {
    aggressiveTwoWheelers: boolean;
    unstructuredTraffic: boolean;
    laneChanging: boolean;
  };
}

/** Means over the seeds run for one scenario. */
export interface ScenarioMetrics {
  averageWaitTime: number;
  averageDelay: number;
  throughput: number;
  averageQueueLength: number;
  maxQueueLength: number;
  collisionCount: number;
}

export interface ScenarioSimulationResult {
  scenarioId: string;
  name: string;
  strategy: Strategy;
  volumeScale: number;
  duration: number;
  seedCount: number;
  metrics: ScenarioMetrics;
}

export interface ComparisonDelta {
  absolute: number;
  percentage: number | null;
  direction: "better" | "worse" | "neutral";
}
