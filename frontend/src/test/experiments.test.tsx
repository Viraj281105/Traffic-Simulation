import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type {
  ExperimentResult,
  ExperimentStatus,
} from "../services/v3/experiments";

const getExperiment = vi.fn();
const getExperimentResult = vi.fn();

vi.mock("../services/v3/experiments", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../services/v3/experiments")>()),
  getExperiment: (id: string) => getExperiment(id) as Promise<unknown>,
  getExperimentResult: (id: string) =>
    getExperimentResult(id) as Promise<unknown>,
}));

import { ExperimentsApiError } from "../services/v3/experiments";
import { ExperimentPage } from "../components/experiments/ExperimentPage";
import { axeViolations } from "./axe";
import {
  EXPERIMENTS_PREFIX,
  VIEW_ROUTES,
  experimentPath,
  resolveRoute,
} from "../routing";
import nginxTemplate from "../../templates/default.conf.template?raw";

const ID = "0f3c9a1e11114222833394444555566";

const completed: ExperimentStatus = {
  id: ID,
  name: "Peak hour robustness",
  status: "completed",
  error: null,
  createdAt: "2026-10-15T10:00:00+00:00",
  counts: { conditions: 10, alternatives: 3, replications: 1, totalRuns: 30 },
  specFingerprint: "abcdef0123456789",
  resultAvailable: true,
  progress: null,
};

const LIMITATIONS = [
  "Every input distribution is an assumption of the analyst, not an estimate from data.",
  "The unit of inference is the sampled condition, not the simulation run.",
];

// The planted dataset of backend/tests/uncertainty/test_analysis.py (every number computed by hand).
const result: ExperimentResult = {
  experimentId: ID,
  name: "Peak hour robustness",
  scenario: { name: "Test junction", fingerprint: "1111222233334444" },
  alternatives: [
    {
      id: "base",
      label: "Fixed-time signal",
      strategy: "fixed_time",
      isBaseline: true,
      fingerprint: "a",
      changesFromBase: [],
    },
    {
      id: "A",
      label: "Adaptive signal",
      strategy: "adaptive",
      isBaseline: false,
      fingerprint: "b",
      changesFromBase: [],
    },
    {
      id: "B",
      label: "Roundabout",
      strategy: "roundabout",
      isBaseline: false,
      fingerprint: "c",
      changesFromBase: [],
    },
  ],
  baseline: "base",
  specFingerprint: "abcdef0123456789",
  assumptions: [
    {
      id: "demand",
      kind: "demand_scale",
      distribution: { kind: "uniform" },
      bounds: [0.8, 1.2],
      basis: "assumed",
      rationale: "plausible weekday variation",
    },
  ],
  analysis: {
    primaryIndicator: "averageDelay",
    lowerIsBetter: true,
    tolerance: { kind: "absolute", value: 1 },
    confidenceLevel: 0.95,
    baseline: "base",
    counts: {
      conditions: 10,
      validConditions: 10,
      alternatives: 3,
      replications: 1,
      totalRuns: 30,
    },
    exclusions: {
      excluded: 0,
      overallShare: 0,
      byReason: {},
      worstStratumShare: 0,
    },
    alternatives: {
      base: {
        isBaseline: true,
        meanOutcome: 24,
        regret: { mean: 4.04, p95: 5, sampleMax: 5 },
        preferenceShare: 0.2,
        comparison: null,
      },
      A: {
        isBaseline: false,
        meanOutcome: 22.35,
        regret: { mean: 2.39, p95: 5.2, sampleMax: 5.2 },
        preferenceShare: 0.5,
        comparison: {
          win: { count: 5, p: 0.5, ci: [0.2366, 0.7634] },
          tie: { count: 3, p: 0.3, ci: [0.1078, 0.6032] },
          loss: { count: 2, p: 0.2, ci: [0.0567, 0.5098] },
          difference: {
            mean: { value: -1.65, ci: [-4.5, 1.2] },
            median: { value: -2.75, ci: [-5, 0.5] },
            p5: { value: -5, ci: [-5, -5] },
            p95: { value: 5, ci: [0.5, 5] },
          },
        },
      },
      B: {
        isBaseline: false,
        meanOutcome: 22.71,
        regret: { mean: 2.75, p95: 5.5, sampleMax: 5.5 },
        preferenceShare: 0.5,
        comparison: {
          win: { count: 3, p: 0.3, ci: [0.1078, 0.6032] },
          tie: { count: 7, p: 0.7, ci: [0.3968, 0.8922] },
          loss: { count: 0, p: 0, ci: [0, 0.2775] },
          difference: {
            mean: { value: -1.29, ci: [-3.1, 0.1] },
            median: { value: 0.15, ci: [-5, 0.5] },
            p5: { value: -5, ci: [-5, -5] },
            p95: { value: 0.5, ci: [0.5, 0.5] },
          },
        },
      },
    },
    eligibility: {
      class: "exploratory",
      validConditions: 10,
      criteria: [
        { id: "precision", passed: false, detail: "largest half-width 0.265" },
        {
          id: "stability",
          passed: null,
          detail: "split-half stability is not computed in this version",
        },
        { id: "replications", passed: false, detail: "1 per condition" },
        { id: "exclusions", passed: true, detail: "0.0 % excluded overall" },
        { id: "predeclaration", passed: true, detail: "fixed before the run" },
      ],
    },
    realWorldValidity: "None — assumptions only",
    limitations: LIMITATIONS,
  },
  resultFingerprint: "fedcba9876543210",
  provenance: {
    gitCommit: "9086a9a0123456789abcdef0123456789abcdef0",
    pythonVersion: "3.14.7",
    sampling: "seeded Latin hypercube, stratified per factor",
    commonRandomNumbers: true,
    seedRule: "sha256(...)",
    note: "The full reproducibility manifest arrives in a later release.",
  },
  execution: {
    runsPlanned: 30,
    runsExecuted: 30,
    workers: 2,
    wallSeconds: 12.5,
  },
};

beforeEach(() => {
  getExperiment.mockReset();
  getExperimentResult.mockReset();
});

function ready() {
  getExperiment.mockResolvedValue(completed);
  getExperimentResult.mockResolvedValue(result);
}

describe("ExperimentPage: a finished experiment", () => {
  it("shows the name, the limitations banner and real-world validity first", async () => {
    ready();
    render(<ExperimentPage experimentId={ID} />);
    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: "Peak hour robustness",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Real-world validity: None — assumptions only"),
    ).toBeInTheDocument();
    const banner = screen.getByRole("region", { name: "Read this first" });
    for (const text of LIMITATIONS) {
      expect(within(banner).getByText(text)).toBeInTheDocument();
    }
    // the banner is the first section of the result
    const sections = screen.getAllByRole("region");
    expect(sections[0]).toBe(banner);
  });

  it("keeps conditions, replications and total runs separate", async () => {
    ready();
    render(<ExperimentPage experimentId={ID} />);
    const run = await screen.findByRole("region", { name: "What was run" });
    expect(within(run).getByText("Sampled conditions")).toBeInTheDocument();
    expect(
      within(run).getByText("Replications per condition"),
    ).toBeInTheDocument();
    expect(within(run).getByText("Total simulation runs")).toBeInTheDocument();
    expect(
      within(run).getByText(
        /10 conditions × 3 alternatives × 1 replications = 30 runs/,
      ),
    ).toBeInTheDocument();
    expect(
      within(run).getByText(/rests on 10 valid conditions, not on 30 runs/),
    ).toBeInTheDocument();
  });

  it("reports eligibility honestly, including what is not assessed", async () => {
    ready();
    render(<ExperimentPage experimentId={ID} />);
    const block = await screen.findByRole("region", {
      name: "Can this be called robust?",
    });
    expect(within(block).getByText(/Exploratory only\./)).toBeInTheDocument();
    const items = within(block).getAllByRole("listitem");
    expect(items).toHaveLength(5);
    expect(items[1]).toHaveTextContent(
      "Stability (split-half): Not assessed. Split-half stability is not computed",
    );
    expect(items[0]).toHaveTextContent("Precision: Not met.");
    expect(items[3]).toHaveTextContent("Excluded conditions: Met.");
    expect(
      within(block).queryByText(/Eligible for robustness statements/),
    ).not.toBeInTheDocument();
  });

  it("lists wins, ties and losses with their counts and intervals", async () => {
    ready();
    render(<ExperimentPage experimentId={ID} />);
    const table = await screen.findByRole("table", {
      name: /Share of the 10 valid conditions/,
    });
    const rows = within(table).getAllByRole("row");
    expect(rows).toHaveLength(3); // header + two alternatives (the baseline is the reference)
    const adaptive = within(rows[1]);
    expect(adaptive.getByRole("rowheader")).toHaveTextContent(
      "Adaptive signal",
    );
    const cells = adaptive.getAllByRole("cell");
    expect(cells[0]).toHaveTextContent("50 %");
    expect(cells[0]).toHaveTextContent("5 of 10");
    expect(cells[0]).toHaveTextContent("24 % to 76 %");
    expect(cells[1]).toHaveTextContent("30 %");
    expect(cells[2]).toHaveTextContent("20 %");
    expect(cells[3]).toHaveTextContent("−1.65 s");
    expect(cells[3]).toHaveTextContent("−4.50 to 1.20 s");
    expect(cells[4]).toHaveTextContent("−2.75 s");
    const roundabout = within(rows[2]).getAllByRole("cell");
    expect(roundabout[1]).toHaveTextContent("70 %");
    expect(roundabout[2]).toHaveTextContent("0 %");
  });

  it("shows regret and preference share for every alternative, baseline included", async () => {
    ready();
    render(<ExperimentPage experimentId={ID} />);
    const table = await screen.findByRole("table", {
      name: /Regret is how much worse/,
    });
    const rows = within(table).getAllByRole("row");
    expect(rows).toHaveLength(4);
    expect(rows[1]).toHaveTextContent("Fixed-time signal (baseline)");
    expect(rows[1]).toHaveTextContent("4.04 s");
    expect(rows[1]).toHaveTextContent("20 %");
    expect(rows[3]).toHaveTextContent("5.50 s");
  });

  it("shows the assumptions with their basis and reason", async () => {
    ready();
    render(<ExperimentPage experimentId={ID} />);
    const table = await screen.findByRole("table", {
      name: /Each factor was drawn from the range shown/,
    });
    const row = within(table).getAllByRole("row")[1];
    expect(row).toHaveTextContent("Demand (multiplier)");
    expect(row).toHaveTextContent("uniform");
    expect(row).toHaveTextContent("0.8 to 1.2");
    expect(row).toHaveTextContent("Assumed by the analyst");
    expect(row).toHaveTextContent("plausible weekday variation");
  });

  it("never names a winner or a best option", async () => {
    ready();
    const { container } = render(<ExperimentPage experimentId={ID} />);
    await screen.findByRole("heading", { level: 1 });
    expect(container.textContent).not.toMatch(
      /winner|the best option|recommend/i,
    );
  });

  it("says a number is unavailable instead of showing zero", async () => {
    const missing = structuredClone(result);
    missing.analysis.alternatives.A.regret = undefined;
    missing.analysis.alternatives.A.meanOutcome = undefined;
    missing.analysis.alternatives.A.preferenceShare = undefined;
    getExperiment.mockResolvedValue(completed);
    getExperimentResult.mockResolvedValue(missing);
    render(<ExperimentPage experimentId={ID} />);
    const table = await screen.findByRole("table", {
      name: /Regret is how much worse/,
    });
    const adaptive = within(table).getAllByRole("row")[2];
    expect(adaptive).toHaveTextContent("not available");
    expect(adaptive).not.toHaveTextContent("0.00 s");
  });

  it("handles an experiment with no valid condition", async () => {
    const empty = structuredClone(result);
    empty.analysis.counts.validConditions = 0;
    empty.analysis.alternatives.A.comparison = null;
    empty.analysis.alternatives.B.comparison = null;
    getExperiment.mockResolvedValue(completed);
    getExperimentResult.mockResolvedValue(empty);
    render(<ExperimentPage experimentId={ID} />);
    expect(
      (await screen.findAllByText("No valid condition to compare.")).length,
    ).toBe(2);
  });

  it("names why conditions were excluded, with the count for each reason", async () => {
    const excluded = structuredClone(result);
    excluded.analysis.counts.validConditions = 7;
    excluded.analysis.exclusions = {
      excluded: 3,
      overallShare: 0.3,
      byReason: { no_completed_vehicles: 2, run_failed: 1 },
      worstStratumShare: 0.5,
    };
    getExperiment.mockResolvedValue(completed);
    getExperimentResult.mockResolvedValue(excluded);
    render(<ExperimentPage experimentId={ID} />);
    const run = await screen.findByRole("region", { name: "What was run" });
    expect(run).toHaveTextContent(
      "3 (no vehicle finished its trip (the delay is undefined; the scenario may be too short): 2; a simulation failed: 1)",
    );
  });

  it("has no accessibility violations", async () => {
    ready();
    const { container } = render(<ExperimentPage experimentId={ID} />);
    await screen.findByRole("heading", { level: 1 });
    expect(await axeViolations(container)).toEqual([]);
  });
});

describe("ExperimentPage: other states", () => {
  it("follows a running experiment until it finishes", async () => {
    const running: ExperimentStatus = {
      ...completed,
      status: "running",
      resultAvailable: false,
      progress: {
        phase: "simulating",
        total: 30,
        completed: 12,
        fraction: 0.4,
        elapsedSeconds: 8,
      },
    };
    getExperiment
      .mockResolvedValueOnce(running)
      .mockResolvedValueOnce(running)
      .mockResolvedValue(completed);
    getExperimentResult.mockResolvedValue(result);
    render(<ExperimentPage experimentId={ID} pollMs={5} />);
    expect(
      await screen.findByText(/12 of 30 simulations finished \(40 %\)/),
    ).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toBeInTheDocument();
    expect(
      await screen.findByText("Real-world validity: None — assumptions only"),
    ).toBeInTheDocument();
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
    expect(getExperiment.mock.calls.length).toBeGreaterThanOrEqual(3);
  });

  it("explains a queued experiment", async () => {
    getExperiment.mockResolvedValue({
      ...completed,
      status: "queued",
      resultAvailable: false,
    });
    render(<ExperimentPage experimentId={ID} pollMs={100000} />);
    expect(
      await screen.findByText("Waiting for a free worker."),
    ).toBeInTheDocument();
  });

  it("shows why a failed experiment has no result", async () => {
    getExperiment.mockResolvedValue({
      ...completed,
      status: "failed",
      resultAvailable: false,
      error: "Interrupted by a server restart before it finished.",
    });
    render(<ExperimentPage experimentId={ID} />);
    expect(
      await screen.findByText("This experiment did not produce a result"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Interrupted by a server restart/),
    ).toBeInTheDocument();
    expect(getExperimentResult).not.toHaveBeenCalled();
  });

  it("treats someone else's or an unknown experiment as not found", async () => {
    getExperiment.mockRejectedValue(
      new ExperimentsApiError(404, ["Experiment not found"]),
    );
    render(<ExperimentPage experimentId={ID} />);
    expect(
      await screen.findByRole("heading", { name: "Experiment not found" }),
    ).toBeInTheDocument();
    expect(screen.getByText(ID)).toBeInTheDocument();
  });

  it("offers a retry when the server cannot be reached", async () => {
    getExperiment
      .mockRejectedValueOnce(new ExperimentsApiError(0, ["no network"]))
      .mockResolvedValue(completed);
    getExperimentResult.mockResolvedValue(result);
    const quiet = vi
      .spyOn(console, "error")
      .mockImplementation(() => undefined);
    render(<ExperimentPage experimentId={ID} />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Could not load this experiment",
    );
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(
      await screen.findByRole("heading", { level: 1, name: completed.name }),
    ).toBeInTheDocument();
    quiet.mockRestore();
  });

  it("stops polling when the page is closed", async () => {
    getExperiment.mockResolvedValue({
      ...completed,
      status: "running",
      resultAvailable: false,
    });
    const { unmount } = render(<ExperimentPage experimentId={ID} pollMs={5} />);
    await waitFor(() => {
      expect(getExperiment.mock.calls.length).toBeGreaterThanOrEqual(2);
    });
    unmount();
    const calls = getExperiment.mock.calls.length;
    await new Promise((r) => setTimeout(r, 40));
    expect(getExperiment.mock.calls.length).toBe(calls);
  });
});

describe("experiment routes", () => {
  it("maps /app/experiments/:id to the experiment page", () => {
    expect(resolveRoute(`${EXPERIMENTS_PREFIX}${ID}`)).toEqual({
      kind: "experiment",
      experimentId: ID,
    });
    expect(resolveRoute(`/app/experiments/${ID}/`)).toEqual({
      kind: "experiment",
      experimentId: ID,
    });
    expect(experimentPath(ID)).toBe(`/app/experiments/${ID}`);
  });

  it.each([
    "/app/experiments",
    "/app/experiments/bad.id",
    "/app/experiments/a/b",
    `/app/experiments/${"x".repeat(129)}`,
  ])("treats %s as not found", (path) => {
    expect(resolveRoute(path)).toEqual({ kind: "notFound", path });
  });

  it("is served the dashboard by nginx, with the same id rule", () => {
    expect(nginxTemplate).toContain(
      'location ~ "^/app/experiments/[A-Za-z0-9_-]{1,128}/?$" {',
    );
    // the view-route list is unchanged: experiments are a page under Plan, not a view
    expect(Object.values(VIEW_ROUTES)).not.toContain("/app/experiments");
  });
});
