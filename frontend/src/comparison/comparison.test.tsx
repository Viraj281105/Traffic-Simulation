import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../config", () => ({ API_BASE_URL: "" }));
vi.mock("../auth/cognito", () => ({ getAuthToken: () => Promise.resolve("") }));

import { failWith, stubApi } from "../insights/testApi";
import { ComparisonBlock, ComparisonView } from "./ComparisonBlock";
import { getComparison } from "./api";
import { describeComparison } from "./comparisonText";
import { comparisonFixture } from "./fixtures";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("describeComparison", () => {
  it("states the winner, the interval and the p-value in words", () => {
    const words = describeComparison(comparisonFixture);
    expect(words.headline).toBe("Adaptive signal beats Fixed-time signal");
    expect(words.sentence).toContain("4.2 s per vehicle lower average delay");
    expect(words.sentence).toContain("95% confident");
    expect(words.sentence).toContain("-7.3 to -1.1 s per vehicle");
    expect(words.pValue).toContain("p = 0.012");
    expect(words.pValue).toContain("1.2%");
    expect(words.method).toContain("Paired t-test on 30 paired observations");
  });

  it("says higher when higher is better, and names B when B wins", () => {
    const words = describeComparison({
      ...comparisonFixture,
      metric: { ...comparisonFixture.metric, lowerIsBetter: false },
      verdict: "b_better",
    });
    expect(words.headline).toBe("Fixed-time signal beats Adaptive signal");
    expect(words.sentence).toContain("higher average delay");
  });

  it("does not declare a winner when the interval includes zero", () => {
    const words = describeComparison({
      ...comparisonFixture,
      meanDifference: -0.6,
      ci: [-2.1, 0.9],
      pValue: 0.41,
      verdict: "no_clear_difference",
      eligibility: "indicative",
    });
    expect(words.headline).toMatch(/^No clear winner/);
    expect(words.sentence).toContain("includes zero");
    expect(words.pValue).toContain("p = 0.41");
  });
});

describe("ComparisonBlock", () => {
  it("loads from the contract URL and shows the result", async () => {
    const { calls } = stubApi({
      "GET /api/v3/experiments/exp1/comparison": comparisonFixture,
    });
    render(<ComparisonBlock experimentId="exp1" />);
    expect(
      await screen.findByText("Adaptive signal beats Fixed-time signal"),
    ).toBeInTheDocument();
    expect(calls[0]?.key).toBe("GET /api/v3/experiments/exp1/comparison");
    expect(screen.getByText("Eligible")).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: /Gap in average delay/ }),
    ).toBeInTheDocument();
  });

  it("passes the chosen alternatives and metric as query parameters", async () => {
    const { calls } = stubApi({});
    await getComparison("e 2", { a: "x", b: "y", metric: "mean_delay" }).catch(
      () => undefined,
    );
    expect(calls[0]?.key).toBe(
      "GET /api/v3/experiments/e%202/comparison?a=x&b=y&metric=mean_delay",
    );
  });

  it("shows an empty state when the comparison does not exist yet", async () => {
    stubApi({});
    render(<ComparisonBlock experimentId="missing" />);
    expect(await screen.findByText("No comparison yet")).toBeInTheDocument();
  });

  it("shows the server's reason when the request fails", async () => {
    stubApi({
      "GET /api/v3/experiments/exp1/comparison": failWith(500, "Store offline"),
    });
    render(<ComparisonBlock experimentId="exp1" />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Store offline");
  });

  it("renders from data in hand", () => {
    render(<ComparisonView result={comparisonFixture} />);
    expect(screen.getByText(/95% confidence interval/)).toBeInTheDocument();
  });
});
