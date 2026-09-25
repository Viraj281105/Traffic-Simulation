/**
 * Helpers shared by the guided comparison's screens and the dashboard shell:
 * reading a dual snapshot into metric contexts, naming a scenario, keeping a
 * finished comparison for the session table, and exporting one as CSV.
 */
import type { DualSnapshot, LiveSnapshot } from "../../types/simulation";
import type { SimulationConfigValues } from "../../types/config";
import { demandLevelFor, vehiclesPerHour } from "../../types/config";
import {
  comparisonCsv,
  downloadText,
  isInWarmup,
  type MetricContext,
} from "../../metrics/catalog";
import { sideSummary } from "../../metrics/plainLanguage";

/** One comparison the user ran this session, kept so alternatives can be
 *  read side by side without saving each one. */
export interface SessionRun {
  id: string;
  config: SimulationConfigValues;
  complete: boolean;
  delay: [number | null, number | null];
  served: [number | null, number | null];
  maxQueue: [number | null, number | null];
}

/** Metric contexts for both sides. Saved comparisons carry metrics only, so
 *  time and warm-up are read defensively. */
export function contextsOf(snapshot: DualSnapshot | null): {
  signal: MetricContext;
  roundabout: MetricContext;
} {
  const partial = (s: LiveSnapshot | undefined) =>
    s as Partial<LiveSnapshot> | undefined;
  return {
    signal: {
      metrics: snapshot?.signal.metrics,
      geometry: "fixed_time_signal",
      inWarmup: isInWarmup(
        partial(snapshot?.signal)?.timestamp,
        partial(snapshot?.signal)?.warmupTime,
      ),
    },
    roundabout: {
      metrics: snapshot?.roundabout.metrics,
      geometry: "roundabout",
      inWarmup: isInWarmup(
        partial(snapshot?.roundabout)?.timestamp,
        partial(snapshot?.roundabout)?.warmupTime,
      ),
    },
  };
}

export function sessionRunFrom(
  id: string,
  config: SimulationConfigValues,
  snapshot: DualSnapshot,
  complete: boolean,
): SessionRun {
  const { signal, roundabout } = contextsOf(snapshot);
  const s = sideSummary(signal);
  const r = sideSummary(roundabout);
  return {
    id,
    config,
    complete,
    delay: [s.delay, r.delay],
    served: [s.served, r.served],
    maxQueue: [s.maxQueue, r.maxQueue],
  };
}

export function scenarioLabel(config: SimulationConfigValues): string {
  const level = demandLevelFor(config.arrivalRate, config.lanes);
  return `${level ? level.label : "Custom"} traffic (≈ ${vehiclesPerHour(config.arrivalRate).toLocaleString()} veh/h)`;
}

/** Every catalog metric for both sides, with the scenario in the header. */
export function downloadComparisonCsv(
  snapshot: DualSnapshot,
  config: SimulationConfigValues,
  source: string,
  elapsedSeconds: number | null,
  warmupSeconds: number | null,
) {
  const { signal, roundabout } = contextsOf(snapshot);
  const header = [
    `Signal vs roundabout — ${source}`,
    `Scenario: ${scenarioLabel(config)}, ${String(config.lanes)} lane(s) per approach, seed ${String(config.randomSeed)}`,
    elapsedSeconds !== null
      ? `Simulated time: ${elapsedSeconds.toFixed(1)} s`
      : "",
    warmupSeconds !== null
      ? `Warm-up excluded: ${warmupSeconds.toFixed(0)} s`
      : "",
  ].filter(Boolean);
  downloadText(
    `comparison_${Date.now().toString()}.csv`,
    comparisonCsv(signal, roundabout, header),
    "text/csv;charset=utf-8",
  );
}
