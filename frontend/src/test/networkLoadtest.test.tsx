import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../config", () => ({ API_BASE_URL: "" }));
vi.mock("../auth/cognito", () => ({ getAuthToken: () => Promise.resolve("") }));

import { parseLoadTest } from "../loadtest/api";
import { failingSummary, passingSummary } from "../loadtest/fixtures";
import { LoadTestDashboard } from "../loadtest/LoadTestDashboard";
import { LoadTestTab } from "../loadtest/LoadTestTab";
import { axeViolations } from "./axe";
import { failWith, stubNet } from "./netApi";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("LoadTestDashboard", () => {
  it("shows p95 latency, error rate, VUs and passing thresholds", () => {
    render(<LoadTestDashboard summary={passingSummary} />);
    expect(screen.getByRole("status")).toHaveTextContent(
      "ALL THRESHOLDS PASSED",
    );
    expect(
      screen.getByText("95th percentile response time").closest(".dash-stat"),
    ).toHaveTextContent("403");
    expect(
      screen.getAllByText("Error rate")[0].closest(".dash-stat"),
    ).toHaveTextContent("0.09%");
    expect(
      screen.getByText("Virtual users").closest(".dash-stat"),
    ).toHaveTextContent("20");
    expect(screen.getAllByText("Pass")).toHaveLength(2);
    expect(
      screen.getByText("POST /api/v2/network-metrics/simulate"),
    ).toBeInTheDocument();
  });

  it("marks failed thresholds", () => {
    render(<LoadTestDashboard summary={failingSummary} />);
    expect(screen.getAllByRole("status")[0]).toHaveTextContent(
      "2 OF 2 THRESHOLDS FAILED",
    );
    expect(screen.getAllByText("Fail")).toHaveLength(2);
  });

  it("shows a missing latency as unavailable, not zero", () => {
    render(
      <LoadTestDashboard
        summary={{
          ...passingSummary,
          latencyMs: { ...passingSummary.latencyMs, p95: null },
        }}
      />,
    );
    expect(
      screen.getByText("95th percentile response time").closest(".dash-stat"),
    ).toHaveTextContent("Not available");
  });

  it("has no accessibility violations", async () => {
    const { container } = render(
      <LoadTestDashboard summary={failingSummary} />,
    );
    expect(await axeViolations(container)).toEqual([]);
  });
});

describe("parseLoadTest", () => {
  it("accepts the contract and refuses other JSON", () => {
    expect(parseLoadTest(JSON.stringify(passingSummary)).scenario).toBe(
      "network-metrics-smoke",
    );
    expect(() => parseLoadTest("[")).toThrow("not valid JSON");
    expect(() => parseLoadTest("{}")).toThrow("urbanflow-loadtest-summary");
  });
});

describe("LoadTestTab", () => {
  it("reads the newest summary from /api/v3/loadtests/latest", async () => {
    const { calls } = stubNet({
      "GET /api/v3/loadtests/latest": passingSummary,
    });
    render(<LoadTestTab />);
    expect(
      await screen.findByText(/network-metrics-smoke against/),
    ).toBeInTheDocument();
    expect(calls[0]?.key).toBe("GET /api/v3/loadtests/latest");
  });

  it("says no result is published yet on a 404", async () => {
    stubNet({ "GET /api/v3/loadtests/latest": failWith(404, "none") });
    render(<LoadTestTab />);
    expect(await screen.findByText("No load test yet")).toBeInTheDocument();
  });

  it("opens a summary file", async () => {
    stubNet({});
    render(<LoadTestTab />);
    await screen.findByText("No load test yet");
    const file = new File([JSON.stringify(failingSummary)], "s.json", {
      type: "application/json",
    });
    await userEvent.upload(
      screen.getByLabelText("Load-test summary file"),
      file,
    );
    expect(
      await screen.findByText(/2 OF 2 THRESHOLDS FAILED/),
    ).toBeInTheDocument();
  });

  it("explains a file that is not a summary", async () => {
    stubNet({});
    render(<LoadTestTab />);
    await screen.findByText("No load test yet");
    const file = new File(["{}"], "s.json", { type: "application/json" });
    await userEvent.upload(
      screen.getByLabelText("Load-test summary file"),
      file,
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "not a load-test summary",
    );
  });
});
