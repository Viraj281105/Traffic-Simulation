import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../config", () => ({ API_BASE_URL: "" }));
vi.mock("../auth/cognito", () => ({ getAuthToken: () => Promise.resolve("") }));

import { stubApi } from "../insights/testApi";
import { metricsFixture } from "./fixtures";
import { RunMetricsSection, RunMetricsView } from "./MetricPanels";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("RunMetricsView", () => {
  it("shows delay and travel-time cards with their intervals", () => {
    render(<RunMetricsView metrics={metricsFixture} />);
    expect(screen.getByText("Average delay")).toBeInTheDocument();
    expect(screen.getByText("18.4")).toBeInTheDocument();
    expect(screen.getByText("Interval: 17.1 to 19.7 s")).toBeInTheDocument();
    expect(screen.getByText("61.2")).toBeInTheDocument();
    expect(screen.getByText(/1,840 vehicles/)).toBeInTheDocument();
  });

  it("labels safety as a proxy and emissions as an estimate", () => {
    render(<RunMetricsView metrics={metricsFixture} />);
    expect(
      screen.getByText("Proxy measure, not crash data"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Model estimate, not a measurement"),
    ).toBeInTheDocument();
    expect(screen.getByText("Encounters under 1.5 s")).toBeInTheDocument();
    expect(screen.getByText(/not measured emissions/)).toBeInTheDocument();
    expect(
      screen.getByText("Light vehicles only; no cold-start effects."),
    ).toBeInTheDocument();
  });

  it("shows a missing value as not available, never as zero", () => {
    render(<RunMetricsView metrics={metricsFixture} />);
    // CO2 per vehicle is null in the fixture.
    expect(screen.getAllByText("Not available")).toHaveLength(1);
  });
});

describe("RunMetricsSection", () => {
  it("loads the run's metrics from the contract URL", async () => {
    const { calls } = stubApi({
      "GET /api/v3/runs/run1/metrics": metricsFixture,
    });
    render(<RunMetricsSection runId="run1" />);
    expect(
      await screen.findByText("Delay and travel time"),
    ).toBeInTheDocument();
    expect(calls[0]?.key).toBe("GET /api/v3/runs/run1/metrics");
  });

  it("explains when the run has no metrics yet", async () => {
    stubApi({});
    render(<RunMetricsSection runId="run1" />);
    expect(await screen.findByText("No metrics yet")).toBeInTheDocument();
  });
});
