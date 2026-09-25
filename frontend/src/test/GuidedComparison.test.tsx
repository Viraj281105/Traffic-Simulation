/**
 * The guided comparison, end to end in the dashboard shell: describe the
 * junction, run it (the config reaches the backend before Play), read the
 * results in plain language, check reliability on the same scenario, and
 * open the specialist layer. Hooks and services are mocked as in
 * App.test.tsx; the metric values are fixtures, not simulated results.
 */
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { RunningMetrics } from "../types/simulation";

const updateSimulationConfig = vi.fn();
const runReliabilityCheck = vi.fn();

vi.mock("../services/api", () => ({
  updateSimulationConfig: (payload: unknown) =>
    updateSimulationConfig(payload) as Promise<void>,
  runReliabilityCheck: (scenario: unknown, n: number) =>
    runReliabilityCheck(scenario, n) as Promise<unknown>,
  saveReplay: vi.fn().mockResolvedValue({ runId: "run_9" }),
  listReplays: vi.fn().mockResolvedValue([]),
  getRunRecord: vi.fn(),
  getReplay: vi.fn(),
  deleteReplay: vi.fn(),
  reproduceRun: vi.fn(),
  updateRunMetadata: vi.fn(),
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
  signal: side(
    "fixed_time_signal",
    metrics({ averageDelay: 30, maxQueueLength: 12 }),
  ),
  roundabout: side(
    "roundabout",
    metrics({ averageDelay: 22, maxQueueLength: 6, idleOpportunityLoss: 0 }),
  ),
};

beforeEach(() => {
  vi.clearAllMocks();
  updateSimulationConfig.mockResolvedValue(undefined);
  wsState.snapshot = null;
  wsState.isPlaying = false;
  sessionStorage.clear();
  window.history.replaceState(null, "", "/app/comparative");
});

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
    // No research jargon on the first screen.
    expect(screen.queryByText(/veh\/s|seed|tick/i)).not.toBeInTheDocument();
  });

  it("warns that multi-lane roundabout results are indicative", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("radio", { name: /2 lanes/i }));

    expect(screen.getByRole("note")).toHaveTextContent(
      /single circulating lane/i,
    );
  });

  it("sends the chosen scenario to the backend before playing it", async () => {
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
    await user.click(screen.getByRole("radio", { name: /rush hour/i }));
    await user.click(
      screen.getByRole("button", { name: /run the comparison/i }),
    );

    // The watch step is shown straight away…
    expect(
      screen.getByRole("heading", { name: /watch the comparison/i }),
    ).toBeInTheDocument();
    const payload = updateSimulationConfig.mock.lastCall?.[0] as {
      arrivalRate: number;
      intersectionType: string;
    };
    expect(payload.arrivalRate).toBe(0.45);
    expect(payload.intersectionType).toBe("fixed_time_signal");
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
    const inShort = screen.getByRole("region", { name: /in short/i });
    expect(inShort).toHaveTextContent(
      /Drivers lost less time at the roundabout: 8 s less per driver/,
    );
    expect(inShort).toHaveTextContent(/does not pick a winner/);
    expect(
      screen.getByRole("heading", { name: /how long do drivers wait\?/i }),
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
    const [scenario, patterns] = runReliabilityCheck.mock.calls[0] as [
      { arrivalRate: number; lanesNorth: number; duration: number },
      number,
    ];
    expect(patterns).toBe(5);
    expect(scenario).toMatchObject({
      arrivalRate: 0.3,
      lanesNorth: 1,
      duration: 300,
    });
  });
});
