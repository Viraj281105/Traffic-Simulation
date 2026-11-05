import { render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../config", () => ({ API_BASE_URL: "" }));
vi.mock("../auth/cognito", () => ({ getAuthToken: () => Promise.resolve("") }));

import { stubApi } from "../insights/testApi";
import { nightlyFixture } from "./fixtures";
import {
  NightlyRegressionTable,
  NightlyRegressionView,
} from "./NightlyRegressionView";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("NightlyRegressionTable", () => {
  it("summarises the latest night and how many did not pass", () => {
    render(<NightlyRegressionTable data={nightlyFixture} />);
    expect(
      screen.getByText(/2 of the last 3 nights did not pass/),
    ).toBeInTheDocument();
    const strip = screen.getByRole("list", { name: /Last nights/ });
    expect(within(strip).getAllByRole("img")).toHaveLength(3);
  });

  it("explains what went wrong with expected and actual values", () => {
    render(<NightlyRegressionTable data={nightlyFixture} />);
    expect(
      screen.getByText(/Average delay moved outside the allowed range/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Expected 21.4 s, got 24.9 s \(allowed difference 1\)/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/The golden file could not be read/),
    ).toBeInTheDocument();
  });

  it("handles no runs", () => {
    render(
      <NightlyRegressionTable
        data={{ generatedAt: "2026-11-04T00:00:00Z", runs: [] }}
      />,
    );
    expect(screen.getByText("No nightly runs yet")).toBeInTheDocument();
  });
});

describe("NightlyRegressionView", () => {
  it("loads the nightly results with the limit in the query", async () => {
    const { calls } = stubApi({
      "GET /api/v3/regression/nightly?limit=30": nightlyFixture,
    });
    render(<NightlyRegressionView />);
    expect(await screen.findByText("Nightly regression")).toBeInTheDocument();
    expect(await screen.findByText(/Latest night/)).toBeInTheDocument();
    expect(calls[0]?.key).toBe("GET /api/v3/regression/nightly?limit=30");
  });
});
