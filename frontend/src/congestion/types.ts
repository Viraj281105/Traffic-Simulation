/**
 * Contract: POST /api/v2/network-metrics/congestion (congestion propagation).
 * Source of truth: backend/src/netmetrics/congestion.py (analyse_congestion)
 * and backend/src/netmetrics/router.py. See src/CONTRACTS_P5.md.
 *
 * A link is congested when its occupancy ratio stays at or above `threshold`
 * for `minHoldSeconds`; its onset is the start of that run. Spillback is a
 * run in which a link's head vehicle is ready but the next link is full.
 * Times are seconds from the start of the run.
 */
import type { MapData } from "../mapview/types";

export type SpreadDirection = "upstream" | "downstream" | "lateral";

export interface CongestionLinkRow {
  id: string;
  from: string;
  to: string;
  name?: string | null;
  length: number;
  lanes: number;
  /** Vehicles the link can store. */
  capacity: number;
  /** Null when the link never became congested. */
  onsetSeconds: number | null;
  /** 1 = first link to congest; null when never congested. */
  rank: number | null;
  peakOccupancyRatio: number;
}

export interface SpreadStep {
  link: string;
  rank: number;
  onsetSeconds: number;
  /** The nearby link that congested just before this one; null for the origin. */
  parent: string | null;
  direction: SpreadDirection | null;
  hops: number;
  /** Metres per second; null when there was no earlier link or no time gap. */
  speedMps: number | null;
}

export interface Spread {
  congestedLinks: number;
  totalLinks: number;
  /** The first link to congest; null when none did. */
  origin: string | null;
  order: SpreadStep[];
  durationSeconds: number;
  maxHops: number;
  meanSpeedMps: number | null;
  upstreamSpeedMps: number | null;
  downstreamSpeedMps: number | null;
  maxDistanceFromOriginMeters: number;
}

export interface SpillbackEvent {
  link: string;
  blockedBy: string;
  startSeconds: number;
  endSeconds: number;
  durationSeconds: number;
  peakOccupancyRatio: number;
  /** How many links back the blockage reaches (1 = this link only). */
  chainLength: number;
}

export interface SpillbackSummary {
  events: number;
  linksAffected: number;
  links: string[];
  totalBlockedSeconds: number;
  longestSeconds: number;
  maxChainLength: number;
  firstStartSeconds: number | null;
}

/** Links by time buckets; rows are in congestion order (first onset first),
 *  links that never congested last. `values[row][bucket]` is the mean
 *  occupancy ratio, 0..1. */
export interface Heatmap {
  metric: "occupancyRatio";
  bucketSeconds: number;
  bucketStarts: number[];
  linkIds: string[];
  values: number[][];
  queue: number[][];
  blockedFraction: number[][];
}

export interface CongestionResult {
  format: "urbanflow-congestion";
  version: number;
  seed: number;
  duration: number;
  threshold: number;
  minHoldSeconds: number;
  inModelOnly: boolean;
  run: {
    generated: number;
    entered: number;
    completed: number;
    active: number;
    blockedAtEntry: number;
    conserved: boolean;
  };
  links: CongestionLinkRow[];
  heatmap: Heatmap;
  spillback: { events: SpillbackEvent[]; summary: SpillbackSummary };
  spread: Spread;
  /** With `includeMap`; link `value` is the peak occupancy ratio. */
  map?: MapData;
}
