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

/** The scenario the dashboard starts with and "Reset defaults" restores.
 *  One lane per approach: the only configuration the model is calibrated
 *  for on both controls (docs/reports/v1-known-limitations.md §1, §3). */
export const DEFAULT_CONFIG_VALUES: SimulationConfigValues = {
  lanes: 1,
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
      "The dashboard's default scenario: one 3.5 m lane per approach, balanced demand",
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

/** Body of POST /api/simulation/config for a scenario (the backend compiles
 *  it with _compile_dashboard_config). The reliability check sends the same
 *  body, so it repeats exactly the scenario the live comparison ran. */
export interface DashboardScenarioPayload {
  intersectionType: "fixed_time_signal" | "roundabout";
  intersectionSize: number;
  laneWidth: number;
  lanesNorth: number;
  lanesSouth: number;
  lanesEast: number;
  lanesWest: number;
  arrivalRate: number;
  duration: number;
  randomSeed: number;
  greenDuration: number;
  yellowDuration: number;
  allRedDuration: number;
  criticalGap: number;
  followUpTime: number;
  nsGreenDuration?: number;
  ewGreenDuration?: number;
}

export function dashboardPayload(
  config: SimulationConfigValues,
  intersectionType: DashboardScenarioPayload["intersectionType"],
): DashboardScenarioPayload {
  const { lanes, laneWidth, nsGreenDuration, ewGreenDuration } = config;
  return {
    intersectionType,
    intersectionSize: lanes * laneWidth * 2 + 4.0,
    laneWidth,
    lanesNorth: lanes,
    lanesSouth: lanes,
    lanesEast: lanes,
    lanesWest: lanes,
    arrivalRate: config.arrivalRate,
    duration: config.duration,
    randomSeed: config.randomSeed,
    greenDuration: config.greenDuration,
    yellowDuration: config.yellowDuration,
    allRedDuration: config.allRedDuration,
    criticalGap: config.criticalGap,
    followUpTime: config.followUpTime,
    ...(nsGreenDuration !== null && nsGreenDuration !== undefined
      ? { nsGreenDuration }
      : {}),
    ...(ewGreenDuration !== null && ewGreenDuration !== undefined
      ? { ewGreenDuration }
      : {}),
  };
}

/** Everyday traffic levels offered when describing a junction. Rates are
 *  total arrivals across all four approaches. The descriptions say what the
 *  traffic is like, never which control will cope better. */
export interface DemandLevel {
  id: "quiet" | "steady" | "busy" | "peak";
  label: string;
  arrivalRate: number;
  description: string;
}

export const DEMAND_LEVELS: DemandLevel[] = [
  {
    id: "quiet",
    label: "Quiet",
    arrivalRate: 0.1,
    description: "A residential crossing, or a main road late at night.",
  },
  {
    id: "steady",
    label: "Steady",
    arrivalRate: 0.2,
    description: "A local through-road during the day.",
  },
  {
    id: "busy",
    label: "Busy",
    arrivalRate: 0.3,
    description: "A main-road junction at a busy time of day.",
  },
  {
    id: "peak",
    label: "Rush hour",
    arrivalRate: 0.45,
    description: "Heavy peak traffic; queues are likely.",
  },
];

export function demandLevelFor(arrivalRate: number): DemandLevel | null {
  return (
    DEMAND_LEVELS.find((d) => Math.abs(d.arrivalRate - arrivalRate) < 1e-6) ??
    null
  );
}

/** Vehicles per hour arriving in total, rounded for display. */
export function vehiclesPerHour(arrivalRate: number): number {
  return Math.round(arrivalRate * 3600);
}

export interface RunLength {
  seconds: number;
  label: string;
  description: string;
}

export const RUN_LENGTHS: RunLength[] = [
  {
    seconds: 120,
    label: "Quick look",
    description: "2 minutes of traffic. Fast, but numbers are less steady.",
  },
  {
    seconds: 300,
    label: "Standard",
    description: "5 minutes of traffic. A good balance for most questions.",
  },
  {
    seconds: 600,
    label: "Thorough",
    description: "10 minutes of traffic. Steadier numbers, longer to watch.",
  },
];

/** Length of one full signal cycle with the paired north–south / east–west
 *  phase plan the dashboard runs (green, yellow, all-red for each corridor;
 *  see DEFAULT_CONFIG.controller.phaseSequence in backend/src/main.py). */
export function signalCycleSeconds(config: SimulationConfigValues): number {
  const ns = config.nsGreenDuration ?? config.greenDuration;
  const ew = config.ewGreenDuration ?? config.greenDuration;
  return ns + ew + 2 * (config.yellowDuration + config.allRedDuration);
}
