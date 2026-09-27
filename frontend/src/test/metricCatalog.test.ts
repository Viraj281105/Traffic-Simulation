import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import {
  METRICS,
  comparisonCsv,
  formatDifference,
  formatMetric,
  metricDifference,
  metricLabel,
  metricState,
  singleRunCsv,
  type MetricContext,
} from "../metrics/catalog";
import type { RunningMetrics } from "../types/simulation";

const def = (key: string) => {
  const d = METRICS.find((m) => m.key === key);
  if (!d) throw new Error(`no metric ${key}`);
  return d;
};

function ctx(
  overrides: Partial<RunningMetrics>,
  extra: Partial<MetricContext> = {},
): MetricContext {
  return {
    metrics: {
      throughput: 5,
      averageDelay: 12.34,
      throughputRate: 18,
      idleOpportunityLoss: 0.125,
      minTTC: null,
      minPET: null,
      petApplicable: true,
      ttcThresholdSeconds: 1.5,
      travelTimeReliability: 1.4,
      collisionCount: 0,
      ...overrides,
    } as RunningMetrics,
    geometry: "fixed_time_signal",
    inWarmup: false,
    ...extra,
  };
}

// Keys the collector emits that are context for other metrics rather than
// metrics themselves (thresholds, applicability, sample-size flag, and the
// per-approach queue shown as bars).
const CONTEXT_KEYS = new Set([
  "currentQueueLengths",
  "travelTimeReliabilityLowSampleSize",
  "ttcThresholdSeconds",
  "petThresholdSeconds",
  "petApplicable",
  "vehicleLimit",
  "vehicleLimitReached",
]);

describe("metric catalog", () => {
  it("covers every key the backend collector emits", () => {
    const source = readFileSync(
      resolve(process.cwd(), "../backend/src/metrics/collector.py"),
      "utf8",
    );
    const block = source.slice(source.indexOf("base_metrics = {"));
    const emitted = new Set(
      [...block.matchAll(/^\s+"(\w+)":/gm)].map((m) => m[1]),
    );
    emitted.add("masterEfficiencyScore"); // assigned after the literal
    const described = new Set<string>(METRICS.map((m) => m.key));
    const missing = [...emitted].filter(
      (k) => !described.has(k) && !CONTEXT_KEYS.has(k),
    );
    expect(missing).toEqual([]);
    expect(emitted.size).toBeGreaterThanOrEqual(35);
  });

  it("describes every metric the backend collector reports", () => {
    const keys = new Set(METRICS.map((m) => m.key));
    for (const key of [
      "averageDelay",
      "medianDelay",
      "p95Delay",
      "minDelay",
      "maxDelay",
      "delayStdDev",
      "averageWaitTime",
      "throughput",
      "throughputRate",
      "maxQueueLength",
      "averageQueueLength",
      "activeAverageQueueLength",
      "queueStdDev",
      "totalStops",
      "averageStopsPerVehicle",
      "speedVarianceIndex",
      "travelTimeReliability",
      "idleOpportunityLoss",
      "directionalFairnessIndex",
      "activeVehicleCount",
      "totalVehiclesSpawned",
      "averageTravelSpeed",
      "queueStabilityIndex",
      "congestionRecoveryTime",
      "spaceFootprintConsumed",
      "intersectionUtilization",
      "criticalSaturationVolume",
      "masterEfficiencyScore",
      "collisionCount",
      "minTTC",
      "ttcEventCount",
      "ttcSampleCount",
      "minPET",
      "petEventCount",
      "petSampleCount",
    ]) {
      expect(keys.has(key as never)).toBe(true);
    }
  });

  it("formats values with their units", () => {
    expect(formatMetric(def("averageDelay"), ctx({}))).toBe("12.3 s");
    expect(formatMetric(def("throughputRate"), ctx({}))).toBe("18.0 veh/min");
  });

  it("shows a 0-1 fraction as a percentage", () => {
    expect(formatMetric(def("idleOpportunityLoss"), ctx({}))).toBe("12.5%");
  });

  it("never turns an unobserved minimum into a zero", () => {
    expect(formatMetric(def("minTTC"), ctx({}))).toBe("None observed");
  });

  it("marks PET as not applicable for the roundabout", () => {
    const rb = ctx({ petApplicable: false }, { geometry: "roundabout" });
    expect(formatMetric(def("minPET"), rb)).toBe("N/A");
    expect(formatMetric(def("petEventCount"), rb)).toBe("N/A");
    expect(formatMetric(def("idleOpportunityLoss"), rb)).toBe("N/A");
  });

  it("hides post-warm-up metrics during warm-up but keeps whole-run ones", () => {
    const warm = ctx({}, { inWarmup: true });
    expect(formatMetric(def("averageDelay"), warm)).toBe("—");
    expect(metricState(def("averageDelay"), warm)).toMatchObject({
      note: "Warm-up in progress",
    });
    expect(formatMetric(def("collisionCount"), warm)).toBe("0");
  });

  it("shows exit-based metrics as empty until a vehicle is served", () => {
    const none = ctx({ throughput: 0, averageDelay: 0 });
    expect(formatMetric(def("averageDelay"), none)).toBe("—");
    expect(formatMetric(def("directionalFairnessIndex"), none)).toBe("—");
    // A count of zero is a real result.
    expect(formatMetric(def("throughput"), none)).toBe("0 veh");
  });

  it("flags a low-sample planning time index", () => {
    const s = metricState(
      def("travelTimeReliability"),
      ctx({ travelTimeReliabilityLowSampleSize: true }),
    );
    expect(s).toMatchObject({ kind: "value", note: "Low sample (n < 20)" });
  });

  it("names the TTC threshold the backend used", () => {
    expect(
      metricLabel(def("ttcEventCount"), ctx({}).metrics ?? undefined),
    ).toBe("Low-TTC events (TTC ≤ 1.5 s)");
  });

  it("reports differences as roundabout minus signal, in units", () => {
    const signal = ctx({ averageDelay: 20 });
    const roundabout = ctx({ averageDelay: 12.5 }, { geometry: "roundabout" });
    const d = metricDifference(def("averageDelay"), signal, roundabout);
    expect(d).toBe(-7.5);
    expect(formatDifference(def("averageDelay"), d)).toBe("−7.5 s");
    expect(formatDifference(def("idleOpportunityLoss"), 2)).toBe("+2.0 pp");
    expect(
      metricDifference(def("minPET"), signal, {
        ...roundabout,
        metrics: {
          ...roundabout.metrics,
          petApplicable: false,
        } as RunningMetrics,
      }),
    ).toBeNull();
  });

  it("exports every metric without ranking columns", () => {
    const single = singleRunCsv(ctx({}), ["test"]);
    expect(
      single.split("\n").filter((l) => l && !l.startsWith("#")),
    ).toHaveLength(METRICS.length + 1);
    const pair = comparisonCsv(
      ctx({}),
      ctx({}, { geometry: "roundabout" }),
      [],
    );
    expect(pair).toContain("roundabout_minus_signal");
    expect(pair.toLowerCase()).not.toContain("winner");
  });

  it("keeps the fixed-weight composite within one geometry", () => {
    const composite = def("masterEfficiencyScore");
    expect(composite.withinGeometryOnly).toBe(true);
    expect(composite.description).toMatch(
      /not a signal-versus-roundabout score/i,
    );
    expect(composite.description).toMatch(/idle loss is signal-only/i);

    const signal = ctx({ masterEfficiencyScore: 70 });
    const roundabout = ctx(
      { masterEfficiencyScore: 75 },
      { geometry: "roundabout" },
    );
    // Single-run export keeps it...
    expect(singleRunCsv(signal, [])).toContain("masterEfficiencyScore");
    // ...but no side-by-side export ever sets the two geometries against each other.
    expect(comparisonCsv(signal, roundabout, [])).not.toContain(
      "masterEfficiencyScore",
    );
  });

  it("shows no composite before anything has been measured", () => {
    const composite = def("masterEfficiencyScore");
    const state = metricState(
      composite,
      ctx({ throughput: 0, masterEfficiencyScore: null }),
    );
    expect(state.kind).toBe("none");
    expect(
      metricState(
        composite,
        ctx({ masterEfficiencyScore: 55 }, { inWarmup: true }),
      ).kind,
    ).toBe("none");
  });

  it("describes TTC as different-lane, per-tick, and not a crash probability", () => {
    const ttc = def("minTTC").description;
    expect(ttc).toMatch(/different lanes/i);
    expect(ttc).toMatch(/not a collision or crash probability/i);
    expect(ttc).not.toMatch(/following vehicle and its leader/i);
    expect(def("ttcEventCount").description).toMatch(/exposure count/i);
    expect(def("petEventCount").description).toMatch(/generous/i);
  });

  it("describes delay as extra travel time, distinct from queued time", () => {
    expect(def("averageDelay").description).toMatch(
      /not the same as time spent queued/i,
    );
    expect(def("averageWaitTime").description).toMatch(
      /not the same as delay/i,
    );
    expect(def("criticalSaturationVolume").description).toMatch(
      /not a measured capacity/i,
    );
  });
});
