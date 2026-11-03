import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { BreakpointView } from "../components/stress/StressLabPage";
import type { BreakpointResult } from "../services/v3/stress";

const result = (flags: (boolean | undefined)[]): BreakpointResult => ({
  format: "urbanflow-breakpoints",
  factor: "demand_scale",
  strategies: ["fixed_time", "roundabout"],
  seedsPerLevel: 3,
  table: flags.map((flag, i) => ({
    level: [0.5, 1, 1.5][i] ?? i,
    meanDelay: { fixed_time: 50, roundabout: 30 },
    preferred: "roundabout",
    preferenceShare: { fixed_time: 0, roundabout: 1 },
    preferredServedLess: flag,
  })),
  breakpoints: [],
  tooFewToAssess: null,
  note: "",
});

describe("stress breakpoints: preferred strategy that served less", () => {
  it("marks only the levels where the lowest-delay strategy served less", () => {
    render(<BreakpointView result={result([true, false, undefined])} />);
    expect(screen.getAllByText(/served less of the demand/)).toHaveLength(1);
  });
});
