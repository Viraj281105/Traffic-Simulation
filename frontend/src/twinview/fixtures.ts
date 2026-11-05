/** Contract fixtures for the digital twin (shapes of TwinRunner.state() and
 *  what_if()). Not real measurements. */
import type { TwinState, WhatIfResult } from "./types";

const w = (
  window: number,
  predicted: Record<string, number>,
  observed: Record<string, number>,
) => ({
  window,
  time: window * 60,
  predicted,
  observed,
  observedSpeed: {},
});

export const twinFixture: TwinState = {
  format: "urbanflow-twin-state",
  version: 1,
  graph: "Two-junction corridor",
  intervalSeconds: 60,
  warmupSeconds: 120,
  seed: 1,
  start: 0,
  latestWindow: 3,
  currentFlows: [
    { origin: "W", destination: "E", vehiclesPerHour: 600 },
    { origin: "N1", destination: "S2", vehiclesPerHour: 150 },
  ],
  timeline: [
    w(0, { "W>J1": 9, "J1>J2": 8 }, { "W>J1": 10, "J1>J2": 8 }),
    w(1, { "W>J1": 10, "J1>J2": 9 }, { "W>J1": 11, "J1>J2": 10 }),
    w(2, { "W>J1": 10, "J1>J2": 10 }, { "W>J1": 14, "J1>J2": 12 }),
    w(3, { "W>J1": 11, "J1>J2": 10 }, { "W>J1": 18, "J1>J2": 15 }),
  ],
  comparison: {
    network: {
      n: 4,
      mae: 5.25,
      mape: 18.63,
      bias: -5.25,
      lagWindows: 1,
      lagSeconds: 60,
    },
    perLink: {
      "J1>J2": { n: 4, mae: 2, mape: 15, bias: -2 },
      "W>J1": { n: 4, mae: 3.25, mape: 21.64, bias: -3.25 },
    },
    series: [
      { window: 0, predicted: 17, observed: 18, error: -1, errorPct: 5.555556 },
      { window: 1, predicted: 19, observed: 21, error: -2, errorPct: 9.52381 },
      {
        window: 2,
        predicted: 20,
        observed: 26,
        error: -6,
        errorPct: 23.076923,
      },
      {
        window: 3,
        predicted: 21,
        observed: 33,
        error: -12,
        errorPct: 36.363636,
      },
    ],
    alertThresholdPct: 25,
    alert: true,
    alerts: [
      { window: 3, kind: "window", errorPct: 36.363636, thresholdPct: 25 },
    ],
  },
};

export const quietTwinFixture: TwinState = {
  ...twinFixture,
  comparison: {
    ...twinFixture.comparison,
    alert: false,
    alerts: [],
    series: twinFixture.comparison.series.slice(0, 2),
  },
};

export const whatIfFixture: WhatIfResult = {
  window: 4,
  horizonWindows: 1,
  scenario: {
    closeLinks: ["J1>J2"],
    demandScale: 1.2,
    lanes: {},
    speedFactors: {},
  },
  baseline: { completed: 14, meanDelaySeconds: 21.5, meanTravelSeconds: 74.2 },
  variant: {
    completed: 9,
    meanDelaySeconds: null,
    meanTravelSeconds: null,
    unroutable: 6,
  },
  delta: { completed: -5, meanDelaySeconds: null, meanTravelSeconds: null },
  perLink: {
    "J1>J2": {
      baseline: 10,
      variant: null,
      delta: null,
      peakOccupancyDelta: null,
    },
    "W>J1": { baseline: 11, variant: 13, delta: 2, peakOccupancyDelta: 5 },
  },
};

export const mildWhatIfFixture: WhatIfResult = {
  ...whatIfFixture,
  scenario: { ...whatIfFixture.scenario, closeLinks: [], demandScale: 1.5 },
  variant: {
    completed: 17,
    meanDelaySeconds: 28.9,
    meanTravelSeconds: 82.4,
    unroutable: 0,
  },
  delta: { completed: 3, meanDelaySeconds: 7.4, meanTravelSeconds: 8.2 },
  perLink: {
    "J1>J2": { baseline: 10, variant: 12, delta: 2, peakOccupancyDelta: 6 },
    "W>J1": { baseline: 11, variant: 14, delta: 3, peakOccupancyDelta: 7 },
  },
};
