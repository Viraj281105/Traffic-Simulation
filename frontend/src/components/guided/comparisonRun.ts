/**
 * Helpers shared by the guided comparison's screens and the dashboard shell:
 * reading a comparison snapshot into per-strategy metric contexts, reading a
 * saved comparison back, naming a scenario, keeping a finished comparison for
 * the session table, and exporting one as CSV.
 */
import type {
  ComparisonSnapshot,
  DualSnapshot,
  LiveSnapshot,
  RunningMetrics,
} from "../../types/simulation";
import type { SimulationConfigValues } from "../../types/config";
import { demandLevelFor, vehiclesPerHour } from "../../types/config";
import {
  downloadText,
  isInWarmup,
  multiRunCsv,
  type MetricContext,
} from "../../metrics/catalog";
import { sideSummary, type SideSummary } from "../../metrics/plainLanguage";
import { describeMix } from "../../vehicles/vehicleClasses";
import { isMeteredEntry } from "../../scenario/scenarioTypes";
import {
  strategyInfo,
  type StrategyInfo,
} from "../../strategies/strategyCatalog";

/** One strategy's run, read for display. */
export interface StrategyRun {
  strategy: StrategyInfo;
  snapshot: Partial<LiveSnapshot> | undefined;
  ctx: MetricContext;
  summary: SideSummary;
}

function contextFor(
  info: StrategyInfo,
  s: Partial<LiveSnapshot> | undefined,
): MetricContext {
  return {
    metrics: s?.metrics,
    geometry: info.family === "roundabout" ? "roundabout" : "fixed_time_signal",
    inWarmup: isInWarmup(s?.timestamp, s?.warmupTime),
  };
}

/** Every run of a comparison, in the order chosen. Saved comparisons carry
 *  metrics only, so time and warm-up are read defensively. */
export function strategyRuns(
  snapshot: ComparisonSnapshot | null,
): StrategyRun[] {
  if (!snapshot) return [];
  return snapshot.runs.map((run, i) => {
    const strategy = strategyInfo(run.strategy, undefined, i);
    const s = run.snapshot as Partial<LiveSnapshot> | undefined;
    const ctx = contextFor(strategy, s);
    return { strategy, snapshot: s, ctx, summary: sideSummary(ctx) };
  });
}

/** True once every strategy has results worth reading (after warm-up, with
 *  at least one vehicle through). */
export function hasComparisonResults(runs: StrategyRun[]): boolean {
  return runs.length > 0 && runs.every((r) => r.summary.delay !== null);
}

/** The strategies a signal-vs-roundabout pair (a legacy "dual" run) ran:
 *  the signal as the config set it, the roundabout as its entries were. */
export function legacyPairStrategies(
  config: Pick<SimulationConfigValues, "signalControl" | "scenario">,
): [string, string] {
  return [
    config.signalControl === "adaptive"
      ? "adaptive_signal"
      : "fixed_time_signal",
    config.scenario && isMeteredEntry(config.scenario)
      ? "metered_entry_roundabout"
      : "conventional_roundabout",
  ];
}

/** A saved comparison's metrics as a comparison snapshot: the per-strategy
 *  shape a comparison of chosen strategies stores, or the signal/roundabout
 *  pair older comparisons stored. Null for a single-control save. */
export function savedComparison(
  metrics: Record<string, unknown>,
  config: Pick<SimulationConfigValues, "signalControl" | "scenario">,
): ComparisonSnapshot | null {
  const asRun = (strategy: string, m: unknown) => ({
    strategy,
    snapshot: { metrics: m as RunningMetrics } as LiveSnapshot,
  });
  const byStrategy = metrics.strategies;
  if (byStrategy && typeof byStrategy === "object") {
    return {
      tick: 0,
      elapsed: 0,
      runs: Object.entries(byStrategy as Record<string, unknown>).map(
        ([id, m]) => asRun(id, m),
      ),
    };
  }
  if (metrics.signal && metrics.roundabout) {
    const [signalId, roundaboutId] = legacyPairStrategies(config);
    return {
      tick: 0,
      elapsed: 0,
      runs: [
        asRun(signalId, metrics.signal),
        asRun(roundaboutId, metrics.roundabout),
      ],
    };
  }
  return null;
}

/** The pair as the signal-vs-roundabout charts expect it, when the
 *  comparison is exactly one signal and one roundabout; null otherwise. */
export function asSignalRoundaboutPair(
  snapshot: ComparisonSnapshot | null,
): DualSnapshot | null {
  if (!snapshot || snapshot.runs.length !== 2) return null;
  const [a, b] = snapshot.runs;
  const fa = strategyInfo(a.strategy).family;
  const fb = strategyInfo(b.strategy).family;
  if (fa === fb) return null;
  const [signal, roundabout] = fa === "signal" ? [a, b] : [b, a];
  return {
    tick: snapshot.tick,
    elapsed: snapshot.elapsed,
    signal: signal.snapshot,
    roundabout: roundabout.snapshot,
  };
}

/** The values the session table keeps for one strategy. */
export interface SessionValues {
  delay: number | null;
  served: number | null;
  maxQueue: number | null;
}

/** One comparison the user ran this session, kept so alternatives can be
 *  read side by side without saving each one. */
export interface SessionRun {
  id: string;
  config: SimulationConfigValues;
  complete: boolean;
  strategies: string[];
  values: Record<string, SessionValues>;
}

export function sessionRunFrom(
  id: string,
  config: SimulationConfigValues,
  snapshot: ComparisonSnapshot,
  complete: boolean,
): SessionRun {
  const runs = strategyRuns(snapshot);
  return {
    id,
    config,
    complete,
    strategies: runs.map((r) => r.strategy.id),
    values: Object.fromEntries(
      runs.map((r) => [
        r.strategy.id,
        {
          delay: r.summary.delay,
          served: r.summary.served,
          maxQueue: r.summary.maxQueue,
        },
      ]),
    ),
  };
}

export function scenarioLabel(config: SimulationConfigValues): string {
  if (config.scenario) {
    return `“${config.scenario.name}” (≈ ${vehiclesPerHour(config.arrivalRate).toLocaleString()} veh/h)`;
  }
  const level = demandLevelFor(config.arrivalRate, config.lanes);
  return `${level ? level.label : "Custom"} traffic (≈ ${vehiclesPerHour(config.arrivalRate).toLocaleString()} veh/h)`;
}

/** Every catalog metric for every strategy, with the scenario in the
 *  header. Differences are against the first strategy; none ranks them. */
export function downloadComparisonCsv(
  runs: StrategyRun[],
  config: SimulationConfigValues,
  source: string,
  elapsedSeconds: number | null,
  warmupSeconds: number | null,
) {
  const header = [
    `Strategy comparison — ${source}`,
    `Strategies: ${runs.map((r) => r.strategy.fullName).join(", ")}`,
    `Scenario: ${scenarioLabel(config)}, ${String(config.lanes)} lane(s) per approach, seed ${String(config.randomSeed)}`,
    `Traffic: ${describeMix(config.vehicleMix)}`,
    elapsedSeconds !== null
      ? `Simulated time: ${elapsedSeconds.toFixed(1)} s`
      : "",
    warmupSeconds !== null
      ? `Warm-up excluded: ${warmupSeconds.toFixed(0)} s`
      : "",
  ].filter(Boolean);
  downloadText(
    `comparison_${Date.now().toString()}.csv`,
    multiRunCsv(
      runs.map((r) => ({ label: r.strategy.id, ctx: r.ctx })),
      header,
    ),
    "text/csv;charset=utf-8",
  );
}
