import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { prettyName, seriesColour } from "../components/dashboard/format";
import {
  provenanceCounts,
  simulatedTime,
} from "../components/copilot/proposalStats";
import { failureSums } from "../components/stress/stressStats";
import {
  daysLeft,
  lifeLeft,
  scopeCoverage,
} from "../components/tokens/tokenStats";
import type { ExperimentProposal } from "../services/v3/copilot";
import type { SuiteResult } from "../services/v3/stress";
import type { TokenMetadata } from "../services/v3/tokens";

const listJobs = vi.fn();
const startSuite = vi.fn();
const getJob = vi.fn();
const getJobResult = vi.fn();

vi.mock("../services/v3/stress", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../services/v3/stress")>()),
  listJobs: () => listJobs() as Promise<unknown>,
  startSuite: (b: unknown) => startSuite(b) as Promise<unknown>,
  getJob: (id: string) => getJob(id) as Promise<unknown>,
  getJobResult: (id: string) => getJobResult(id) as Promise<unknown>,
}));

import { StressLabPage } from "../components/stress/StressLabPage";

describe("dashboard helpers", () => {
  it("names strategies and keeps one colour per strategy", () => {
    expect(prettyName("baseline:fixed_time")).toBe("Fixed time");
    expect(seriesColour("baseline:roundabout")).toBe(
      seriesColour("roundabout"),
    );
    expect(seriesColour("something_new", 1)).toMatch(/^var\(/);
  });

  it("formats simulated time", () => {
    expect(simulatedTime(45)).toBe("45 s");
    expect(simulatedTime(600)).toBe("10 min");
    expect(simulatedTime(23040)).toBe("6.4 h");
  });

  it("counts proposal fields by source, defaulting to rule", () => {
    const counts = provenanceCounts({
      fieldProvenance: { alternatives: "user", aggression: "model" },
    } as unknown as ExperimentProposal);
    expect(counts).toEqual({ user: 1, model: 1, rule: 7 });
  });

  it("sums failures per strategy", () => {
    const sums = failureSums({
      strategies: ["a", "b"],
      failureTotals: { a: { gridlock: 2, spillback: 1 }, b: {} },
    } as unknown as SuiteResult);
    expect(sums).toEqual({ a: 3, b: 0 });
  });

  it("computes token expiry and scope coverage", () => {
    const now = Date.parse("2026-10-27T00:00:00Z");
    const t: TokenMetadata = {
      id: "1",
      name: "x",
      scopes: ["experiments:read", "experiments:run"],
      createdAt: "2026-10-17T00:00:00Z",
      expiresAt: "2026-11-06T00:00:00Z",
      lastUsedAt: null,
    };
    expect(daysLeft(t.expiresAt, now)).toBe(10);
    expect(lifeLeft(t, now)).toBeCloseTo(0.5);
    expect(daysLeft(t.expiresAt, Date.parse("2027-01-01T00:00:00Z"))).toBe(0);
    const cover = scopeCoverage([
      t,
      { ...t, id: "2", scopes: ["experiments:read"] },
    ]);
    expect(cover["experiments:read"]).toBe(2);
    expect(cover["experiments:run"]).toBe(1);
    expect(cover["tokens:manage"]).toBe(0);
  });
});

const job = {
  id: "j1",
  kind: "suite",
  status: "completed",
  createdAt: "2026-10-27T00:00:00+00:00",
  runs: 32,
  resultAvailable: true,
  error: null,
};

const suite: SuiteResult = {
  format: "urbanflow-stress-suite",
  generator: "gen-v1",
  seed: 1,
  suiteFingerprint: "fp123",
  strategies: ["fixed_time", "adaptive"],
  rules: { gridlock: "Mean delay above the limit" },
  failureTotals: { fixed_time: { gridlock: 2 }, adaptive: { gridlock: 0 } },
  scenarios: [
    {
      index: 0,
      family: "surge",
      name: "Surge 1",
      results: {
        fixed_time: { failures: { gridlock: 1 }, meanDelay: 40, runErrors: 0 },
        adaptive: { failures: {}, meanDelay: 12.5, runErrors: 0 },
      },
    },
  ],
  note: "Stationary extremes.",
};

describe("StressLabPage", () => {
  beforeEach(() => {
    listJobs.mockResolvedValue([job]);
    startSuite.mockResolvedValue({ ...job, status: "queued" });
    getJob.mockResolvedValue(job);
    getJobResult.mockResolvedValue(suite);
  });

  it("starts a suite and summarises failures from the server's numbers", async () => {
    const user = userEvent.setup();
    render(<StressLabPage />);
    expect(await screen.findByText(/32 runs/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Run stress suite/ }));
    expect(startSuite).toHaveBeenCalledWith({
      seed: 1,
      count: 8,
      seedsPerRun: 2,
    });
    expect(await screen.findByText("Failures found")).toBeInTheDocument();
    expect(screen.getByText("Fewest failures")).toBeInTheDocument();
    expect(screen.getByText("Adaptive")).toBeInTheDocument();
    expect(screen.getByText("40.0 s · gridlock")).toBeInTheDocument();
  });

  it("shows an empty state when there are no jobs", async () => {
    listJobs.mockResolvedValue([]);
    render(<StressLabPage />);
    expect(await screen.findByText("No jobs yet")).toBeInTheDocument();
  });
});
