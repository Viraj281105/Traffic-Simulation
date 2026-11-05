/** Contract fixture for POST /api/v2/network-metrics/simulate: the corridor
 *  of src/mapview/fixtures.ts over 120 s in 30 s buckets. Not real data. */
import { corridorMap } from "../mapview/fixtures";
import type { NetworkMetrics } from "./types";

const link = (
  passed: number,
  capacity: number,
  mean: number,
  peak: number,
  queue: number,
  blocked: number,
) => ({
  passed,
  flowVph: passed * 30,
  capacity,
  meanOccupancy: mean,
  peakOccupancy: peak,
  meanOccupancyRatio: Math.round((mean / capacity) * 1e4) / 1e4,
  meanQueue: queue,
  peakQueue: Math.ceil(queue * 2),
  densityVehPerKmLane: Math.round((mean / (capacity / 0.14)) * 1e3) / 1e3,
  blockedSeconds: blocked,
});

export const metricsFixture: NetworkMetrics = {
  format: "urbanflow-network-metrics",
  version: 1,
  seed: 1,
  duration: 120,
  bucketSeconds: 30,
  inModelOnly: true,
  network: {
    generated: 38,
    entered: 36,
    blockedAtEntry: 2,
    completed: 21,
    active: 15,
    conserved: true,
    throughputVph: 630,
    totalDelaySeconds: 412,
    totalDelayHours: 0.1144,
    meanDelaySeconds: 19.6,
    meanTravelSeconds: 71.4,
    totalTravelSeconds: 1499.4,
    meanVehiclesInNetwork: 14.5,
    meanQueuedVehicles: 3.2,
    blockedLinkSeconds: 18,
    unroutable: 0,
  },
  perLink: {
    "J1>J2": link(18, 56, 34.7, 49, 4.1, 14),
    "J2>E": link(16, 56, 6.7, 12, 0.4, 0),
    "J2>S2": link(5, 28, 1.4, 4, 0, 0),
    "N1>J1": link(9, 28, 8.7, 17, 1.8, 4),
    "W>J1": link(20, 56, 15.7, 31, 1.2, 0),
  },
  perNode: {
    E: {
      kind: "gate",
      passed: 16,
      throughputVph: 480,
      meanOccupancy: 6.7,
      peakOccupancy: 12,
      meanQueue: 0.4,
      peakQueue: 1,
    },
    J1: {
      kind: "junction",
      passed: 29,
      throughputVph: 870,
      meanOccupancy: 24.4,
      peakOccupancy: 48,
      meanQueue: 3,
      peakQueue: 9,
    },
    J2: {
      kind: "junction",
      passed: 21,
      throughputVph: 630,
      meanOccupancy: 34.7,
      peakOccupancy: 49,
      meanQueue: 4.1,
      peakQueue: 9,
    },
  },
  series: [
    {
      tStart: 0,
      vehiclesInNetwork: 6.2,
      queuedVehicles: 0.4,
      exitedVehicles: 2,
    },
    {
      tStart: 30,
      vehiclesInNetwork: 13.1,
      queuedVehicles: 2.1,
      exitedVehicles: 5,
    },
    {
      tStart: 60,
      vehiclesInNetwork: 18.4,
      queuedVehicles: 4.6,
      exitedVehicles: 6,
    },
    {
      tStart: 90,
      vehiclesInNetwork: 20.3,
      queuedVehicles: 5.7,
      exitedVehicles: 8,
    },
  ],
  fundamentalDiagram: {
    bucketSeconds: 30,
    points: [
      { tStart: 0, densityVehPerKmLane: 3.1, flowVehPerHourLane: 120 },
      { tStart: 30, densityVehPerKmLane: 6.6, flowVehPerHourLane: 260 },
      { tStart: 60, densityVehPerKmLane: 9.2, flowVehPerHourLane: 310 },
      { tStart: 90, densityVehPerKmLane: 10.1, flowVehPerHourLane: 285 },
    ],
    peakFlow: { flowVehPerHourLane: 310, densityVehPerKmLane: 9.2 },
  },
  notes: [
    "Delay counts vehicles that completed their trip; vehicles still in the network at the end are not included.",
    "Mesoscopic, uncalibrated model: compare scenarios, do not read these as predictions.",
  ],
  map: corridorMap,
};
