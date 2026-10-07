import type { VehicleMix } from "../vehicles/vehicleClasses";
import { sameMix } from "../vehicles/vehicleClasses";
import type { ScenarioDocument } from "../scenario/scenarioTypes";

/** V1.3: how a signal times its greens. */
export type SignalControl = "fixed_time" | "adaptive";

/** V1.3 adaptive signal settings (backend controller.adaptive). Each one is
 *  optional; the backend default applies when absent. */
export interface AdaptiveSettings {
  /** Seconds a green always lasts. */
  minGreen?: number;
  /** Most seconds a green may continue once someone waits on red. */
  maxGreen?: number;
  /** Passage time: the green ends after this long with no vehicle moving
   *  through the detection zone. */
  extensionStep?: number;
  /** Stop-line detection zone length (m). */
  detectionDistance?: number;
  /** Vehicles waiting on red needed to call for a green. */
  demandThreshold?: number;
}

/** The backend's defaults (controllers/adaptive_signal.py DEFAULT_ADAPTIVE). */
export const ADAPTIVE_DEFAULTS: Required<AdaptiveSettings> = {
  minGreen: 10,
  maxGreen: 50,
  extensionStep: 2.5,
  detectionDistance: 30,
  demandThreshold: 1,
};

export function adaptiveSettings(
  config: Pick<SimulationConfigValues, "adaptive">,
): Required<AdaptiveSettings> {
  return { ...ADAPTIVE_DEFAULTS, ...(config.adaptive ?? {}) };
}

export function isAdaptive(
  config: Pick<SimulationConfigValues, "signalControl">,
): boolean {
  return config.signalControl === "adaptive";
}

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
  /** V1.1 share of arrivals per vehicle class. null/absent = cars only, the
   *  calibrated population exactly as in V1.0. */
  vehicleMix?: VehicleMix | null;
  /** V1.2 lane changing on multi-lane approaches. Absent = on. */
  laneChanging?: boolean;
  /** V1.2 lanes on the east–west road when it differs from `lanes` (the
   *  north–south road). Signal-only: a roundabout needs the same count on
   *  every approach. null/absent = same as `lanes`. */
  lanesEastWest?: number | null;
  /** V1.3: fixed timetable (absent/"fixed_time") or a signal that responds
   *  to traffic ("adaptive"). */
  signalControl?: SignalControl;
  /** V1.3 adaptive settings; null/absent = the defaults. */
  adaptive?: AdaptiveSettings | null;
  /** V1.4: a custom scenario built in the scenario builder. When set, the
   *  backend runs this document and the flat fields above only mirror it
   *  for display (see scenario/scenarioModel.configValuesFromScenario). */
  scenario?: ScenarioDocument | null;
}

/** Field-by-field equality, comparing the vehicle mix by value. */
export function sameConfigValues(
  a: SimulationConfigValues,
  b: SimulationConfigValues,
): boolean {
  const keys = new Set([...Object.keys(a), ...Object.keys(b)]) as Set<
    keyof SimulationConfigValues
  >;
  return [...keys].every((k) => {
    if (k === "vehicleMix") return sameMix(a.vehicleMix, b.vehicleMix);
    if (k === "scenario")
      return (
        JSON.stringify(a.scenario ?? null) ===
        JSON.stringify(b.scenario ?? null)
      );
    if (k === "laneChanging")
      return (a.laneChanging ?? true) === (b.laneChanging ?? true);
    if (k === "signalControl")
      return (
        (a.signalControl ?? "fixed_time") === (b.signalControl ?? "fixed_time")
      );
    if (k === "adaptive")
      return (
        JSON.stringify(adaptiveSettings(a)) ===
        JSON.stringify(adaptiveSettings(b))
      );
    return (a[k] ?? null) === (b[k] ?? null);
  });
}

/** The scenario the dashboard starts with and "Reset defaults" restores.
 *  These are the calibrated baseline parameters — the same signal timing,
 *  gap acceptance and vehicle population as the pinned capacity study
 *  (docs/reports/comparative_report.md §2) — at one lane per approach and
 *  "Busy" demand (75% of the measured 1-lane capacity). */
export const DEFAULT_CONFIG_VALUES: SimulationConfigValues = {
  lanes: 1,
  laneWidth: 3.5,
  arrivalRate: 940 / 3600,
  duration: 300,
  randomSeed: 42,
  greenDuration: 30,
  yellowDuration: 4,
  allRedDuration: 2,
  criticalGap: 4.0,
  followUpTime: 2.5,
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
  /** Omitted for cars only (the calibrated population). */
  vehicleMix?: VehicleMix;
  /** Omitted while on (the default). */
  laneChanging?: false;
  /** Omitted for the fixed timetable (the default). */
  signalControl?: "adaptive";
  /** Only the settings that differ from the defaults. */
  adaptive?: AdaptiveSettings;
  /** V1.4: a scenario document; the backend then runs it and ignores the
   *  flat fields above (they still describe it, for older readers). */
  scenario?: ScenarioDocument;
}

export function dashboardPayload(
  config: SimulationConfigValues,
  intersectionType: DashboardScenarioPayload["intersectionType"],
  /** Use `lanesEastWest` (the signal-only research view). Off everywhere
   *  else: a signal-vs-roundabout comparison needs one junction shape for
   *  both, and a roundabout needs equal lane counts on every approach. */
  perRoadLanes = false,
): DashboardScenarioPayload {
  const { lanes, laneWidth, nsGreenDuration, ewGreenDuration } = config;
  const lanesEW =
    perRoadLanes && intersectionType === "fixed_time_signal"
      ? (config.lanesEastWest ?? lanes)
      : lanes;
  return {
    intersectionType,
    intersectionSize: lanes * laneWidth * 2 + 4.0,
    laneWidth,
    lanesNorth: lanes,
    lanesSouth: lanes,
    lanesEast: lanesEW,
    lanesWest: lanesEW,
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
    // Sent only when they differ from the defaults, so a cars-only scenario
    // posts exactly the body it always has.
    ...(config.vehicleMix ? { vehicleMix: config.vehicleMix } : {}),
    ...(config.laneChanging === false ? { laneChanging: false as const } : {}),
    ...(isAdaptive(config) ? adaptivePayload(config.adaptive) : {}),
    ...(config.scenario ? { scenario: config.scenario } : {}),
  };
}

function adaptivePayload(
  settings: AdaptiveSettings | null | undefined,
): Pick<DashboardScenarioPayload, "signalControl" | "adaptive"> {
  const changed = Object.fromEntries(
    Object.entries(settings ?? {}).filter(
      ([key, value]) =>
        value !== undefined &&
        value !== ADAPTIVE_DEFAULTS[key as keyof AdaptiveSettings],
    ),
  ) as AdaptiveSettings;
  return {
    signalControl: "adaptive",
    ...(Object.keys(changed).length ? { adaptive: changed } : {}),
  };
}

// Demand levels live in ./demand (calibrated against measured capacity).
export {
  DEMAND_LEVELS,
  demandLevelFor,
  demandRate,
  demandVph,
  type DemandLevel,
} from "./demand";

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
