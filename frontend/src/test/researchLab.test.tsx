/**
 * Research lab information architecture: the Overview teaches, the tools run
 * studies, the three-way study page holds the method. These tests cover what
 * each page shows, where it sends you, and that the diagrams are labelled and
 * keyboard-reachable. Statistical outputs themselves are covered by
 * evidence.test.ts and adaptiveSignal.test.tsx.
 */
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { completedJob } from "./studyJob";
import { ResearchHub } from "../components/ResearchHub";
import { ThreeWayStudyPage } from "../components/ThreeWayStudyPage";
import { JunctionStudyPage } from "../components/JunctionStudyPage";
import { METRICS } from "../metrics/catalog";
import { resolveRoute, VIEW_ROUTES } from "../routing";

vi.mock("../services/scenarioApi", () => ({
  validateScenario: vi.fn().mockResolvedValue({
    valid: true,
    errors: [],
    warnings: [],
    strategies: ["fixed_time", "adaptive", "roundabout"],
  }),
  compileScenario: vi.fn(),
}));

const metricLabel = (key: string) => {
  const def = METRICS.find((m) => m.key === key);
  if (!def) throw new Error(`no metric ${key}`);
  return def;
};

describe("Overview", () => {
  it("answers the orientation questions in order", () => {
    render(<ResearchHub />);
    expect(
      screen.getByRole("heading", {
        level: 1,
        name: /how urbanflow compares traffic control/i,
      }),
    ).toBeInTheDocument();
    const headings = screen
      .getAllByRole("heading", { level: 2 })
      .map((h) => h.textContent);
    expect(headings).toEqual([
      "How a study proceeds",
      "Three ways to run a junction",
      "What the measures mean",
      "Why one run is not enough",
      "What the evidence can and cannot say",
      "Where to go next",
    ]);
  });

  it("no longer carries the three-way methodology or its run controls", () => {
    render(<ResearchHub />);
    expect(
      screen.queryByRole("heading", { name: /three-way study/i, level: 2 }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /run the three-way study/i }),
    ).not.toBeInTheDocument();
    // "Matched seeds" appears only as a pointer on the tool card, never as a
    // section of its own.
    expect(
      screen.queryByRole("heading", { name: /matched seeds/i }),
    ).not.toBeInTheDocument();
    for (const mention of screen.queryAllByText(/matched seeds/i)) {
      expect(mention.closest(".tool-card")).not.toBeNull();
    }
    expect(screen.queryByText(/Student-t/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/How the adaptive signal decides/i)).toBeNull();
    // The study's own form is not on the overview, nor is the junction study.
    expect(screen.queryByLabelText("Scenario name")).not.toBeInTheDocument();
    expect(screen.queryByText(/Lanes per approach/i)).not.toBeInTheDocument();
  });

  it("draws the seven-stage workflow with what goes in and out", () => {
    render(<ResearchHub />);
    const stages = within(
      document.getElementById("workflow") as HTMLElement,
    ).getAllByRole("listitem");
    const titles = stages.map(
      (s) => within(s).getByRole("heading").textContent,
    );
    expect(titles).toEqual([
      "Junction setup",
      "Traffic demand",
      "Control strategies",
      "Simulation runs",
      "Metrics",
      "Statistical analysis",
      "Findings",
    ]);
    for (const stage of stages) {
      expect(within(stage).getByText("In")).toBeInTheDocument();
      expect(within(stage).getByText("Out")).toBeInTheDocument();
    }
  });

  it("explains the three controls with the engine's own defaults", () => {
    render(<ResearchHub />);
    const section = within(
      document.getElementById("strategies") as HTMLElement,
    );
    for (const name of ["Fixed-time signal", "Adaptive signal", "Roundabout"]) {
      expect(section.getByRole("heading", { name })).toBeInTheDocument();
    }
    expect(section.getByText("Green 30 s")).toBeInTheDocument();
    expect(section.getByText("Yellow 4 s")).toBeInTheDocument();
    expect(section.getByText("Min green 10 s")).toBeInTheDocument();
    expect(section.getByText("Max green 50 s")).toBeInTheDocument();
    expect(section.getByText("Critical gap 4.0 s")).toBeInTheDocument();
    // Each schematic says what it shows.
    const diagrams = section.getAllByRole("img", {
      name: /fixed-time signal:|adaptive signal:|roundabout:/i,
    });
    expect(diagrams).toHaveLength(3);
  });

  it("explains the measures UrbanFlow reports, from the catalog's own names", () => {
    render(<ResearchHub />);
    const section = within(document.getElementById("metrics") as HTMLElement);
    for (const key of [
      "averageDelay",
      "averageWaitTime",
      "averageStopsPerVehicle",
      "throughput",
      "averageQueueLength",
      "averageTravelSpeed",
      "travelTimeReliability",
    ]) {
      const def = metricLabel(key);
      const card = section
        .getByRole("heading", { level: 4, name: new RegExp(def.label) })
        .closest("article") as HTMLElement;
      expect(card).not.toBeNull();
      // The exact definition is the catalog's, unchanged.
      expect(card).toHaveTextContent(def.description);
      for (const label of [
        "Why it matters",
        "Reading an example",
        "Keep in mind",
      ]) {
        expect(within(card).getByText(label)).toBeInTheDocument();
      }
    }
    expect(
      section.getByRole("heading", { level: 4, name: /minimum ttc/i }),
    ).toBeInTheDocument();
  });

  it("separates a queue from throughput and does not equate small with good", () => {
    render(<ResearchHub />);
    const section = document.getElementById("metrics") as HTMLElement;
    expect(section).toHaveTextContent(/A smaller queue is not always better/);
    expect(section).toHaveTextContent(/Higher is not automatically better/);
    expect(section).toHaveTextContent(/vehicles waiting/i);
    expect(section).toHaveTextContent(/made it through/i);
  });

  it("says plainly which measures do not exist", () => {
    render(<ResearchHub />);
    const section = document.getElementById("metrics") as HTMLElement;
    const card = within(section)
      .getByRole("heading", { level: 4, name: /fuel use and emissions/i })
      .closest("article") as HTMLElement;
    expect(card).toHaveTextContent(/not available/i);
    expect(card).toHaveTextContent(/no fuel or emissions model/i);
    expect(section).toHaveTextContent(
      /surrogate indicator, not a crash probability/i,
    );
    expect(section).toHaveTextContent(
      /rather than a plain average travel time/i,
    );
  });

  it("labels example data as example data and updates with the run count", async () => {
    const user = userEvent.setup();
    render(<ResearchHub />);
    const section = within(
      document.getElementById("comparison") as HTMLElement,
    );
    expect(
      section.getByText(/example data, not an urbanflow result/i),
    ).toBeInTheDocument();

    const status = section.getByRole("status");
    expect(status).toHaveTextContent(/Inconclusive/);
    expect(status).toHaveTextContent(/includes 0/);
    const three = section.getByRole("button", { name: "After 3 runs" });
    const ten = section.getByRole("button", { name: "After 10 runs" });
    expect(three).toHaveAttribute("aria-pressed", "true");

    // Reachable and operable from the keyboard.
    await user.tab();
    ten.focus();
    expect(ten).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(ten).toHaveAttribute("aria-pressed", "true");
    expect(three).toHaveAttribute("aria-pressed", "false");
    expect(section.getByRole("status")).toHaveTextContent(/Control B lower/);
    expect(section.getByRole("status")).toHaveTextContent(/excludes 0/);
  });

  it("lays out the evidence from one run to a real-world claim", () => {
    render(<ResearchHub />);
    const ladder = screen.getByRole("list", {
      name: /evidence ladder/i,
    });
    const rungs = within(ladder)
      .getAllByRole("heading", { level: 3 })
      .map((h) => h.textContent);
    expect(rungs).toEqual([
      "A measured simulation output",
      "A pattern across repeated runs",
      "A statistically supported difference",
      "A real-world claim",
    ]);
    const section = document.getElementById("evidence") as HTMLElement;
    expect(section).toHaveTextContent(/Inconclusive is a result of its own/);
    expect(section).toHaveTextContent(/not observed traffic/);
    expect(section).toHaveTextContent(
      /surrogate proxies, not measured crash risk/,
    );
    expect(section).toHaveTextContent(/no emissions model/i);
    expect(section).toHaveTextContent(
      /not automatically a practically important/,
    );
    expect(section).toHaveTextContent(
      /does not declare one design better everywhere/,
    );
  });

  it("never leads to a dead end", () => {
    const { container } = render(<ResearchHub />);
    const hrefs = [...container.querySelectorAll("a[href]")].map(
      (a) => a.getAttribute("href") as string,
    );
    expect(hrefs.length).toBeGreaterThan(15);
    for (const href of hrefs) {
      if (href.startsWith("#")) {
        expect(document.getElementById(href.slice(1))).not.toBeNull();
      } else {
        expect(resolveRoute(href).kind).toBe("view");
      }
    }
    // Every Research lab tool is offered somewhere on the overview.
    for (const route of [
      VIEW_ROUTES.junction,
      VIEW_ROUTES.threeWay,
      VIEW_ROUTES.validation,
      VIEW_ROUTES.volume,
      VIEW_ROUTES.signal,
      VIEW_ROUTES.roundabout,
      VIEW_ROUTES.history,
    ]) {
      expect(hrefs).toContain(route);
    }
  });

  it("gives every diagram a text alternative or hides it as decoration", () => {
    const { container } = render(<ResearchHub />);
    for (const svg of container.querySelectorAll("svg")) {
      if (svg.getAttribute("aria-hidden") === "true") continue;
      if (svg.closest("[aria-hidden='true']")) continue;
      // Icons from the icon set are hidden; anything left is a diagram.
      expect(svg.getAttribute("role")).toBe("img");
      expect(svg.getAttribute("aria-label")?.length ?? 0).toBeGreaterThan(20);
    }
  });

  it("keeps the metric-by-question reference one click away", async () => {
    const user = userEvent.setup();
    render(<ResearchHub />);
    const summary = screen.getByText("All measures, by everyday question");
    await user.click(summary);
    expect(
      screen.getByRole("columnheader", { name: "Everyday question" }),
    ).toBeVisible();
    expect(screen.getByText("How much time do drivers lose?")).toBeVisible();
  });
});

const STAT = (mean: number) => ({
  mean,
  ci: 1.5,
  ciConfidence: 0.95,
  ciDegreesOfFreedom: 4,
});

const STUDY = {
  controls: ["fixed_time", "adaptive", "roundabout"],
  lanesPerApproach: 1,
  seeds: [1, 2, 3, 4, 5],
  duration: 300,
  warmupTime: 30,
  confidenceLevel: 0.95,
  adaptiveSettings: {},
  calibration: { calibrated: true, note: "Calibrated comparison." },
  tieTolerance: { absSeconds: 1, relative: 0.05 },
  collisionCount: { fixed_time: 0, adaptive: 0, roundabout: 0 },
  method: { design: "d", interval: "t", delayComparison: "p" },
  results: [
    {
      level: "light",
      demandVph: 310,
      degreeOfSaturation: 0.25,
      vehicleLimitReached: false,
      controls: {
        fixed_time: { averageDelay: STAT(20) },
        adaptive: { averageDelay: STAT(11) },
        roundabout: { averageDelay: STAT(6) },
      },
      delayComparisons: {
        adaptive_vs_fixed_time: {
          meanDifference: -9,
          ciLow: -11,
          ciHigh: -7,
          reading: "lower",
        },
        adaptive_vs_roundabout: {
          meanDifference: 0.4,
          ciLow: -1,
          ciHigh: 2,
          reading: "tie",
        },
        fixed_time_vs_roundabout: {
          meanDifference: 6,
          ciLow: -2,
          ciHigh: 14,
          reading: "inconclusive",
        },
      },
    },
  ],
};

describe("Three-way study page", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  it("holds the method, in the order a reader needs it", () => {
    render(<ThreeWayStudyPage />);
    expect(
      screen.getByRole("heading", { level: 1, name: "Three-way study" }),
    ).toBeInTheDocument();
    const headings = screen
      .getAllByRole("heading", { level: 2 })
      .map((h) => h.textContent);
    expect(headings).toEqual([
      "What is compared",
      "Matched seeds",
      "From seeds to a reading",
      "How the conclusion is classified",
      "Assumptions and limits",
      "Run the study",
    ]);
    // The adaptive signal's decision table moved here with its explanation.
    expect(
      screen.getByText("How the adaptive signal decides"),
    ).toBeInTheDocument();
    expect(screen.getByText("Maximum green / max-out")).toBeInTheDocument();
  });

  it("states the implemented confidence level, tolerance and decision order", () => {
    render(<ThreeWayStudyPage />);
    const rule = document.getElementById("rule") as HTMLElement;
    expect(rule).toHaveTextContent(
      /95 % interval of the per-seed gaps exclude 0/,
    );
    expect(rule).toHaveTextContent(
      /1 s, or 5 % of the larger mean, whichever is larger/,
    );
    expect(rule).toHaveTextContent(/not a significance test/);
    expect(rule).toHaveTextContent(/checked first, on the two means/);
    expect(rule).toHaveTextContent(
      /4\.303 with 3 seeds, 2\.776 with 5 and 2\.262 with 10/,
    );
    expect(rule).toHaveTextContent(/not evidence of “no difference”/);
    const limits = document.getElementById("limits") as HTMLElement;
    expect(limits).toHaveTextContent(/18 readings per study/);
    expect(limits).toHaveTextContent(
      /without\s+multiple-comparison correction/,
    );
    expect(limits).toHaveTextContent(/one lane per approach with cars only/);
  });

  it("draws the matched seeds and labels the example numbers as illustrative", () => {
    render(<ThreeWayStudyPage />);
    expect(
      screen.getByRole("img", {
        name: /each seed is run once under the fixed-time signal/i,
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/illustrative numbers, not a study result/i),
    ).toBeInTheDocument();
  });

  it("walks one reading per pair through the same decision rule", async () => {
    const user = userEvent.setup();
    render(<ThreeWayStudyPage />);
    const paired = within(document.getElementById("paired") as HTMLElement);
    const reading = () => paired.getByRole("status").textContent;

    expect(reading()).toMatch(/Reading: Adaptive lower\./);
    expect(reading()).toMatch(/not a tie/);
    expect(reading()).toMatch(/t = 2\.776/);

    await user.click(
      paired.getByRole("button", { name: "Adaptive vs Roundabout" }),
    );
    expect(reading()).toMatch(/Reading: About the same\./);
    expect(reading()).toMatch(/they count as about the same/);

    await user.click(
      paired.getByRole("button", { name: "Fixed-time vs Roundabout" }),
    );
    expect(reading()).toMatch(/Reading: Inconclusive\./);
    expect(reading()).toMatch(/includes 0/);

    const table = paired.getByRole("table");
    expect(within(table).getAllByRole("row")).toHaveLength(1 + 5 + 1);
  });

  it("still runs the study and reports every pair with its interval", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(completedJob(STUDY)), { status: 202 }),
    );
    const user = userEvent.setup();
    render(<ThreeWayStudyPage />);
    await user.click(
      screen.getByRole("button", { name: /run the three-way study/i }),
    );
    await waitFor(() => {
      expect(screen.getByText(/Mean delay per vehicle/)).toBeInTheDocument();
    });
    expect(
      JSON.parse(vi.mocked(fetch).mock.calls[0][1]?.body as string),
    ).toEqual({ lanes: 1, numSeeds: 5, duration: 300 });
    const row = within(
      screen.getByRole("table", { name: /Mean delay per vehicle/ }),
    ).getByRole("row", { name: /Light/ });
    expect(row).toHaveTextContent("Adaptive lower (-9.0 s, -11.0 to -7.0)");
    expect(row).toHaveTextContent("About the same");
    expect(row).toHaveTextContent("Inconclusive");
  });
});

describe("Your own junction page", () => {
  it("opens with a short orientation and keeps the full explanation one click away", async () => {
    const user = userEvent.setup();
    render(<JunctionStudyPage />);
    expect(
      screen.getByRole("heading", {
        level: 1,
        name: /your own junction: a controlled study/i,
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("Same in every control")).toBeInTheDocument();
    expect(screen.getByText("Only this differs")).toBeInTheDocument();
    expect(screen.getByLabelText("Scenario name")).toBeInTheDocument();
    await user.click(screen.getByText("How the study is built"));
    expect(
      screen.getByText(/compiled from the same scenario document/),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: /how readings are decided/i }),
    ).toHaveAttribute("href", VIEW_ROUTES.threeWay);
  });
});
