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

/**
 * Analysis measures: computed by the backend from per-vehicle trip and
 * trajectory records or from several seeded runs (metrics/trip_metrics.py,
 * metrics/trajectory_metrics.py, uncertainty/comparison.py,
 * study/sensitivity.py), not part of the live collector snapshot. They are
 * described here for the glossary only; the live metric panels and CSV exports
 * read METRICS and never show these.
 */
export interface AnalysisMetricDef {
  /** Field name in the backend's analysis output. */
  key: string;
  label: string;
  unit: string;
  description: string;
  /** Everyday-words version for the glossary. */
  plain: string;
}

export const ANALYSIS_GROUP = {
  id: "analysis",
  title: "Trip, safety and comparison analysis",
  blurb:
    "Measures worked out from per-vehicle records or from several seeded runs. Fuel and CO₂ are model estimates and time-to-collision is a proxy; none of these is a real-world measurement.",
} as const;

export const ANALYSIS_METRICS: AnalysisMetricDef[] = [
  {
    key: "totalDelayVehicleHours",
    label: "Total delay",
    unit: "vehicle-h",
    description:
      "Sum of every trip's delay (travel time minus the time at the driver's own desired speed, never below zero) divided by 3600. It grows with both how long each vehicle is held up and how many vehicles there are.",
    plain:
      "All the lost time of all vehicles added up, in vehicle-hours. Ten vehicles each losing six minutes make one vehicle-hour. It rises with traffic volume as well as with congestion, so compare it only between runs with the same demand.",
  },
  {
    key: "delayRatio",
    label: "Delay ratio",
    unit: "",
    description:
      "Total delay divided by total travel time over the same trips: the share of all time spent travelling that was lost to delay.",
    plain:
      "The fraction of everyone's travel time that was lost. 0.25 means a quarter of all time on the road was delay. It does not depend on how many vehicles there were.",
  },
  {
    key: "planningTimeIndex",
    label: "Planning time index",
    unit: "",
    description:
      "95th-percentile travel time divided by median travel time. Flagged as low-sample below 20 trips.",
    plain:
      "How much extra time a careful traveller should allow. 1.5 means that to be on time 19 days out of 20 you need half as long again as a typical trip. Closer to 1 is more predictable. Shaky with fewer than 20 trips.",
  },
  {
    key: "p95TravelTimeS",
    label: "95th-percentile travel time",
    unit: "s",
    description:
      "Travel time that 95% of trips did not exceed (linear interpolation between the sorted trips). Flagged as low-sample below 20 trips.",
    plain:
      "A slow-day travel time: 19 in 20 trips were faster than this. It shows the bad end of the spread that an average hides. Shaky with fewer than 20 trips.",
  },
  {
    key: "fuelLiters",
    label: "Fuel used (estimate)",
    unit: "L",
    description:
      "ESTIMATE from a simple speed, idle and acceleration fuel model for a generic petrol car, summed over each vehicle's speed samples. No vehicle class, road grade, cold start or electrification. Not a measurement.",
    plain:
      "A rough model estimate of fuel burnt, assuming ordinary petrol cars. Use it to compare runs, not as a real fuel figure.",
  },
  {
    key: "co2Kg",
    label: "CO₂ (estimate)",
    unit: "kg",
    description:
      "ESTIMATE: the fuel estimate multiplied by 2.31 kg CO₂ per litre of petrol. It inherits every limit of the fuel model and is not a measurement.",
    plain:
      "A rough model estimate of CO₂, worked out from the fuel estimate. Use it to compare runs, not as a real emissions figure.",
  },
  {
    key: "idleShare",
    label: "Idle share",
    unit: "",
    description:
      "Time vehicles spent almost stationary (speed under 0.1 m/s) divided by their total time in the run, over the vehicles analysed.",
    plain:
      "The fraction of vehicle time spent standing still. 0.2 means vehicles were stopped a fifth of the time they were in the simulation. Idling is also where the fuel estimate burns fuel for no distance.",
  },
  {
    key: "minTtcS",
    label: "Time-to-collision (proxy)",
    unit: "s",
    description:
      "For a follower behind a leader on the same lane: bumper gap divided by closing speed, defined only while the follower is closing, and zero if already touching. Assumes constant speeds. A surrogate safety proxy, not a crash prediction; the smallest value seen is reported.",
    plain:
      "How many seconds until a following vehicle would hit the one ahead if neither changed speed. Smaller is closer. It is a warning sign used to compare runs, not a prediction that a crash will happen.",
  },
  {
    key: "timeExposedTtcS",
    label: "Time exposed to low TTC",
    unit: "s",
    description:
      "Seconds for which time-to-collision was below the threshold (default 1.5 s), counted across all pairs and samples. A proxy measure of exposure, not of crashes.",
    plain:
      "How long, in total, vehicles spent in close-following situations. It measures how much time was spent near the edge, not how many separate close calls there were.",
  },
  {
    key: "timeIntegratedTtcS",
    label: "Time-integrated TTC",
    unit: "s²",
    description:
      "Sum, over samples where time-to-collision was below the threshold, of (threshold minus time-to-collision) times the sample length. Weights closer approaches more heavily than time-exposed does. A proxy measure, not a crash prediction.",
    plain:
      "Like time exposed to low TTC, but a very close approach counts for more than a mild one. Larger means more time spent closer to a collision. A proxy for comparing runs.",
  },
  {
    key: "conflictEvents",
    label: "Conflict events",
    unit: "",
    description:
      "Separate episodes of low time-to-collision: a run of consecutive below-threshold samples for one vehicle pair counts once. A proxy count, not crashes.",
    plain:
      "How many separate close calls there were. One long close call counts once, unlike the raw count of moments.",
  },
  {
    key: "confidenceInterval",
    label: "Confidence interval",
    unit: "",
    description:
      "Range, in the metric's own units, that would contain the true average difference in the stated share of repeats (default 95%) if the study were run many times. Computed either by a Student t formula or by percentile bootstrap, and the method is always named.",
    plain:
      "A range for the true difference rather than a single number. A narrow range means the result is well pinned down; a wide one means more runs are needed. If it includes zero, the data cannot tell the two apart.",
  },
  {
    key: "pValue",
    label: "p-value",
    unit: "",
    description:
      "Two-sided probability of seeing a difference at least this large if the two strategies were really the same, from a paired t test or a sign-flip randomisation test. It says nothing about whether the difference matters in practice.",
    plain:
      "How surprising the result would be if there were no real difference. Small values (below 0.05, say) mean it is unlikely to be chance. It does not say the difference is big or useful: read it with the confidence interval.",
  },
  {
    key: "pairedComparison",
    label: "Paired comparison",
    unit: "",
    description:
      "Strategies A and B are run on the same seeds, and the analysis uses the per-seed difference a minus b. Pairing removes the seed-to-seed variation both strategies share. Both sides must have the same seeds in the same order.",
    plain:
      "Comparing two strategies on identical random traffic, seed by seed, and looking at the differences. Because both face the same traffic, the difference is much less muddied by luck.",
  },
  {
    key: "sensitivityIndex",
    label: "Sensitivity (first-order / total index)",
    unit: "",
    description:
      "Variance-based Sobol-lite indices for inputs varied over their ranges. First-order S1 is the share of output variance explained by an input alone; total ST adds its interactions with other inputs. Estimates are noisy with small samples and may fall slightly outside 0 to 1; they are reported unclipped and ranked by ST, so read ranks as indicative.",
    plain:
      "Which input changes the result most. The first-order index is the share of the result's variation one input explains on its own; the total index also counts its effects in combination with other inputs. With few samples the figures are rough, so use them for ranking.",
  },
  {
    key: "throughputVph",
    label: "Network throughput",
    unit: "veh/h",
    description:
      "Vehicles that finished their trip, scaled to one hour, over the whole network (network-metrics simulate).",
    plain:
      "How many vehicles got all the way through the network, per hour. Vehicles still travelling at the end of the run are not counted.",
  },
  {
    key: "meanVehiclesInNetwork",
    label: "Vehicles in the network",
    unit: "vehicles",
    description:
      "Time-averaged number of vehicles on all links of the network during the run.",
    plain:
      "How many vehicles were on the roads at a typical moment of the run. More vehicles means a busier network.",
  },
  {
    key: "meanQueuedVehicles",
    label: "Queued vehicles",
    unit: "vehicles",
    description:
      "Time-averaged number of vehicles waiting at the front of a link, summed over all links.",
    plain:
      "How many vehicles were waiting in queues at a typical moment, added up over every road in the network.",
  },
  {
    key: "blockedLinkSeconds",
    label: "Blocked link time",
    unit: "link-s",
    description:
      "Total time, summed over links, during which a link had a vehicle ready to leave but the next link was full.",
    plain:
      "Time that roads could not let vehicles through because the road ahead was full. Two roads blocked for ten seconds each count as twenty link-seconds.",
  },
  {
    key: "meanOccupancyRatio",
    label: "Link fullness",
    unit: "fraction",
    description:
      "Mean number of vehicles on a link divided by the number it can store (length times lanes). 0 is empty, 1 is full.",
    plain:
      "How full a road was: 0 is empty and 1 is packed. The congestion screens colour roads and cells by this.",
  },
  {
    key: "densityVehPerKmLane",
    label: "Density",
    unit: "veh/km/lane",
    description:
      "Vehicles per kilometre of lane, weighted by lane length over the network, one value per time bucket.",
    plain:
      "How closely packed the vehicles were, per kilometre of lane. The sideways axis of the fundamental diagram.",
  },
  {
    key: "flowVehPerHourLane",
    label: "Flow per lane",
    unit: "veh/h/lane",
    description:
      "Vehicles passing per hour per lane, weighted by lane length over the network, one value per time bucket.",
    plain:
      "How many vehicles moved through each lane per hour. The upward axis of the fundamental diagram; its highest dot shows the busiest the network got.",
  },
  {
    key: "congestionOnsetSeconds",
    label: "Congestion onset",
    unit: "s",
    description:
      "Time at which a link first stayed at or above the congestion threshold of fullness for the minimum hold time.",
    plain:
      "The moment a road first became congested, counted from the start of the run. Roads are listed in the order they congested.",
  },
  {
    key: "spillbackSeconds",
    label: "Spillback time",
    unit: "s",
    description:
      "Duration of a run in which a link head vehicle was ready to leave but the next link was full.",
    plain:
      "How long a queue was backed up into the road behind it because the road ahead had no room.",
  },
  {
    key: "geh",
    label: "GEH",
    unit: "",
    description:
      "GEH = sqrt(2 (M - C)^2 / (M + C)) for modelled hourly flow M and counted hourly flow C on a link. Below 5 is the usual acceptable fit.",
    plain:
      "A traffic-engineering score for how well the modelled flow on a road matches the count. Below 5 is generally accepted as a good match; larger is a miss.",
  },
  {
    key: "rmseVph",
    label: "Flow error (RMSE)",
    unit: "veh/h",
    description:
      "Root mean square of simulated minus counted hourly flow over the counted links.",
    plain:
      "The typical size of the miss between modelled and counted flow, in vehicles per hour. Big misses count extra.",
  },
  {
    key: "mapePercent",
    label: "Flow error (MAPE)",
    unit: "%",
    description:
      "Mean of absolute percentage errors over links whose counted flow is at least the minimum; links with tiny counts are skipped and reported.",
    plain:
      "How far off the model is on average, as a percentage of the counted flow. Roads with very small counts are left out because a tiny denominator would give a meaningless percentage.",
  },
  {
    key: "twinMae",
    label: "Twin error (MAE)",
    unit: "vehicles / window",
    description:
      "Mean absolute difference between predicted and observed vehicle counts per window (digital twin comparison).",
    plain:
      "On average, how many vehicles per time window the twin predicted wrongly, whether too many or too few.",
  },
  {
    key: "twinMape",
    label: "Twin error (MAPE)",
    unit: "%",
    description:
      "Mean absolute error as a percentage of the observed count, over windows where the observed count is above zero.",
    plain:
      "How wrong the twin was as a share of what really happened. Windows where nothing was observed are skipped.",
  },
  {
    key: "twinBias",
    label: "Twin bias",
    unit: "vehicles / window",
    description:
      "Mean of predicted minus observed count per window. Negative means the twin predicts too few vehicles.",
    plain:
      "Whether the twin leans one way. A negative number means it usually predicts fewer vehicles than were seen; a positive number means more.",
  },
  {
    key: "mean_wait_s",
    label: "Mean wait per entered vehicle (network RL)",
    unit: "s",
    description:
      "Stopped vehicle-seconds in the network divided by the number of vehicles that entered it, from the network RL evaluation.",
    plain:
      "Total time vehicles spent stopped, divided by the vehicles that entered the network. It is not the delay of a finished trip, so do not compare it with delay figures from other screens.",
  },
  {
    key: "loadTestP95Ms",
    label: "Response time, 95th percentile",
    unit: "ms",
    description:
      "The response time that 95% of load-test requests beat (k6 http_req_duration p(95)).",
    plain:
      "How long the slowest 5% of requests took at least. If this is 400 ms, nineteen in twenty requests were faster than that.",
  },
  {
    key: "loadTestErrorRate",
    label: "Load-test error rate",
    unit: "fraction",
    description:
      "Share of load-test requests that failed (k6 http_req_failed rate).",
    plain:
      "The fraction of requests that failed during the load test. 0.01 means one in a hundred.",
  },
  {
    key: "resilienceScore",
    label: "Resilience score",
    unit: "/1",
    description:
      "A weighted mean of four parts (recovery 0.35, throughput 0.25, peak delay 0.20, area under the delay curve 0.20), each between 0 and 1, from one signal strategy run with and without a disruption on the same seed. Mean over seeds with a bootstrap 95% interval.",
    plain:
      "A single number from 0 to 1 for how well a signal strategy copes with a disruption; higher is better. It compares strategies inside the model under one scenario. It is not a prediction, and the weights are modelling choices.",
  },
  {
    key: "recoveryTimeSeconds",
    label: "Recovery time",
    unit: "s",
    description:
      "Seconds from the end of the last disruption window until the mean accrued delay stays within a tolerance of the undisturbed run for several buckets in a row. Missing when it never does before the run ends.",
    plain:
      "How long the network took to get back to normal after the disruption ended. If it never got back before the run finished, the figure is shown as not recovered, not as zero.",
  },
  {
    key: "peakExcessDelaySeconds",
    label: "Peak extra delay",
    unit: "s",
    description:
      "Largest gap, over the buckets of the run, between the mean accrued delay with the disruption and without it, never below zero.",
    plain:
      "The worst moment: how many more seconds of delay the average vehicle in the network had, against the same run without the disruption.",
  },
  {
    key: "throughputLoss",
    label: "Throughput loss",
    unit: "fraction",
    description:
      "Vehicles completed without the disruption minus vehicles completed with it, divided by the former, never below zero.",
    plain:
      "The share of finished trips lost to the disruption. 0.1 means one trip in ten that would have finished did not. A demand surge can make it zero.",
  },
  {
    key: "areaUnderDelayCurve",
    label: "Area under the delay curve",
    unit: "s squared",
    description:
      "Sum over buckets of the extra mean accrued delay against the undisturbed run, times the bucket length.",
    plain:
      "The whole cost of a disruption in one number: how big the extra delay was and how long it lasted. Use it to compare strategies on the same scenario, not as seconds of delay.",
  },
  {
    key: "emergencyTravelTime",
    label: "Emergency vehicle travel time",
    unit: "s",
    description:
      "Mean time an emergency vehicle took from entering to leaving the junction, per seed, compared with and without signal pre-emption over paired seeds.",
    plain:
      "How long the ambulance or fire truck took to cross. The comparison pairs each seed with and without pre-emption, so both arms saw the same traffic.",
  },
  {
    key: "collateralDelay",
    label: "Collateral delay",
    unit: "s per vehicle",
    description:
      "Mean time lost by non-emergency vehicles, per seed, compared with and without pre-emption over paired seeds.",
    plain:
      "What pre-emption costs everyone else: the extra seconds the other vehicles lost on average. A small or unreliable difference means the cost was hard to see.",
  },
  {
    key: "personDelayPerPerson",
    label: "Person delay",
    unit: "s per person",
    description:
      "Delay of every vehicle weighted by its assumed occupancy (cars and buses), divided by the people carried.",
    plain:
      "Delay counted per person, not per vehicle, so a full bus counts for its passengers. It shows whether transit priority helps more people than it holds up.",
  },
  {
    key: "busScheduleLateness",
    label: "Bus lateness",
    unit: "s",
    description:
      "Mean time a bus reached the stop line after its timetable time, which is free-flow running time plus dwell plus padding.",
    plain:
      "How far behind its timetable a bus was when it reached the signal. Lower is better; with transit priority switched on it should shrink.",
  },
  {
    key: "messageDeliveryRatio",
    label: "Message delivery ratio",
    unit: "fraction",
    description:
      "Messages delivered divided by messages attempted over all connected vehicles, after the channel's loss and range rules. Missing when no message was sent.",
    plain:
      "The share of signal-timing and hazard messages that actually arrived. 0.9 means nine in ten got through. It falls as the channel loses messages.",
  },
  {
    key: "delayBenefitSeconds",
    label: "Delay benefit of connected vehicles",
    unit: "s per vehicle",
    description:
      "Baseline mean delay minus cooperative mean delay per vehicle, for one latency and loss setting. Positive is better.",
    plain:
      "How many seconds each vehicle saves when it receives signal timings and warnings. The latency by loss grid shows how late or lost messages shrink that saving.",
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
