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
    title: "Safety & Environment",
    blurb:
      "Collisions, surrogate safety measures (TTC, PET), and estimated environmental impact (fuel, CO₂). Thresholds are literature defaults; environmental metrics are simplified kinematic estimates, not real-world measurements.",
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
  /** Everyday-words version for the glossary, where the description is too
   *  technical. Absent: the description is already plain enough. Same
   *  claims discipline as the description: no overstating. */
  plain?: string;
  /** Accumulates only after the warm-up period (most metrics). */
  postWarmup: boolean;
  /** Display multiplier (e.g. a 0-1 fraction shown as a percentage). */
  scale?: number;
  /** Geometries where the backend genuinely measures this metric. */
  appliesTo?: Geometry[];
  /** Shown in place of a null value. */
  nullText?: string;
  /** True when the value is meaningful only within one geometry and
   *  scenario. Such a metric is never shown side by side across the two
   *  geometries (comparison tables, comparison CSVs). */
  withinGeometryOnly?: boolean;
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
      "Mean extra travel time of vehicles that exited after warm-up: actual travel time minus the time the same journey would take at the driver's own desired speed. It includes any slowing the layout itself forces (for example easing into a roundabout), so it is not the same as time spent queued; compare it with Average queued time.",
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
    plain:
      "The middle driver's lost time: half of drivers lost less than this, half lost more.",
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
    plain:
      "The time lost by the unluckiest 1 in 20 drivers, or more. It shows how bad a bad trip is, not a typical one.",
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
      "Mean time per exited vehicle spent below the waiting-speed threshold (0.5 m/s), after warm-up. Not the same as delay: a vehicle that keeps rolling slowly is delayed but not queued.",
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
    plain:
      "How much longer a bad trip takes than a normal one. 1.0 means bad trips are no slower than normal; 1.5 means 50% slower. Treat it with care when only a few vehicles have finished.",
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
    plain:
      "How long the queue is whenever there is one, ignoring moments with no queue at all.",
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
      "Jain's fairness index over the approaches' mean queued time (not delay): 1.00 = equal; the floor is 1 ÷ the number of approaches with traffic (0.25 with four). Noisy when few vehicles have exited.",
    plain:
      "Whether drivers on every approach wait about the same. 1.00 means equally; lower means some approaches wait much more than others. It wobbles when few vehicles have finished.",
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
    plain:
      "How long the junction held a sizeable queue (more than 5 vehicles in total) after the warm-up.",
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
    plain:
      "How many times two simulated vehicles overlapped. In the model this should be zero; any other number points to a problem in the model.",
    postWarmup: false,
  },
  {
    key: "minTTC",
    label: "Minimum TTC",
    unit: "s",
    decimals: 2,
    group: "safety",
    description:
      "Smallest constant-velocity time-to-collision seen so far between two vehicles on different lanes within 50 m (crossing and merging pairs; same-lane following is excluded), after warm-up. A running minimum: it can only fall during a run. A surrogate indicator, not a collision or crash probability.",
    plain:
      "The closest call so far between two vehicles heading for each other from different lanes, as seconds before they would meet if nobody changed speed. Smaller is closer. A warning sign in the model, not a crash prediction.",
    postWarmup: true,
    nullText: "None observed",
  },
  {
    key: "ttcEventCount",
    label: "Low-TTC raw hits",
    unit: "",
    decimals: 0,
    group: "safety",
    description:
      "Simulation ticks (0.1 s each) in which a different-lane pair had a time-to-collision at or below the threshold. One long close approach is counted many times, so this is a raw exposure count, not a number of distinct near-misses.",
    plain:
      "How many moments (tenths of a second) had a close call. One long close call counts many times, so this measures exposure, not separate incidents.",
    postWarmup: true,
  },
  {
    key: "nearMissCount",
    label: "Near-miss events",
    unit: "",
    decimals: 0,
    group: "safety",
    description:
      "Deduplicated near-miss events: a time-to-collision at or below the threshold. A pair of vehicles can only trigger one event per cooldown window (default 5 s), meaning a sustained tailgating situation counts as one encounter, not many.",
    plain:
      "How many separate close calls there were. A pair of vehicles counts once per few seconds, so one long close call is one event.",
    postWarmup: true,
  },
  {
    key: "minPET",
    label: "Minimum PET",
    unit: "s",
    decimals: 2,
    group: "safety",
    description:
      "Smallest gap between one vehicle leaving a signal conflict point and a different vehicle reaching it, after warm-up. A surrogate indicator, not a crash probability. Not measured for roundabouts.",
    plain:
      "The smallest gap between one vehicle leaving a crossing point and another arriving at it. Smaller is tighter. Signals only; a warning sign, not a crash prediction.",
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
      "Successive crossings of a signal conflict point with a gap at or below the PET threshold (a count of crossings, unlike the per-tick TTC count). The default threshold is generous, so many ordinary crossings qualify. Not measured for roundabouts.",
    plain:
      "How many times a vehicle reached a crossing point soon after another had left it. The cut-off is generous, so many ordinary crossings count. Signals only.",
    postWarmup: true,
    appliesTo: ["fixed_time_signal"],
  },
  {
    key: "estimatedFuelLitersTotal",
    label: "Estimated fuel",
    unit: "L",
    decimals: 3,
    group: "safety",
    description:
      "⚠️ ESTIMATE: Simplified kinematic estimation of total fuel consumed since warm-up. Assumes generic petrol passenger cars. Not calibrated to real-world vehicles.",
    plain:
      "A rough estimate of fuel burnt, assuming ordinary petrol cars. Use it to compare runs, not as a real fuel figure.",
    postWarmup: true,
  },
  {
    key: "estimatedCO2KgTotal",
    label: "Estimated CO₂",
    unit: "kg",
    decimals: 3,
    group: "safety",
    description:
      "⚠️ ESTIMATE: Simplified estimation of CO₂ emissions based on estimated fuel consumption (approx 2.31 kg CO₂ / L petrol).",
    plain:
      "A rough estimate of CO₂ from the fuel estimate. Use it to compare runs, not as a real emissions figure.",
    postWarmup: true,
  },

  // ── Capacity & demand ────────────────────────────────────────────────────
  {
    key: "totalVehiclesSpawned",
    label: "Vehicles admitted",
    unit: "veh",
    decimals: 0,
    group: "capacity",
    description:
      "All vehicles that entered the network since the run began, including warm-up. Not the offered demand: while an entry is full its next arrival waits at the edge and no further demand arrives on that approach, and generation also stops at the per-run vehicle limit.",
    postWarmup: false,
  },
  {
    key: "averageEntryWait",
    needsExits: true,
    label: "Wait to enter",
    unit: "s",
    decimals: 1,
    group: "capacity",
    description:
      "Mean time vehicles that exited after warm-up waited outside the network before entering, because their entry was full. Delay and wait time start at entry, so this is the part they cannot see. Near 0 unless the scenario queues arrivals outside the network (traffic.entryQueue).",
    postWarmup: true,
  },
  {
    key: "unfinishedShare",
    label: "Unfinished after warm-up",
    unit: "%",
    decimals: 1,
    scale: 100,
    group: "capacity",
    description:
      "Of the vehicles admitted after warm-up, the share still in the network. Delay, wait, stops and throughput describe only vehicles that exited, so this is the part of the traffic they leave out.",
    plain:
      "Of the vehicles that entered after the warm-up, the share still on the road when the run ended. The other measures only describe vehicles that finished, so this shows who they leave out.",
    postWarmup: true,
    nullText: "N/A",
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
    label: "Served-rate estimate",
    unit: "veh/s",
    decimals: 3,
    group: "capacity",
    description:
      "Backend estimate (reported as criticalSaturationVolume): the observed throughput rate when it is below the configured arrival rate, otherwise the configured arrival rate scaled by the served share of post-warm-up vehicles. It cannot exceed the demand you configured, so it is not a measured capacity.",
    plain:
      "A rough rate of vehicles served per second. It cannot be higher than the traffic you asked for, so it is not the junction's true capacity.",
    postWarmup: true,
  },
  {
    key: "intersectionUtilization",
    label: "Time with traffic moving",
    unit: "%",
    decimals: 1,
    group: "capacity",
    description:
      "Share of post-warm-up ticks with vehicles present in which their mean speed was above the waiting threshold (reported as intersectionUtilization). It is not the share of capacity used, and it sits near 100 % whenever traffic keeps moving.",
    plain:
      "How often traffic was moving rather than standing. It stays near 100% whenever traffic flows, so it does not say how full the junction is.",
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
      "Share of post-warm-up ticks where a red approach had a queue while every green approach was empty. Signal-only (also measured for metered roundabouts, D-W2-6).",
    plain:
      "How often a red approach had a queue while every green approach was empty: green time that served nobody. Signals only (and metered roundabouts).",
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
      "Area from the configured geometry, defined differently per layout: the outer circle of the roundabout (π × outer radius², including the central island) versus the crossing box of the signal ((2 × lanes × lane width)²). Design context, not a like-for-like land-take comparison.",
    plain:
      "The ground area the junction layout covers, worked out differently for each layout. Use it for context, not as a like-for-like land comparison.",
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
    plain: "The least time any driver lost.",
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
    plain: "The most time any driver lost.",
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
    plain:
      "How widely the time lost varies from driver to driver. Larger means less predictable trips.",
    postWarmup: true,
  },
  {
    key: "queueStdDev",
    label: "Queue standard deviation",
    unit: "veh",
    decimals: 2,
    group: "diagnostic",
    description: "Sample standard deviation of the junction-wide total queue.",
    plain: "How much the total queue size swings up and down.",
    postWarmup: true,
  },
  {
    key: "queueStabilityIndex",
    label: "Queue stability index",
    unit: "",
    decimals: 2,
    group: "diagnostic",
    description:
      "Coefficient of variation of the junction-wide total queue (standard deviation ÷ mean): how much the queue fluctuates relative to its size. It does not say whether the queue is growing, and it becomes very large when the average queue is near zero.",
    plain:
      "How much the queue swings compared with its usual size. High means it surges and drains; it does not say whether the queue is growing, and it is very large when queues are near zero.",
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
    plain:
      "How uneven vehicle speeds are at the same moment. Higher means more stop-and-go mixing.",
    postWarmup: true,
  },
  {
    key: "ttcSampleCount",
    label: "TTC observations",
    unit: "",
    decimals: 0,
    group: "diagnostic",
    description:
      "Number of different-lane pair observations (per 0.1 s tick) that had a defined time-to-collision after warm-up. Depends on how many vehicles share space, so it differs by layout and is not comparable as a risk measure.",
    plain:
      "How many vehicle-pair moments the close-call measure looked at. It depends on how crowded the junction is, so it is not a risk score.",
    postWarmup: true,
  },
  {
    key: "petSampleCount",
    label: "PET observations",
    unit: "",
    decimals: 0,
    group: "diagnostic",
    description:
      "Number of successive-crossing PET observations at signal conflict points after warm-up.",
    plain:
      "How many successive crossings the crossing-gap measure looked at. Signals only.",
    postWarmup: true,
    appliesTo: ["fixed_time_signal"],
  },
  {
    key: "masterEfficiencyScore",
    needsExits: true,
    label: "Fixed-weight composite (same layout only)",
    withinGeometryOnly: true,
    unit: "/100",
    decimals: 1,
    group: "diagnostic",
    description:
      "Backend composite (reported as masterEfficiencyScore) of throughput rate, queued time, stops, fairness and idle loss with fixed weights. Only meaningful for comparing runs of the same layout and scenario. It is not a signal-versus-roundabout score: idle loss is signal-only (a conventional roundabout always receives its full points; measured for metered roundabouts) and the throughput term mostly reflects how much traffic arrived.",
    plain:
      "A single score out of 100 from throughput, queued time, stops, fairness and idle green, with fixed weights. Only compare it between runs of the same layout and scenario; it does not rank a signal against a roundabout.",
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
    if (def.withinGeometryOnly) continue; // never across geometries
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
    if (def.withinGeometryOnly) continue; // runs may be of different layouts
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
