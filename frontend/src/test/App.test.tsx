/**
 * Smoke and wiring tests for App — the dashboard shell.
 *
 * App owns view-mode switching, which hook drives the active view, and the
 * config-sync effect that pushes the sidebar's settings to the backend. It was
 * entirely uncovered despite being the component every demo session starts in,
 * so a crash on mount or a broken mode switch would reach a viewer first.
 *
 * The hooks and services are mocked: this is about App's own orchestration, not
 * a re-test of the stream client (see websocket.test.ts) or the hook (see
 * useWebSocketSnapshot.test.tsx).
 */
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const updateSimulationConfig = vi.fn();
const saveReplay = vi.fn();
const getRunRecord = vi.fn();
const getReplay = vi.fn();

vi.mock("../services/api", () => ({
  updateSimulationConfig: async (payload: unknown): Promise<void> => {
    await updateSimulationConfig(payload);
  },
  saveReplay: async (payload: unknown): Promise<void> => {
    await saveReplay(payload);
  },
  playSimulation: vi.fn().mockResolvedValue(undefined),
  pauseSimulation: vi.fn().mockResolvedValue(undefined),
  stopSimulation: vi.fn().mockResolvedValue(undefined),
  playDualSimulation: vi.fn().mockResolvedValue(undefined),
  pauseDualSimulation: vi.fn().mockResolvedValue(undefined),
  stopDualSimulation: vi.fn().mockResolvedValue(undefined),
  listSweeps: vi.fn().mockResolvedValue([]),
  getSweep: vi.fn(),
  listReplays: vi.fn().mockResolvedValue([]),
  deleteReplay: vi.fn().mockResolvedValue({ status: "ok" }),
  getRunRecord: (id: string) => getRunRecord(id) as Promise<unknown>,
  getReplay: (id: string) => getReplay(id) as Promise<unknown>,
  reproduceRun: vi.fn(),
  updateRunMetadata: vi.fn(),
  runExportUrl: (id: string, format: string) =>
    `/api/v1/study/history/runs/${id}/export?format=${format}`,
  ApiError: class ApiError extends Error {
    status: number;
    constructor(status: number) {
      super(`HTTP ${String(status)}`);
      this.status = status;
    }
  },
}));

const RUN_RECORD = {
  runId: "run_1",
  name: "Saved roundabout",
  notes: null,
  tags: [],
  batchId: "replay",
  createdAt: "2026-09-22 10:00:00",
  status: "completed",
  intersectionType: "roundabout",
  provenanceRecorded: true,
  runMode: "single",
  seed: 77,
  gitCommitHash: "abcdef0123456789",
  pythonVersion: "3.11.9",
  configSource: "engine",
  configAvailable: true,
  exactConfig: true,
  timing: { timeStep: 0.1, duration: 300, warmupTime: 30, elapsed: 90 },
  config: { simulation: { randomSeed: 77 } },
  summaryMetrics: { throughput: 12, averageWaitTime: 3 },
  savedReplay: true,
};

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
    isPlaying: false,
    error: null,
    play: vi.fn().mockResolvedValue(undefined),
    pause: vi.fn().mockResolvedValue(undefined),
    reset: vi.fn().mockResolvedValue(undefined),
  }),
}));

// Signed out by default, as a first visit is. The Research lab tab asks for a
// sign-in first, so tests that navigate there sign in with signIn(). The
// user's session and profile are not under test: getSession reports none.
const authState: { user: object | null } = { user: null };
const signIn = () => {
  authState.user = {
    getSession: (cb: (err: Error | null, session: null) => void) => {
      cb(null, null);
    },
    signOut: vi.fn(),
  };
};

vi.mock("../auth/cognito", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../auth/cognito")>()),
  getCurrentUser: () => authState.user,
  getAuthToken: () => Promise.resolve(null),
}));

// The junction study validates its scenario against the backend as it is
// edited; here every scenario can be simulated.
vi.mock("../services/scenarioApi", () => ({
  validateScenario: vi.fn().mockResolvedValue({
    valid: true,
    errors: [],
    warnings: [],
    strategies: ["fixed_time", "adaptive", "roundabout"],
  }),
  compileScenario: vi.fn(),
}));

vi.mock("../hooks/useContainerSize", () => ({
  useContainerSize: () => [() => undefined, { width: 800, height: 600 }],
}));

import { App } from "../App";

beforeEach(() => {
  vi.clearAllMocks();
  updateSimulationConfig.mockResolvedValue(undefined);
  saveReplay.mockResolvedValue({ replay_id: "r1" });
  wsState.snapshot = null;
  wsState.isPlaying = false;
  wsState.error = null;
  authState.user = null;
  sessionStorage.clear();
  window.history.replaceState(null, "", "/app/comparative");
});

describe("App", () => {
  it("mounts without crashing and renders its shell", () => {
    const { container } = render(<App />);

    expect(container.firstChild).not.toBeNull();
  });

  it("pushes the current configuration to the backend on mount", async () => {
    render(<App />);

    await waitFor(() => {
      expect(updateSimulationConfig).toHaveBeenCalled();
    });
    const payload = updateSimulationConfig.mock.calls[0][0] as Record<
      string,
      unknown
    >;
    expect(payload).toHaveProperty("intersectionType");
    expect(payload).toHaveProperty("arrivalRate");
    expect(payload).toHaveProperty("duration");
  });

  it("survives a failed config sync instead of crashing the dashboard", async () => {
    updateSimulationConfig.mockRejectedValue(new Error("backend unreachable"));
    const consoleError = vi
      .spyOn(console, "error")
      .mockImplementation(() => undefined);

    const { container } = render(<App />);

    await waitFor(() => {
      expect(updateSimulationConfig).toHaveBeenCalled();
    });
    expect(container.firstChild).not.toBeNull();
    consoleError.mockRestore();
  });

  it("starts in comparative mode", async () => {
    render(<App />);

    await waitFor(() => {
      expect(updateSimulationConfig).toHaveBeenCalled();
    });
    const payload = updateSimulationConfig.mock.calls[0][0] as {
      intersectionType: string;
    };
    // Comparative view drives the signal config on the live session.
    expect(payload.intersectionType).toBe("fixed_time_signal");
  });

  it("re-syncs the config when the view switches to the roundabout", async () => {
    signIn();
    const user = userEvent.setup();
    render(<App />);
    await waitFor(() => {
      expect(updateSimulationConfig).toHaveBeenCalled();
    });

    // Single-control views live in the Research lab.
    await user.click(screen.getByRole("link", { name: "Research lab" }));
    updateSimulationConfig.mockClear();
    await user.click(
      within(
        screen.getByRole("navigation", { name: "Research tools" }),
      ).getByRole("link", { name: /roundabout on its own/i }),
    );

    // The sync is debounced, so a sync scheduled by the Research-lab
    // navigation can still land after mockClear(); wait for the latest one.
    await waitFor(() => {
      const allCalls = updateSimulationConfig.mock.calls;
      expect(allCalls.length).toBeGreaterThan(0);
      const payload = allCalls[allCalls.length - 1][0] as {
        intersectionType: string;
      };
      expect(payload.intersectionType).toBe("roundabout");
    });
  });

  it("remembers the light theme across mounts", async () => {
    sessionStorage.setItem("signals-theme", "light");

    render(<App />);

    await waitFor(() => {
      expect(document.documentElement.classList.contains("light")).toBe(true);
    });
  });

  it("defaults to the light theme when no preference is stored", async () => {
    sessionStorage.removeItem("signals-theme");

    expect(() => render(<App />)).not.toThrow();
    await waitFor(() => {
      expect(document.documentElement.classList.contains("light")).toBe(true);
    });
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });

  it("keeps the dark theme when the visitor chose it", async () => {
    sessionStorage.setItem("signals-theme", "dark");

    render(<App />);

    await waitFor(() => {
      expect(document.documentElement.classList.contains("dark")).toBe(true);
    });
    expect(document.documentElement.classList.contains("light")).toBe(false);
  });

  it("shows the view named by the URL, so a refresh stays on it", () => {
    window.history.replaceState(null, "", "/app/history");

    render(<App />);

    expect(screen.getByRole("link", { name: "Saved" })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  it("asks a signed-out visitor to sign in before opening the Research lab", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("link", { name: "Research lab" }));

    expect(window.location.pathname).toBe("/app/comparative");
    expect(
      screen.getByRole("heading", { name: "UrbanFlow" }),
    ).toBeInTheDocument();
  });

  it("gives every view tab its own URL and follows back/forward", async () => {
    signIn();
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("link", { name: "Research lab" }));
    expect(window.location.pathname).toBe("/app/research");
    expect(
      screen.getByRole("heading", {
        name: /how urbanflow compares traffic control/i,
      }),
    ).toBeInTheDocument();

    const researchNav = () =>
      within(screen.getByRole("navigation", { name: "Research tools" }));
    await user.click(
      researchNav().getByRole("link", { name: /traffic-level sweep/i }),
    );
    expect(window.location.pathname).toBe("/app/volume");
    expect(
      researchNav().getByRole("link", { name: /traffic-level sweep/i }),
    ).toHaveAttribute("aria-current", "page");
    // The section tab stays current for every research tool.
    expect(screen.getByRole("link", { name: "Research lab" })).toHaveAttribute(
      "aria-current",
      "page",
    );

    act(() => {
      window.history.replaceState(null, "", "/app/signal");
      window.dispatchEvent(new PopStateEvent("popstate"));
    });
    expect(
      researchNav().getByRole("link", { name: /signal on its own/i }),
    ).toHaveAttribute("aria-current", "page");
  });

  describe("Your own junction tab", () => {
    const researchNav = () =>
      within(screen.getByRole("navigation", { name: "Research tools" }));
    const studyHeading = /your own junction: a controlled study/i;

    it("is a Research lab tab, next to the Overview and the three-way study", async () => {
      signIn();
      const user = userEvent.setup();
      render(<App />);
      await user.click(screen.getByRole("link", { name: "Research lab" }));

      const labels = researchNav()
        .getAllByRole("link")
        .map((link) => link.textContent);
      expect(labels).toEqual([
        "Overview",
        "Your own junction",
        "Three-way study",
        "Statistical validation",
        "Traffic-level sweep",
        "Signal on its own",
        "Roundabout on its own",
      ]);
      expect(
        researchNav().getByRole("link", { name: "Your own junction" }),
      ).toHaveAttribute("href", "/app/junction");
    });

    it("keeps the study off the Research lab overview", async () => {
      signIn();
      const user = userEvent.setup();
      render(<App />);
      await user.click(screen.getByRole("link", { name: "Research lab" }));

      expect(
        screen.getByRole("heading", {
          name: /how urbanflow compares traffic control/i,
        }),
      ).toBeInTheDocument();
      expect(
        screen.queryByRole("heading", { name: studyHeading }),
      ).not.toBeInTheDocument();
      expect(screen.queryByLabelText("Scenario name")).not.toBeInTheDocument();
      // The overview still offers it: the tab, plus a card linking to it.
      const links = screen.getAllByRole("link", { name: /your own junction/i });
      expect(links.length).toBeGreaterThanOrEqual(2);
      for (const link of links) {
        expect(link).toHaveAttribute("href", "/app/junction");
      }
    });

    it("opens the existing study and switches cleanly with Statistical validation", async () => {
      signIn();
      const user = userEvent.setup();
      render(<App />);
      await user.click(screen.getByRole("link", { name: "Research lab" }));

      await user.click(
        researchNav().getByRole("link", { name: "Your own junction" }),
      );
      expect(window.location.pathname).toBe("/app/junction");
      expect(
        await screen.findByRole("heading", { level: 1, name: studyHeading }),
      ).toBeInTheDocument();
      expect(
        researchNav().getByRole("link", { name: "Your own junction" }),
      ).toHaveAttribute("aria-current", "page");
      expect(
        screen.getByRole("link", { name: "Research lab" }),
      ).toHaveAttribute("aria-current", "page");
      expect(screen.getByLabelText("Scenario name")).toBeInTheDocument();
      expect(
        screen.getByRole("button", {
          name: /run the study \(15 simulations\)/i,
        }),
      ).toBeInTheDocument();
      // Nothing from the other research pages shares the screen.
      expect(
        screen.queryByRole("heading", {
          name: /how urbanflow compares traffic control/i,
        }),
      ).not.toBeInTheDocument();

      await user.click(
        researchNav().getByRole("link", { name: "Statistical validation" }),
      );
      expect(window.location.pathname).toBe("/app/validation");
      expect(
        await screen.findByRole("heading", {
          name: /statistical validation studio/i,
        }),
      ).toBeInTheDocument();
      expect(
        screen.queryByRole("heading", { name: studyHeading }),
      ).not.toBeInTheDocument();
      expect(screen.queryByLabelText("Scenario name")).not.toBeInTheDocument();

      await user.click(
        researchNav().getByRole("link", { name: "Your own junction" }),
      );
      expect(
        await screen.findByRole("heading", { level: 1, name: studyHeading }),
      ).toBeInTheDocument();
      expect(screen.getAllByLabelText("Scenario name")).toHaveLength(1);
      expect(
        screen.queryByRole("heading", {
          name: /statistical validation studio/i,
        }),
      ).not.toBeInTheDocument();
    });

    it("opens straight from its URL, as after a refresh", async () => {
      window.history.replaceState(null, "", "/app/junction");
      render(<App />);

      expect(
        await screen.findByRole("heading", { level: 1, name: studyHeading }),
      ).toBeInTheDocument();
      expect(
        researchNav().getByRole("link", { name: "Your own junction" }),
      ).toHaveAttribute("aria-current", "page");
      expect(
        screen.getByRole("link", { name: "Research lab" }),
      ).toHaveAttribute("aria-current", "page");
    });
  });

  describe("Three-way study tab", () => {
    const researchNav = () =>
      within(screen.getByRole("navigation", { name: "Research tools" }));

    it("is reached from the overview and from its own tab", async () => {
      signIn();
      const user = userEvent.setup();
      render(<App />);
      await user.click(screen.getByRole("link", { name: "Research lab" }));

      // The overview's methodology button leads to the method page.
      await user.click(screen.getByRole("link", { name: "Methodology" }));
      expect(window.location.pathname).toBe("/app/three-way");
      expect(
        await screen.findByRole("heading", {
          level: 1,
          name: "Three-way study",
        }),
      ).toBeInTheDocument();
      expect(
        researchNav().getByRole("link", { name: "Three-way study" }),
      ).toHaveAttribute("aria-current", "page");
      expect(
        screen.getByRole("link", { name: "Research lab" }),
      ).toHaveAttribute("aria-current", "page");
      // Nothing from the overview shares the page, and the run controls live here.
      expect(
        screen.queryByRole("heading", {
          name: /how urbanflow compares traffic control/i,
        }),
      ).not.toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: /run the three-way study/i }),
      ).toBeInTheDocument();

      await user.click(researchNav().getByRole("link", { name: "Overview" }));
      expect(
        await screen.findByRole("heading", {
          name: /how urbanflow compares traffic control/i,
        }),
      ).toBeInTheDocument();
      expect(
        screen.queryByRole("heading", { level: 1, name: "Three-way study" }),
      ).not.toBeInTheDocument();
    });

    it("opens straight from its URL, as after a refresh", async () => {
      window.history.replaceState(null, "", "/app/three-way");
      render(<App />);
      expect(
        await screen.findByRole("heading", {
          level: 1,
          name: "Three-way study",
        }),
      ).toBeInTheDocument();
      expect(
        researchNav().getByRole("link", { name: "Three-way study" }),
      ).toHaveAttribute("aria-current", "page");
    });

    it("keeps every other research tool one click away", async () => {
      signIn();
      const user = userEvent.setup();
      render(<App />);
      await user.click(screen.getByRole("link", { name: "Research lab" }));
      for (const [name, path] of [
        ["Your own junction", "/app/junction"],
        ["Three-way study", "/app/three-way"],
        ["Statistical validation", "/app/validation"],
        ["Traffic-level sweep", "/app/volume"],
        ["Signal on its own", "/app/signal"],
        ["Roundabout on its own", "/app/roundabout"],
      ] as const) {
        expect(researchNav().getByRole("link", { name })).toHaveAttribute(
          "href",
          path,
        );
      }
    });
  });

  it("redirects the legacy /app.html entry to the default view", async () => {
    window.history.replaceState(null, "", "/app.html");

    render(<App />);

    await waitFor(() => {
      expect(window.location.pathname).toBe("/app/comparative");
    });
    expect(screen.getByRole("link", { name: "Compare" })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  it("renders a not-found page for unknown routes instead of a dashboard", () => {
    window.history.replaceState(null, "", "/app/does-not-exist");

    render(<App />);

    expect(
      screen.getByRole("heading", { name: /page not found/i }),
    ).toBeInTheDocument();
    expect(updateSimulationConfig).not.toHaveBeenCalled();
  });

  it("opens a saved run directly from its URL, inside History", async () => {
    getRunRecord.mockResolvedValue(RUN_RECORD);
    window.history.replaceState(null, "", "/app/runs/run_1");

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Saved roundabout" }),
    ).toBeInTheDocument();
    expect(getRunRecord).toHaveBeenCalledWith("run_1");
    expect(screen.getByRole("link", { name: "Saved" })).toHaveAttribute(
      "aria-current",
      "page",
    );

    // Back to History and forward again.
    act(() => {
      window.history.replaceState(null, "", "/app/history");
      window.dispatchEvent(new PopStateEvent("popstate"));
    });
    expect(
      await screen.findByRole("heading", { name: "Saved runs" }),
    ).toBeInTheDocument();
    act(() => {
      window.history.replaceState(null, "", "/app/runs/run_1");
      window.dispatchEvent(new PopStateEvent("popstate"));
    });
    expect(
      await screen.findByRole("heading", { name: "Saved roundabout" }),
    ).toBeInTheDocument();
  });

  it("restores a saved run into its simulation view from the run page", async () => {
    const user = userEvent.setup();
    getRunRecord.mockResolvedValue(RUN_RECORD);
    getReplay.mockResolvedValue({
      id: "run_1",
      name: "Saved roundabout",
      config: {
        simulation: { randomSeed: 77, duration: 300 },
        geometry: { intersectionType: "roundabout" },
      },
      // Stored metrics are the collector's full metrics object.
      metrics: {
        throughput: 12,
        averageWaitTime: 3,
        currentQueueLengths: { north: 0, south: 1, east: 0, west: 2 },
      },
      created_at: "2026-09-22 10:00:00",
    });
    window.history.replaceState(null, "", "/app/runs/run_1");
    render(<App />);

    await user.click(
      await screen.findByRole("button", { name: "Open in simulator" }),
    );
    await waitFor(() => {
      expect(window.location.pathname).toBe("/app/roundabout");
    });
    await waitFor(() => {
      const last = updateSimulationConfig.mock.lastCall?.[0] as {
        randomSeed: number;
        intersectionType: string;
      };
      expect(last.randomSeed).toBe(77);
      expect(last.intersectionType).toBe("roundabout");
    });
  });

  it("opens the run comparison from its URL", async () => {
    getRunRecord.mockImplementation((id: string) =>
      Promise.resolve({ ...RUN_RECORD, runId: id, name: `Run ${id}` }),
    );
    window.history.replaceState(null, "", "/app/compare?runs=r1,r2");

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Compare saved runs" }),
    ).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "Run r2" })).toBeVisible();
  });

  it("treats a malformed run URL as not found", () => {
    window.history.replaceState(null, "", "/app/runs/bad.id");
    render(<App />);
    expect(
      screen.getByRole("heading", { name: /page not found/i }),
    ).toBeInTheDocument();
  });
});
