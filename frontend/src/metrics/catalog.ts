/**
 * The single description of every evaluation metric the backend reports
 * (backend/src/metrics/collector.py → snapshot "metrics"). Panels, tables and
 * CSV exports all read labels, units, precision, grouping and applicability
 * from here, so a metric is described once and presented consistently.
 *
 * Nothing here computes a metric: values always come from the backend. The
 * only transformation is unit presentation (a 0-1 fraction shown as %).
 */
import type { RunningMetrics } from "../types/simulation";

export type MetricGroupId =
  "performance" | "flow" | "safety" | "capacity" | "diagnostic";

export type Geometry = "fixed_time_signal" | "roundabout";

export interface MetricGroup {
  id: MetricGroupId;
  title: string;
  /** One line shown under the group heading. */
  blurb: string;
}

export const METRIC_GROUPS: MetricGroup[] = [
  {
    id: "performance",
    title: "Performance",
    blurb: "Delay, service and speed of vehicles through the junction.",
  },
  {
    id: "flow",
    title: "Traffic flow",
    blurb: "Queues, stops and how evenly the approaches are served.",
  },
  {
    id: "safety",
    title: "Safety",
    blurb:
      "Collisions and surrogate measures (TTC, PET). Thresholds are literature defaults; event counts are exploratory, not a validated safety ranking.",
  },
  {
    id: "capacity",
    title: "Capacity & demand",
    blurb: "Offered demand, served demand and capacity estimates.",
  },
  {
    id: "diagnostic",
    title: "Distribution & diagnostics",
    blurb: "Spread statistics and research indices behind the headline values.",
  },
];

type NumericKey = {
  [K in keyof RunningMetrics]-?: RunningMetrics[K] extends
    number | null | undefined
    ? K
    : never;
}[keyof RunningMetrics];

export interface MetricDef {
  key: NumericKey;
  label: string;
  /** Unit shown after the value ("" for dimensionless indices). */
  unit: string;
  decimals: number;
  group: MetricGroupId;
  /** Plain-language definition, used for tooltips and exports. */
  description: string;
  /** Accumulates only after the warm-up period (most metrics). */
  postWarmup: boolean;
  /** Display multiplier (e.g. a 0-1 fraction shown as a percentage). */
  scale?: number;
  /** Geometries where the backend genuinely measures this metric. */
  appliesTo?: Geometry[];
  /** Shown in place of a null value. */
  nullText?: string;
  /** Computed over vehicles that exited after warm-up. The backend reports
   *  a placeholder (0, or 1.0 for ratios) until one has, so it is shown as
   *  "—" rather than as a result. */
  needsExits?: boolean;
}

const BOTH: Geometry[] = ["fixed_time_signal", "roundabout"];

export const METRICS: MetricDef[] = [
  // ── Performance ──────────────────────────────────────────────────────────
  {
    key: "averageDelay",
    needsExits: true,
    label: "Average delay",
    unit: "s",
    decimals: 1,
    group: "performance",
    description:
      "Mean control delay of vehicles that exited after warm-up: actual travel time minus free-flow travel time.",
    postWarmup: true,
  },
  {
    key: "medianDelay",
    needsExits: true,
    label: "Median delay",
    unit: "s",
    decimals: 1,
    group: "performance",
    description: "Median control delay of vehicles that exited after warm-up.",
    postWarmup: true,
  },
  {
    key: "p95Delay",
    needsExits: true,
    label: "95th percentile delay",
    unit: "s",
    decimals: 1,
    group: "performance",
    description:
      "Control delay not exceeded by 95% of vehicles that exited after warm-up.",
    postWarmup: true,
  },
  {
    key: "averageWaitTime",
    needsExits: true,
    label: "Average queued time",
    unit: "s",
    decimals: 1,
    group: "performance",
    description:
      "Mean time per exited vehicle spent below the waiting-speed threshold (0.5 m/s), after warm-up.",
    postWarmup: true,
  },
  {
    key: "throughput",
    label: "Vehicles served",
    unit: "veh",
    decimals: 0,
    group: "performance",
    description: "Count of vehicles that exited the junction after warm-up.",
    postWarmup: true,
  },
  {
    key: "throughputRate",
    label: "Throughput rate",
    unit: "veh/min",
    decimals: 1,
    group: "performance",
    description:
      "Exits per minute over the most recent 60 s of simulated time (after warm-up).",
    postWarmup: true,
  },
  {
    key: "averageTravelSpeed",
    label: "Current mean speed",
    unit: "m/s",
    decimals: 1,
    group: "performance",
    description:
      "Mean instantaneous speed of the vehicles in the network right now (not a run average).",
    postWarmup: false,
  },
  {
    key: "travelTimeReliability",
    needsExits: true,
    label: "Planning time index",
    unit: "",
    decimals: 2,
    group: "performance",
    description:
      "95th percentile travel time divided by median travel time (1.0 = perfectly reliable). Flagged when fewer than 20 vehicles back it.",
    postWarmup: true,
    nullText: "N/A",
  },

  // ── Traffic flow ─────────────────────────────────────────────────────────
  {
    key: "averageQueueLength",
    label: "Average queue per approach",
    unit: "veh",
    decimals: 1,
    group: "flow",
    description:
      "Time-averaged queue on each approach, averaged across the four approaches (after warm-up).",
    postWarmup: true,
  },
  {
    key: "maxQueueLength",
    label: "Maximum queue",
    unit: "veh",
    decimals: 0,
    group: "flow",
    description: "Largest queue observed on any single approach after warm-up.",
    postWarmup: true,
  },
  {
    key: "activeAverageQueueLength",
    label: "Average total queue when queued",
    unit: "veh",
    decimals: 1,
    group: "flow",
    description:
      "Mean of the junction-wide total queue over the ticks where any vehicle was queued.",
    postWarmup: true,
  },
  {
    key: "averageStopsPerVehicle",
    needsExits: true,
    label: "Stops per vehicle",
    unit: "",
    decimals: 2,
    group: "flow",
    description:
      "Mean number of stops (speed below 0.1 m/s) per vehicle that exited after warm-up.",
    postWarmup: true,
  },
  {
    key: "totalStops",
    label: "Total stops",
    unit: "",
    decimals: 0,
    group: "flow",
    description: "Stops made by vehicles that exited after warm-up (a count).",
    postWarmup: true,
  },
  {
    key: "directionalFairnessIndex",
    needsExits: true,
    label: "Directional fairness",
    unit: "",
    decimals: 2,
    group: "flow",
    description:
      "Jain's fairness index over the four approaches' mean waits: 1.00 = equal, 0.25 = one approach bears it all.",
    postWarmup: true,
  },
  {
    key: "congestionRecoveryTime",
    label: "Time congested",
    unit: "s",
    decimals: 1,
    group: "flow",
    description:
      "Simulated time after warm-up during which more than 5 vehicles were queued in total. (Reported by the backend as congestionRecoveryTime.)",
    postWarmup: true,
  },

  // ── Safety ───────────────────────────────────────────────────────────────
  {
    key: "collisionCount",
    label: "Collisions",
    unit: "",
    decimals: 0,
    group: "safety",
    description:
      "Distinct vehicle-pair overlaps since the run began (each counted once, not per tick). Includes warm-up.",
    postWarmup: false,
  },
  {
    key: "minTTC",
    label: "Minimum TTC",
    unit: "s",
    decimals: 2,
    group: "safety",
    description:
      "Smallest time-to-collision observed between a following vehicle and its leader after warm-up.",
    postWarmup: true,
    nullText: "None observed",
  },
  {
    key: "ttcEventCount",
    label: "Low-TTC events",
    unit: "",
    decimals: 0,
    group: "safety",
    description:
      "Observations with time-to-collision at or below the TTC threshold (see label).",
    postWarmup: true,
  },
  {
    key: "minPET",
    label: "Minimum PET",
    unit: "s",
    decimals: 2,
    group: "safety",
    description:
      "Smallest post-encroachment time at a signal conflict point after warm-up. Not measured for roundabouts.",
    postWarmup: true,
    appliesTo: ["fixed_time_signal"],
    nullText: "None observed",
  },
  {
    key: "petEventCount",
    label: "Low-PET events",
    unit: "",
    decimals: 0,
    group: "safety",
    description:
      "Conflict-point crossings with post-encroachment time at or below the PET threshold. Not measured for roundabouts.",
    postWarmup: true,
    appliesTo: ["fixed_time_signal"],
  },

  // ── Capacity & demand ────────────────────────────────────────────────────
  {
    key: "totalVehiclesSpawned",
    label: "Vehicles generated",
    unit: "veh",
    decimals: 0,
    group: "capacity",
    description: "All vehicles generated since the run began (offered demand).",
    postWarmup: false,
  },
  {
    key: "activeVehicleCount",
    label: "Vehicles in network now",
    unit: "veh",
    decimals: 0,
    group: "capacity",
    description: "Vehicles currently on the approaches or in the junction.",
    postWarmup: false,
  },
  {
    key: "criticalSaturationVolume",
    label: "Critical saturation volume",
    unit: "veh/s",
    decimals: 3,
    group: "capacity",
    description:
      "Backend saturation estimate: the observed throughput rate when it is below the configured arrival rate (demand not fully served), otherwise the configured arrival rate scaled by the served share of post-warm-up vehicles.",
    postWarmup: true,
  },
  {
    key: "intersectionUtilization",
    label: "Service utilization",
    unit: "%",
    decimals: 1,
    group: "capacity",
    description:
      "Share of post-warm-up ticks with vehicles present in which their mean speed was above the waiting threshold.",
    postWarmup: true,
  },
  {
    key: "idleOpportunityLoss",
    label: "Idle green loss",
    unit: "%",
    decimals: 1,
    scale: 100,
    group: "capacity",
    description:
      "Share of post-warm-up ticks where a red approach had a queue while every green approach was empty. Signal-only.",
    postWarmup: true,
    appliesTo: ["fixed_time_signal"],
  },
  {
    key: "spaceFootprintConsumed",
    label: "Junction footprint",
    unit: "m²",
    decimals: 0,
    group: "capacity",
    description:
      "Area of the junction from the configured geometry (ring area for a roundabout, crossing box for a signal).",
    postWarmup: false,
  },

  // ── Distribution & diagnostics ───────────────────────────────────────────
  {
    key: "minDelay",
    needsExits: true,
    label: "Minimum delay",
    unit: "s",
    decimals: 1,
    group: "diagnostic",
    description: "Smallest control delay of an exited vehicle after warm-up.",
    postWarmup: true,
  },
  {
    key: "maxDelay",
    needsExits: true,
    label: "Maximum delay",
    unit: "s",
    decimals: 1,
    group: "diagnostic",
    description: "Largest control delay of an exited vehicle after warm-up.",
    postWarmup: true,
  },
  {
    key: "delayStdDev",
    needsExits: true,
    label: "Delay standard deviation",
    unit: "s",
    decimals: 1,
    group: "diagnostic",
    description: "Sample standard deviation of control delay.",
    postWarmup: true,
  },
  {
    key: "queueStdDev",
    label: "Queue standard deviation",
    unit: "veh",
    decimals: 2,
    group: "diagnostic",
    description: "Sample standard deviation of the junction-wide total queue.",
    postWarmup: true,
  },
  {
    key: "queueStabilityIndex",
    label: "Queue stability index",
    unit: "",
    decimals: 2,
    group: "diagnostic",
    description:
      "Coefficient of variation of the junction-wide total queue (standard deviation ÷ mean). Lower is steadier.",
    postWarmup: true,
  },
  {
    key: "speedVarianceIndex",
    label: "Speed variance index",
    unit: "",
    decimals: 3,
    group: "diagnostic",
    description:
      "Time-averaged coefficient of variation of vehicle speeds (ticks with at least two vehicles).",
    postWarmup: true,
  },
  {
    key: "ttcSampleCount",
    label: "TTC observations",
    unit: "",
    decimals: 0,
    group: "diagnostic",
    description: "Number of leader-follower TTC observations after warm-up.",
    postWarmup: true,
  },
  {
    key: "petSampleCount",
    label: "PET observations",
    unit: "",
    decimals: 0,
    group: "diagnostic",
    description: "Number of conflict-point PET observations after warm-up.",
    postWarmup: true,
    appliesTo: ["fixed_time_signal"],
  },
  {
    key: "masterEfficiencyScore",
    needsExits: true,
    label: "Composite score (fixed weights)",
    unit: "/100",
    decimals: 1,
    group: "diagnostic",
    description:
      "Backend composite of throughput rate, queued time, stops, fairness and idle loss with fixed weights. A weighting choice, not a verdict.",
    postWarmup: true,
  },
];

export const METRICS_BY_GROUP: Record<MetricGroupId, MetricDef[]> =
  METRIC_GROUPS.reduce(
    (acc, g) => {
      acc[g.id] = METRICS.filter((m) => m.group === g.id);
      return acc;
    },
    {} as Record<MetricGroupId, MetricDef[]>,
  );

/** Label with any threshold the backend reported alongside the metric. */
export function metricLabel(def: MetricDef, m?: RunningMetrics): string {
  if (def.key === "ttcEventCount" && m?.ttcThresholdSeconds !== undefined) {
    return `${def.label} (TTC ≤ ${m.ttcThresholdSeconds.toFixed(1)} s)`;
  }
  if (def.key === "petEventCount" && m?.petThresholdSeconds !== undefined) {
    return `${def.label} (PET ≤ ${m.petThresholdSeconds.toFixed(1)} s)`;
  }
  return def.label;
}

export const WARMUP_NOTE = "Warm-up in progress";

export type MetricState =
  | { kind: "value"; value: number; note?: string }
  | { kind: "none"; text: string; note?: string };

export interface MetricContext {
  metrics: RunningMetrics | undefined | null;
  geometry: Geometry;
  /** True while the snapshot is still inside the warm-up period. */
  inWarmup: boolean;
}

/** Resolves what should be shown for one metric, never inventing a value. */
export function metricState(def: MetricDef, ctx: MetricContext): MetricState {
  const { metrics, geometry, inWarmup } = ctx;
  if (!metrics) return { kind: "none", text: "—" };
  const applies = def.appliesTo ?? BOTH;
  if (!applies.includes(geometry)) {
    return {
      kind: "none",
      text: "N/A",
      note: "Not measured for this geometry",
    };
  }
  if (
    (def.key === "minPET" ||
      def.key === "petEventCount" ||
      def.key === "petSampleCount") &&
    metrics.petApplicable === false
  ) {
    return { kind: "none", text: "N/A", note: "Not measured for this run" };
  }
  if (def.postWarmup && inWarmup) {
    return { kind: "none", text: "—", note: WARMUP_NOTE };
  }
  if (def.needsExits && metrics.throughput === 0) {
    return { kind: "none", text: "—", note: "No vehicles served yet" };
  }
  const raw = metrics[def.key];
  if (raw === undefined) {
    return { kind: "none", text: "—", note: "Not reported by this backend" };
  }
  if (raw === null || !Number.isFinite(raw)) {
    return { kind: "none", text: def.nullText ?? "N/A" };
  }
  const value = raw * (def.scale ?? 1);
  if (
    def.key === "travelTimeReliability" &&
    metrics.travelTimeReliabilityLowSampleSize
  ) {
    return { kind: "value", value, note: "Low sample (n < 20)" };
  }
  return { kind: "value", value };
}

export function formatNumber(value: number, decimals: number): string {
  return value.toLocaleString(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

/** Display text for a metric, with its unit unless `withUnit` is false (for
 *  compact tables that carry the unit in the row label instead). */
export function formatMetric(
  def: MetricDef,
  ctx: MetricContext,
  withUnit = true,
): string {
  const state = metricState(def, ctx);
  if (state.kind === "none") return state.text;
  const n = formatNumber(state.value, def.decimals);
  if (!def.unit || !withUnit) return n;
  return def.unit === "%" ? `${n}%` : `${n} ${def.unit}`;
}

/** Signed difference (roundabout − signal) in the metric's own units, or
 *  null when either side has no comparable value. */
export function metricDifference(
  def: MetricDef,
  signal: MetricContext,
  roundabout: MetricContext,
): number | null {
  const a = metricState(def, signal);
  const b = metricState(def, roundabout);
  if (a.kind !== "value" || b.kind !== "value") return null;
  return b.value - a.value;
}

export function formatDifference(
  def: MetricDef,
  diff: number | null,
  withUnit = true,
): string {
  if (diff === null) return "—";
  const rounded = Number(diff.toFixed(def.decimals));
  if (rounded === 0) return formatNumber(0, def.decimals);
  const sign = rounded > 0 ? "+" : "−";
  const n = formatNumber(Math.abs(rounded), def.decimals);
  if (!def.unit || !withUnit) return `${sign}${n}`;
  return def.unit === "%" ? `${sign}${n} pp` : `${sign}${n} ${def.unit}`;
}

/** True when the snapshot's simulated time is still within warm-up. */
export function isInWarmup(
  timestamp: number | undefined,
  warmupTime: number | undefined,
): boolean {
  if (timestamp === undefined || warmupTime === undefined) return false;
  return timestamp < warmupTime;
}

function csvCell(v: string): string {
  return /[",\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v;
}

function rawCell(def: MetricDef, ctx: MetricContext): string {
  const s = metricState(def, ctx);
  return s.kind === "value" ? String(s.value) : s.text;
}

/** CSV of every metric for one run. */
export function singleRunCsv(ctx: MetricContext, header: string[]): string {
  const rows = [
    ...header.map((h) => `# ${h}`),
    "group,metric,key,unit,value,note",
  ];
  for (const def of METRICS) {
    const s = metricState(def, ctx);
    rows.push(
      [
        def.group,
        metricLabel(def, ctx.metrics ?? undefined),
        def.key,
        def.unit,
        rawCell(def, ctx),
        s.note ?? "",
      ]
        .map(csvCell)
        .join(","),
    );
  }
  return rows.join("\n") + "\n";
}

/** CSV of every metric for a signal/roundabout pair. The difference column is
 *  roundabout minus signal in the metric's unit; no column ranks the two. */
export function comparisonCsv(
  signal: MetricContext,
  roundabout: MetricContext,
  header: string[],
): string {
  const rows = [
    ...header.map((h) => `# ${h}`),
    "group,metric,key,unit,fixed_time_signal,roundabout,roundabout_minus_signal",
  ];
  for (const def of METRICS) {
    const diff = metricDifference(def, signal, roundabout);
    rows.push(
      [
        def.group,
        metricLabel(def, signal.metrics ?? roundabout.metrics ?? undefined),
        def.key,
        def.unit,
        rawCell(def, signal),
        rawCell(def, roundabout),
        diff === null ? "" : String(diff),
      ]
        .map(csvCell)
        .join(","),
    );
  }
  return rows.join("\n") + "\n";
}

/** CSV of every metric for any number of runs (or comparison sides). Each
 *  difference column is that column minus the baseline column, in the
 *  metric's unit (percentage points for %); a difference is left empty
 *  whenever either value is unavailable. No column ranks the runs. */
export function multiRunCsv(
  columns: { label: string; ctx: MetricContext }[],
  header: string[],
  baselineIndex = 0,
): string {
  const baseline = columns[baselineIndex];
  const others = columns.filter((_, i) => i !== baselineIndex);
  const rows = [
    ...header.map((h) => `# ${h}`),
    [
      "group",
      "metric",
      "key",
      "unit",
      ...columns.map((c) => c.label),
      ...others.map((c) => `${c.label} minus ${baseline.label}`),
    ]
      .map(csvCell)
      .join(","),
  ];
  for (const def of METRICS) {
    const labelSource = columns.find((c) => c.ctx.metrics)?.ctx.metrics;
    rows.push(
      [
        def.group,
        metricLabel(def, labelSource ?? undefined),
        def.key,
        def.unit,
        ...columns.map((c) => rawCell(def, c.ctx)),
        ...others.map((c) => {
          const diff = metricDifference(def, baseline.ctx, c.ctx);
          return diff === null ? "" : String(diff);
        }),
      ]
        .map(csvCell)
        .join(","),
    );
  }
  return rows.join("\n") + "\n";
}

/** Triggers a browser download of text content. */
export function downloadText(filename: string, content: string, type: string) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
