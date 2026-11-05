import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../config", () => ({ API_BASE_URL: "" }));
vi.mock("../auth/cognito", () => ({ getAuthToken: () => Promise.resolve("") }));

import { metricsFixture } from "../netmetrics/fixtures";
import { MetricsTab } from "../netmetrics/MetricsTab";
import {
  FundamentalDiagramChart,
  NetworkMetricsPanel,
  PerLinkTable,
} from "../netmetrics/NetworkMetricsPanel";
import { axeViolations } from "./axe";
import { stubNet } from "./netApi";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("NetworkMetricsPanel", () => {
  it("shows the network KPIs and says every vehicle is accounted for", () => {
    render(<NetworkMetricsPanel metrics={metricsFixture} />);
    expect(
      screen.getByText("Throughput").closest(".dash-stat"),
    ).toHaveTextContent("630");
    expect(
      screen.getByText("Mean delay").closest(".dash-stat"),
    ).toHaveTextContent("19.6");
    expect(screen.getByText(/38 vehicles were generated/)).toHaveTextContent(
      "Every vehicle is accounted for.",
    );
  });

  it("shows a missing mean delay as unavailable, never zero", () => {
    render(
      <NetworkMetricsPanel
        metrics={{
          ...metricsFixture,
          network: {
            ...metricsFixture.network,
            meanDelaySeconds: null,
            meanTravelSeconds: null,
          },
        }}
      />,
    );
    expect(
      screen.getByText("Mean delay").closest(".dash-stat"),
    ).toHaveTextContent("Not available");
  });

  it("warns when the vehicle count did not balance", () => {
    render(
      <NetworkMetricsPanel
        metrics={{
          ...metricsFixture,
          network: { ...metricsFixture.network, conserved: false },
        }}
      />,
    );
    expect(screen.getByText(/did not balance/)).toBeInTheDocument();
  });

  it("has no accessibility violations", async () => {
    const { container } = render(
      <NetworkMetricsPanel metrics={metricsFixture} />,
    );
    expect(await axeViolations(container)).toEqual([]);
  });
});

describe("FundamentalDiagramChart", () => {
  it("plots one dot per bucket and marks the busiest", () => {
    const { container } = render(
      <FundamentalDiagramChart diagram={metricsFixture.fundamentalDiagram} />,
    );
    expect(container.querySelectorAll("circle.nw-dot")).toHaveLength(4);
    expect(container.querySelectorAll("circle.is-peak")).toHaveLength(1);
    expect(
      screen.getByRole("img", { name: /highest flow 310 vehicles per hour/ }),
    ).toBeInTheDocument();
  });

  it("says so when there are no points", () => {
    render(
      <FundamentalDiagramChart
        diagram={{ bucketSeconds: 30, points: [], peakFlow: null }}
      />,
    );
    expect(
      screen.getByText("There are no points to plot."),
    ).toBeInTheDocument();
  });
});

describe("PerLinkTable", () => {
  it("sorts by fullness first and re-sorts by name", async () => {
    render(<PerLinkTable perLink={metricsFixture.perLink} />);
    const names = () =>
      within(screen.getByRole("table"))
        .getAllByRole("row")
        .slice(1)
        .map((r) => within(r).getAllByRole("rowheader")[0].textContent);
    expect(names()[0]).toBe("J1>J2");
    await userEvent.selectOptions(screen.getByLabelText("Sort links by"), "id");
    expect(names()).toEqual(["J1>J2", "J2>E", "J2>S2", "N1>J1", "W>J1"]);
  });
});

describe("MetricsTab", () => {
  it("runs the grid and shows the metrics", async () => {
    const { calls } = stubNet({
      "POST /api/v2/network-metrics/simulate": metricsFixture,
    });
    render(<MetricsTab />);
    await userEvent.click(screen.getByRole("button", { name: "Run network" }));
    expect(await screen.findByText("Fundamental diagram")).toBeInTheDocument();
    expect(calls[0]?.body).toMatchObject({
      grid: { preset: "3x3", vehiclesPerHour: 300 },
      includeMap: true,
    });
  });
});
