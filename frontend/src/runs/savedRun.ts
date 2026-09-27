/**
 * Presentation helpers for stored runs (the saved-run page, the run
 * comparison and History). They only map a stored record onto the metric
 * catalog's contexts and label what was recorded; nothing here computes a
 * metric or fills in a value a run did not store.
 */
import type { Geometry, MetricContext } from "../metrics/catalog";
import type { RunRecord, RunReproducibility } from "../services/api";
import type { RunningMetrics } from "../types/simulation";

/** One column of metrics: a single run, or one side of a comparison run. */
export interface RunColumn {
  /** Unique within a comparison, e.g. "<runId>" or "<runId>:signal". */
  key: string;
  runId: string;
  side: "signal" | "roundabout" | null;
  /** Short heading, e.g. "Signal" for one side of a comparison run. */
  label: string;
  ctx: MetricContext;
}

type Timing = RunReproducibility["timing"];

function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

/** A comparison (lockstep signal vs roundabout) run: recorded as such, or —
 *  for runs saved before the run mode was recorded — stored with one
 *  metrics object per geometry, the same test History has always used. */
export function isComparisonRun(
  record: Pick<RunRecord, "runMode" | "summaryMetrics">,
): boolean {
  if (record.runMode === "dual") return true;
  const m = record.summaryMetrics;
  return isObject(m.signal) && isObject(m.roundabout);
}

/** Geometry of a single-intersection run for metric applicability. */
export function geometryOf(
  record: Pick<RunRecord, "intersectionType" | "config">,
): Geometry {
  const geometry = record.config?.geometry;
  const fromConfig = isObject(geometry) ? geometry.intersectionType : undefined;
  const type = record.intersectionType ?? fromConfig;
  return type === "roundabout" ? "roundabout" : "fixed_time_signal";
}

/** Whether the stored metrics were captured inside the warm-up period:
 *  null when the run did not record enough timing to tell. */
export function capturedInWarmup(
  timing: Timing,
  config: Record<string, unknown> | null,
): boolean | null {
  const sim = isObject(config?.simulation) ? config.simulation : undefined;
  const warmup =
    timing.warmupTime ??
    (typeof sim?.warmupTime === "number" ? sim.warmupTime : null);
  if (timing.elapsed === null || warmup === null) return null;
  return timing.elapsed < warmup;
}

/** The metric columns of a stored run: one, or two for a comparison run. */
export function metricColumns(record: RunRecord): RunColumn[] {
  const inWarmup = capturedInWarmup(record.timing, record.config) === true;
  if (isComparisonRun(record)) {
    const m = record.summaryMetrics;
    return (["signal", "roundabout"] as const).map((side) => ({
      key: `${record.runId}:${side}`,
      runId: record.runId,
      side,
      label: side === "signal" ? "Signal" : "Roundabout",
      ctx: {
        metrics: (isObject(m[side]) ? m[side] : null) as RunningMetrics | null,
        geometry: side === "signal" ? "fixed_time_signal" : "roundabout",
        inWarmup,
      },
    }));
  }
  const hasMetrics = Object.keys(record.summaryMetrics).length > 0;
  return [
    {
      key: record.runId,
      runId: record.runId,
      side: null,
      label: intersectionLabel(record.intersectionType),
      ctx: {
        metrics: hasMetrics
          ? (record.summaryMetrics as unknown as RunningMetrics)
          : null,
        geometry: geometryOf(record),
        inWarmup,
      },
    },
  ];
}

export function intersectionLabel(type: string | null | undefined): string {
  switch (type) {
    case "fixed_time_signal":
      return "Fixed-time signal";
    case "roundabout":
      return "Roundabout";
    case "comparative":
      return "Signal vs roundabout";
    case null:
    case undefined:
    case "unknown":
      return "—";
    default:
      return type;
  }
}

export function shortRunId(runId: string): string {
  return runId.slice(0, 8);
}

export function runDisplayName(
  record: Pick<RunReproducibility, "name" | "runId">,
): string {
  return record.name ?? `Run ${shortRunId(record.runId)}`;
}

/** Cell text and tooltip for a recorded git commit. */
export function commitLabel(hash: string | null | undefined): {
  text: string;
  title: string;
} {
  if (!hash) {
    return { text: "—", title: "Not recorded for this run" };
  }
  if (hash === "unknown") {
    return {
      text: "unknown",
      title:
        "The backend could not read its git commit when this run was saved",
    };
  }
  return { text: hash.slice(0, 7), title: hash };
}

/** Cell text and tooltip for what kind of configuration was stored. */
export function configLabel(
  rep:
    | Pick<RunReproducibility, "exactConfig" | "configAvailable">
    | null
    | undefined,
): { text: string; title: string } {
  if (rep?.exactConfig) {
    return {
      text: "Exact",
      title: "The exact configuration the simulation ran with is stored",
    };
  }
  if (rep?.configAvailable) {
    return {
      text: "Settings",
      title: "Only the dashboard settings were stored for this run",
    };
  }
  return { text: "—", title: "No configuration recorded for this run" };
}

/** One-line reproducibility status of a stored run. */
export function provenanceStatus(
  record: Pick<
    RunReproducibility,
    "provenanceRecorded" | "exactConfig" | "configAvailable"
  >,
): { label: string; detail: string } {
  if (!record.provenanceRecorded) {
    return {
      label: "Recorded before provenance tracking",
      detail:
        "This run has no recorded code version, timing or configuration source. Values it did not record are shown as —.",
    };
  }
  if (record.exactConfig) {
    return {
      label: "Exact configuration recorded",
      detail:
        "The configuration, seed and timing the engine actually ran with are stored with this run.",
    };
  }
  return {
    label: "Dashboard settings only",
    detail:
      "No running engine was available when this run was saved, so only the dashboard's settings were stored. Anything they omit is re-run with backend defaults.",
  };
}

/** Dotted-path leaves of a nested configuration, in a stable order. Arrays
 *  are kept whole (as JSON), matching the backend CSV export. */
export function flattenConfig(
  value: unknown,
  prefix = "",
  out: [string, string][] = [],
): [string, string][] {
  if (isObject(value)) {
    for (const key of Object.keys(value).sort()) {
      flattenConfig(value[key], prefix ? `${prefix}.${key}` : key, out);
    }
  } else if (prefix) {
    out.push([
      prefix,
      typeof value === "string" ? value : JSON.stringify(value),
    ]);
  }
  return out;
}

/** Configuration keys whose stored values are not identical across the
 *  given runs; a key a run did not store shows as null for that run. */
export function configDifferences(
  configs: (Record<string, unknown> | null)[],
): { path: string; values: (string | null)[] }[] {
  const maps = configs.map((c) => new Map(c ? flattenConfig(c) : []));
  const paths = new Set<string>();
  for (const m of maps) for (const k of m.keys()) paths.add(k);
  const rows: { path: string; values: (string | null)[] }[] = [];
  for (const path of [...paths].sort()) {
    const values = maps.map((m) => m.get(path) ?? null);
    if (new Set(values).size > 1) rows.push({ path, values });
  }
  return rows;
}

export function formatSeconds(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${Number(value.toFixed(2)).toString()} s`;
}
