/**
 * The guided comparison, end to end in the dashboard shell: pick the
 * strategies, describe the junction, run it (the config and the strategies
 * reach the backend before Play), watch every strategy, read the results in
 * plain language, check reliability on the same scenario, and open the
 * specialist layer. Hooks and services are mocked as in App.test.tsx; the
 * metric values are fixtures, not simulated results.
 */
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { RunningMetrics } from "../types/simulation";
import { STRATEGY_CATALOG } from "./strategyCatalogFixture";
import { resetStrategyCatalog } from "../strategies/strategyCatalog";

const updateSimulationConfig = vi.fn();
const listStrategies = vi.fn();
const runReliabilityCheck = vi.fn();

// The reliability check runs as a backend study job; its result is what the
// job resolves with.
vi.mock("../services/studyJobs", () => ({
  STUDY_JOB_ROUTES: { monteCarlo: "/mc/jobs", sweep: "/sweep/jobs" },
  runStudyJob: (route: string, body: { scenario: unknown; numSeeds: number }) =>
    runReliabilityCheck(
      body.scenario,
      body.numSeeds,
      route,
    ) as Promise<unknown>,
}));

vi.mock("../services/api", () => ({
  updateSimulationConfig: (payload: unknown) =>
    updateSimulationConfig(payload) as Promise<void>,
  listStrategies: () => listStrategies() as Promise<unknown>,
  saveReplay: vi.fn().mockResolvedValue({ runId: "run_9" }),
  listReplays: vi.fn().mockResolvedValue([]),
  getRunRecord: vi.fn(),
  getReplay: vi.fn(),
  deleteReplay: vi.fn(),
  reproduceRun: vi.fn(),
  updateRunMetadata: vi.fn(),
  fetchRunExport: vi.fn(),
  runExportUrl: () => "",
  ApiError: class ApiError extends Error {},
}));

const wsState = {
  snapshot: null as unknown,
  connectionStatus: "connected" as const,
  isPlaying: false,
  error: null as string | null,
  play: vi.fn().mockResolvedValue(undefined),
  pause: vi.fn().mockResolvedValue(undefined),
  stop: vi.fn().mockResolvedValue(undefined),
};

vi.mock("../hooks/useWebSocketSnapshot", () => ({
  useWebSocketSnapshot: () => wsState,
}));

vi.mock("../hooks/useSimulationPolling", () => ({
  useSimulationPolling: () => ({
    vehicle: null,
    status: null,
    isLoading: false,
    error: null,
    start: vi.fn(),
    stop: vi.fn(),
    reset: vi.fn(),
  }),
}));

vi.mock("../hooks/useContainerSize", () => ({
  useContainerSize: () => [() => undefined, { width: 800, height: 600 }],
}));

import { App } from "../App";

function metrics(overrides: Partial<RunningMetrics>): RunningMetrics {
  return {
    averageDelay: 20,
    medianDelay: 18,
    minDelay: 2,
    maxDelay: 60,
    p95Delay: 45,
    delayStdDev: 9,
    averageWaitTime: 12,
    throughput: 200,
    throughputRate: 20,
    currentQueueLengths: { north: 1, south: 2, east: 0, west: 1 },
    maxQueueLength: 9,
    averageQueueLength: 2.5,
    activeAverageQueueLength: 6,
    queueStdDev: 2,
    totalStops: 220,
    averageStopsPerVehicle: 1.1,
    speedVarianceIndex: 0.4,
    travelTimeReliability: 1.6,
    idleOpportunityLoss: 0.12,
    directionalFairnessIndex: 0.97,
    activeVehicleCount: 14,
    totalVehiclesSpawned: 260,
    averageTravelSpeed: 8,
    queueStabilityIndex: 0.8,
    congestionRecoveryTime: 40,
    spaceFootprintConsumed: 200,
    intersectionUtilization: 70,
    criticalSaturationVolume: 0.3,
    collisionCount: 0,
    ...overrides,
  };
}

function side(type: "fixed_time_signal" | "roundabout", m: RunningMetrics) {
  return {
    timestamp: 300,
    warmupTime: 30,
    tick: 3000,
    samplingFrequency: 10,
    simulationStatus: "completed",
    vehicles: [],
    vehicleCounts: {
      active: 14,
      approaching: 6,
      waiting: 5,
      crossing: 2,
      inRoundabout: 1,
      exited: 240,
    },
    controller:
      type === "fixed_time_signal"
        ? {
            type,
            currentPhase: "ns_green",
            phaseTimeRemaining: 3,
            cycleNumber: 5,
            timeInCurrentState: 1,
            signals: [],
          }
        : {
            type,
            circulatingCount: 2,
            yieldingCount: 1,
            gapAcceptance: 4.5,
            innerRadius: 10,
            outerRadius: 20,
            timeInCurrentState: 1,
          },
    intersection: { approaches: [] },
    metrics: m,
  };
}

const COMPLETED = {
  tick: 3000,
  elapsed: 300,
  runs: [
    {
      strategy: "fixed_time_signal",
      snapshot: side(
        "fixed_time_signal",
        metrics({ averageDelay: 30, maxQueueLength: 12 }),
      ),
    },
    {
      strategy: "conventional_roundabout",
      snapshot: side(
        "roundabout",
        metrics({
          averageDelay: 22,
          maxQueueLength: 6,
          idleOpportunityLoss: 0,
        }),
      ),
    },
  ],
};

/** All four strategies, each with its own delay so each is attributable. */
const FOUR_WAY = {
  tick: 3000,
  elapsed: 300,
  runs: (
    [
      ["fixed_time_signal", "fixed_time_signal", 30, 200],
      ["adaptive_signal", "fixed_time_signal", 26, 204],
      ["conventional_roundabout", "roundabout", 22, 206],
      ["metered_entry_roundabout", "roundabout", 24, 198],
    ] as const
  ).map(([strategy, type, delay, served]) => ({
    strategy,
    snapshot: side(type, metrics({ averageDelay: delay, throughput: served })),
  })),
};

beforeEach(() => {
  vi.clearAllMocks();
  resetStrategyCatalog();
  listStrategies.mockResolvedValue(STRATEGY_CATALOG);
  updateSimulationConfig.mockResolvedValue(undefined);
  wsState.snapshot = null;
  wsState.isPlaying = false;
  sessionStorage.clear();
  window.history.replaceState(null, "", "/app/comparative");
});

const picker = () =>
  screen.findByRole("group", { name: /which strategies should we compare/i });

describe("Guided comparison", () => {
  it("starts by asking about the junction, in everyday terms", () => {
    render(<App />);

    expect(
      screen.getByRole("heading", {
        name: /describe the junction you want to test/i,
      }),
    ).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /busy/i })).toBeChecked();
    expect(screen.getByRole("radio", { name: /1 lane/i })).toBeChecked();
    // No research jargon on the first screen (the seed is in Advanced).
    expect(screen.queryByText(/veh\/s|seed|tick/i)).not.toBeInTheDocument();
  });

  it("warns that multi-lane roundabout results are indicative", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("radio", { name: /2 lanes/i }));

    expect(screen.getByRole("note")).toHaveTextContent(
      /indicative.*inner ring/i,
    );
  });

  it("keeps the demand level when the lane count changes", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole("radio", { name: /3 lanes/i }));
    // "Busy" stays selected and now means 75% of the 3-lane capacity.
    expect(screen.getByRole("radio", { name: /busy/i })).toBeChecked();
    expect(screen.getByText(/1,970 vehicles \/ hour/)).toBeInTheDocument();
  });

  it("shows every strategy as its own card, with two chosen to start", async () => {
    render(<App />);
    const group = await picker();
    expect(within(group).getAllByRole("checkbox")).toHaveLength(4);
    expect(
      within(group).getByRole("checkbox", { name: /fixed-time signal/i }),
    ).toBeChecked();
    expect(
      within(group).getByRole("checkbox", { name: /^roundabout$/i }),
    ).toBeChecked();
    expect(
      within(group).getByRole("checkbox", { name: /adaptive signal/i }),
    ).not.toBeChecked();
    expect(
      within(group).getByRole("checkbox", { name: /metered roundabout/i }),
    ).not.toBeChecked();
    expect(group).toHaveTextContent(/2 of 4 selected/);
  });

  it("lets any combination be chosen, and the run follows the choice", async () => {
    const user = userEvent.setup();
    render(<App />);
    const group = await picker();

    await user.click(within(group).getByRole("button", { name: /all 4/i }));
    expect(group).toHaveTextContent(/4 of 4 selected/);
    expect(
      screen.getByRole("button", { name: /run 4 strategies/i }),
    ).toBeEnabled();

    // Down to one: still runnable (watch one strategy on its own).
    for (const name of [
      /fixed-time signal/i,
      /^roundabout$/i,
      /metered roundabout/i,
    ]) {
      await user.click(within(group).getByRole("checkbox", { name }));
    }
    expect(group).toHaveTextContent(/1 of 4 selected/);
    expect(
      screen.getByRole("button", { name: /run the simulation/i }),
    ).toBeEnabled();

    // None: nothing to run, and the picker says why.
    await user.click(
      within(group).getByRole("checkbox", { name: /adaptive signal/i }),
    );
    expect(group).toHaveTextContent(/pick at least one/i);
    expect(
      screen.getByRole("button", { name: /run the simulation/i }),
    ).toBeDisabled();
  });

  it("never offers strategies it could not load", async () => {
    const user = userEvent.setup();
    listStrategies.mockRejectedValueOnce(new Error("offline"));
    render(<App />);
    expect(
      await screen.findByText(/list of strategies could not be loaded/i),
    ).toBeInTheDocument();
    expect(screen.queryAllByRole("checkbox")).toHaveLength(0);
    expect(
      screen.getByRole("button", { name: /run the simulation/i }),
    ).toBeDisabled();

    await user.click(screen.getByRole("button", { name: /try again/i }));
    expect(
      await screen.findByRole("checkbox", { name: /adaptive signal/i }),
    ).toBeInTheDocument();
  });

  it("sends the chosen scenario and strategies to the backend before playing", async () => {
    const user = userEvent.setup();
    let resolveSync: () => void = () => undefined;
    render(<App />);
    await waitFor(() => {
      expect(updateSimulationConfig).toHaveBeenCalled();
    });

    updateSimulationConfig.mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          resolveSync = resolve;
        }),
    );
    await user.click(screen.getByRole("radio", { name: /near capacity/i }));
    await user.click(
      await screen.findByRole("button", { name: /run 2 strategies/i }),
    );

    // The watch step is shown straight away…
    expect(
      screen.getByRole("heading", { name: /watch both run/i }),
    ).toBeInTheDocument();

    // Wait for the debounced config call with the "Near capacity" arrivalRate.
    // 90% of the measured 1-lane reference capacity (1,250 veh/h) = 1,125 → 1,130 veh/h.
    await waitFor(() => {
      const payload = updateSimulationConfig.mock.lastCall?.[0] as {
        arrivalRate: number;
        intersectionType: string;
        strategies: string[];
      };
      expect(payload.arrivalRate).toBeCloseTo(1130 / 3600, 9);
      expect(payload.intersectionType).toBe("fixed_time_signal");
      expect(payload.strategies).toEqual([
        "fixed_time_signal",
        "conventional_roundabout",
      ]);
    });

    // …but Play waits for the backend to hold the new scenario.
    expect(wsState.play).not.toHaveBeenCalled();
    resolveSync();
    await waitFor(() => {
      expect(wsState.play).toHaveBeenCalledTimes(1);
    });
  });

  it("explains the results in plain language, with the evidence on demand", async () => {
    const user = userEvent.setup();
    wsState.snapshot = COMPLETED;
    render(<App />);

    await user.click(screen.getByRole("button", { name: /results/i }));

    expect(
      screen.getByRole("heading", { name: /results for your junction/i }),
    ).toBeInTheDocument();
    const glance = screen.getByRole("region", { name: /at a glance/i });
    expect(glance).toHaveTextContent(/Fixed-time signal.*30 s/);
    expect(glance).toHaveTextContent(/Roundabout.*22 s/);
    expect(glance).toHaveTextContent(/does not pick a winner/);
    expect(
      screen.getByText(
        /Least time lost with the roundabout, most with the fixed-time signal: 8 s apart/,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /how much time do drivers lose\?/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /why did this happen\?/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/traffic pattern #\d+/)).toBeInTheDocument();

    // The specialist layer keeps every catalog metric.
    const specialist = screen
      .getByText(/all measurements & method/i)
      .closest("details") as HTMLElement;
    expect(
      within(specialist).getByRole("rowheader", { name: /average delay/i }),
    ).toBeInTheDocument();
    expect(
      within(specialist).getByRole("rowheader", { name: /minimum ttc/i }),
    ).toBeInTheDocument();
    // A signal/roundabout pair keeps its charts.
    expect(
      within(specialist).getByRole("button", {
        name: /charts & user-weighted scoring/i,
      }),
    ).toBeInTheDocument();
  });

  it("keeps time lost apart from waiting and never sets the composite side by side", async () => {
    const user = userEvent.setup();
    wsState.snapshot = COMPLETED;
    render(<App />);
    await user.click(screen.getByRole("button", { name: /results/i }));

    // Delay is "time lost", queued time is its own row, and the definition is stated.
    expect(
      screen.getByText(/Time spent nearly stopped, on average/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Time lost is not the same as waiting/i),
    ).toBeInTheDocument();
    expect(screen.queryByText(/how long do drivers wait/i)).toBeNull();
    expect(screen.queryByText(/is that a long wait/i)).toBeNull();

    // The fixed-weight composite is not in the comparison table.
    const specialist = screen
      .getByText(/all measurements & method/i)
      .closest("details") as HTMLElement;
    expect(
      within(specialist).queryByRole("rowheader", { name: /composite/i }),
    ).toBeNull();
  });

  it("tells the user when vehicle generation was cut off", async () => {
    const user = userEvent.setup();
    const capped = structuredClone(COMPLETED);
    capped.runs[0].snapshot.metrics.vehicleLimitReached = true;
    capped.runs[0].snapshot.metrics.vehicleLimit = 200;
    wsState.snapshot = capped;
    render(<App />);
    await user.click(screen.getByRole("button", { name: /results/i }));
    expect(
      screen.getByText(/Vehicle generation reached its limit of 200 vehicles/i),
    ).toBeInTheDocument();
  });

  it("attributes each result to its own strategy in a four-way comparison", async () => {
    const user = userEvent.setup();
    wsState.snapshot = FOUR_WAY;
    render(<App />);
    await user.click(screen.getByRole("button", { name: /results/i }));

    const glance = screen.getByRole("region", { name: /at a glance/i });
    const card = (name: RegExp) =>
      within(glance).getByRole("heading", { name }).closest("article");
    expect(card(/^fixed-time signal$/i)).toHaveTextContent(/30 s.*200/);
    expect(card(/^adaptive signal$/i)).toHaveTextContent(/26 s.*204/);
    expect(card(/^roundabout$/i)).toHaveTextContent(/22 s.*206/);
    expect(card(/^metered roundabout$/i)).toHaveTextContent(/24 s.*198/);

    // Bars name every strategy for every measure.
    const delayRow = screen.getByRole("group", {
      name: "Time lost per driver, on average",
    });
    expect(within(delayRow).getAllByText(/^\d+ s$/)).toHaveLength(4);
    expect(
      screen.getByText(
        /The roundabout got 8 more vehicles through than the metered roundabout/i,
      ),
    ).toBeInTheDocument();

    // One strategy in full, without leaving the comparison.
    await user.click(screen.getByRole("tab", { name: /metered roundabout/i }));
    expect(screen.getByRole("tabpanel")).toHaveAccessibleName(
      "Metered roundabout",
    );
    // A signal/roundabout pair's charts are not offered for four.
    expect(
      screen.queryByRole("button", { name: /charts & user-weighted/i }),
    ).toBeNull();
  });

  it("shows a map per strategy and inspects one without losing the others", async () => {
    const user = userEvent.setup();
    wsState.snapshot = FOUR_WAY;
    render(<App />);
    // The step names how many strategies are running.
    await user.click(screen.getByRole("button", { name: /watch all 4 run/i }));

    for (const name of [
      /^fixed-time signal$/i,
      /^adaptive signal$/i,
      /^roundabout$/i,
      /^metered roundabout$/i,
    ]) {
      expect(screen.getByRole("region", { name })).toBeInTheDocument();
    }
    const adaptiveMap = screen.getByRole("region", {
      name: /^adaptive signal$/i,
    });
    await user.click(
      within(adaptiveMap).getByRole("button", { name: /inspect/i }),
    );
    expect(
      screen.getByRole("button", { name: /back to the comparison/i }),
    ).toBeInTheDocument();
    // Every map stays on screen.
    expect(screen.getAllByRole("button", { name: /inspect/i })).toHaveLength(4);
  });

  it("checks reliability by repeating the same scenario", async () => {
    const user = userEvent.setup();
    wsState.snapshot = COMPLETED;
    const stat = (mean: number) => ({
      mean,
      std: 1,
      min: mean - 1,
      max: mean + 1,
      ci95: 0.9,
    });
    runReliabilityCheck.mockResolvedValue({
      numSeeds: 5,
      duration: 300,
      signal: { delay: stat(30), throughput: stat(200), queue: stat(3) },
      roundabout: { delay: stat(22), throughput: stat(201), queue: stat(2) },
      comparison: {
        delay: {
          pValue: 0.001,
          significant: true,
          cohensD: 2.1,
          degreesOfFreedom: 7.9,
        },
        throughput: { pValue: 0.7, significant: false, cohensD: 0.1 },
        queue: { pValue: 0.04, significant: true, cohensD: 1.2 },
      },
      seedRuns: [1, 2, 3, 4, 5].map((seed) => ({
        seed,
        signal: { delay: 30, throughput: 200, queue: 3 },
        roundabout: { delay: 22, throughput: 201, queue: 2 },
      })),
    });
    render(<App />);
    await user.click(screen.getByRole("button", { name: /results/i }));

    await user.click(
      screen.getByRole("button", { name: /check reliability/i }),
    );

    expect(
      await screen.findByText(
        /drivers lost less time at the roundabout — and the difference held up across 5 traffic patterns/i,
      ),
    ).toBeInTheDocument();
    const [scenario, patterns, route] = runReliabilityCheck.mock.calls[0] as [
      { arrivalRate: number; lanesNorth: number; duration: number },
      number,
      string,
    ];
    expect(route).toBe("/mc/jobs");
    expect(patterns).toBe(5);
    expect(scenario).toMatchObject({
      arrivalRate: 940 / 3600,
      lanesNorth: 1,
      duration: 300,
    });
  });
});
