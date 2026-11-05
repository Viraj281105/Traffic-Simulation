/** Shapes of /api/v2/incidents/* (backend/src/incidents/: router.py,
 *  model.py, catalogue.py, resilience.py, engine.py). Copied from the code;
 *  see src/CONTRACTS_P6.md. A value the server could not compute is null. */

export type Strategy = "fixed_time" | "max_pressure";
export type IncidentType = "crash" | "blocked_lane" | "closure";
export type WeatherKind = "rain" | "fog" | "snow" | "ice";

export interface Incident {
  id?: string;
  type: IncidentType;
  links: string[];
  start: number;
  duration: number;
  lanesBlocked: number;
  speedFactor?: number | null;
  policy: "drain" | "hold";
}

export interface WeatherWindow {
  kind: WeatherKind;
  severity: number;
  start: number;
  duration: number;
}

export interface Surge {
  origin: string | null;
  destination: string | null;
  start: number;
  duration: number;
  multiplier: number;
}

export interface Scenario {
  incidents: Incident[];
  weather: WeatherWindow[];
  surges: Surge[];
  reroute: boolean;
}

/** The scenario a catalogue preset carries leaves out empty lists and
 *  defaults, so every part is optional there. */
export interface PresetScenario {
  incidents?: Partial<Incident>[];
  weather?: Partial<WeatherWindow>[];
  surges?: Partial<Surge>[];
  reroute?: boolean;
}

export interface NetworkSpec {
  kind: "corridor" | "grid";
  rows?: number;
  cols?: number;
  spacing?: number;
  vehiclesPerHour?: number;
  demandScale?: number;
}

export interface Preset {
  id: string;
  family: string;
  title: string;
  description: string;
  network: NetworkSpec;
  scenario: PresetScenario;
  duration: number;
}

export interface WeatherFactors {
  speed: number;
  saturation: number;
  headway: number;
  discharge: number;
}

export interface ScoreFormula {
  weights: Record<"recovery" | "throughput" | "peak" | "area", number>;
  peakScaleSeconds: number;
  areaScaleSeconds: number;
}

/** GET /api/v2/incidents/catalogue */
export interface IncidentCatalogue {
  format: string;
  version: number;
  inModelOnly: boolean;
  disruptionTypes: {
    type: string;
    effect: string;
    defaultSpeedFactor?: number;
  }[];
  weather: {
    fullSeverityFactors: Record<string, WeatherFactors>;
    status: string;
  };
  strategies: Strategy[];
  scoreFormula: ScoreFormula;
  scenarios: Preset[];
  stressLabExtension: { note: string };
}

export interface NetworkDescription {
  name: string;
  nodes: number;
  links: number;
  flows: { origin: string; destination: string; vehiclesPerHour: number }[];
}

export interface DelaySeries {
  bucketSeconds: number;
  time: number[];
  meanAccruedDelay: number[];
  active: number[];
  completed: number[];
  entered: number[];
  blocked: number[];
}

/** run_disruption() output (engine.py). */
export interface DisruptionRun {
  format: string;
  version: number;
  strategy: Strategy;
  seed: number;
  duration: number;
  generated: number;
  entered: number;
  blockedAtEntry: number;
  completed: number;
  active: number;
  conserved: boolean;
  meanTravelSeconds: number | null;
  meanDelaySeconds: number | null;
  totalTravelSeconds: number;
  totalDelaySeconds: number;
  unroutable: string[];
  reroutedVehicles: number;
  rerouteEvents: number;
  switches: Record<string, number>;
  perLink: Record<
    string,
    { passed: number; peakOccupancy: number; occupancy: number }
  >;
  perNode: Record<string, { passed: number }>;
  segments: {
    start: number;
    fullyBlocked: string[];
    laneLoss: Record<string, number>;
    weather: { speed: number; saturation: number; headway: number };
    surgeActive: boolean;
  }[];
  series: DelaySeries;
}

/** run_metrics() output (resilience.py): one scenario run against its
 *  undisturbed twin. */
export interface RunMetrics {
  seed: number;
  recovered: boolean;
  recoveryTimeSeconds: number | null;
  peakDelaySeconds: number;
  peakExcessDelaySeconds: number;
  throughputLoss: number;
  areaUnderDelayCurve: number;
  meanExcessDelaySeconds: number;
  excessDelayVehicleSeconds: number;
  completedBaseline: number;
  completed: number;
  blockedAtEntry: number;
  reroutedVehicles: number;
  conserved: boolean;
  components: Record<"recovery" | "throughput" | "peak" | "area", number>;
  score: number;
}

/** POST /api/v2/incidents/simulate */
export interface SimulateResponse {
  network: NetworkDescription;
  scenario: Scenario;
  duration: number;
  inModelOnly: boolean;
  run: DisruptionRun;
  /** Present with compareBaseline. */
  baseline?: DisruptionRun;
  /** Present with compareBaseline; null when the disruption ends too close to
   *  the end of the run to measure recovery. */
  metrics?: RunMetrics | null;
}

export interface StrategyResilience {
  score: number;
  /** null with a single seed. */
  scoreInterval: [number, number] | null;
  recoveredRuns: number;
  runs: number;
  /** Mean over the runs that recovered; null if none did. */
  recoveryTimeSeconds: number | null;
  peakDelaySeconds: number;
  peakExcessDelaySeconds: number;
  throughputLoss: number;
  areaUnderDelayCurve: number;
  excessDelayVehicleSeconds: number;
  perSeed: RunMetrics[];
}

/** POST /api/v2/incidents/resilience */
export interface ResilienceResponse {
  format: string;
  version: number;
  inModelOnly: boolean;
  duration: number;
  bucketSeconds: number;
  disruptionEnd: number;
  seeds: number[];
  tolerance: {
    relative: number;
    absoluteSeconds: number;
    holdBuckets: number;
  };
  scoreFormula: ScoreFormula & { interval: string };
  strategies: Partial<Record<Strategy, StrategyResilience>>;
  best: Strategy;
  note: string;
  network: NetworkDescription;
  scenario: Scenario;
}
