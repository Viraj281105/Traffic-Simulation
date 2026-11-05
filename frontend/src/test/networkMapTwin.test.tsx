import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../config", () => ({ API_BASE_URL: "" }));
vi.mock("../auth/cognito", () => ({ getAuthToken: () => Promise.resolve("") }));

import { corridorMap, gridFixture } from "../mapview/fixtures";
import { MapTab } from "../mapview/MapTab";
import { MapViewer } from "../mapview/MapViewer";
import { metricsFixture } from "../netmetrics/fixtures";
import { sampleObservations } from "../twinview/sample";
import { TwinDashboard } from "../twinview/TwinDashboard";
import {
  mildWhatIfFixture,
  quietTwinFixture,
  twinFixture,
  whatIfFixture,
} from "../twinview/fixtures";
import { parseObservations } from "../twinview/observations";
import { whatIfSummary } from "../twinview/text";
import { TwinTab } from "../twinview/TwinTab";
import { WhatIfPanel, WhatIfResultView } from "../twinview/WhatIfPanel";
import { axeViolations } from "./axe";
import { stubNet } from "./netApi";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("MapViewer", () => {
  it("draws every link and node and works without coordinates", () => {
    const { container } = render(
      <MapViewer map={corridorMap} perLink={metricsFixture.perLink} />,
    );
    expect(container.querySelectorAll("line[data-link]")).toHaveLength(5);
    expect(container.querySelectorAll("circle[data-node]")).toHaveLength(6);
    expect(container.querySelectorAll("circle.is-signal")).toHaveLength(2);
    expect(screen.getByText(/no real-world coordinates/)).toBeInTheDocument();
    expect(
      screen.getByText(/Highest average fullness: J1>J2 \(0.62\)/),
    ).toBeInTheDocument();
  });

  it("recolours by the chosen metric and has a legend", async () => {
    const { container } = render(
      <MapViewer map={corridorMap} perLink={metricsFixture.perLink} />,
    );
    const before = container
      .querySelector("line[data-link='J2>E']")
      ?.getAttribute("stroke");
    await userEvent.selectOptions(
      screen.getByLabelText("Colour roads by"),
      "length",
    );
    const after = container
      .querySelector("line[data-link='J2>E']")
      ?.getAttribute("stroke");
    expect(after).not.toBe(before);
    expect(
      screen.getByRole("group", { name: "Legend: Length" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Node kinds" })).toHaveTextContent(
      "gate, where vehicles enter or leave (4)",
    );
  });

  it("offers only geometry when the run gave no values", () => {
    render(<MapViewer map={gridFixture.map} />);
    const options = within(
      screen.getByLabelText("Colour roads by"),
    ).getAllByRole("option");
    expect(options.map((o) => o.getAttribute("value"))).toEqual([
      "length",
      "lanes",
      "speed",
    ]);
  });

  it("has no accessibility violations", async () => {
    const { container } = render(<MapViewer map={corridorMap} />);
    expect(await axeViolations(container)).toEqual([]);
  });
});

describe("MapTab", () => {
  it("shows the layout from GET /grid", async () => {
    const { calls } = stubNet({
      "GET /api/v2/network-metrics/grid?vehiclesPerHour=300&preset=3x3":
        gridFixture,
    });
    render(<MapTab />);
    await userEvent.click(
      screen.getByRole("button", { name: "Show layout only" }),
    );
    expect(
      await screen.findByRole("img", { name: /Map of Two-junction corridor/ }),
    ).toBeInTheDocument();
    expect(calls).toHaveLength(1);
  });

  it("runs the network with map data and colours by occupancy", async () => {
    const { calls } = stubNet({
      "POST /api/v2/network-metrics/simulate": metricsFixture,
    });
    render(<MapTab />);
    await userEvent.click(
      screen.getByRole("button", { name: "Run and colour the map" }),
    );
    expect(await screen.findByLabelText("Colour roads by")).toHaveValue(
      "value",
    );
    expect(calls[0]?.body).toMatchObject({ includeMap: true });
  });
});

describe("TwinDashboard", () => {
  it("shows MAE, MAPE, bias and the alert in plain words", () => {
    render(<TwinDashboard state={twinFixture} />);
    expect(
      screen.getByText("Average miss (MAE)").closest(".dash-stat"),
    ).toHaveTextContent("5.25");
    expect(
      screen.getByText("Average miss (MAPE)").closest(".dash-stat"),
    ).toHaveTextContent("18.6");
    expect(
      screen.getAllByText("Bias")[0].closest(".dash-stat"),
    ).toHaveTextContent("Predicts too few vehicles");
    expect(screen.getByRole("list", { name: "Alerts" })).toHaveTextContent(
      "At 180 s (window 3) the network total was off by 36.4%, more than the 25% allowed.",
    );
    expect(
      screen.getByText("The twin has drifted from what was observed."),
    ).toBeInTheDocument();
  });

  it("is calm when there are no alerts", () => {
    render(<TwinDashboard state={quietTwinFixture} />);
    expect(
      screen.getByText(/No alerts: no window was off by more than 25%/),
    ).toBeInTheDocument();
  });

  it("charts a chosen link and lists per-link scores", async () => {
    render(<TwinDashboard state={twinFixture} />);
    expect(
      screen.getByRole("img", { name: /summed over the observed links/ }),
    ).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText("Link"), "W>J1");
    expect(
      screen.getByRole("img", {
        name: "Predicted and observed vehicles per window on W>J1",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("rowheader", { name: "W>J1" }).closest("tr"),
    ).toHaveTextContent("3.25");
  });

  it("has no accessibility violations", async () => {
    const { container } = render(<TwinDashboard state={twinFixture} />);
    expect(await axeViolations(container)).toEqual([]);
  });
});

describe("what-if", () => {
  it("summarises a closure, with the unknown delay stated as unknown", () => {
    const text = whatIfSummary(whatIfFixture);
    expect(text).toContain("closing J1>J2 and scaling demand to 120%");
    expect(text).toContain("5 fewer vehicles finish their trips");
    expect(text).toContain("cannot be told");
    expect(text).toContain("6 vehicles would have no route");
  });

  it("shows baseline against variant with closed links marked", () => {
    render(<WhatIfResultView result={whatIfFixture} />);
    expect(
      screen.getByRole("rowheader", { name: "J1>J2" }).closest("tr"),
    ).toHaveTextContent("Closed");
    render(<WhatIfResultView result={mildWhatIfFixture} />);
    expect(screen.getAllByText(/\+7.4 s/).length).toBeGreaterThan(0);
  });

  it("posts the scenario with the comparison's observations", async () => {
    const { calls } = stubNet({ "POST /api/v2/twin/whatif": whatIfFixture });
    const base = { observations: sampleObservations(), intervalSeconds: 60 };
    render(<WhatIfPanel base={base} linkIds={["J1>J2", "W>J1"]} />);
    await userEvent.type(screen.getByLabelText(/Links to close/), "J1>J2");
    await userEvent.clear(screen.getByLabelText(/Demand/));
    await userEvent.type(screen.getByLabelText(/Demand/), "1.2");
    await userEvent.click(screen.getByRole("button", { name: "Run what-if" }));
    expect(await screen.findByText(/closing J1>J2/)).toBeInTheDocument();
    expect(calls[0]?.body).toMatchObject({
      scenario: { closeLinks: ["J1>J2"], demandScale: 1.2 },
      horizonWindows: 1,
      intervalSeconds: 60,
    });
  });
});

describe("TwinTab", () => {
  it("validates observations before calling the server", async () => {
    const { calls } = stubNet({});
    render(<TwinTab />);
    await userEvent.click(screen.getByRole("button", { name: "Compare" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "not valid JSON",
    );
    expect(calls).toHaveLength(0);
    expect(() => parseObservations('[{"linkId":"a"}]')).toThrow(
      "Observation 1 needs",
    );
  });

  it("compares the example observations and then offers the what-if", async () => {
    const { calls } = stubNet({
      "POST /api/v2/twin/compare": twinFixture,
      "POST /api/v2/twin/whatif": whatIfFixture,
    });
    render(<TwinTab />);
    expect(
      screen.getByText(/Compare some observations first/),
    ).toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: "Insert example observations" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Compare" }));
    expect(await screen.findByText("Average miss (MAE)")).toBeInTheDocument();
    expect(calls[0]?.body).toMatchObject({
      intervalSeconds: 60,
      alertThresholdPct: 25,
      observations: expect.arrayContaining([
        { linkId: "W>J1", timestamp: 0, count: 10 },
      ]) as unknown,
    });
    await userEvent.click(screen.getByRole("button", { name: "Run what-if" }));
    expect(
      await screen.findByText(/Over the next 1 window/),
    ).toBeInTheDocument();
  });
});
