/**
 * @vitest-environment jsdom
 *
 * The entry model (traffic.entryQueue) on the frontend: the setup control in
 * the guided questions and the junction builder, the dashboard payload and
 * scenario round trip, the live capacity card, and the saved-run comparison
 * caution when runs used different entry models.
 */
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  DEFAULT_CONFIG_VALUES,
  dashboardPayload,
  normalEntryQueue,
  sameConfigValues,
} from "../types/config";
import {
  configValuesFromScenario,
  describeEntryModel,
  sameScenario,
  scenarioFromConfigValues,
} from "../scenario/scenarioModel";
import { ScenarioSetup } from "../components/guided/ScenarioSetup";
import { AdvancedSettings } from "../components/scenario/AdvancedSettings";
import { EntryModelChoice } from "../components/scenario/EntryModelChoice";
import {
  ENTRY_POPULATIONS,
  entryModelSentence,
  outsideNetworkText,
} from "../metrics/entryModel";
import { entryModelOfConfig } from "../runs/savedRun";
import type { ScenarioDocument } from "../scenario/scenarioTypes";
import type { RunningMetrics } from "../types/simulation";
import { axeViolations } from "./axe";
import { ControlComparisonStudy } from "../components/ControlComparisonStudy";
import { servedDemandNote } from "../metrics/servedDemand";
import { completedJob } from "./studyJob";

vi.mock("../config", () => ({ API_BASE_URL: "http://localhost:8000" }));
vi.mock("../services/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../services/api")>()),
  listStrategies: () =>
    import("./strategyCatalogFixture").then((m) => m.STRATEGY_CATALOG),
}));

const QUEUED = {
  ...DEFAULT_CONFIG_VALUES,
  entryQueue: { enabled: true, capacity: null },
};

describe("dashboard payload", () => {
  it("is unchanged for the default entry model", () => {
    const body = dashboardPayload(DEFAULT_CONFIG_VALUES, "fixed_time_signal");
    expect(body).not.toHaveProperty("entryQueue");
    expect(
      dashboardPayload(
        { ...DEFAULT_CONFIG_VALUES, entryQueue: { enabled: false } },
        "fixed_time_signal",
      ),
    ).toEqual(body);
  });

  it("sends the point queue, with its limit, when chosen", () => {
    expect(dashboardPayload(QUEUED, "roundabout").entryQueue).toEqual({
      enabled: true,
      capacity: null,
    });
    expect(
      dashboardPayload(
        {
          ...DEFAULT_CONFIG_VALUES,
          entryQueue: { enabled: true, capacity: 8 },
        },
        "fixed_time_signal",
      ).entryQueue,
    ).toEqual({ enabled: true, capacity: 8 });
  });

  it("carries the queue inside a scenario document, not beside it", () => {
    const doc = scenarioFromConfigValues(QUEUED);
    expect(doc.traffic?.entryQueue).toEqual({ enabled: true, capacity: null });
    const body = dashboardPayload(
      configValuesFromScenario(doc, DEFAULT_CONFIG_VALUES),
      "fixed_time_signal",
    );
    expect(body).not.toHaveProperty("entryQueue");
    expect(body.scenario?.traffic?.entryQueue).toEqual({
      enabled: true,
      capacity: null,
    });
  });

  it("compares settings by the model that runs", () => {
    expect(
      sameConfigValues(DEFAULT_CONFIG_VALUES, {
        ...DEFAULT_CONFIG_VALUES,
        entryQueue: { enabled: false, capacity: 4 },
      }),
    ).toBe(true);
    expect(sameConfigValues(DEFAULT_CONFIG_VALUES, QUEUED)).toBe(false);
    expect(
      sameConfigValues(QUEUED, {
        ...QUEUED,
        entryQueue: { enabled: true, capacity: 10 },
      }),
    ).toBe(false);
    expect(normalEntryQueue({ enabled: true })).toEqual({
      enabled: true,
      capacity: null,
    });
  });
});

describe("scenario documents", () => {
  it("round-trip the entry model and default to holding arrivals back", () => {
    const plain = scenarioFromConfigValues(DEFAULT_CONFIG_VALUES);
    expect(plain.traffic?.entryQueue).toBeUndefined();
    expect(configValuesFromScenario(plain, QUEUED).entryQueue).toBeNull();
    const queued = scenarioFromConfigValues({
      ...DEFAULT_CONFIG_VALUES,
      entryQueue: { enabled: true, capacity: 12 },
    });
    expect(
      configValuesFromScenario(queued, DEFAULT_CONFIG_VALUES).entryQueue,
    ).toEqual({ enabled: true, capacity: 12 });
  });

  it("treat a disabled queue as the same scenario as none", () => {
    const plain = scenarioFromConfigValues(DEFAULT_CONFIG_VALUES);
    const disabled: ScenarioDocument = {
      ...plain,
      traffic: { ...plain.traffic, entryQueue: { enabled: false } },
    };
    expect(sameScenario(plain, disabled)).toBe(true);
    const queued: ScenarioDocument = {
      ...plain,
      traffic: { ...plain.traffic, entryQueue: { enabled: true } },
    };
    expect(sameScenario(plain, queued)).toBe(false);
  });

  it("name the queue in the scenario description", () => {
    expect(describeEntryModel(null)).toBe("");
    expect(describeEntryModel({ enabled: false })).toBe("");
    expect(describeEntryModel({ enabled: true })).toBe(
      "; arrivals queue outside the map",
    );
    expect(describeEntryModel({ enabled: true, capacity: 5 })).toMatch(
      /at most 5 per road/,
    );
  });
});

describe("entry model control", () => {
  it("explains every vehicle population and has no accessibility violations", async () => {
    const { container } = render(
      <EntryModelChoice value={null} onChange={() => {}} />,
    );
    const group = screen.getByRole("radiogroup", {
      name: "When traffic cannot get in",
    });
    const hold = within(group).getByRole("radio", {
      name: "Hold arrivals back",
    });
    expect(hold).toBeChecked();
    // Named by the title alone; the summary is its description.
    expect(hold).toHaveAccessibleDescription(/every earlier result/);
    expect(
      within(group).getByRole("radio", { name: "Queue outside the map" }),
    ).toHaveAccessibleDescription(/Wait to enter/);
    for (const p of ENTRY_POPULATIONS) {
      expect(screen.getByText(p.term)).toBeInTheDocument();
    }
    expect(ENTRY_POPULATIONS.map((p) => p.term)).toEqual([
      "Waiting outside",
      "Admitted",
      "Exited",
      "Still in the network",
      "Rejected",
    ]);
    expect(await axeViolations(container)).toEqual([]);
  });

  it("runs the guided comparison with the queue and its limit", async () => {
    const onRun = vi.fn();
    render(
      <ScenarioSetup
        config={DEFAULT_CONFIG_VALUES}
        onRun={onRun}
        runInProgress={false}
      />,
    );
    await userEvent.click(
      await screen.findByRole("radio", { name: /Queue outside the map/ }),
    );
    const limit = screen.getByLabelText("Queue limit per road");
    await userEvent.type(limit, "25");
    expect(screen.getByText("arrivals queue outside the map")).toBeVisible();
    await userEvent.click(
      screen.getByRole("button", {
        name: /Run 2 strategies|Run the simulation/,
      }),
    );
    expect(onRun).toHaveBeenCalledWith(
      expect.objectContaining({
        entryQueue: { enabled: true, capacity: 25 },
      }),
    );
  });

  it("keeps the default model for a run that never touches it", async () => {
    const onRun = vi.fn();
    render(
      <ScenarioSetup
        config={DEFAULT_CONFIG_VALUES}
        onRun={onRun}
        runInProgress={false}
      />,
    );
    await userEvent.click(
      await screen.findByRole("button", {
        name: /Run 2 strategies|Run the simulation/,
      }),
    );
    const sent = onRun.mock.calls[0][0] as typeof QUEUED;
    expect(normalEntryQueue(sent.entryQueue)).toBeNull();
    expect(dashboardPayload(sent, "fixed_time_signal")).not.toHaveProperty(
      "entryQueue",
    );
  });

  it("sets and clears the document's queue in the junction builder", async () => {
    let doc = scenarioFromConfigValues(DEFAULT_CONFIG_VALUES);
    const update = (mutate: (d: ScenarioDocument) => void) => {
      const next = structuredClone(doc);
      mutate(next);
      doc = next;
    };
    const { rerender } = render(
      <AdvancedSettings value={doc} update={update} />,
    );
    await userEvent.click(
      screen.getByRole("radio", { name: /Queue outside the map/ }),
    );
    expect(doc.traffic?.entryQueue).toEqual({ enabled: true, capacity: null });
    rerender(<AdvancedSettings value={doc} update={update} />);
    await userEvent.click(
      screen.getByRole("radio", { name: /Hold arrivals back/ }),
    );
    expect(doc.traffic).not.toHaveProperty("entryQueue");
    // The aggression profile in the same block is kept.
    expect(doc.traffic?.driverAggression).toBeDefined();
  });
});

describe("live and saved results", () => {
  const accounting = (
    entryModel: "suspend" | "queue",
    waitingAtEntry: number,
    rejected: number,
  ) =>
    ({
      demandAccounting: {
        entryModel,
        arrivals: 100,
        admitted: 100 - waitingAtEntry - rejected,
        waitingAtEntry,
        rejected,
        entryBlockedSeconds: 0,
        nominalDemand: 100,
        estimatedSuppressedArrivals: 0,
        meanEntryWaitSeconds: null,
        maxEntryWaitSeconds: 0,
        oldestWaitingSeconds: null,
        admittedShareOfNominal: 0.9,
        demandFiguresAreEstimates: true,
        byApproach: {},
      },
    }) as unknown as RunningMetrics;

  it("show vehicles outside the network only under the queue model", () => {
    expect(outsideNetworkText(accounting("suspend", 1, 0))).toBeNull();
    expect(outsideNetworkText(accounting("queue", 7, 0))).toBe(
      "7 waiting outside",
    );
    expect(outsideNetworkText(accounting("queue", 7, 3))).toBe(
      "7 waiting outside, 3 rejected",
    );
  });

  it("read the entry model of a stored configuration", () => {
    expect(entryModelOfConfig(null)).toBeNull();
    expect(entryModelOfConfig({ traffic: { arrivalRate: 0.5 } })).toBe(
      "suspend",
    );
    expect(
      entryModelOfConfig({ traffic: { entryQueue: { enabled: true } } }),
    ).toBe("queue");
    expect(
      entryModelOfConfig({
        scenario: { traffic: { entryQueue: { enabled: true } } },
      }),
    ).toBe("queue");
    expect(
      entryModelOfConfig({ traffic: { entryQueue: { enabled: false } } }),
    ).toBe("suspend");
  });
});

const STAT = (mean: number) => ({
  mean,
  ci: 1.5,
  ciConfidence: 0.95,
  ciDegreesOfFreedom: 4,
});

/** A three-way study at one level under the point queue, where fixed-time
 *  has the lower in-network delay but its vehicles waited longer outside
 *  (the checkpoint 9 measurement at 900 veh/h per arm, rounded). */
const QUEUE_STUDY = {
  controls: ["fixed_time", "adaptive", "roundabout"],
  lanesPerApproach: 1,
  seeds: [1, 2, 3],
  duration: 600,
  warmupTime: 60,
  confidenceLevel: 0.95,
  adaptiveSettings: {},
  calibration: { calibrated: false, note: "Exploratory." },
  tieTolerance: { absSeconds: 1, relative: 0.05 },
  collisionCount: { fixed_time: 0, adaptive: 0, roundabout: 0 },
  entryModel: { model: "queue", capacity: null },
  method: {
    design: "Same seeds.",
    interval: "t",
    delayComparison: "Paired per-seed differences.",
  },
  results: [
    {
      level: "over",
      demandVph: 3600,
      degreeOfSaturation: 1.2,
      vehicleLimitReached: false,
      controls: {
        fixed_time: { averageDelay: STAT(154), averageEntryWait: STAT(80) },
        adaptive: { averageDelay: STAT(160), averageEntryWait: STAT(78) },
        roundabout: { averageDelay: STAT(157), averageEntryWait: STAT(63) },
      },
      delayComparisons: {
        fixed_time_vs_roundabout: {
          meanDifference: -3.3,
          ciLow: -6,
          ciHigh: -0.6,
          reading: "lower",
          servedDemand: {
            admittedShareOfNominalDifference: -0.01,
            unfinishedShareDifference: -0.01,
            comparable: true,
            lowerDelayServedLess: false,
            averageEntryWaitDifference: 17.4,
            entryWaitReversesDelay: true,
          },
        },
      },
    },
  ],
};

describe("study results under the point queue", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  it("word the entry-wait caution without a verdict", () => {
    const base = {
      admittedShareOfNominalDifference: 0,
      unfinishedShareDifference: 0,
      comparable: true,
      lowerDelayServedLess: false,
    };
    expect(servedDemandNote(base)).toBeNull();
    const note = servedDemandNote({ ...base, entryWaitReversesDelay: true });
    expect(note).toMatch(/wait to enter/);
    expect(note).not.toMatch(/better|worse/i);
    // Both cautions together.
    expect(
      servedDemandNote({
        ...base,
        lowerDelayServedLess: true,
        entryWaitReversesDelay: true,
      }),
    ).toMatch(/served less.*wait to enter/s);
  });

  it("name the queue only when a study ran it", () => {
    expect(entryModelSentence(undefined)).toBeNull();
    expect(entryModelSentence({ model: "suspend", capacity: null })).toBeNull();
    expect(entryModelSentence({ model: "queue", capacity: null })).toMatch(
      /queue outside the map/,
    );
    expect(entryModelSentence({ model: "queue", capacity: 9 })).toMatch(
      /at most 9 per road/,
    );
  });

  it("sends the chosen model and shows the wait to enter beside delay", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(completedJob(QUEUE_STUDY)), { status: 202 }),
    );
    render(<ControlComparisonStudy />);
    await userEvent.click(
      screen.getByRole("radio", { name: /Queue outside the map/ }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: /Run the three-way study/ }),
    );
    await waitFor(() => {
      expect(screen.getByText(/Mean delay per vehicle/)).toBeInTheDocument();
    });
    expect(
      JSON.parse(vi.mocked(fetch).mock.calls[0][1]?.body as string),
    ).toEqual({
      lanes: 1,
      numSeeds: 5,
      duration: 300,
      entryQueue: { enabled: true, capacity: null },
    });
    expect(
      screen.getByText(/waited in a queue outside the map/),
    ).toBeInTheDocument();
    const delay = screen.getByRole("table", { name: /Mean delay per vehicle/ });
    expect(
      within(delay).getByText(/Counting the wait to enter as well/),
    ).toBeInTheDocument();
    const served = screen.getByRole("table", { name: /Throughput, queue/ });
    expect(
      within(served).getByRole("columnheader", { name: "Wait to enter (s)" }),
    ).toBeInTheDocument();
    expect(within(served).getByText("63.0 ± 1.5")).toBeInTheDocument();
  });

  it("adds no column for a default study", async () => {
    const { entryModel: _unused, ...plain } = QUEUE_STUDY;
    void _unused;
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(completedJob(plain)), { status: 202 }),
    );
    render(<ControlComparisonStudy />);
    await userEvent.click(
      screen.getByRole("button", { name: /Run the three-way study/ }),
    );
    await waitFor(() => {
      expect(screen.getByText(/Mean delay per vehicle/)).toBeInTheDocument();
    });
    expect(
      JSON.parse(vi.mocked(fetch).mock.calls[0][1]?.body as string),
    ).not.toHaveProperty("entryQueue");
    expect(screen.queryByText("Wait to enter (s)")).toBeNull();
    expect(screen.queryByText(/queue outside the map/)).toBeNull();
  });
});
