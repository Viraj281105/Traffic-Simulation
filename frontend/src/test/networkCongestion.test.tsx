import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../config", () => ({ API_BASE_URL: "" }));
vi.mock("../auth/cognito", () => ({ getAuthToken: () => Promise.resolve("") }));

import { congestionFixture } from "../congestion/fixtures";
import { CongestionHeatmap } from "../congestion/CongestionHeatmap";
import { CongestionTab } from "../congestion/CongestionTab";
import { CongestionView } from "../congestion/CongestionView";
import { spreadSummary } from "../congestion/spreadText";
import { axeViolations } from "./axe";
import { failWith, stubNet } from "./netApi";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("spreadSummary", () => {
  it("tells the spread in plain words from the server's numbers", () => {
    const [first, reach, spill] = spreadSummary(congestionFixture);
    expect(first).toContain("Congestion first formed on J1>J2 at 38 s");
    expect(first).toContain("3 of 5 links");
    expect(reach).toContain("46 s");
    expect(reach).toContain("350 m");
    expect(reach).toContain("6.1 m/s");
    expect(spill).toContain("2 times on 2 links");
    expect(spill).toContain("38 s in total");
  });

  it("says so when nothing congested and nothing backed up", () => {
    const quiet = {
      ...congestionFixture,
      spread: {
        ...congestionFixture.spread,
        congestedLinks: 0,
        origin: null,
        order: [],
      },
      spillback: {
        events: [],
        summary: { ...congestionFixture.spillback.summary, events: 0 },
      },
    };
    const lines = spreadSummary(quiet);
    expect(lines[0]).toMatch(/no congestion spread was found/);
    expect(lines[1]).toMatch(/no spillback/);
  });
});

describe("CongestionHeatmap", () => {
  it("draws one cell per link and time bucket, first-congested link on top", () => {
    const { container } = render(
      <CongestionHeatmap heatmap={congestionFixture.heatmap} />,
    );
    expect(container.querySelectorAll("rect[data-cell]")).toHaveLength(5 * 4);
    expect(
      screen.getByRole("img", {
        name: /each of 5 links was in each of 4 time buckets/,
      }),
    ).toBeInTheDocument();
    const firstRow = container.querySelector("rect[data-cell]");
    expect(firstRow).toHaveAttribute("data-cell", "J1>J2@0");
    expect(
      container.querySelector("[data-cell='J1>J2@90'] title"),
    ).toHaveTextContent("85% full");
  });
});

describe("CongestionView", () => {
  it("lists links in congestion order and the spillback events", () => {
    render(<CongestionView result={congestionFixture} />);
    const table = screen.getByRole("table", { name: /became congested/ });
    const rows = within(table).getAllByRole("row");
    expect(within(rows[1]).getByText("J1>J2")).toBeInTheDocument();
    expect(within(rows[1]).getByText("88%")).toBeInTheDocument();
    expect(
      within(rows[2]).getByText("Backwards along the road"),
    ).toBeInTheDocument();
    expect(within(rows[4]).getByText("Not congested")).toBeInTheDocument();
    const events = within(
      screen.getByRole("list", { name: "Spillback events" }),
    );
    expect(events.getAllByRole("listitem")).toHaveLength(2);
    expect(events.getByText(/from 74 s to 96 s/)).toBeInTheDocument();
  });

  it("has no accessibility violations", async () => {
    const { container } = render(<CongestionView result={congestionFixture} />);
    expect(await axeViolations(container)).toEqual([]);
  });
});

describe("CongestionTab", () => {
  it("posts the scenario and the chosen threshold, then shows the result", async () => {
    const { calls } = stubNet({
      "POST /api/v2/network-metrics/congestion": congestionFixture,
    });
    render(<CongestionTab />);
    await userEvent.click(
      screen.getByRole("button", { name: "Analyse congestion" }),
    );
    expect(
      await screen.findByText(/Congestion first formed on J1>J2/),
    ).toBeInTheDocument();
    expect(calls[0]?.body).toMatchObject({
      grid: { preset: "3x3", vehiclesPerHour: 900 },
      duration: 600,
      seed: 1,
      includeMap: true,
      threshold: 0.3,
    });
  });

  it("shows the server's reason when the run is refused", async () => {
    stubNet({
      "POST /api/v2/network-metrics/congestion": failWith(
        422,
        "At most 400 nodes are allowed",
      ),
    });
    render(<CongestionTab />);
    await userEvent.click(
      screen.getByRole("button", { name: "Analyse congestion" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "At most 400 nodes are allowed",
    );
  });
});
