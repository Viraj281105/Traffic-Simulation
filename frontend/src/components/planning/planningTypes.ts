/**
 * Types for V1.7 Phase 1: Scenario Planning & Comparison Dashboard.
 */
import type { Strategy } from "../../scenario/scenarioTypes";

export interface ScenarioItemConfig {
  id: string;
  name: string;
  isBaseline: boolean;
  strategy: Strategy;
  /** Volume multiplier vs base scenario approaches (e.g. 1.0, 1.25, 0.75) */
  volumeScale: number;
  /** Signal green time in seconds (for fixed-time and adaptive) */
  greenTime: number;
  /** Yellow time in seconds */
  yellowTime: number;
  /** Simulation duration in seconds */
  duration: number;
  /** Vehicle mix percentages */
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

export interface ScenarioSimulationResult {
  scenarioId: string;
  name: string;
  strategy: Strategy;
  volumeScale: number;
  duration: number;
  seedCount: number;
  metrics: {
    averageWaitTime: number;
    averageDelay: number;
    throughput: number;
    averageQueueLength: number;
    maxQueueLength: number;
    averageTravelSpeed: number;
    collisionCount: number;
    minTTC: number | null;
    ttcEventCount: number;
  };
  perSeed?: Array<{
    seed: number;
    averageWaitTime: number;
    averageDelay: number;
    throughput: number;
    averageQueueLength: number;
    maxQueueLength: number;
    averageTravelSpeed: number;
    collisionCount: number;
  }>;
}

export interface ComparisonDelta {
  absolute: number;
  percentage: number | null;
  /** "better" | "worse" | "neutral" */
  direction: "better" | "worse" | "neutral";
}

export interface ScenarioComparisonData {
  baseline: ScenarioSimulationResult;
  scenarios: Array<{
    result: ScenarioSimulationResult;
    deltas: {
      averageWaitTime: ComparisonDelta;
      averageDelay: ComparisonDelta;
      throughput: ComparisonDelta;
      averageQueueLength: ComparisonDelta;
      maxQueueLength: ComparisonDelta;
      averageTravelSpeed: ComparisonDelta;
      collisionCount: ComparisonDelta;
    };
  }>;
}

export interface SavedExperimentData {
  id: string;
  name: string;
  description: string;
  created_at: string;
  user_id?: string | null;
  scenarios: ScenarioItemConfig[];
  results: ScenarioSimulationResult[];
}
