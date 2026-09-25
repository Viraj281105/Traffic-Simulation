/**
 * Traffic demand levels, calibrated against measured capacity.
 *
 * REFERENCE_CAPACITY_VPH is, for each lane count, the mean of the two
 * controls' measured maximum served flow (seeds 1-3, 240 s runs, 30 s
 * warm-up, offered 4,320 and 5,400 veh/h; docs/reports/comparative_report.md
 * §2). It is the same number for both controls, so a level never favours one
 * of them: "At capacity" is where, on average, the two junctions run out of
 * room, not where either one wins. Mirrored by backend
 * study/calibration.py::REFERENCE_CAPACITY_VPH (a test keeps them equal).
 */

export type LaneCount = 1 | 2 | 3;

export const REFERENCE_CAPACITY_VPH: Record<LaneCount, number> = {
  1: 1250,
  2: 2180,
  3: 2620,
};

export type DemandLevelId =
  "light" | "moderate" | "busy" | "near" | "capacity" | "over";

export interface DemandLevel {
  id: DemandLevelId;
  label: string;
  /** Demand as a share of the reference capacity (degree of saturation). */
  ratio: number;
  description: string;
}

export const DEMAND_LEVELS: DemandLevel[] = [
  {
    id: "light",
    label: "Light",
    ratio: 0.25,
    description: "Mostly free-flowing; vehicles rarely meet at the junction.",
  },
  {
    id: "moderate",
    label: "Moderate",
    ratio: 0.5,
    description: "Regular traffic; short waits are common.",
  },
  {
    id: "busy",
    label: "Busy",
    ratio: 0.75,
    description: "Queues form and clear; both junctions are working hard.",
  },
  {
    id: "near",
    label: "Near capacity",
    ratio: 0.9,
    description: "Close to the most the junctions can carry; queues grow.",
  },
  {
    id: "capacity",
    label: "At capacity",
    ratio: 1.0,
    description: "As much traffic as the junctions can carry on average.",
  },
  {
    id: "over",
    label: "Over capacity",
    ratio: 1.3,
    description: "More traffic than can be served; queues keep growing.",
  },
];

function laneCount(lanes: number): LaneCount {
  return Math.min(3, Math.max(1, Math.round(lanes))) as LaneCount;
}

/** Total arrivals (veh/h, rounded to 10) for a level at a lane count. */
export function demandVph(level: DemandLevel, lanes: number): number {
  return (
    Math.round((level.ratio * REFERENCE_CAPACITY_VPH[laneCount(lanes)]) / 10) *
    10
  );
}

/** Arrival rate (veh/s, whole junction) for a level at a lane count. */
export function demandRate(level: DemandLevel, lanes: number): number {
  return demandVph(level, lanes) / 3600;
}

/** The level whose rate matches, for this lane count; null for a custom rate. */
export function demandLevelFor(
  arrivalRate: number,
  lanes: number,
): DemandLevel | null {
  return (
    DEMAND_LEVELS.find(
      (d) => Math.abs(demandRate(d, lanes) - arrivalRate) < 1e-6,
    ) ?? null
  );
}

/** Degree of saturation of a rate against the reference capacity. */
export function saturationRatio(arrivalRate: number, lanes: number): number {
  return (arrivalRate * 3600) / REFERENCE_CAPACITY_VPH[laneCount(lanes)];
}

// ── Research lab sweep presets ────────────────────────────────────────────

export type TierPresetId = "standard" | "wide" | "transition";

export interface TierPreset {
  id: TierPresetId;
  title: string;
  detail: string;
  /** Demand levels as shares of the reference capacity. */
  ratios: number[];
}

export const TIER_PRESETS: TierPreset[] = [
  {
    id: "standard",
    title: "Standard — 8 levels",
    detail: "20% to 160% of capacity",
    ratios: [0.2, 0.4, 0.6, 0.8, 0.9, 1.0, 1.2, 1.6],
  },
  {
    id: "wide",
    title: "Wide — 10 levels",
    detail: "10% to 200% of capacity",
    ratios: [0.1, 0.25, 0.4, 0.55, 0.7, 0.85, 1.0, 1.25, 1.5, 2.0],
  },
  {
    id: "transition",
    title: "Transition — 10 levels",
    detail: "60% to 150% of capacity, where queues start to build",
    ratios: [0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 1.0, 1.1, 1.25, 1.5],
  },
];

/** Arrival rates (veh/s) of a sweep preset at a lane count. */
export function sweepRates(preset: TierPreset, lanes: number): number[] {
  const cap = REFERENCE_CAPACITY_VPH[laneCount(lanes)];
  return preset.ratios.map((r) => Math.round(((r * cap) / 3600) * 1000) / 1000);
}

// ── Speed limit options (Research lab) ────────────────────────────────────

export const SPEED_LIMITS = {
  calmed: { label: "30 km/h", metresPerSecond: 8.33 },
  standard: { label: "50 km/h", metresPerSecond: 13.89 },
  arterial: { label: "60 km/h", metresPerSecond: 16.67 },
} as const;
