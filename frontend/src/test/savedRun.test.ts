import { describe, expect, it } from "vitest";

import { multiRunCsv } from "../metrics/catalog";
import type { RunRecord } from "../services/api";
import {
  capturedInWarmup,
  configDifferences,
  isComparisonRun,
  metricColumns,
} from "../runs/savedRun";
import type { RunningMetrics } from "../types/simulation";

const timing = {
  timeStep: 0.1,
  duration: 300,
  warmupTime: 30,
  elapsed: 120,
};

describe("saved-run helpers", () => {
  it("tells warm-up captures apart, and says so when it cannot", () => {
    expect(capturedInWarmup(timing, null)).toBe(false);
    expect(capturedInWarmup({ ...timing, elapsed: 10 }, null)).toBe(true);
    expect(
      capturedInWarmup({ ...timing, warmupTime: null, elapsed: null }, null),
    ).toBeNull();
    // Legacy engine configs carry their own warm-up.
    expect(
      capturedInWarmup(
        { timeStep: null, duration: null, warmupTime: null, elapsed: 5 },
        { simulation: { warmupTime: 15 } },
      ),
    ).toBe(true);
  });

  it("splits comparison runs into signal and roundabout columns", () => {
    const record = {
      runId: "r",
      runMode: null,
      intersectionType: "fixed_time_signal",
      timing,
      config: null,
      summaryMetrics: { signal: { throughput: 1 }, roundabout: {} },
    } as unknown as RunRecord;
    expect(isComparisonRun(record)).toBe(true);
    const cols = metricColumns(record);
    expect(cols.map((c) => [c.key, c.ctx.geometry])).toEqual([
      ["r:signal", "fixed_time_signal"],
      ["r:roundabout", "roundabout"],
    ]);
  });

  it("lists only configuration values that differ", () => {
    expect(
      configDifferences([
        { a: 1, b: { c: [1, 2] }, same: "x" },
        { a: 2, b: { c: [1, 2] }, same: "x", extra: true },
      ]),
    ).toEqual([
      { path: "a", values: ["1", "2"] },
      { path: "extra", values: [null, "true"] },
    ]);
  });
});

describe("multiRunCsv", () => {
  it("leaves a difference empty when either value is unavailable", () => {
    const ctx = (m: Partial<RunningMetrics> | null) => ({
      metrics: m as RunningMetrics | null,
      geometry: "fixed_time_signal" as const,
      inWarmup: false,
    });
    const csv = multiRunCsv(
      [
        { label: "A", ctx: ctx({ throughput: 10, averageDelay: 5 }) },
        { label: "B", ctx: ctx({ throughput: 14 }) },
      ],
      ["header"],
    );
    const lines = csv.trim().split("\n");
    expect(lines[0]).toBe("# header");
    expect(lines[1]).toBe("group,metric,key,unit,A,B,B minus A");
    const served = lines.find((l) => l.includes(",throughput,"));
    expect(served?.endsWith(",10,14,4")).toBe(true);
    const delay = lines.find((l) => l.includes(",averageDelay,"));
    // B did not store a delay: its cell is "—" and no difference is given.
    expect(delay?.endsWith(",5,—,")).toBe(true);
  });
});
