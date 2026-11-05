/**
 * Contract: POST /api/v2/network-metrics/simulate (network-wide metrics).
 * Source of truth: backend/src/netmetrics/metrics.py (compute_metrics) and
 * backend/src/netmetrics/router.py. See src/CONTRACTS_P5.md.
 *
 * The model is mesoscopic and uncalibrated (`inModelOnly`): the numbers
 * compare scenarios, they are not predictions. Delay counts only vehicles
 * that completed their trip.
 */
import type { MapData } from "../mapview/types";

export interface NetworkTotals {
  generated: number;
  entered: number;
  blockedAtEntry: number;
  completed: number;
  active: number;
  /** Every generated vehicle is accounted for (entered + blocked, and so on). */
  conserved: boolean;
  throughputVph: number;
  totalDelaySeconds: number;
  totalDelayHours: number;
  /** Null when no vehicle completed its trip. */
  meanDelaySeconds: number | null;
  meanTravelSeconds: number | null;
  totalTravelSeconds: number;
  meanVehiclesInNetwork: number;
  meanQueuedVehicles: number;
  blockedLinkSeconds: number;
  unroutable: number;
}

export interface LinkMetrics {
  passed: number;
  flowVph: number;
  /** Storage capacity of the link, vehicles. */
  capacity: number;
  meanOccupancy: number;
  peakOccupancy: number;
  /** 0..1: mean vehicles divided by capacity. */
  meanOccupancyRatio: number;
  meanQueue: number;
  peakQueue: number;
  densityVehPerKmLane: number;
  blockedSeconds: number;
}

export interface NodeMetrics {
  kind: "junction" | "gate";
  passed: number;
  throughputVph: number;
  meanOccupancy: number;
  peakOccupancy: number;
  meanQueue: number;
  peakQueue: number;
}

export interface SeriesBucket {
  tStart: number;
  vehiclesInNetwork: number;
  queuedVehicles: number;
  exitedVehicles: number;
}

export interface DiagramPoint {
  tStart: number;
  densityVehPerKmLane: number;
  flowVehPerHourLane: number;
}

export interface FundamentalDiagram {
  bucketSeconds: number;
  points: DiagramPoint[];
  peakFlow: {
    flowVehPerHourLane: number;
    densityVehPerKmLane: number;
  } | null;
  /** Only with `perLinkDiagram: true`. */
  perLink?: Record<
    string,
    { densityVehPerKmLane: number; flowVehPerHourLane: number }[]
  >;
}

export interface NetworkMetrics {
  format: "urbanflow-network-metrics";
  version: number;
  seed: number;
  duration: number;
  bucketSeconds: number;
  inModelOnly: boolean;
  network: NetworkTotals;
  perLink: Record<string, LinkMetrics>;
  perNode: Record<string, NodeMetrics>;
  series: SeriesBucket[];
  fundamentalDiagram: FundamentalDiagram;
  notes: string[];
  /** With `includeMap`; link `value` is the mean occupancy ratio. */
  map?: MapData;
}
