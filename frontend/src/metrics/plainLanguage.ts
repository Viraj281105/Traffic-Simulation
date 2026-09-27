/**
 * Plain-language reading of a signal-vs-roundabout comparison.
 *
 * catalog.ts describes every metric the way a specialist needs it; this
 * module is its everyday counterpart. It answers the questions a
 * non-specialist brings to a comparison — how much time do drivers lose, how much
 * traffic gets through, how long do queues get, is every direction treated
 * alike, why do the two differ, how sure can I be — using only values the
 * backend reported (read through catalog.metricState, so warm-up, "no
 * vehicles yet" and "not measured here" are honoured exactly as in the
 * technical tables).
 *
 * Nothing here computes a new metric or ranks the controls. The only
 * judgement calls are presentation thresholds, all declared below and shown
 * to the user wherever a label depends on them:
 *   - SIMILARITY: when a difference is small enough to call "about the same";
 *   - LOS_THRESHOLDS: the Highway Capacity Manual's delay bands, used as an
 *     indicative "is that a lot of time lost?" reference;
 *   - FAIRNESS_BANDS: words for Jain's fairness index;
 *   - EFFECT_SIZE_BANDS: Cohen's conventional small/medium/large bands.
 */
import {
  METRICS,
  metricState,
  type MetricContext,
  type MetricDef,
} from "./catalog";

export type Side = "signal" | "roundabout";

export const SIDE_NAME: Record<Side, string> = {
  signal: "traffic signal",
  roundabout: "roundabout",
};

export const SIDE_TITLE: Record<Side, string> = {
  signal: "Traffic signal",
  roundabout: "Roundabout",
};

// ── Reading one metric ─────────────────────────────────────────────────────

const DEF_BY_KEY = new Map(METRICS.map((d) => [d.key, d]));

export function metricDef(key: MetricDef["key"]): MetricDef {
  const def = DEF_BY_KEY.get(key);
  if (!def) throw new Error(`Unknown metric ${key}`);
  return def;
}

/** The displayed value of a metric (after the catalog's unit scaling), or
 *  null whenever the catalog would show a dash, N/A or a warm-up note. */
export function metricValue(
  key: MetricDef["key"],
  ctx: MetricContext,
): number | null {
  const state = metricState(metricDef(key), ctx);
  return state.kind === "value" ? state.value : null;
}

/** The handful of numbers the plain-language layer is built on, per control. */
export interface SideSummary {
  /** Mean extra travel time per driver versus driving through an empty
   *  junction at the driver's own speed, s. Includes slowing the layout itself
   *  forces; it is NOT the same as time spent queued. */
  delay: number | null;
  /** Mean time per driver spent nearly stopped (below 0.5 m/s), s. */
  queuedTime: number | null;
  /** Delay not exceeded by 95% of drivers, s. */
  p95Delay: number | null;
  /** Mean stops per driver. */
  stops: number | null;
  /** Vehicles that got through after the warm-up. */
  served: number | null;
  /** Vehicles still on the approaches or in the junction right now. */
  inNetwork: number | null;
  /** Time-averaged queue on one approach, vehicles. */
  avgQueue: number | null;
  /** Longest queue seen on any approach, vehicles. */
  maxQueue: number | null;
  /** Measured time with more than 5 vehicles queued in total, s. */
  congestedSeconds: number | null;
  /** Jain's index over the four approaches' mean waits (0.25–1). */
  fairness: number | null;
  /** Vehicle overlaps since the run began (a model-integrity signal). */
  collisions: number | null;
  /** Share (%) of measured time a signal wasted green on an empty road
   *  while a red approach queued. Signal only. */
  idleGreenPct: number | null;
}

export function sideSummary(ctx: MetricContext): SideSummary {
  const v = (key: MetricDef["key"]) => metricValue(key, ctx);
  return {
    delay: v("averageDelay"),
    queuedTime: v("averageWaitTime"),
    p95Delay: v("p95Delay"),
    stops: v("averageStopsPerVehicle"),
    served: v("throughput"),
    inNetwork: v("activeVehicleCount"),
    avgQueue: v("averageQueueLength"),
    maxQueue: v("maxQueueLength"),
    congestedSeconds: v("congestionRecoveryTime"),
    fairness: v("directionalFairnessIndex"),
    collisions: v("collisionCount"),
    idleGreenPct: v("idleOpportunityLoss"),
  };
}

/** True once both controls have results worth reading (after warm-up, with
 *  at least one vehicle through on each side). */
export function hasResults(s: SideSummary, r: SideSummary): boolean {
  return s.delay !== null && r.delay !== null;
}

// ── Comparing the two controls ─────────────────────────────────────────────

export interface Similarity {
  /** Differences at or below this many units read as "about the same". */
  abs: number;
  /** …or at or below this share of the larger value. */
  rel: number;
}

/** When two values are close enough to call "about the same". A difference
 *  counts as a difference only if it exceeds BOTH the absolute and the
 *  relative tolerance, so tiny values do not produce large percentages and
 *  large values do not hide real gaps. Presentation thresholds only. */
export const SIMILARITY = {
  delay: { abs: 1, rel: 0.05 },
  vehicles: { abs: 3, rel: 0.02 },
  queue: { abs: 0.5, rel: 0.1 },
  stops: { abs: 0.1, rel: 0.1 },
  fairness: { abs: 0.03, rel: 0 },
} satisfies Record<string, Similarity>;

export interface Comparison {
  signal: number;
  roundabout: number;
  /** Absolute gap between the two. */
  gap: number;
  /** Gap as a share of the larger value (0–1), or null if both are 0. */
  share: number | null;
  similar: boolean;
  /** Which control has the smaller value (null when similar). */
  lower: Side | null;
  higher: Side | null;
}

export function compare(
  signal: number | null,
  roundabout: number | null,
  tol: Similarity,
): Comparison | null {
  if (signal === null || roundabout === null) return null;
  const gap = Math.abs(roundabout - signal);
  const larger = Math.max(Math.abs(signal), Math.abs(roundabout));
  const share = larger > 0 ? gap / larger : null;
  // A hair of slack so a gap exactly at the tolerance is not tipped over it
  // by floating-point rounding.
  const similar =
    gap <= tol.abs + 1e-9 || (share !== null && share <= tol.rel + 1e-9);
  const lower: Side | null = similar
    ? null
    : signal < roundabout
      ? "signal"
      : "roundabout";
  return {
    signal,
    roundabout,
    gap,
    share,
    similar,
    lower,
    higher:
      lower === null ? null : lower === "signal" ? "roundabout" : "signal",
  };
}

// ── Formatting helpers ─────────────────────────────────────────────────────

export function seconds(value: number, decimals = 0): string {
  return `${value.toFixed(decimals)} s`;
}

/** 135 → "2 min 15 s", 45 → "45 s". */
export function duration(totalSeconds: number): string {
  const s = Math.max(0, Math.round(totalSeconds));
  const m = Math.floor(s / 60);
  const rest = s % 60;
  if (m === 0) return `${String(rest)} s`;
  if (rest === 0) return `${String(m)} min`;
  return `${String(m)} min ${String(rest)} s`;
}

/** 135 → "2:15" (a clock reading for progress displays). */
export function clock(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds));
  return `${String(Math.floor(s / 60))}:${String(s % 60).padStart(2, "0")}`;
}

export function count(value: number): string {
  return Math.round(value).toLocaleString();
}

function plural(n: number, one: string, many: string): string {
  return Math.round(n) === 1 ? one : many;
}

// ── "Is that a lot of time lost?" — indicative level of service ────────────

export type LosGrade = "A" | "B" | "C" | "D" | "E" | "F";

/** Upper bounds (s of average control delay) of grades A–E in the Highway
 *  Capacity Manual (6th ed.): signalised intersections use the first set;
 *  roundabouts use the stricter unsignalised set, because drivers expect
 *  less time lost where there is no red light. Above the last bound: F.
 *
 *  This is the one definition of the bands for the whole app (the Research
 *  Lab's sweep dashboard imports it). The grade is an indicative reading of
 *  simulated delay, which also counts geometric slow-down; it is not an HCM
 *  level-of-service analysis. */
export const LOS_THRESHOLDS: Record<Side, number[]> = {
  signal: [10, 20, 35, 55, 80],
  roundabout: [10, 15, 25, 35, 50],
};

export const LOS_WORDS: Record<LosGrade, string> = {
  A: "Very little time lost",
  B: "Little time lost",
  C: "A moderate amount of time lost",
  D: "A lot of time lost",
  E: "A great deal of time lost",
  F: "An excessive amount of time lost",
};

const GRADES: LosGrade[] = ["A", "B", "C", "D", "E", "F"];

export function levelOfService(delay: number, side: Side): LosGrade {
  const bounds = LOS_THRESHOLDS[side];
  const index = bounds.findIndex((b) => delay <= b);
  return GRADES[index === -1 ? 5 : index];
}

// ── "Is every direction treated alike?" ────────────────────────────────────

/** Words for Jain's fairness index over the approaches' mean waits
 *  (1.00 = every direction waits the same; 0.25 = one direction bears all
 *  the waiting). Lower bounds, checked in order. Presentation bands only. */
export const FAIRNESS_BANDS: { min: number; label: string; meaning: string }[] =
  [
    {
      min: 0.95,
      label: "Very even",
      meaning: "every direction waits about the same",
    },
    {
      min: 0.85,
      label: "Mostly even",
      meaning: "some directions wait a little longer than others",
    },
    {
      min: 0.7,
      label: "Uneven",
      meaning: "some directions wait noticeably longer",
    },
    {
      min: 0,
      label: "Very uneven",
      meaning: "one or two directions carry most of the waiting",
    },
  ];

export function fairnessBand(index: number) {
  return (
    FAIRNESS_BANDS.find((b) => index >= b.min) ??
    FAIRNESS_BANDS[FAIRNESS_BANDS.length - 1]
  );
}

// ── The one-paragraph answer ───────────────────────────────────────────────

/** Short sentences answering "what happened?", one per everyday question,
 *  each stating both values so nothing is hidden behind a summary word. */
export function headlineFindings(s: SideSummary, r: SideSummary): string[] {
  const lines: string[] = [];

  const delay = compare(s.delay, r.delay, SIMILARITY.delay);
  if (delay) {
    const pair = `${seconds(delay.signal)} at the signal, ${seconds(delay.roundabout)} at the roundabout`;
    lines.push(
      delay.similar || !delay.lower
        ? `Drivers lost about the same time at both (${pair}).`
        : `Drivers lost less time at the ${SIDE_NAME[delay.lower]}: ${seconds(delay.gap)} less per driver on average (${pair}).`,
    );
  }

  const served = compare(s.served, r.served, SIMILARITY.vehicles);
  if (served) {
    const pair = `${count(served.signal)} vs ${count(served.roundabout)}`;
    lines.push(
      served.similar || !served.higher
        ? `Both got about the same number of vehicles through (${pair}).`
        : `The ${SIDE_NAME[served.higher]} got ${count(served.gap)} more ${plural(served.gap, "vehicle", "vehicles")} through from the same arrivals (${pair}).`,
    );
  }

  const queue = compare(s.maxQueue, r.maxQueue, SIMILARITY.queue);
  if (queue) {
    lines.push(
      queue.similar
        ? `The longest queues were about the same (${count(queue.signal)} and ${count(queue.roundabout)} vehicles).`
        : `The longest queue reached ${count(queue.signal)} ${plural(queue.signal, "vehicle", "vehicles")} at the signal and ${count(queue.roundabout)} at the roundabout.`,
    );
  }

  return lines;
}

// ── "Why did that happen?" ─────────────────────────────────────────────────

export interface ScenarioFacts {
  lanes: number;
  arrivalRate: number;
  greenNs: number;
  greenEw: number;
  cycleSeconds: number;
  criticalGap: number;
}

export interface Explanation {
  title: string;
  body: string;
}

/** How each control works, then what this run's own numbers show about it.
 *  Every data-driven line quotes the measurement it rests on; none claims a
 *  control is better in general. */
export function explanations(
  s: SideSummary,
  r: SideSummary,
  facts: ScenarioFacts,
): Explanation[] {
  const out: Explanation[] = [];
  const greens =
    facts.greenNs === facts.greenEw
      ? `${seconds(facts.greenNs)} of green`
      : `${seconds(facts.greenNs)} (north–south) or ${seconds(facts.greenEw)} (east–west) of green`;

  out.push({
    title: "Time lost is not the same as waiting",
    body: "“Time lost” compares each journey with driving through an empty junction at the driver’s own speed. It includes queuing, but also any slowing the layout itself forces, such as easing into a roundabout entry, so a junction can show time lost even when nobody queues. “Time spent nearly stopped” counts only the standing time.",
  });

  const lostVsQueued = compare(s.delay, r.delay, SIMILARITY.delay);
  const queuedCmp = compare(s.queuedTime, r.queuedTime, SIMILARITY.delay);
  if (
    lostVsQueued &&
    queuedCmp &&
    lostVsQueued.lower &&
    queuedCmp.lower &&
    lostVsQueued.lower !== queuedCmp.lower
  ) {
    out.push({
      title: "Time lost and time queued point different ways",
      body: `Drivers lost less time at the ${SIDE_NAME[lostVsQueued.lower]} (${seconds(lostVsQueued.signal)} at the signal, ${seconds(lostVsQueued.roundabout)} at the roundabout) but spent less time nearly stopped at the ${SIDE_NAME[queuedCmp.lower]} (${seconds(queuedCmp.signal, 1)} vs ${seconds(queuedCmp.roundabout, 1)}). Both are measured; they answer different questions, so neither is the “real” wait.`,
    });
  }

  out.push({
    title: "How the signal decides who goes",
    body: `The signal works on a fixed timetable: each direction gets ${greens}, then waits while the other direction goes — one full cycle takes ${seconds(facts.cycleSeconds)}. A driver who arrives on red waits for the next green even if no one else is using the junction.`,
  });
  out.push({
    title: "How the roundabout decides who goes",
    body: `Nobody gets a red light at the roundabout. Drivers give way to traffic already circling and go when they see a gap of at least ${seconds(facts.criticalGap, 1)}. When traffic is light, most drivers barely stop; as it gets busier, gaps become rarer and queues build at the entries.`,
  });

  if (s.idleGreenPct !== null && s.idleGreenPct >= 5) {
    out.push({
      title: "The signal's fixed timing cost time",
      body: `For ${String(Math.round(s.idleGreenPct))}% of the measured time the signal showed green to an empty road while vehicles queued on red. That waiting came from the timetable, not from other traffic.`,
    });
  }

  const stops = compare(s.stops, r.stops, SIMILARITY.stops);
  if (stops) {
    out.push({
      title: "Stop-and-go",
      body: stops.similar
        ? `Drivers came to a stop about as often at both (${stops.signal.toFixed(1)} vs ${stops.roundabout.toFixed(1)} stops per driver).`
        : `Drivers stopped ${stops.signal.toFixed(1)} times on average at the signal and ${stops.roundabout.toFixed(1)} times at the roundabout. Every stop adds time to slow down and pull away again.`,
    });
  }

  const backlog = compare(s.inNetwork, r.inNetwork, SIMILARITY.vehicles);
  if (
    backlog &&
    !backlog.similar &&
    backlog.higher &&
    backlog.gap >= 5 &&
    (backlog.share ?? 0) >= 0.2
  ) {
    out.push({
      title: "One side was falling behind",
      body: `When the clock stopped, ${count(backlog.higher === "signal" ? backlog.signal : backlog.roundabout)} vehicles were still waiting or moving through the ${SIDE_NAME[backlog.higher]}, against ${count(backlog.higher === "signal" ? backlog.roundabout : backlog.signal)} at the ${SIDE_NAME[backlog.higher === "signal" ? "roundabout" : "signal"]}. Traffic was arriving faster than the ${SIDE_NAME[backlog.higher]} could clear it.`,
    });
  }

  out.push({
    title: "Traffic level matters most",
    body: `This run had about ${count(facts.arrivalRate * 3600)} vehicles arriving per hour. How the two controls compare can change a lot as traffic gets lighter or heavier, so try the same junction at another traffic level before drawing conclusions.`,
  });
  return out;
}

// ── "Can I trust this?" ────────────────────────────────────────────────────

export interface TrustNote {
  tone: "info" | "caution";
  text: string;
}

export interface TrustFacts {
  seed: number;
  lanes: number;
  warmupSeconds: number | null;
  /** Simulated time measured after the warm-up; null when unknown. */
  measuredSeconds: number | null;
  /** The run reached its configured duration. */
  complete: boolean;
  collisions: number;
  lowReliabilitySample: boolean;
  /** Vehicle generation hit its per-run limit: later demand was not offered. */
  vehicleLimitReached?: boolean;
  /** The limit, when known. */
  vehicleLimit?: number | null;
}

/** What a reader needs to weigh one run's numbers. Always includes what makes
 *  the comparison fair and what the model does not cover; adds cautions only
 *  when this run's own conditions call for them. */
export function trustNotes(f: TrustFacts): TrustNote[] {
  const notes: TrustNote[] = [
    {
      tone: "info",
      text: `Fair test: both controls got exactly the same vehicles, arriving at the same moments (traffic pattern #${String(f.seed)}). Only the way the junction is controlled changed.`,
    },
  ];
  if (f.warmupSeconds !== null) {
    notes.push({
      tone: "info",
      text: `The first ${duration(f.warmupSeconds)} are a warm-up while traffic builds up from an empty road; they are not counted.`,
    });
  }
  if (!f.complete) {
    notes.push({
      tone: "caution",
      text:
        f.measuredSeconds !== null
          ? `These are results so far: only ${duration(f.measuredSeconds)} of traffic has been measured. Numbers can still move.`
          : "These are results so far, from a run that had not finished. Numbers can still move.",
    });
  } else if (f.measuredSeconds !== null && f.measuredSeconds < 120) {
    notes.push({
      tone: "caution",
      text: `Only ${duration(f.measuredSeconds)} of traffic was measured. Short runs swing a lot; a longer run gives steadier numbers.`,
    });
  }
  if (f.lanes > 1) {
    notes.push({
      tone: "caution",
      text: `With ${String(f.lanes)} lanes per approach both junctions model every lane, but drivers leaving the roundabout from an inner ring cross the outer ring without lane markings, and the model is not collision-free across all demand at this setting. Read these results as indicative. One lane per approach is the calibrated comparison.`,
    });
  }
  if (f.collisions > 0) {
    notes.push({
      tone: "caution",
      text: `The model recorded ${String(f.collisions)} ${plural(f.collisions, "vehicle overlap", "vehicle overlaps")}. Real vehicles cannot pass through each other, so this is a limit of the model in this scenario, not a prediction of crashes.`,
    });
  }
  if (f.vehicleLimitReached) {
    notes.push({
      tone: "caution",
      text: `Vehicle generation reached its limit${f.vehicleLimit ? ` of ${String(f.vehicleLimit)} vehicles` : ""}, so traffic stopped arriving before the run ended. Both controls received the same shortened demand, but the results describe less traffic than the scenario asks for. Shorten the run or lower the traffic level to compare the full demand.`,
    });
  }
  if (f.lowReliabilitySample) {
    notes.push({
      tone: "caution",
      text: "Fewer than 20 vehicles got through on at least one side, so the spread of journey times rests on very few drivers.",
    });
  }
  notes.push({
    tone: "info",
    text: "How much traffic each of the four roads carries is set by the traffic pattern too, so some roads are busier than others; it is the same for both controls. Per-road figures such as fairness and the longest queue reflect that.",
  });
  notes.push({
    tone: "info",
    text: "One run is one traffic pattern. A different pattern of arrivals could shift the numbers — the reliability check below repeats the comparison to find out whether the difference holds.",
  });
  notes.push({
    tone: "info",
    text: "Not modelled: pedestrians, cyclists, buses and lorries, or crash risk. Real signals and roundabouts also differ in safety, land and cost, which this comparison does not measure.",
  });
  return notes;
}

// ── Reliability check (repeating the scenario over new traffic patterns) ───

export interface StatSummary {
  mean: number;
  std: number;
  min: number;
  max: number;
  ci95: number;
}

export interface GroupComparison {
  pValue: number | null;
  significant: boolean;
  cohensD: number;
  degreesOfFreedom?: number;
}

export type StudyMetric = "delay" | "throughput" | "queue";

export interface ReliabilityResult {
  numSeeds: number;
  seeds?: number[];
  duration: number;
  /** Exploratory when the scenario uses more than one lane per approach. */
  calibration?: { calibrated: boolean; note: string };
  vehicleLimitReachedSeeds?: number[];
  signal: Record<StudyMetric, StatSummary>;
  roundabout: Record<StudyMetric, StatSummary>;
  comparison: Record<StudyMetric, GroupComparison>;
  seedRuns: {
    seed: number;
    signal: Record<StudyMetric, number>;
    roundabout: Record<StudyMetric, number>;
  }[];
}

/** Cohen's conventional bands for |d|: below 0.2 negligible, then small,
 *  medium, and large from 0.8. */
export const EFFECT_SIZE_BANDS = [
  { min: 0.8, label: "large" },
  { min: 0.5, label: "medium" },
  { min: 0.2, label: "small" },
  { min: 0, label: "negligible" },
] as const;

export function effectSizeWord(d: number): string {
  const abs = Math.abs(d);
  return (EFFECT_SIZE_BANDS.find((b) => abs >= b.min) ?? EFFECT_SIZE_BANDS[3])
    .label;
}

export type ReliabilityVerdict = "consistent" | "not-consistent" | "no-gap";

export interface ReliabilityReading {
  metric: StudyMetric;
  verdict: ReliabilityVerdict;
  headline: string;
  detail: string;
  /** Patterns where each side had the lower value (ties counted apart). */
  tally: { signal: number; roundabout: number; tie: number };
}

const STUDY_METRIC_WORDS: Record<
  StudyMetric,
  { noun: string; unit: (v: number) => string }
> = {
  delay: {
    noun: "time lost per driver",
    unit: (v) => seconds(v, 1),
  },
  throughput: {
    noun: "vehicles through",
    unit: (v) => `${v.toFixed(0)} vehicles`,
  },
  queue: {
    noun: "average queue",
    unit: (v) => `${v.toFixed(1)} vehicles`,
  },
};

const STUDY_SIMILARITY: Record<StudyMetric, Similarity> = {
  delay: SIMILARITY.delay,
  throughput: SIMILARITY.vehicles,
  queue: SIMILARITY.queue,
};

/** Reads the repeated-comparison study for one metric. "Consistent" means
 *  the backend's Welch t-test found the difference significant at the 5%
 *  level; the size word compares the gap with pattern-to-pattern variation
 *  (Cohen's d). No reading claims more than that test supports. */
export function readReliability(
  result: ReliabilityResult,
  metric: StudyMetric,
): ReliabilityReading {
  const words = STUDY_METRIC_WORDS[metric];
  const s = result.signal[metric];
  const r = result.roundabout[metric];
  const cmp = result.comparison[metric];
  const tally = { signal: 0, roundabout: 0, tie: 0 };
  for (const run of result.seedRuns) {
    const a = run.signal[metric];
    const b = run.roundabout[metric];
    // Same "about the same" rule as everywhere else, per metric.
    const c = compare(a, b, STUDY_SIMILARITY[metric]);
    if (c?.lower === "signal") tally.signal += 1;
    else if (c?.lower === "roundabout") tally.roundabout += 1;
    else tally.tie += 1;
  }
  const n = result.numSeeds;
  const gap = compare(s.mean, r.mean, STUDY_SIMILARITY[metric]);
  const lowerSide: Side = s.mean <= r.mean ? "signal" : "roundabout";
  const lowerCount = tally[lowerSide];
  const means = `${words.unit(s.mean)} at the signal, ${words.unit(r.mean)} at the roundabout on average`;
  const size = effectSizeWord(cmp.cohensD);
  const pText =
    cmp.pValue === null
      ? "no test possible"
      : cmp.pValue < 0.001
        ? "p < 0.001"
        : `p = ${cmp.pValue.toFixed(3)}`;

  if (cmp.significant) {
    const higherSide: Side = lowerSide === "signal" ? "roundabout" : "signal";
    const direction =
      metric === "throughput"
        ? `More vehicles got through the ${SIDE_NAME[higherSide]}`
        : metric === "delay"
          ? `Drivers lost less time at the ${SIDE_NAME[lowerSide]}`
          : `Queues were shorter at the ${SIDE_NAME[lowerSide]}`;
    return {
      metric,
      verdict: "consistent",
      headline: `${direction} — and the difference held up across ${String(n)} traffic patterns.`,
      detail: `${means}; the ${SIDE_NAME[lowerSide]} was lower in ${String(lowerCount)} of ${String(n)} patterns. A gap this steady is unlikely to be luck (${pText}). Compared with how much results vary from pattern to pattern, the gap is ${size}.`,
      tally,
    };
  }
  if (!gap || gap.similar) {
    return {
      metric,
      verdict: "no-gap",
      headline: `Across ${String(n)} traffic patterns, the ${words.noun} was about the same for both.`,
      detail: `${means}. No meaningful difference showed up (${pText}).`,
      tally,
    };
  }
  return {
    metric,
    verdict: "not-consistent",
    headline: `The ${words.noun} differed, but not consistently enough to rule out chance.`,
    detail: `${means}; the ${SIDE_NAME[lowerSide]} was lower in ${String(lowerCount)} of ${String(n)} patterns. The difference could be down to which vehicles happened to arrive when (${pText}). Repeating with more patterns can settle it.`,
    tally,
  };
}

// ── The metric map: plain question ↔ technical measurement ─────────────────

export interface PlainMetric {
  question: string;
  plain: string;
  keys: MetricDef["key"][];
}

/** How the everyday questions map onto the catalog's measurements. Shown to
 *  specialists (Research lab) so the translation itself is inspectable. */
export const PLAIN_METRIC_MAP: PlainMetric[] = [
  {
    question: "How much time do drivers lose?",
    plain:
      "Extra travel time per driver compared with driving through an empty junction at their own speed (including slowing the layout forces, not only queuing); the time lost that 1 in 20 drivers exceeds; time spent nearly stopped; how often drivers stop.",
    keys: [
      "averageDelay",
      "p95Delay",
      "averageWaitTime",
      "averageStopsPerVehicle",
    ],
  },
  {
    question: "How much traffic gets through?",
    plain:
      "Vehicles that made it through after the warm-up, and vehicles still waiting or moving when the clock stopped.",
    keys: ["throughput", "activeVehicleCount"],
  },
  {
    question: "How long do queues get?",
    plain:
      "The typical queue on one approach, the longest queue seen, and how long more than 5 vehicles were queued.",
    keys: ["averageQueueLength", "maxQueueLength", "congestionRecoveryTime"],
  },
  {
    question: "Is every direction treated alike?",
    plain: "Whether waiting is shared evenly between the four approaches.",
    keys: ["directionalFairnessIndex"],
  },
  {
    question: "Why did it happen?",
    plain:
      "Green time wasted on empty roads (signal only) and stop-and-go, alongside how each control works.",
    keys: ["idleOpportunityLoss", "averageStopsPerVehicle"],
  },
  {
    question: "Can I trust it?",
    plain:
      "Model integrity (vehicle overlaps), the size of the sample behind journey-time spread, and a repeat over several traffic patterns.",
    keys: ["collisionCount", "travelTimeReliability"],
  },
];
