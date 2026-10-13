import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { RunRecord } from "../services/api";

const getRunRecord = vi.fn();
const getReplay = vi.fn();
const reproduceRun = vi.fn();
const updateRunMetadata = vi.fn();
const fetchRunExport = vi.fn();

vi.mock("../services/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../services/api")>()),
  getRunRecord: (id: string) => getRunRecord(id) as Promise<unknown>,
  getReplay: (id: string) => getReplay(id) as Promise<unknown>,
  reproduceRun: (id: string) => reproduceRun(id) as Promise<unknown>,
  updateRunMetadata: (id: string, c: unknown) =>
    updateRunMetadata(id, c) as Promise<unknown>,
  fetchRunExport: (id: string, format: string) =>
    fetchRunExport(id, format) as Promise<unknown>,
}));

import { ApiError } from "../services/api";
import { RunPage } from "../components/RunPage";
import { axeViolations } from "./axe";

const RUN_ID = "0f3c9a1e-1111-4222-8333-944445555666";

const exact: RunRecord = {
  runId: RUN_ID,
  name: "Roundabout baseline",
  notes: "first pass",
  tags: ["baseline"],
  batchId: "replay",
  createdAt: "2026-09-22 10:00:00",
  status: "completed",
  intersectionType: "roundabout",
  provenanceRecorded: true,
  runMode: "single",
  seed: 1234,
  gitCommitHash: "abcdef0123456789abcdef0123456789abcdef01",
  pythonVersion: "3.11.9",
  configSource: "engine",
  configAvailable: true,
  exactConfig: true,
  timing: { timeStep: 0.1, duration: 300, warmupTime: 30, elapsed: 120 },
  config: {
    simulation: { randomSeed: 1234, duration: 300 },
    geometry: { intersectionType: "roundabout" },
  },
  summaryMetrics: {
    throughput: 57,
    averageDelay: 12.34,
    petApplicable: false,
    minPET: null,
  },
  savedReplay: true,
};

const legacy: RunRecord = {
  ...exact,
  runId: "legacy_run",
  name: "Old run",
  notes: null,
  tags: [],
  intersectionType: "fixed_time_signal",
  provenanceRecorded: false,
  runMode: null,
  seed: null,
  gitCommitHash: null,
  pythonVersion: null,
  configSource: null,
  configAvailable: false,
  exactConfig: false,
  timing: { timeStep: null, duration: null, warmupTime: null, elapsed: null },
  config: null,
  summaryMetrics: {},
  savedReplay: false,
};

function fact(label: string): HTMLElement {
  const dt = screen.getByText(label, { selector: "dt" });
  const row = dt.closest(".run-fact");
  if (!(row instanceof HTMLElement)) throw new Error("fact not found");
  return within(row).getByRole("definition");
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("RunPage", () => {
  it("shows identity, provenance, configuration and catalog metrics", async () => {
    getRunRecord.mockResolvedValue(exact);
    render(<RunPage runId={RUN_ID} onOpenInSimulator={vi.fn()} />);

    expect(screen.getByRole("status")).toHaveTextContent("Loading run");
    expect(
      await screen.findByRole("heading", { name: "Roundabout baseline" }),
    ).toBeInTheDocument();
    expect(fact("Run ID")).toHaveTextContent(RUN_ID);
    expect(fact("Seed")).toHaveTextContent("1234");
    expect(fact("Git commit")).toHaveTextContent(exact.gitCommitHash ?? "");
    expect(fact("Intersection")).toHaveTextContent("Roundabout");
    expect(fact("Simulated time when saved")).toHaveTextContent("120 s");
    expect(screen.getByText("Exact configuration recorded.")).toBeVisible();
    expect(screen.getByText(/"randomSeed": 1234/)).toBeInTheDocument();

    // Metrics come from the shared catalog: labelled, with units.
    const served = document.querySelector('[data-metric="throughput"] dd');
    expect(served).toHaveTextContent("57 veh");
    // PET is not measured for a roundabout: N/A, never 0.
    const pet = document.querySelector('[data-metric="minPET"] dd');
    expect(pet).toHaveTextContent("N/A");
    // A metric the run did not store stays unavailable.
    const p95 = document.querySelector('[data-metric="p95Delay"] dd');
    expect(p95).toHaveTextContent("—");

    // Exports are buttons, not links: a saved run is private, so the file is
    // fetched with the user's token rather than by a tokenless link.
    expect(screen.getByRole("button", { name: "Export JSON" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Export CSV" })).toBeEnabled();
    expect(screen.queryByRole("link", { name: /Export/ })).toBeNull();
    expect(screen.getByLabelText("Tags (comma-separated)")).toHaveValue(
      "baseline",
    );
    expect(screen.getByLabelText("Notes")).toHaveValue("first pass");
  });

  it("downloads exports through the signed-in client", async () => {
    const user = userEvent.setup();
    getRunRecord.mockResolvedValue(exact);
    fetchRunExport.mockResolvedValue('{"exportVersion":1}');
    const created: Blob[] = [];
    const createObjectURL = vi.fn((blob: Blob) => {
      created.push(blob);
      return "blob:run";
    });
    const revokeObjectURL = vi.fn();
    Object.assign(URL, { createObjectURL, revokeObjectURL });
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => undefined);
    render(<RunPage runId={RUN_ID} onOpenInSimulator={vi.fn()} />);

    await user.click(
      await screen.findByRole("button", { name: "Export JSON" }),
    );

    expect(fetchRunExport).toHaveBeenCalledWith(RUN_ID, "json");
    await vi.waitFor(() => {
      expect(click).toHaveBeenCalledTimes(1);
    });
    expect(created[0].type).toBe("application/json");
    expect(created[0].size).toBe('{"exportVersion":1}'.length);
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:run");
    expect(screen.queryByRole("alert")).toBeNull();
    click.mockRestore();
  });

  it("says so when an export cannot be downloaded", async () => {
    const user = userEvent.setup();
    getRunRecord.mockResolvedValue(exact);
    fetchRunExport.mockRejectedValue(new ApiError(404, "Not Found"));
    render(<RunPage runId={RUN_ID} onOpenInSimulator={vi.fn()} />);

    await user.click(await screen.findByRole("button", { name: "Export CSV" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The CSV export could not be downloaded. Try again.",
    );
    expect(fetchRunExport).toHaveBeenCalledWith(RUN_ID, "csv");
    expect(screen.getByRole("button", { name: "Export CSV" })).toBeEnabled();
  });

  // axe walks the whole rendered document: about 3 s for the planner form on
  // an idle machine, past the default 5 s when the full suite runs alongside
  // other work. It waits only on rendered output, so the budget hides no race.
  it(
    "has no automatically detectable accessibility violations (axe)",
    { timeout: 15_000 },
    async () => {
      getRunRecord.mockResolvedValue(exact);
      // Inside <main>, as the app mounts it (PageTransition renders <main>).
      render(
        <main>
          <RunPage runId={RUN_ID} onOpenInSimulator={vi.fn()} />
        </main>,
      );
      await screen.findByRole("heading", { name: "Roundabout baseline" });
      expect(await axeViolations(document.body)).toEqual([]);
    },
  );

  it("shows a not-found state for an unknown run", async () => {
    getRunRecord.mockRejectedValue(new ApiError(404, "Not Found"));
    render(<RunPage runId="missing_run" onOpenInSimulator={vi.fn()} />);
    expect(
      await screen.findByRole("heading", { name: "Run not found" }),
    ).toBeInTheDocument();
    expect(screen.getByText("missing_run")).toBeInTheDocument();
  });

  it("shows an error with retry when loading fails", async () => {
    const user = userEvent.setup();
    const consoleError = vi
      .spyOn(console, "error")
      .mockImplementation(() => undefined);
    getRunRecord.mockRejectedValueOnce(new Error("offline"));
    render(<RunPage runId={RUN_ID} onOpenInSimulator={vi.fn()} />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "could not be loaded",
    );
    getRunRecord.mockResolvedValueOnce(exact);
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(
      await screen.findByRole("heading", { name: "Roundabout baseline" }),
    ).toBeInTheDocument();
    consoleError.mockRestore();
  });

  it("shows — for everything a legacy run did not record", async () => {
    getRunRecord.mockResolvedValue(legacy);
    render(<RunPage runId="legacy_run" onOpenInSimulator={vi.fn()} />);
    await screen.findByRole("heading", { name: "Old run" });
    expect(fact("Seed")).toHaveTextContent("—");
    expect(fact("Git commit")).toHaveTextContent("—");
    expect(fact("Time step")).toHaveTextContent("—");
    expect(
      screen.getByText("Recorded before provenance tracking."),
    ).toBeVisible();
    expect(
      screen.getByText("No metrics were stored with this run."),
    ).toBeVisible();
    expect(
      screen.getByText("No configuration was recorded for this run."),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Open in simulator" }),
    ).toBeDisabled();
  });

  it("restores the run through the History Open flow", async () => {
    const user = userEvent.setup();
    const onOpen = vi.fn();
    const replay = { id: RUN_ID, name: "Roundabout baseline", config: {} };
    getRunRecord.mockResolvedValue(exact);
    getReplay.mockResolvedValue(replay);
    render(<RunPage runId={RUN_ID} onOpenInSimulator={onOpen} />);
    await user.click(
      await screen.findByRole("button", { name: "Open in simulator" }),
    );
    expect(getReplay).toHaveBeenCalledWith(RUN_ID);
    expect(onOpen).toHaveBeenCalledWith(replay);
  });

  it("renames the run and saves notes and tags", async () => {
    const user = userEvent.setup();
    getRunRecord.mockResolvedValue(exact);
    updateRunMetadata.mockImplementation((_id: string, changes: object) =>
      Promise.resolve({ ...exact, ...changes }),
    );
    render(<RunPage runId={RUN_ID} onOpenInSimulator={vi.fn()} />);
    await user.click(await screen.findByRole("button", { name: "Rename" }));
    const input = screen.getByLabelText("Run name");
    await user.clear(input);
    await user.type(input, "Renamed");
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(updateRunMetadata).toHaveBeenCalledWith(RUN_ID, { name: "Renamed" });
    expect(
      await screen.findByRole("heading", { name: "Renamed" }),
    ).toBeInTheDocument();

    const tags = screen.getByLabelText("Tags (comma-separated)");
    await user.clear(tags);
    await user.type(tags, "peak, calibrated");
    await user.click(
      screen.getByRole("button", { name: "Save notes and tags" }),
    );
    expect(updateRunMetadata).toHaveBeenLastCalledWith(RUN_ID, {
      notes: "first pass",
      tags: ["peak", "calibrated"],
    });
  });

  it("reports headless reproduction with its limitations", async () => {
    const user = userEvent.setup();
    getRunRecord.mockResolvedValue(exact);
    reproduceRun.mockResolvedValue({
      runId: RUN_ID,
      mode: "single",
      seed: 1234,
      reproducedElapsed: 120,
      isDeterministic: true,
      comparedMetrics: ["averageDelay", "throughput"],
      tolerances: { averageDelaySeconds: 0.05, throughputVehicles: 0.1 },
      discrepancies: [],
      limitations: [
        "The run was recorded at commit abc; this server runs def.",
      ],
      recordedGitCommitHash: exact.gitCommitHash,
      provenance: { gitCommitHash: "fedcba9876", pythonVersion: "3.11.9" },
    });
    render(<RunPage runId={RUN_ID} onOpenInSimulator={vi.fn()} />);
    await user.click(
      await screen.findByRole("button", {
        name: "Verify reproduction (headless)",
      }),
    );
    expect(
      await screen.findByText(/Matched within tolerance/),
    ).toBeInTheDocument();
    expect(screen.getByText(/this server runs def/)).toBeInTheDocument();
  });

  it("presents a comparison run as signal and roundabout columns", async () => {
    getRunRecord.mockResolvedValue({
      ...exact,
      intersectionType: "comparative",
      runMode: "dual",
      summaryMetrics: {
        signal: { throughput: 40, petApplicable: true, minPET: 1.5 },
        roundabout: { throughput: 44, petApplicable: false, minPET: null },
      },
    });
    render(<RunPage runId={RUN_ID} onOpenInSimulator={vi.fn()} />);
    await screen.findByRole("heading", { name: "Roundabout baseline" });
    const row = document.querySelector<HTMLElement>(
      'tr[data-metric="throughput"]',
    );
    if (!row) throw new Error("throughput row missing");
    expect(
      within(row)
        .getAllByRole("cell")
        .map((c) => c.textContent),
    ).toEqual(["40 veh", "44 veh", "+4 veh"]);
    const pet = document.querySelector<HTMLElement>('tr[data-metric="minPET"]');
    if (!pet) throw new Error("PET row missing");
    const cells = within(pet).getAllByRole("cell");
    expect(cells[0]).toHaveTextContent("1.50 s");
    expect(cells[1]).toHaveTextContent("N/A");
    expect(cells[2]).toHaveTextContent("—");
  });
});
