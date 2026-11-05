/** Contract fixtures for /api/v2/incidents/*: the shapes of
 *  backend/src/incidents with small invented numbers. Not real results. */
import type {
  DisruptionRun,
  IncidentCatalogue,
  ResilienceResponse,
  RunMetrics,
  SimulateResponse,
} from "./types";

const TIME = [30, 60, 90, 120, 150, 180, 210, 240];

function run(delay: number[], completed: number): DisruptionRun {
  return {
    format: "urbanflow-incident-run",
    version: 1,
    strategy: "fixed_time",
    seed: 1,
    duration: 240,
    generated: 60,
    entered: 58,
    blockedAtEntry: 2,
    completed,
    active: 58 - completed,
    conserved: true,
    meanTravelSeconds: 71.5,
    meanDelaySeconds: 12.25,
    totalTravelSeconds: 3000,
    totalDelaySeconds: 500,
    unroutable: [],
    reroutedVehicles: 0,
    rerouteEvents: 0,
    switches: {},
    perLink: { "J1>J2": { passed: 30, peakOccupancy: 9, occupancy: 2 } },
    perNode: { J1: { passed: 30 } },
    segments: [
      {
        start: 0,
        fullyBlocked: [],
        laneLoss: {},
        weather: { speed: 1, saturation: 1, headway: 1 },
        surgeActive: false,
      },
    ],
    series: {
      bucketSeconds: 30,
      time: TIME,
      meanAccruedDelay: delay,
      active: [4, 6, 8, 9, 8, 7, 5, 4],
      completed: [2, 4, 5, 5, 6, 7, 8, 9],
      entered: [8, 8, 8, 8, 8, 8, 8, 8],
      blocked: [0, 0, 1, 1, 0, 0, 0, 0],
    },
  };
}

export const incidentMetricsFixture: RunMetrics = {
  seed: 1,
  recovered: true,
  recoveryTimeSeconds: 60,
  peakDelaySeconds: 41.5,
  peakExcessDelaySeconds: 31.25,
  throughputLoss: 0.12,
  areaUnderDelayCurve: 2400,
  meanExcessDelaySeconds: 10,
  excessDelayVehicleSeconds: 180,
  completedBaseline: 50,
  completed: 44,
  blockedAtEntry: 2,
  reroutedVehicles: 0,
  conserved: true,
  components: { recovery: 0.6, throughput: 0.88, peak: 0.66, area: 0.75 },
  score: 0.7,
};

export const incidentCatalogueFixture: IncidentCatalogue = {
  format: "urbanflow-incident-catalogue",
  version: 1,
  inModelOnly: true,
  disruptionTypes: [
    {
      type: "crash",
      effect: "lanesBlocked lanes lost; remaining lanes slowed.",
      defaultSpeedFactor: 0.6,
    },
    { type: "weather", effect: "network-wide multipliers." },
  ],
  weather: {
    fullSeverityFactors: {
      rain: { speed: 0.9, saturation: 0.92, headway: 1.1, discharge: 0.83 },
    },
    status: "Modelling assumptions; not measurements and not calibrated.",
  },
  strategies: ["fixed_time", "max_pressure"],
  scoreFormula: {
    weights: { recovery: 0.35, throughput: 0.25, peak: 0.2, area: 0.2 },
    peakScaleSeconds: 60,
    areaScaleSeconds: 30,
  },
  scenarios: [
    {
      id: "corridor-crash",
      family: "incident",
      title: "Crash on the corridor arterial",
      description: "One of two lanes of J1>J2 is lost for 4 minutes.",
      network: { kind: "corridor", demandScale: 1.8 },
      scenario: {
        incidents: [
          {
            type: "crash",
            links: ["J1>J2"],
            start: 200,
            duration: 240,
            lanesBlocked: 1,
          },
        ],
      },
      duration: 1200,
    },
    {
      id: "grid-heavy-rain",
      family: "weather",
      title: "Heavy rain on a 3x3 grid",
      description: "Rain at full severity for 6 minutes.",
      network: { kind: "grid", rows: 3, cols: 3, vehiclesPerHour: 800 },
      scenario: {
        weather: [{ kind: "rain", severity: 1, start: 200, duration: 360 }],
      },
      duration: 1200,
    },
    {
      id: "grid-event-surge",
      family: "surge",
      title: "Event-day surge towards the east gate",
      description: "Demand on the middle-row flows doubles for 6 minutes.",
      network: { kind: "grid", rows: 3, cols: 3, vehiclesPerHour: 800 },
      scenario: {
        surges: [
          {
            origin: "GW1",
            destination: "GE1",
            start: 200,
            duration: 360,
            multiplier: 2,
          },
        ],
      },
      duration: 1200,
    },
  ],
  stressLabExtension: { note: "Exposed here, not in the V3 catalogue." },
};

export const simulateFixture: SimulateResponse = {
  network: {
    name: "Two-junction corridor",
    nodes: 4,
    links: 6,
    flows: [{ origin: "W", destination: "E", vehiclesPerHour: 900 }],
  },
  scenario: {
    incidents: [
      {
        type: "crash",
        links: ["J1>J2"],
        start: 60,
        duration: 90,
        lanesBlocked: 1,
        policy: "drain",
      },
    ],
    weather: [],
    surges: [],
    reroute: true,
  },
  duration: 240,
  inModelOnly: true,
  run: run([2, 9, 24, 41.5, 30, 14, 6, 3], 44),
  baseline: run([2, 3, 4, 10.25, 4, 3, 3, 3], 50),
  metrics: incidentMetricsFixture,
};

const seedRun = (
  seed: number,
  score: number,
  rec: number | null,
): RunMetrics => ({
  ...incidentMetricsFixture,
  seed,
  score,
  recovered: rec !== null,
  recoveryTimeSeconds: rec,
});

export const resilienceFixture: ResilienceResponse = {
  format: "urbanflow-resilience",
  version: 1,
  inModelOnly: true,
  duration: 1200,
  bucketSeconds: 30,
  disruptionEnd: 440,
  seeds: [1, 2, 3],
  tolerance: { relative: 0.1, absoluteSeconds: 3, holdBuckets: 3 },
  scoreFormula: {
    weights: { recovery: 0.35, throughput: 0.25, peak: 0.2, area: 0.2 },
    peakScaleSeconds: 60,
    areaScaleSeconds: 30,
    interval: "95% seeded bootstrap percentile interval of the mean score",
  },
  strategies: {
    fixed_time: {
      score: 0.62,
      scoreInterval: [0.55, 0.69],
      recoveredRuns: 2,
      runs: 3,
      recoveryTimeSeconds: 90,
      peakDelaySeconds: 48,
      peakExcessDelaySeconds: 35,
      throughputLoss: 0.11,
      areaUnderDelayCurve: 3100,
      excessDelayVehicleSeconds: 210,
      perSeed: [
        seedRun(1, 0.6, 90),
        seedRun(2, 0.65, 90),
        seedRun(3, 0.61, null),
      ],
    },
    max_pressure: {
      score: 0.74,
      scoreInterval: [0.7, 0.78],
      recoveredRuns: 3,
      runs: 3,
      recoveryTimeSeconds: 60,
      peakDelaySeconds: 39,
      peakExcessDelaySeconds: 27,
      throughputLoss: 0.07,
      areaUnderDelayCurve: 2200,
      excessDelayVehicleSeconds: 150,
      perSeed: [
        seedRun(1, 0.72, 60),
        seedRun(2, 0.75, 60),
        seedRun(3, 0.75, 60),
      ],
    },
  },
  best: "max_pressure",
  note: "Scores compare strategies inside this model under this scenario. Intervals are narrow with few seeds and do not cover model error.",
  network: simulateFixture.network,
  scenario: simulateFixture.scenario,
};
