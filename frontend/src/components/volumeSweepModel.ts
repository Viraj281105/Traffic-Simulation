/**
 * The volume sweep as the dashboard reads it: the backend's sweep payload
 * (both the flat shape and the older one nested under `results`), offered
 * demand derived from each tier's arrival rate, the plain-language crossover
 * summary, the rows the charts plot, the sweep form's configuration and the
 * per-tier tallies and CSV the views show. Pure data; no React.
 */
import {
  SPEED_LIMITS,
  TIER_PRESETS,
  sweepRates,
  type TierPresetId,
} from "../types/demand";
import type { RunningMetrics } from "../types/simulation";

export type SweepWinner = "signal" | "roundabout" | "tie" | "inconclusive";

export interface Calibration {
  calibrated: boolean;
  note: string;
}

export interface TieTolerance {
  absSeconds: number;
  relative: number;
}

/** Same rule as backend study/tolerances.py and plainLanguage SIMILARITY.delay. */
export const DEFAULT_TIE_TOLERANCE: TieTolerance = {
  absSeconds: 1,
  relative: 0.05,
};

export function tieText(t: TieTolerance | undefined): string {
  const tol = t ?? DEFAULT_TIE_TOLERANCE;
  return `≤${tol.absSeconds.toString()} s or ≤${(tol.relative * 100).toString()}%`;
}

export function winnerLabel(w: SweepWinner): string {
  if (w === "roundabout") return "Lower delay: roundabout";
  if (w === "signal") return "Lower delay: signal";
  if (w === "tie") return "About the same";
  return "Inconclusive";
}

export interface SweepRun {
  arrivalRate: number;
  hourlyVolumeVehPerHour: number;
  /** Lower mean delay at this tier. "inconclusive": too few vehicles got
   *  through, or the vehicle limit cut demand off, so no direction is given. */
  winner: SweepWinner;
  inconclusiveReason?: "low_sample" | "vehicle_limit_reached" | null;
  vehicleLimitReached?: boolean;
  delayDeltaPercent: number;
  throughputDeltaPercent?: number;
  queueDeltaPercent?: number;
  signal: {
    delay: number;
    delayMedian?: number;
    delayStdDev?: number;
    delayMin?: number;
    delayMax?: number;
    delayP95?: number;
    throughput: number;
    throughputRate?: number;
    queue: number;
    queueMax?: number;
    queueStdDev?: number;
    /** Full collector metrics for this tier's run (same set as live). */
    metrics?: RunningMetrics;
  };
  roundabout: {
    delay: number;
    delayMedian?: number;
    delayStdDev?: number;
    delayMin?: number;
    delayMax?: number;
    delayP95?: number;
    throughput: number;
    throughputRate?: number;
    queue: number;
    queueMax?: number;
    queueStdDev?: number;
    metrics?: RunningMetrics;
  };
}

export interface SweepCurves {
  rates: number[];
  volumesVehPerHour: number[];
  signal: {
    delays: number[];
    delayStds?: number[];
    delayMins?: number[];
    delayMaxs?: number[];
    throughputs: number[];
    queues: number[];
    queueStds?: number[];
    queueMaxs?: number[];
  };
  roundabout: {
    delays: number[];
    delayStds?: number[];
    delayMins?: number[];
    delayMaxs?: number[];
    throughputs: number[];
    queues: number[];
    queueStds?: number[];
    queueMaxs?: number[];
  };
  crossoverArrivalRate: number | null;
  crossoverHourlyVolume: number | null;
  /** The two decided tiers the change lies between (not interpolated). */
  crossoverBracketArrivalRates?: [number, number] | null;
}

export interface SweepSession {
  sessionId: string;
  name: string;
  duration: number;
  randomSeed: number;
  seedsPerTier?: number;
  tieTolerance?: TieTolerance;
  /** Absent on sweeps saved before calibration was recorded. */
  calibration?: Calibration;
  curves: SweepCurves;
  runs: SweepRun[];
}

export interface SavedSweep {
  id: string;
  name: string;
  created_at: string;
}

/** A sweep session from either payload shape the backend returns (flat, or
 *  nested under `results` for older saved sweeps), with `fallback` for any
 *  identifying field the payload lacks. */
export function parseSweepSession(
  data: unknown,
  fallback: Pick<
    SweepSession,
    "sessionId" | "name" | "duration" | "randomSeed"
  >,
): SweepSession {
  const raw = data as Record<string, unknown>;
  const rawResults =
    raw.results && typeof raw.results === "object"
      ? (raw.results as Record<string, unknown>)
      : {};
  const pick = (key: string): unknown => raw[key] ?? rawResults[key];
  const text = (...keys: string[]): string | undefined => {
    for (const key of keys) {
      if (typeof raw[key] === "string") return raw[key];
    }
    for (const key of keys) {
      if (typeof rawResults[key] === "string") return rawResults[key];
    }
    return undefined;
  };
  const runs = Array.isArray(raw.runs) ? raw.runs : rawResults.runs;
  const curves = (pick("curves") as SweepCurves | undefined) ?? {
    rates: [],
    volumesVehPerHour: [],
    signal: { delays: [], throughputs: [], queues: [] },
    roundabout: { delays: [], throughputs: [], queues: [] },
    crossoverArrivalRate: null,
    crossoverHourlyVolume: null,
  };
  return withOfferedVolumes({
    sessionId: text("sessionId", "id") ?? fallback.sessionId,
    name: text("name") ?? fallback.name,
    duration: Number(pick("duration") ?? fallback.duration),
    randomSeed: Number(pick("randomSeed") ?? fallback.randomSeed),
    curves,
    runs: Array.isArray(runs) ? (runs as SweepRun[]) : [],
    calibration: pick("calibration") as Calibration | undefined,
    tieTolerance: pick("tieTolerance") as TieTolerance | undefined,
    seedsPerTier: pick("seedsPerTier") as number | undefined,
  });
}

/**
 * Offered demand in veh/h is always derived from each tier's arrivalRate
 * (the whole junction's rate, split across the four approaches by the
 * spawner): veh/h = rate x 3600. Sweeps saved before the backend fix
 * stored rate x 3600 x 4, overstating demand four-fold, so stored hourly
 * values are recomputed rather than trusted.
 */
function withOfferedVolumes(session: SweepSession): SweepSession {
  const vph = (rate: number) => Math.round(rate * 3600);
  return {
    ...session,
    runs: session.runs.map((r) => ({
      ...r,
      hourlyVolumeVehPerHour: vph(r.arrivalRate),
    })),
    curves: {
      ...session.curves,
      volumesVehPerHour: session.curves.rates.map(vph),
      crossoverHourlyVolume:
        session.curves.crossoverArrivalRate === null
          ? null
          : vph(session.curves.crossoverArrivalRate),
    },
  };
}

const CONTROL_NAME = { signal: "signal", roundabout: "roundabout" } as const;

/** Describes the sweep's change of direction from the data itself: which
 *  control had the lower mean delay on each side, rather than assuming a
 *  direction. Tiers that were a tie or inconclusive take no part. */
export function crossoverSummary(
  runs: SweepRun[],
  crossover: number | null,
  bracket?: [number, number] | null,
): string {
  const decided = runs.filter(
    (r) => r.winner === "signal" || r.winner === "roundabout",
  );
  const undecided = runs.length - decided.length;
  const suffix = ` (this sweep, one random pattern per tier${undecided > 0 ? `; ${undecided.toString()} tier${undecided === 1 ? " was" : "s were"} a tie or inconclusive` : ""}).`;
  if (crossover !== null) {
    const below = decided.filter(
      (r) => r.arrivalRate < (bracket?.[1] ?? Infinity),
    );
    const last = below.length > 0 ? below[below.length - 1] : undefined;
    const from = bracket
      ? `between ${Math.round(bracket[0] * 3600).toLocaleString()} and ${Math.round(bracket[1] * 3600).toLocaleString()} veh/h`
      : `at ≈${crossover.toLocaleString()} veh/h`;
    if (!last || (last.winner !== "signal" && last.winner !== "roundabout")) {
      return `The control with the lower mean delay changes ${from}${suffix}`;
    }
    const first = CONTROL_NAME[last.winner];
    const other = last.winner === "signal" ? "roundabout" : "signal";
    return `Lower mean delay: ${first} before, ${other} after, the change lying ${from}${suffix}`;
  }
  if (decided.length === 0) {
    return `No tier could be decided: every tier was within the tie tolerance or inconclusive.`;
  }
  const kinds = new Set(decided.map((r) => r.winner));
  if (kinds.size === 1) {
    return `The ${CONTROL_NAME[decided[0].winner as "signal" | "roundabout"]} had the lower mean delay at every decided tier${suffix}`;
  }
  return "No single change: the lower-delay control alternated more than once.";
}

// ── Chart data builder ──────────────────────────────────────────────────────

export function buildChartData(session: SweepSession) {
  if (!Array.isArray(session.runs)) return [];
  return session.runs.map((run) => {
    const sigDelay = Number(run.signal.delay.toFixed(2));
    const rndDelay = Number(run.roundabout.delay.toFixed(2));
    const sigDelayStd = Number((run.signal.delayStdDev ?? 0).toFixed(2));
    const rndDelayStd = Number((run.roundabout.delayStdDev ?? 0).toFixed(2));
    const sigDelayMin = Number(
      (run.signal.delayMin ?? Math.max(0, sigDelay - sigDelayStd)).toFixed(2),
    );
    const sigDelayMax = Number(
      (run.signal.delayMax ?? sigDelay + sigDelayStd).toFixed(2),
    );
    const rndDelayMin = Number(
      (run.roundabout.delayMin ?? Math.max(0, rndDelay - rndDelayStd)).toFixed(
        2,
      ),
    );
    const rndDelayMax = Number(
      (run.roundabout.delayMax ?? rndDelay + rndDelayStd).toFixed(2),
    );
    const sigQueue = Number(run.signal.queue.toFixed(2));
    const rndQueue = Number(run.roundabout.queue.toFixed(2));
    const sigQueueMax = Number((run.signal.queueMax ?? sigQueue).toFixed(2));
    const rndQueueMax = Number(
      (run.roundabout.queueMax ?? rndQueue).toFixed(2),
    );

    return {
      volume: run.hourlyVolumeVehPerHour,
      rate: Number(run.arrivalRate.toFixed(2)),
      signalDelay: sigDelay,
      signalDelayMin: sigDelayMin,
      signalDelayMax: sigDelayMax,
      signalDelayStdDev: sigDelayStd,
      roundaboutDelay: rndDelay,
      roundaboutDelayMin: rndDelayMin,
      roundaboutDelayMax: rndDelayMax,
      roundaboutDelayStdDev: rndDelayStd,
      signalThroughput: run.signal.throughput,
      roundaboutThroughput: run.roundabout.throughput,
      signalQueue: sigQueue,
      signalQueueMax: sigQueueMax,
      roundaboutQueue: rndQueue,
      roundaboutQueueMax: rndQueueMax,
      winner: run.winner,
      delayDeltaPercent: Number(run.delayDeltaPercent.toFixed(1)),
      throughputDeltaPercent: Number(
        (run.throughputDeltaPercent ?? 0).toFixed(1),
      ),
      queueDeltaPercent: Number((run.queueDeltaPercent ?? 0).toFixed(1)),
    };
  });
}

export type SweepChartRow = ReturnType<typeof buildChartData>[number];

// ── Sweep configuration ─────────────────────────────────────────────────────

export type DemandTierPreset = "standard" | "dense" | "granular";
export type SpeedProfileKey = keyof typeof SPEED_LIMITS;

/** What the sweep form edits: duration and seed in the header, the rest in
 *  the advanced drawer. */
export interface SweepConfig {
  duration: number;
  randomSeed: number;
  demandTierPreset: DemandTierPreset;
  arrivalDistribution: "poisson" | "uniform";
  warmupTime: number;
  timeStep: number;
  approachLength: number;
  lanesCount: number;
  speedProfileKey: SpeedProfileKey;
}

export const DEFAULT_SWEEP_CONFIG: SweepConfig = {
  duration: 240,
  randomSeed: 42,
  demandTierPreset: "standard",
  arrivalDistribution: "poisson",
  warmupTime: 30.0,
  timeStep: 0.1,
  approachLength: 200.0,
  lanesCount: 1,
  speedProfileKey: "standard",
};

/** Demand tiers: the three presets, as shares of the capacity measured for
 *  the chosen lane count (types/demand.ts), so they span free flow to
 *  oversaturation at every lane count. */
export function sweepTierRates(
  preset: DemandTierPreset,
  lanesCount: number,
): { rates: number[]; detail: string } {
  const id: TierPresetId =
    preset === "dense"
      ? "wide"
      : preset === "granular"
        ? "transition"
        : "standard";
  const tiers = TIER_PRESETS.find((t) => t.id === id) ?? TIER_PRESETS[0];
  return { rates: sweepRates(tiers, lanesCount), detail: tiers.detail };
}

/** The study scenario the sweep job runs every tier on. */
export function sweepCustomConfig(config: SweepConfig) {
  return {
    simulation: {
      warmupTime: config.warmupTime,
      timeStep: config.timeStep,
      duration: config.duration,
      randomSeed: config.randomSeed,
    },
    roads: {
      approachLength: config.approachLength,
      laneWidth: 3.5,
      speedLimit: SPEED_LIMITS[config.speedProfileKey].metresPerSecond,
      lanesPerApproach: {
        north: config.lanesCount,
        south: config.lanesCount,
        east: config.lanesCount,
        west: config.lanesCount,
      },
    },
    traffic: {
      arrivalDistribution: config.arrivalDistribution,
    },
  };
}

// ── Tier summaries ──────────────────────────────────────────────────────────

export interface TierTally {
  roundabout: number;
  signal: number;
  tie: number;
  inconclusive: number;
  /** Tiers where vehicle generation hit its per-run limit. */
  capped: number;
  total: number;
}

export function tierTally(runs: SweepRun[]): TierTally {
  return {
    roundabout: runs.filter((r) => r.winner === "roundabout").length,
    signal: runs.filter((r) => r.winner === "signal").length,
    tie: runs.filter((r) => r.winner === "tie").length,
    inconclusive: runs.filter((r) => r.winner === "inconclusive").length,
    capped: runs.filter((r) => r.vehicleLimitReached).length,
    total: runs.length,
  };
}

/** Tier with the largest absolute mean-delay difference (roundabout − signal). */
export function largestDelayGap(
  runs: SweepRun[],
): { run: SweepRun; diff: number } | null {
  return runs.reduce<{ run: SweepRun; diff: number } | null>((best, run) => {
    const diff = run.roundabout.delay - run.signal.delay;
    return !best || Math.abs(diff) > Math.abs(best.diff) ? { run, diff } : best;
  }, null);
}

/** Where the demand explorer starts: the crossover if there is one, else the
 *  middle tier. */
export function defaultScrubberVolume(
  session: SweepSession | null,
  runs: SweepRun[],
): number {
  if (session?.curves.crossoverHourlyVolume) {
    return session.curves.crossoverHourlyVolume;
  }
  if (runs.length > 0) {
    const midIdx = Math.floor(runs.length / 2);
    return runs[midIdx].hourlyVolumeVehPerHour;
  }
  return 1440;
}

/** The tier whose offered demand is nearest `volume` (first wins a tie). */
export function closestRun(runs: SweepRun[], volume: number): SweepRun | null {
  if (runs.length === 0) return null;
  let closest = runs[0];
  let minDiff = Math.abs(closest.hourlyVolumeVehPerHour - volume);
  for (const run of runs) {
    const diff = Math.abs(run.hourlyVolumeVehPerHour - volume);
    if (diff < minDiff) {
      minDiff = diff;
      closest = run;
    }
  }
  return closest;
}

/** Scale for the matrix's delay bars: the largest delay on either side, at
 *  least 10 s. */
export function maxTierDelay(runs: SweepRun[]): number {
  if (runs.length === 0) return 60;
  return Math.max(
    ...runs.map((r) => Math.max(r.signal.delay, r.roundabout.delay)),
    10,
  );
}

// ── CSV export ──────────────────────────────────────────────────────────────

export function sweepCsv(runs: SweepRun[]): string {
  const headers = [
    "Arrival Rate (veh/s)",
    "Hourly Volume (veh/h)",
    "Signal Delay (s)",
    "Roundabout Delay (s)",
    "Delay Delta (%)",
    "Signal Throughput (veh)",
    "Roundabout Throughput (veh)",
    "Signal Queue (veh)",
    "Roundabout Queue (veh)",
    "Lower mean delay (tie / inconclusive shown as such)",
  ];

  const rows = runs.map((r) => [
    r.arrivalRate.toFixed(2),
    r.hourlyVolumeVehPerHour.toString(),
    r.signal.delay.toFixed(2),
    r.roundabout.delay.toFixed(2),
    r.delayDeltaPercent.toFixed(1),
    r.signal.throughput.toString(),
    r.roundabout.throughput.toString(),
    r.signal.queue.toFixed(1),
    r.roundabout.queue.toFixed(1),
    r.winner,
  ]);

  return [headers.join(","), ...rows.map((e) => e.join(","))].join("\n");
}
