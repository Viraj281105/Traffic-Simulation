import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../config", () => ({ API_BASE_URL: "" }));
vi.mock("../auth/cognito", () => ({ getAuthToken: () => Promise.resolve("") }));

import { comparisonFixture } from "../comparison/fixtures";
import { sensitivityFixture } from "../sensitivity/fixtures";
import { VIEW_ROUTES, resolveRoute } from "../routing";
import { axeViolations } from "../test/axe";
import { InsightsPage } from "./InsightsPage";
import { IntervalPlot } from "./IntervalPlot";
import { num, pValueText } from "./format";
import { stubApi } from "./testApi";

function visit(search: string) {
  act(() => {
    window.history.replaceState(null, "", `${VIEW_ROUTES.insights}${search}`);
  });
}

beforeEach(() => {
  visit("");
});
afterEach(() => {
  vi.unstubAllGlobals();
});

describe("format", () => {
  it("formats p-values and missing numbers", () => {
    expect(pValueText(0.012)).toBe("p = 0.012");
    expect(pValueText(0.0004)).toBe("p < 0.001");
    expect(pValueText(0.5)).toBe("p = 0.5");
    expect(pValueText(null)).toBe("p-value not available");
    expect(num(null)).toBe("Not available");
    expect(num(0)).toBe("0");
  });
});

describe("route", () => {
  it("resolves /app/insights to the insights view", () => {
    expect(resolveRoute("/app/insights")).toEqual({
      kind: "view",
      view: "insights",
    });
  });
});

describe("IntervalPlot", () => {
  it("draws a missing value as not available instead of zero", () => {
    render(
      <IntervalPlot
        rows={[{ id: "x", label: "Thing", value: null }]}
        unit="s"
        ariaLabel="plot"
      />,
    );
    expect(screen.getByText("not available")).toBeInTheDocument();
  });
});

describe("InsightsPage", () => {
  it("opens on Results and asks for an experiment", () => {
    render(<InsightsPage />);
    expect(screen.getByRole("tab", { name: "Results" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByLabelText("Experiment ID")).toBeInTheDocument();
  });

  it("shows the comparison and sensitivity for the experiment in the address", async () => {
    stubApi({
      "GET /api/v3/experiments/exp1/comparison": comparisonFixture,
      "GET /api/v3/experiments/exp1/sensitivity": sensitivityFixture,
    });
    visit("?tab=results&experiment=exp1");
    render(<InsightsPage />);
    expect(
      await screen.findByText("Adaptive signal beats Fixed-time signal"),
    ).toBeInTheDocument();
    expect(
      await screen.findByText(/changes average delay/),
    ).toBeInTheDocument();
  });

  it("switches tabs through the address", async () => {
    render(<InsightsPage />);
    await userEvent.click(screen.getByRole("tab", { name: "Networks" }));
    expect(window.location.search).toBe("?tab=network");
    expect(await screen.findByText("Upload a network")).toBeInTheDocument();
    expect(
      screen.getByText("Import roads from OpenStreetMap"),
    ).toBeInTheDocument();
  });

  it("has no automatically detectable accessibility violations", async () => {
    visit("?tab=network");
    const { container } = render(<InsightsPage />);
    expect(await axeViolations(container)).toEqual([]);
  });
});
