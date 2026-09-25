import { describe, expect, it } from "vitest";
import {
  SIMILARITY,
  compare,
  duration,
  explanations,
  fairnessBand,
  headlineFindings,
  levelOfService,
  readReliability,
  sideSummary,
  trustNotes,
  type ReliabilityResult,
} from "../metrics/plainLanguage";
import type { RunningMetrics } from "../types/simulation";

function metrics(overrides: Partial<RunningMetrics> = {}): RunningMetrics {
  return {
    averageDelay: 20,
    medianDelay: 18,
    minDelay: 2,
    maxDelay: 60,
    p95Delay: 45,
    delayStdDev: 9,
    averageWaitTime: 12,
    throughput: 200,
    throughputRate: 20,
    currentQueueLengths: { north: 1, south: 2, east: 0, west: 1 },
    maxQueueLength: 9,
    averageQueueLength: 2.5,
    activeAverageQueueLength: 6,
    queueStdDev: 2,
    totalStops: 220,
    averageStopsPerVehicle: 1.1,
    speedVarianceIndex: 0.4,
    travelTimeReliability: 1.6,
    idleOpportunityLoss: 0.12,
    directionalFairnessIndex: 0.97,
    activeVehicleCount: 14,
    totalVehiclesSpawned: 260,
    averageTravelSpeed: 8,
    queueStabilityIndex: 0.8,
    congestionRecoveryTime: 40,
    spaceFootprintConsumed: 200,
    intersectionUtilization: 70,
    criticalSaturationVolume: 0.3,
    collisionCount: 0,
    ...overrides,
  };
}

const ctx = (
  m: RunningMetrics,
  geometry: "fixed_time_signal" | "roundabout",
) => ({
  metrics: m,
  geometry,
  inWarmup: false,
});

describe("compare", () => {
  it("calls a gap within either tolerance about the same", () => {
    expect(compare(20, 20.8, SIMILARITY.delay)?.similar).toBe(true);
    // 5% of 100 s is 5 s, so a 4 s gap reads as about the same.
    expect(compare(100, 104, SIMILARITY.delay)?.similar).toBe(true);
  });

  it("names the lower and higher side of a real difference", () => {
    const c = compare(30, 20, SIMILARITY.delay);
    expect(c).toMatchObject({
      similar: false,
      lower: "roundabout",
      higher: "signal",
      gap: 10,
    });
  });

  it("returns null when either side has no value", () => {
    expect(compare(null, 3, SIMILARITY.delay)).toBeNull();
  });
});

describe("sideSummary", () => {
  it("reads values through the catalog, scaling fractions to percent", () => {
    const s = sideSummary(ctx(metrics(), "fixed_time_signal"));
    expect(s.delay).toBe(20);
    expect(s.idleGreenPct).toBeCloseTo(12);
  });

  it("hides metrics the geometry does not measure", () => {
    const r = sideSummary(ctx(metrics(), "roundabout"));
    expect(r.idleGreenPct).toBeNull();
  });

  it("hides post-warm-up metrics during warm-up and exit-based ones before any exit", () => {
    const warm = sideSummary({
      ...ctx(metrics(), "roundabout"),
      inWarmup: true,
    });
    expect(warm.delay).toBeNull();
    const none = sideSummary(ctx(metrics({ throughput: 0 }), "roundabout"));
    expect(none.delay).toBeNull();
    expect(none.served).toBe(0);
  });
});

describe("levelOfService", () => {
  it("uses the signalised bands for the signal and the stricter ones for the roundabout", () => {
    expect(levelOfService(30, "signal")).toBe("C");
    expect(levelOfService(30, "roundabout")).toBe("D");
    expect(levelOfService(9, "roundabout")).toBe("A");
    expect(levelOfService(90, "signal")).toBe("F");
  });
});

describe("fairnessBand", () => {
  it("maps Jain's index onto words", () => {
    expect(fairnessBand(0.99).label).toBe("Very even");
    expect(fairnessBand(0.9).label).toBe("Mostly even");
    expect(fairnessBand(0.75).label).toBe("Uneven");
    expect(fairnessBand(0.4).label).toBe("Very uneven");
  });
});

describe("headlineFindings", () => {
  const s = sideSummary(
    ctx(
      metrics({ averageDelay: 30, throughput: 200, maxQueueLength: 12 }),
      "fixed_time_signal",
    ),
  );
  const r = sideSummary(
    ctx(
      metrics({ averageDelay: 22, throughput: 201, maxQueueLength: 6 }),
      "roundabout",
    ),
  );

  it("states both values and never uses a winner word", () => {
    const lines = headlineFindings(s, r);
    expect(lines[0]).toBe(
      "Drivers lost less time at the roundabout: 8 s less per driver on average (30 s at the signal, 22 s at the roundabout).",
    );
    expect(lines[1]).toMatch(
      /about the same number of vehicles through \(200 vs 201\)/,
    );
    expect(lines[2]).toMatch(
      /12 vehicles at the signal and 6 at the roundabout/,
    );
    expect(lines.join(" ")).not.toMatch(/\bwin|best|better\b/i);
  });
});

describe("explanations", () => {
  const facts = {
    lanes: 1,
    arrivalRate: 0.3,
    greenNs: 25,
    greenEw: 25,
    cycleSeconds: 60,
    criticalGap: 4.5,
  };

  it("explains both mechanisms with the scenario's own settings", () => {
    const s = sideSummary(ctx(metrics(), "fixed_time_signal"));
    const r = sideSummary(ctx(metrics(), "roundabout"));
    const text = explanations(s, r, facts)
      .map((e) => e.body)
      .join(" ");
    expect(text).toContain("25 s of green");
    expect(text).toContain("60 s");
    expect(text).toContain("4.5 s");
    expect(text).toContain("1,080 vehicles arriving per hour");
  });

  it("adds data-driven reasons only when the run shows them", () => {
    const s = sideSummary(
      ctx(metrics({ idleOpportunityLoss: 0.01 }), "fixed_time_signal"),
    );
    const r = sideSummary(ctx(metrics(), "roundabout"));
    const titles = explanations(s, r, facts).map((e) => e.title);
    expect(titles).not.toContain("The signal's fixed timing cost time");
    expect(titles).not.toContain("One side was falling behind");

    const backlogged = sideSummary(
      ctx(metrics({ activeVehicleCount: 40 }), "roundabout"),
    );
    const withBacklog = explanations(s, backlogged, facts);
    expect(withBacklog.map((e) => e.title)).toContain(
      "One side was falling behind",
    );
  });
});

describe("trustNotes", () => {
  const base = {
    seed: 42,
    lanes: 1,
    warmupSeconds: 30,
    measuredSeconds: 270,
    complete: true,
    collisions: 0,
    lowReliabilitySample: false,
  };

  it("always explains the fair test and the model's scope", () => {
    const notes = trustNotes(base);
    expect(notes.every((n) => n.tone === "info")).toBe(true);
    expect(notes[0].text).toContain("traffic pattern #42");
    expect(notes.some((n) => n.text.includes("Not modelled"))).toBe(true);
  });

  it("adds cautions for partial runs, multi-lane roundabouts and overlaps", () => {
    const notes = trustNotes({
      ...base,
      complete: false,
      measuredSeconds: 45,
      lanes: 2,
      collisions: 1,
    });
    const cautions = notes
      .filter((n) => n.tone === "caution")
      .map((n) => n.text);
    expect(cautions).toHaveLength(3);
    expect(cautions[0]).toContain("only 45 s of traffic");
    expect(cautions[1]).toContain("single circulating lane");
    expect(cautions[2]).toContain("1 vehicle overlap");
  });
});

describe("duration", () => {
  it("reads like speech", () => {
    expect(duration(45)).toBe("45 s");
    expect(duration(120)).toBe("2 min");
    expect(duration(135)).toBe("2 min 15 s");
  });
});

describe("readReliability", () => {
  function study(
    delays: [number, number][],
    comparison: {
      pValue: number | null;
      significant: boolean;
      cohensD: number;
    },
  ): ReliabilityResult {
    const stat = (xs: number[]) => {
      const mean = xs.reduce((a, b) => a + b, 0) / xs.length;
      return {
        mean,
        std: 1,
        min: Math.min(...xs),
        max: Math.max(...xs),
        ci95: 1,
      };
    };
    const zero = { mean: 0, std: 0, min: 0, max: 0, ci95: 0 };
    const none = { pValue: 1, significant: false, cohensD: 0 };
    return {
      numSeeds: delays.length,
      duration: 300,
      signal: {
        delay: stat(delays.map((d) => d[0])),
        throughput: zero,
        queue: zero,
      },
      roundabout: {
        delay: stat(delays.map((d) => d[1])),
        throughput: zero,
        queue: zero,
      },
      comparison: { delay: comparison, throughput: none, queue: none },
      seedRuns: delays.map(([a, b], i) => ({
        seed: i + 1,
        signal: { delay: a, throughput: 0, queue: 0 },
        roundabout: { delay: b, throughput: 0, queue: 0 },
      })),
    };
  }

  it("calls a significant difference consistent and tallies the patterns", () => {
    const reading = readReliability(
      study(
        [
          [30, 20],
          [28, 21],
          [31, 19],
          [29, 22],
          [27, 23],
        ],
        { pValue: 0.002, significant: true, cohensD: 3 },
      ),
      "delay",
    );
    expect(reading.verdict).toBe("consistent");
    expect(reading.headline).toBe(
      "Drivers lost less time at the roundabout — and the difference held up across 5 traffic patterns.",
    );
    expect(reading.tally).toEqual({ signal: 0, roundabout: 5, tie: 0 });
    expect(reading.detail).toContain("large");
  });

  it("does not overclaim a non-significant gap", () => {
    const reading = readReliability(
      study(
        [
          [30, 20],
          [20, 28],
          [31, 22],
        ],
        { pValue: 0.4, significant: false, cohensD: 0.4 },
      ),
      "delay",
    );
    expect(reading.verdict).toBe("not-consistent");
    expect(reading.headline).toMatch(
      /not consistently enough to rule out chance/,
    );
  });

  it("reports no gap when the means are about the same", () => {
    const reading = readReliability(
      study(
        [
          [20, 20.2],
          [21, 20.9],
        ],
        { pValue: 0.9, significant: false, cohensD: 0.05 },
      ),
      "delay",
    );
    expect(reading.verdict).toBe("no-gap");
  });

  it("treats throughput as higher-is-more when consistent", () => {
    const result = study([[1, 1]], {
      pValue: 1,
      significant: false,
      cohensD: 0,
    });
    result.signal.throughput = {
      mean: 250,
      std: 2,
      min: 248,
      max: 252,
      ci95: 2,
    };
    result.roundabout.throughput = {
      mean: 230,
      std: 2,
      min: 228,
      max: 232,
      ci95: 2,
    };
    result.comparison.throughput = {
      pValue: 0.001,
      significant: true,
      cohensD: 5,
    };
    const reading = readReliability(result, "throughput");
    expect(reading.headline).toMatch(
      /^More vehicles got through the traffic signal/,
    );
  });
});
