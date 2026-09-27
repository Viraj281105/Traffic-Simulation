import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { SavedReplay } from "../components/HistoryDashboard";

const listReplays = vi.fn();

vi.mock("../services/api", () => ({
  listReplays: () => listReplays() as Promise<unknown>,
  deleteReplay: vi.fn(),
}));

import { HistoryDashboard } from "../components/HistoryDashboard";

const recorded: SavedReplay = {
  id: "0f3c9a1e-1111-4222-8333-944445555666",
  name: "Signal · seed 1234 · 120 s",
  config: {
    simulation: { duration: 300, randomSeed: 1234, elapsed: 120 },
    geometry: { intersectionType: "fixed_time_signal" },
  },
  metrics: { averageDelay: 12.34, throughput: 57 },
  created_at: "2026-09-22 10:00:00",
  reproducibility: {
    runId: "0f3c9a1e-1111-4222-8333-944445555666",
    name: "Signal · seed 1234 · 120 s",
    notes: null,
    tags: ["baseline"],
    batchId: "replay",
    createdAt: "2026-09-22 10:00:00",
    status: "completed",
    intersectionType: "fixed_time_signal",
    provenanceRecorded: true,
    runMode: "single",
    seed: 1234,
    gitCommitHash: "abcdef0123456789abcdef0123456789abcdef01",
    pythonVersion: "3.11.9",
    configSource: "engine",
    configAvailable: true,
    exactConfig: true,
    timing: { timeStep: 0.1, duration: 300, warmupTime: 30, elapsed: 120 },
  },
};

// A save from before run records existed: no reproducibility block at all.
const legacy: SavedReplay = {
  id: "legacy-run-0001",
  name: "Old run",
  config: {},
  metrics: {},
  created_at: "2026-01-01 09:00:00",
  reproducibility: null,
};

/** A run's row, found through its name link (the row header also holds
 *  the run's tags). */
function rowFor(name: string): HTMLElement {
  const link = screen.getByRole("link", { name });
  const row = link.closest("tr");
  if (!row) throw new Error("row not found");
  return row;
}

beforeEach(() => {
  listReplays.mockReset();
});

describe("HistoryDashboard reproducibility columns", () => {
  it("shows run ID, seed, commit and config status for a recorded run", async () => {
    listReplays.mockResolvedValue([recorded]);
    render(<HistoryDashboard onReplay={vi.fn()} />);
    await screen.findByRole("link", { name: recorded.name });

    const row = within(rowFor(recorded.name));
    expect(row.getByText("0f3c9a1e")).toHaveAttribute("title", recorded.id);
    expect(row.getByText("1234")).toBeInTheDocument();
    expect(row.getByText("abcdef0")).toHaveAttribute(
      "title",
      "abcdef0123456789abcdef0123456789abcdef01",
    );
    expect(row.getByText("Exact")).toBeInTheDocument();
    expect(row.getByText("12.3")).toBeInTheDocument();
    expect(row.getByText("57")).toBeInTheDocument();
  });

  it("shows — for metadata an older run never recorded", async () => {
    listReplays.mockResolvedValue([legacy]);
    render(<HistoryDashboard onReplay={vi.fn()} />);
    await screen.findByRole("link", { name: legacy.name });

    const cells = within(rowFor(legacy.name)).getAllByRole("cell");
    const texts = cells.map((c) => c.textContent);
    // Run ID still shows; seed, commit, config and metrics are unavailable.
    expect(texts).toContain("legacy-r");
    expect(texts.filter((t) => t === "—").length).toBeGreaterThanOrEqual(5);
    expect(screen.queryByText("Exact")).not.toBeInTheDocument();
  });

  it("labels an unreadable commit as unknown rather than hiding it", async () => {
    listReplays.mockResolvedValue([
      {
        ...recorded,
        reproducibility: {
          ...recorded.reproducibility,
          gitCommitHash: "unknown",
          exactConfig: false,
          configSource: "client",
        },
      },
    ]);
    render(<HistoryDashboard onReplay={vi.fn()} />);
    await screen.findByRole("link", { name: recorded.name });

    const row = within(rowFor(recorded.name));
    expect(row.getByText("unknown")).toBeInTheDocument();
    expect(row.getByText("Settings")).toBeInTheDocument();
  });

  it("links each run to its page and shows its tags", async () => {
    listReplays.mockResolvedValue([recorded]);
    render(<HistoryDashboard onReplay={vi.fn()} />);
    const link = await screen.findByRole("link", { name: recorded.name });
    expect(link).toHaveAttribute("href", `/app/runs/${recorded.id}`);
    expect(within(rowFor(recorded.name)).getByText("baseline")).toBeVisible();
  });
});

describe("HistoryDashboard comparison selection", () => {
  it("enables Compare selected for two runs and opens the comparison", async () => {
    const user = userEvent.setup();
    window.history.replaceState(null, "", "/app/history");
    listReplays.mockResolvedValue([recorded, legacy]);
    render(<HistoryDashboard onReplay={vi.fn()} />);
    await screen.findByRole("link", { name: legacy.name });

    const compare = screen.getByRole("button", { name: /compare selected/i });
    expect(compare).toBeDisabled();
    await user.click(
      screen.getByRole("checkbox", {
        name: `Select ${legacy.name} for comparison`,
      }),
    );
    expect(compare).toBeDisabled();
    await user.click(
      screen.getByRole("checkbox", {
        name: `Select ${recorded.name} for comparison`,
      }),
    );
    expect(compare).toBeEnabled();
    await user.click(compare);
    expect(window.location.pathname).toBe("/app/compare");
    expect(new URLSearchParams(window.location.search).get("runs")).toBe(
      `${legacy.id},${recorded.id}`,
    );
  });
});
