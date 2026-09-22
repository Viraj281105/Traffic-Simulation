export interface SimulationConfigValues {
  lanes: number;
  laneWidth: number;
  arrivalRate: number;
  duration: number;
  randomSeed: number;
  /** Shared green for both corridors (backend straightRightDuration). */
  greenDuration: number;
  yellowDuration: number;
  allRedDuration: number;
  criticalGap: number;
  followUpTime: number;
  /** Optional per-corridor greens (backend nsGreenDuration/ewGreenDuration).
   *  null/absent means both corridors use greenDuration. */
  nsGreenDuration?: number | null;
  ewGreenDuration?: number | null;
}

/** The scenario the dashboard starts with and "Reset defaults" restores. */
export const DEFAULT_CONFIG_VALUES: SimulationConfigValues = {
  lanes: 2,
  laneWidth: 3.5,
  arrivalRate: 0.3,
  duration: 300,
  randomSeed: 42,
  greenDuration: 25,
  yellowDuration: 3,
  allRedDuration: 2,
  criticalGap: 4.5,
  followUpTime: 2.8,
  nsGreenDuration: null,
  ewGreenDuration: null,
};

export interface ScenarioPreset {
  id: string;
  name: string;
  emoji: string;
  description: string;
  config: SimulationConfigValues;
}

export const SCENARIO_PRESETS: ScenarioPreset[] = [
  {
    id: "hcm-standard",
    name: "Baseline",
    emoji: "🏛️",
    description:
      "The dashboard's default scenario: two 3.5 m lanes per approach, balanced demand",
    config: { ...DEFAULT_CONFIG_VALUES },
  },
  {
    id: "downtown-peak",
    name: "Downtown Peak",
    emoji: "🏙️",
    description:
      "Dense urban traffic with compact lanes and quick gap acceptance",
    config: {
      lanes: 2,
      laneWidth: 3.2,
      arrivalRate: 0.7,
      duration: 300,
      randomSeed: 101,
      greenDuration: 30,
      yellowDuration: 3,
      allRedDuration: 2,
      criticalGap: 3.8,
      followUpTime: 2.2,
    },
  },
  {
    id: "suburban-light",
    name: "Suburban Collector",
    emoji: "🏡",
    description: "Low-density single-lane road with relaxed driver headway",
    config: {
      lanes: 1,
      laneWidth: 3.6,
      arrivalRate: 0.15,
      duration: 180,
      randomSeed: 202,
      greenDuration: 12,
      yellowDuration: 3,
      allRedDuration: 2,
      criticalGap: 4.8,
      followUpTime: 3.0,
    },
  },
  {
    id: "arterial-heavy",
    name: "Multi-Lane Arterial",
    emoji: "🛣️",
    description:
      "High-capacity 3-lane intersection with extended green timings",
    config: {
      lanes: 3,
      laneWidth: 3.8,
      arrivalRate: 0.6,
      duration: 300,
      randomSeed: 303,
      greenDuration: 35,
      yellowDuration: 4,
      allRedDuration: 2,
      criticalGap: 4.2,
      followUpTime: 2.6,
    },
  },
];
