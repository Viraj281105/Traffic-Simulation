/**
 * The comparison rule the Research lab teaches, and its example numbers.
 *
 * The rule in components/research/evidence.ts restates what the backend does
 * (study/control_comparison.py, study/tolerances.py, study/validation.py).
 * These tests read those files, so a change to the implemented confidence
 * level or tie tolerance fails here until the pages are updated. The matching
 * backend test (tests/study/test_teaching_examples.py) runs the same example
 * numbers through the real `_paired_delay`.
 */
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import {
  CONFIDENCE_LEVEL,
  EXAMPLE_PAIRS,
  EXAMPLE_THREE,
  EXAMPLE_TWO,
  T_95,
  TIE,
  pairedReading,
  readingWords,
} from "../components/research/evidence";

// Vitest runs from the frontend directory.
const backendFile = (name: string) =>
  resolve(process.cwd(), "..", "backend", "src", "study", name);
const haveBackend = existsSync(backendFile("tolerances.py"));

describe("the implemented rule", () => {
  it.skipIf(!haveBackend)("uses the backend's confidence level", () => {
    const source = readFileSync(backendFile("validation.py"), "utf8");
    expect(source).toMatch(/DEFAULT_CONFIDENCE_LEVEL\s*=\s*0\.95\b/);
    expect(CONFIDENCE_LEVEL).toBe(0.95);
  });

  it.skipIf(!haveBackend)("uses the backend's tie tolerance", () => {
    const source = readFileSync(backendFile("tolerances.py"), "utf8");
    expect(source).toMatch(/DELAY_TIE_ABS_SECONDS:\s*float\s*=\s*1\.0\b/);
    expect(source).toMatch(/DELAY_TIE_RELATIVE:\s*float\s*=\s*0\.05\b/);
    expect(TIE).toEqual({ abs: 1, rel: 0.05 });
  });

  it.skipIf(!haveBackend)(
    "decides ties first, then the interval, as the backend does",
    () => {
      const source = readFileSync(backendFile("control_comparison.py"), "utf8");
      const order = [
        "if delays_are_tied(mean_a, mean_b):",
        "elif n > 1 and (high < 0 or low > 0):",
        'reading = "inconclusive"',
      ].map((line) => source.indexOf(line));
      expect(order.every((i) => i >= 0)).toBe(true);
      expect(order).toEqual([...order].sort((a, b) => a - b));
      expect(source).toMatch(
        /_t_critical\(n - 1, confidence\) \* sd \/ math\.sqrt\(n\)/,
      );
    },
  );

  it("offers the standard two-sided 95 % Student-t multipliers", () => {
    expect(T_95[2]).toBe(4.303);
    expect(T_95[4]).toBe(2.776);
    expect(T_95[9]).toBe(2.262);
  });
});

describe("example data (illustrative, not a study result)", () => {
  it("is inconclusive after 3 runs and separated after 10", () => {
    const three = pairedReading(
      EXAMPLE_TWO.a.slice(0, 3),
      EXAMPLE_TWO.b.slice(0, 3),
    );
    expect(three.reading).toBe("inconclusive");
    expect(three.ciLow).toBeLessThan(0);
    expect(three.ciHigh).toBeGreaterThan(0);
    expect(three.meanDifference).toBeCloseTo(3.33, 2);
    expect(three.ciLow).toBeCloseTo(-9.17, 1);
    expect(three.ciHigh).toBeCloseTo(15.84, 1);

    const ten = pairedReading(EXAMPLE_TWO.a, EXAMPLE_TWO.b);
    expect(ten.reading).toBe("higher");
    expect(ten.ciLow).toBeGreaterThan(0);
    expect(ten.meanDifference).toBeCloseTo(4.6, 2);
    expect(ten.ciLow).toBeCloseTo(2.31, 1);
    expect(ten.ciHigh).toBeCloseTo(6.89, 1);
  });

  it("shows each reading once across the three pairs", () => {
    const readings = Object.fromEntries(
      EXAMPLE_PAIRS.map((p) => [
        p.key,
        pairedReading(EXAMPLE_THREE[p.a], EXAMPLE_THREE[p.b]),
      ]),
    );
    expect(readings.adaptive_vs_fixed_time.reading).toBe("lower");
    expect(readings.adaptive_vs_fixed_time.meanDifference).toBeCloseTo(-6.4, 2);
    expect(readings.adaptive_vs_roundabout.reading).toBe("tie");
    expect(readings.fixed_time_vs_roundabout.reading).toBe("inconclusive");
    expect(readings.fixed_time_vs_roundabout.ciLow).toBeLessThan(0);
  });

  it("uses the same words as a study", () => {
    expect(readingWords("lower", "Adaptive", "Fixed-time")).toBe(
      "Adaptive lower",
    );
    expect(readingWords("higher", "Adaptive", "Fixed-time")).toBe(
      "Fixed-time lower",
    );
    expect(readingWords("tie", "A", "B")).toBe("About the same");
    expect(readingWords("inconclusive", "A", "B")).toBe("Inconclusive");
  });
});
