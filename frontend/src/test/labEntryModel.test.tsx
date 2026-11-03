/**
 * @vitest-environment jsdom
 *
 * The entry model in the Discovery Lab and the Stress Lab (checkpoint 11):
 * the choice reaches the request, the default request is unchanged, and
 * results name the model and flag a lower delay that came with less of the
 * demand served (a caution, never a verdict).
 */
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const discovery = vi.hoisted(() => ({
  estimate: vi.fn(),
  startSearch: vi.fn(),
  listSearches: vi.fn(),
  getSearch: vi.fn(),
  getSearchResult: vi.fn(),
}));
vi.mock("../services/v3/discovery", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../services/v3/discovery")>()),
  estimate: (s: unknown) => discovery.estimate(s) as Promise<unknown>,
  startSearch: (s: unknown) => discovery.startSearch(s) as Promise<unknown>,
  listSearches: () => discovery.listSearches() as Promise<unknown>,
  getSearch: (id: string) => discovery.getSearch(id) as Promise<unknown>,
  getSearchResult: (id: string) =>
    discovery.getSearchResult(id) as Promise<unknown>,
}));

const stress = vi.hoisted(() => ({
  startSuite: vi.fn(),
  startBreakpoints: vi.fn(),
  listJobs: vi.fn(),
  getJob: vi.fn(),
  getJobResult: vi.fn(),
}));
vi.mock("../services/v3/stress", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../services/v3/stress")>()),
  startSuite: (b: unknown) => stress.startSuite(b) as Promise<unknown>,
  startBreakpoints: (b: unknown) =>
    stress.startBreakpoints(b) as Promise<unknown>,
  listJobs: () => stress.listJobs() as Promise<unknown>,
  getJob: (id: string) => stress.getJob(id) as Promise<unknown>,
  getJobResult: (id: string) => stress.getJobResult(id) as Promise<unknown>,
}));

import { DiscoveryPage } from "../components/discovery/DiscoveryPage";
import { StressLabPage } from "../components/stress/StressLabPage";

const objectives = {
  averageDelay: 40,
  throughput: 90,
  maxQueueLength: 6,
  nearMissesPer1000: 1,
};

const searchDone = {
  id: "s1",
  name: "Discovery search",
  status: "completed",
  phase: "done",
  createdAt: "2026-11-02T00:00:00+00:00",
  runs: { planned: 200, used: 180 },
  resultAvailable: true,
  error: null,
};

const searchResult = {
  status: "completed",
  complete: true,
  experimental: "EXPERIMENTAL",
  method: "Bounded search.",
  specFingerprint: "abc",
  traceFingerprint: "t",
  entryModel: { model: "queue", capacity: null },
  runs: { planned: 200, used: 180 },
  rejected: {},
  seedPools: {
    tuning: 2,
    selection: 3,
    heldOut: 10,
    heldOutHashCommittedBeforeSearch: "h",
  },
  pareto: [],
  heldOut: {
    seeds: 10,
    differenceMeaning: "candidate minus baseline",
    candidates: {
      c1aaaaaaaa: {
        genome: { strategy: "adaptive" },
        objectives,
        servedDemand: { averageEntryWait: 12, admittedShareOfNominal: 0.7 },
        infeasible: null,
        versusBaselines: {
          fixed_time: {
            meanDifference: -4,
            ci95: [-6, -2],
            n: 10,
            lowerDelayServedLess: true,
          },
          adaptive: { meanDifference: -1, ci95: [-2, 0.5], n: 10 },
          roundabout: { meanDifference: 2, ci95: [1, 3], n: 10 },
        },
      },
    },
    baselines: {},
  },
  bestOnTuningLosesOnHeldOut: false,
  preferenceChanges: null,
};

describe("Discovery Lab entry model", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    discovery.estimate.mockResolvedValue({ runs: 200, simulatedSeconds: 1 });
    discovery.listSearches.mockResolvedValue([]);
    discovery.startSearch.mockResolvedValue({
      ...searchDone,
      status: "queued",
    });
    discovery.getSearch.mockResolvedValue(searchDone);
    discovery.getSearchResult.mockResolvedValue(searchResult);
  });

  it("sends the regime's entry model and explains the result under it", async () => {
    const user = userEvent.setup();
    render(<DiscoveryPage />);
    await user.click(
      await screen.findByRole("radio", { name: "Queue outside the map" }),
    );
    await user.click(screen.getByRole("button", { name: /Start search/ }));
    await waitFor(() => {
      expect(discovery.startSearch).toHaveBeenCalledTimes(1);
    });
    const spec = discovery.startSearch.mock.calls[0][0] as {
      regime: { entryQueue?: unknown };
    };
    expect(spec.regime.entryQueue).toEqual({ enabled: true, capacity: null });
    expect(
      await screen.findByText(/delay objective here includes that wait/),
    ).toBeInTheDocument();
    // Only the comparison whose lower delay came with less served is flagged.
    expect(
      screen.getAllByText(/served less of the demand; may explain/),
    ).toHaveLength(1);
  });

  it("leaves the default regime as it was", async () => {
    const user = userEvent.setup();
    render(<DiscoveryPage />);
    await user.click(
      await screen.findByRole("button", { name: /Start search/ }),
    );
    await waitFor(() => {
      expect(discovery.startSearch).toHaveBeenCalledTimes(1);
    });
    const spec = discovery.startSearch.mock.calls[0][0] as {
      regime: Record<string, unknown>;
    };
    expect(spec.regime.entryQueue ?? null).toBeNull();
  });
});

const job = {
  id: "j1",
  kind: "suite",
  status: "completed",
  createdAt: "2026-11-02T00:00:00+00:00",
  runs: 8,
  resultAvailable: true,
  error: null,
};

const suite = {
  format: "urbanflow-stress-suite",
  generator: "stress-v1",
  seed: 1,
  suiteFingerprint: "f",
  strategies: ["fixed_time", "roundabout"],
  entryModel: { model: "queue", capacity: 10 },
  rules: { gridlock: "No vehicle moves." },
  failureTotals: {},
  scenarios: [
    {
      index: 0,
      family: "over_capacity",
      name: "stress-v1 #0 (over_capacity)",
      results: {
        fixed_time: { failures: {}, meanDelay: 50, runErrors: 0 },
        roundabout: { failures: {}, meanDelay: 30, runErrors: 0 },
      },
      lowestDelayServedLess: true,
    },
    {
      index: 1,
      family: "uneven_split",
      name: "stress-v1 #1 (uneven_split)",
      results: {
        fixed_time: { failures: {}, meanDelay: 20, runErrors: 0 },
        roundabout: { failures: {}, meanDelay: 25, runErrors: 0 },
      },
      lowestDelayServedLess: false,
    },
  ],
  note: "",
};

describe("Stress Lab entry model", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    stress.listJobs.mockResolvedValue([]);
    stress.startSuite.mockResolvedValue({ ...job, status: "queued" });
    stress.startBreakpoints.mockResolvedValue({
      ...job,
      id: "j2",
      kind: "breakpoints",
      status: "queued",
    });
    stress.getJob.mockResolvedValue(job);
    stress.getJobResult.mockResolvedValue(suite);
  });

  it("sends the model to both tools and flags rows that served less", async () => {
    const user = userEvent.setup();
    render(<StressLabPage />);
    await user.click(
      screen.getByRole("radio", { name: "Queue outside the map" }),
    );
    await user.type(screen.getByLabelText("Queue limit per road"), "10");
    await user.click(screen.getByRole("button", { name: /Find breakpoints/ }));
    await user.click(screen.getByRole("button", { name: /Run stress suite/ }));
    await waitFor(() => {
      expect(stress.startSuite).toHaveBeenCalledTimes(1);
    });
    const queue = { enabled: true, capacity: 10 };
    expect(stress.startSuite.mock.calls[0][0]).toMatchObject({
      entryQueue: queue,
    });
    expect(stress.startBreakpoints.mock.calls[0][0]).toMatchObject({
      entryQueue: queue,
    });
    expect(
      await screen.findByText(/at most 10 per road.*do not include that wait/),
    ).toBeInTheDocument();
    const overloaded = screen.getByRole("rowheader", {
      name: /over_capacity/,
    });
    expect(
      within(overloaded).getByText(/served less of the demand/),
    ).toBeInTheDocument();
    expect(
      within(
        screen.getByRole("rowheader", { name: /uneven_split/ }),
      ).queryByText(/served less/),
    ).toBeNull();
  });

  it("sends no entry model by default", async () => {
    const user = userEvent.setup();
    render(<StressLabPage />);
    await user.click(screen.getByRole("button", { name: /Run stress suite/ }));
    await waitFor(() => {
      expect(stress.startSuite).toHaveBeenCalledTimes(1);
    });
    expect(stress.startSuite.mock.calls[0][0]).not.toHaveProperty("entryQueue");
  });
});
