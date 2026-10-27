import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const estimate = vi.fn();
const startSearch = vi.fn();
const listSearches = vi.fn();
const getSearch = vi.fn();
const getSearchResult = vi.fn();

vi.mock("../services/v3/discovery", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../services/v3/discovery")>()),
  estimate: (s: unknown) => estimate(s) as Promise<unknown>,
  startSearch: (s: unknown) => startSearch(s) as Promise<unknown>,
  listSearches: () => listSearches() as Promise<unknown>,
  getSearch: (id: string) => getSearch(id) as Promise<unknown>,
  getSearchResult: (id: string) => getSearchResult(id) as Promise<unknown>,
}));

import { DiscoveryPage } from "../components/discovery/DiscoveryPage";

const done = {
  id: "s1",
  name: "Discovery search",
  status: "completed",
  phase: "done",
  createdAt: "2026-10-27T00:00:00+00:00",
  runs: { planned: 200, used: 180 },
  resultAvailable: true,
  error: null,
};

const result = {
  status: "completed",
  complete: true,
  experimental: "EXPERIMENTAL: found by search under the declared regime.",
  method: "Bounded multi-objective evolutionary search.",
  specFingerprint: "abc",
  traceFingerprint: "trace123",
  runs: { planned: 200, used: 180 },
  rejected: {},
  seedPools: {
    tuning: 2,
    selection: 3,
    heldOut: 10,
    heldOutHashCommittedBeforeSearch: "h",
  },
  pareto: [
    {
      candidate: "c1aaaaaaaa",
      generation: 2,
      genome: { strategy: "adaptive" },
      tuningObjectives: {
        averageDelay: 12.5,
        throughput: 100,
        maxQueueLength: 6,
        nearMissesPer1000: 3,
      },
    },
  ],
  heldOut: {
    seeds: 10,
    differenceMeaning: "candidate minus baseline",
    candidates: {
      c1aaaaaaaa: {
        genome: { strategy: "adaptive" },
        objectives: {
          averageDelay: 13.25,
          throughput: 98,
          maxQueueLength: 7,
          nearMissesPer1000: 2,
        },
        infeasible: null,
        versusBaselines: {
          fixed_time: { meanDifference: 1.5, ci95: [0.5, 2.5], n: 10 },
          adaptive: { meanDifference: -0.5, ci95: [-1, 0.1], n: 10 },
          roundabout: { meanDifference: 0.2, ci95: [-0.3, 0.7], n: 10 },
        },
      },
    },
    baselines: {
      fixed_time: {
        objectives: {
          averageDelay: 11.75,
          throughput: 99,
          maxQueueLength: 6,
          nearMissesPer1000: 2,
        },
        infeasible: null,
      },
    },
  },
  bestOnTuningLosesOnHeldOut: true,
  preferenceChanges: [
    {
      demandScale: 1.2,
      aggression: "high",
      meanDelay: {},
      lowestDelay: "baseline:roundabout",
      seeds: 2,
    },
  ],
};

describe("DiscoveryPage", () => {
  beforeEach(() => {
    estimate.mockResolvedValue({ runs: 200, simulatedSeconds: 30000 });
    listSearches.mockResolvedValue([]);
    startSearch.mockResolvedValue({ ...done, status: "queued" });
    getSearch.mockResolvedValue(done);
    getSearchResult.mockResolvedValue(result);
  });

  it("shows the reserved budget, starts a search and reports held-out results honestly", async () => {
    const user = userEvent.setup();
    render(<DiscoveryPage />);
    expect(
      await screen.findByText(/at most 200 simulation runs/),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Start search/ }));
    expect(await screen.findByText("EXPERIMENTAL")).toBeInTheDocument();
    expect(screen.getByText(/does worse than a baseline/)).toBeInTheDocument();
    expect(screen.getByText("1.50 [0.50, 2.50]")).toBeInTheDocument();
    expect(screen.getByText("baseline:roundabout")).toBeInTheDocument();
    await waitFor(() => {
      expect(startSearch).toHaveBeenCalledTimes(1);
    });
  });
});
