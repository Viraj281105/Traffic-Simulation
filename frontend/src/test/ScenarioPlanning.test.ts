import { describe, expect, it } from "vitest";
import { calculateDelta, formatDeltaText, exportComparisonCsv } from "../components/planning/planningUtils";
import { type ScenarioSimulationResult } from "../components/planning/planningTypes";

describe("planningUtils", () => {
  describe("calculateDelta", () => {
    it("evaluates lower-is-better metrics correctly (e.g. delay, queue)", () => {
      // Lower is better: baseline 20, intervention 15 -> reduction of 5 (better)
      const resBetter = calculateDelta(15, 20, true);
      expect(resBetter.absolute).toBe(-5);
      expect(resBetter.percentage).toBe(-25);
      expect(resBetter.direction).toBe("better");

      // Baseline 20, intervention 25 -> increase of 5 (worse)
      const resWorse = calculateDelta(25, 20, true);
      expect(resWorse.absolute).toBe(5);
      expect(resWorse.percentage).toBe(25);
      expect(resWorse.direction).toBe("worse");

      // Equal values -> neutral
      const resNeutral = calculateDelta(20, 20, true);
      expect(resNeutral.absolute).toBe(0);
      expect(resNeutral.percentage).toBe(0);
      expect(resNeutral.direction).toBe("neutral");
    });

    it("evaluates higher-is-better metrics correctly (e.g. throughput, speed)", () => {
      // Higher is better: baseline 100, intervention 120 -> increase of 20 (better)
      const resBetter = calculateDelta(120, 100, false);
      expect(resBetter.absolute).toBe(20);
      expect(resBetter.percentage).toBe(20);
      expect(resBetter.direction).toBe("better");

      // Baseline 100, intervention 80 -> decrease of 20 (worse)
      const resWorse = calculateDelta(80, 100, false);
      expect(resWorse.absolute).toBe(-20);
      expect(resWorse.percentage).toBe(-20);
      expect(resWorse.direction).toBe("worse");
    });
  });

  describe("formatDeltaText", () => {
    it("formats positive and negative deltas with percentages", () => {
      const delta1 = { absolute: -4.5, percentage: -22.5, direction: "better" as const };
      expect(formatDeltaText(delta1, "s")).toBe("-22.5% (-4.5 s)");

      const delta2 = { absolute: 10, percentage: 15.0, direction: "worse" as const };
      expect(formatDeltaText(delta2, "veh")).toBe("+15% (+10 veh)");
    });
  });

  describe("exportComparisonCsv", () => {
    it("generates structured CSV with baseline and intervention metrics", () => {
      const base: ScenarioSimulationResult = {
        scenarioId: "base",
        name: "Baseline Signal",
        strategy: "fixed_time",
        volumeScale: 1.0,
        duration: 120,
        seedCount: 3,
        metrics: {
          averageWaitTime: 12.0,
          averageDelay: 15.0,
          throughput: 200,
          averageQueueLength: 4.5,
          maxQueueLength: 9,
          averageTravelSpeed: 10.5,
          collisionCount: 0,
          minTTC: 1.5,
          ttcEventCount: 0,
        },
      };

      const intervention: ScenarioSimulationResult = {
        scenarioId: "int_1",
        name: "Intervention Roundabout",
        strategy: "roundabout",
        volumeScale: 1.0,
        duration: 120,
        seedCount: 3,
        metrics: {
          averageWaitTime: 6.0,
          averageDelay: 8.0,
          throughput: 240,
          averageQueueLength: 2.1,
          maxQueueLength: 5,
          averageTravelSpeed: 11.8,
          collisionCount: 0,
          minTTC: 1.5,
          ttcEventCount: 0,
        },
      };

      const csv = exportComparisonCsv("Test Plan", base, [base, intervention]);
      expect(csv).toContain("Experiment: Test Plan");
      expect(csv).toContain('"Baseline Signal",Baseline,fixed_time,x1,120,15.00,—,—,12.00,—,200,—,4.50,—,10.50,—,0');
      expect(csv).toContain('"Intervention Roundabout",Intervention,roundabout,x1,120,8.00,-7.00,-46.7%,6.00,-6.00,240,+20.0%,2.10,-53.3%,11.80,+12.4%,0');
    });
  });
});
