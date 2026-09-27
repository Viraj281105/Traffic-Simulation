import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { RunRecord } from "../services/api";

const getRunRecord = vi.fn();
const listReplays = vi.fn();

vi.mock("../services/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../services/api")>()),
  getRunRecord: (id: string) => getRunRecord(id) as Promise<unknown>,
  listReplays: () => listReplays() as Promise<unknown>,
}));

import { ApiError } from "../services/api";
import { ComparePage } from "../components/ComparePage";

function record(overrides: Partial<RunRecord>): RunRecord {
  return {
    runId: "run_a",
    name: "Signal A",
    notes: null,
    tags: [],
    batchId: "replay",
    createdAt: "2026-09-22 10:00:00",
    status: "completed",
    intersectionType: "fixed_time_signal",
    provenanceRecorded: true,
    runMode: "single",
    seed: 1,
    gitCommitHash: "aaaaaaa1111111",
    pythonVersion: "3.11.9",
    configSource: "engine",
    configAvailable: true,
    exactConfig: true,
    timing: { timeStep: 0.1, duration: 300, warmupTime: 30, elapsed: 300 },
    config: { traffic: { arrivalRate: 0.3 }, simulation: { randomSeed: 1 } },
    summaryMetrics: {
      throughput: 50,
      averageDelay: 10,
      petApplicable: true,
      minPET: 1.2,
    },
    savedReplay: true,
    ...overrides,
  };
}

const signal = record({});
const roundabout = record({
  runId: "run_b",
  name: "Roundabout B",
  intersectionType: "roundabout",
  seed: 2,
  config: { traffic: { arrivalRate: 0.5 }, simulation: { randomSeed: 2 } },
  // No averageDelay stored: must stay unavailable, not become 0.
  summaryMetrics: { throughput: 62, petApplicable: false, minPET: null },
});

function metricRow(key: string): HTMLElement {
  const row = document.querySelector<HTMLElement>(`tr[data-metric="${key}"]`);
  if (!row) throw new Error(`no row for ${key}`);
  return row;
}

beforeEach(() => {
  vi.clearAllMocks();
  listReplays.mockResolvedValue([]);
  getRunRecord.mockImplementation((id: string) => {
    const found = [signal, roundabout].find((r) => r.runId === id);
    return found
      ? Promise.resolve(found)
      : Promise.reject(new ApiError(404, "Not Found"));
  });
});

describe("ComparePage", () => {
  it("compares stored metrics with explicit, unit-bearing differences", async () => {
    window.history.replaceState(null, "", "/app/compare?runs=run_a,run_b");
    render(<ComparePage />);
    await screen.findByRole("link", { name: "Roundabout B" });

    const served = within(metricRow("throughput")).getAllByRole("cell");
    expect(served[0]).toHaveTextContent("50");
    expect(served[1]).toHaveTextContent("62");
    expect(served[1]).toHaveTextContent("Δ +12 veh");

    // Missing on one side: shown as —, and no difference is computed.
    const delay = within(metricRow("averageDelay")).getAllByRole("cell");
    expect(delay[0]).toHaveTextContent("10.0");
    expect(delay[1]).toHaveTextContent("—");
    expect(delay[1]).toHaveTextContent("Δ —");
    expect(delay[1]).not.toHaveTextContent("0.0");

    // PET is not applicable to the roundabout run.
    const pet = within(metricRow("minPET")).getAllByRole("cell");
    expect(pet[1]).toHaveTextContent("N/A");

    // Descriptive notes only; no ranking.
    expect(screen.getByText(/different random seeds/i)).toBeInTheDocument();
    expect(screen.queryByText(/winner|better run|recommend/i)).toBeNull();

    // Settings that differ between the stored configurations.
    const settings = screen.getByRole("rowheader", {
      name: "traffic.arrivalRate",
    });
    expect(settings.closest("tr")).toHaveTextContent("0.30.5");
  });

  it("can switch the baseline the differences are relative to", async () => {
    const user = userEvent.setup();
    window.history.replaceState(null, "", "/app/compare?runs=run_a,run_b");
    render(<ComparePage />);
    await screen.findByRole("link", { name: "Roundabout B" });
    await user.selectOptions(
      screen.getByLabelText("Differences relative to"),
      "run_b",
    );
    const served = within(metricRow("throughput")).getAllByRole("cell");
    expect(served[0]).toHaveTextContent("Δ −12 veh");
  });

  it("reports a missing run and asks for at least two", async () => {
    window.history.replaceState(null, "", "/app/compare?runs=run_a,gone");
    render(<ComparePage />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Run gone was not found",
    );
    expect(
      screen.getByText("Choose at least two saved runs to compare."),
    ).toBeInTheDocument();
  });

  it("offers saved runs to add", async () => {
    const user = userEvent.setup();
    window.history.replaceState(null, "", "/app/compare?runs=run_a");
    listReplays.mockResolvedValue([
      { id: "run_a", name: "Signal A" },
      { id: "run_b", name: "Roundabout B" },
    ]);
    render(<ComparePage />);
    const picker = await screen.findByLabelText("Add a saved run");
    await screen.findByRole("option", { name: /Roundabout B/ });
    expect(
      screen.queryByRole("option", { name: /Signal A/ }),
    ).not.toBeInTheDocument();
    await user.selectOptions(picker, "run_b");
    expect(window.location.search).toBe("?runs=run_a,run_b");
  });
});
