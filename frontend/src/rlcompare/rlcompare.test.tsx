import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../config", () => ({ API_BASE_URL: "" }));
vi.mock("../auth/cognito", () => ({ getAuthToken: () => Promise.resolve("") }));

import { stubApi } from "../insights/testApi";
import { rlFixture } from "./fixtures";
import { RlComparisonChart, RlComparisonView } from "./RlComparisonChart";
import { rlHeadline } from "./rlText";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("rlHeadline", () => {
  it("names the winner, or says there is none", () => {
    expect(rlHeadline(rlFixture)).toBe("RL policy beats Fixed-time signal");
    expect(rlHeadline({ ...rlFixture, verdict: "fixed_better" })).toBe(
      "Fixed-time signal beats RL policy",
    );
    expect(
      rlHeadline({ ...rlFixture, verdict: "no_clear_difference" }),
    ).toMatch(/^No clear difference/);
  });
});

describe("RlComparisonView", () => {
  it("shows the overall gap with interval and p-value, and per-scenario intervals", () => {
    render(<RlComparisonView comparison={rlFixture} />);
    expect(screen.getByText(/-3.4 s per vehicle/)).toHaveTextContent(
      "95% interval: -5.9 to -0.9 s per vehicle; p = 0.009",
    );
    expect(screen.getByText("Peak demand")).toBeInTheDocument();
    expect(screen.getByText("27.1 (25.9 to 28.3)")).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: /95% confidence intervals/ }),
    ).toBeInTheDocument();
    expect(screen.getByText(/not shown to transfer/)).toBeInTheDocument();
  });
});

describe("RlComparisonChart", () => {
  it("loads the comparison from the contract URL", async () => {
    const { calls } = stubApi({
      "GET /api/v3/rl/comparisons/rl1": rlFixture,
    });
    render(<RlComparisonChart comparisonId="rl1" />);
    expect(
      await screen.findByText("RL policy beats Fixed-time signal"),
    ).toBeInTheDocument();
    expect(calls[0]?.key).toBe("GET /api/v3/rl/comparisons/rl1");
  });
});
