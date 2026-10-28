/**
 * V2.0 planner (PL-1 … PL-9 of the release gate, audit §7.1) against a
 * mocked /api/v2/planning. The fixture result carries the awkward cases the
 * wording rules exist for: an unavailable indicator and comparison, a tie,
 * an inconclusive reading and a comparison with no defined statistic.
 */
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PlannerPage } from "../components/planner/PlannerPage";
import { buildStudyRequest } from "../components/planner/plannerRequest";
import {
  NOT_AVAILABLE,
  fieldCalibrationText,
  formatElapsed,
  formatInterval,
  formatNumber,
  groupStudyNotes,
  splitCaveats,
  verdictText,
} from "../components/planner/plannerText";
import { DEFAULT_SCENARIO } from "../scenario/scenarioModel";
import { VIEW_ROUTES, resolveRoute } from "../routing";
import type { PlanningResult, StudyRecord } from "../services/v2/planning";
import { axeViolations } from "./axe";

const STUDY_ID = "abc123";

function value(mean: number | null, low: number | null, high: number | null) {
  return { mean, ciLow: low, ciHigh: high, n: 3, label: "x" };
}

const RESULT: PlanningResult = {
  format: "urbanflow-planning-result",
  name: "Fixture study",
  scenario: { name: "Fixture junction", fingerprint: "d6638e5eb9d4bd7c" },
  alternatives: [
    {
      id: "fixed_time",
      label: "",
      strategy: "fixed_time",
      strategyTitle: "Fixed-time signal",
      isBaseline: true,
      fingerprint: "d6638e5eb9d4bd7c",
    },
    {
      id: "adaptive",
      label: "",
      strategy: "adaptive",
      strategyTitle: "Adaptive signal",
      isBaseline: false,
      fingerprint: "d6638e5eb9d4bd7c",
    },
  ],
  summary: {
    baseline: "fixed_time",
    alternatives: 2,
    scales: [1],
    seeds: 3,
    findings: 1,
    recommendationBasis:
      "None. This study reports evidence for this scenario and these demand levels only; it does not rank or recommend a control.",
  },
  results: [
    {
      alternativeId: "fixed_time",
      demandScale: 1,
      demandVph: 1600,
      vehicleLimitReached: false,
      performance: {
        status: "available",
        values: {
          averageDelay: value(6.96, -5.95, 19.87),
          throughput: value(6.33, 1, 11),
          averageQueueLength: value(0.67, 0.1, 1.2),
        },
        unavailable: [],
      },
      safety: {
        status: "exploratory",
        values: { collisionCount: value(0, 0, 0) },
        unavailable: [
          {
            key: "minTTC",
            label: "Minimum time-to-collision",
            reason: "not reported by the comparison output",
          },
        ],
      },
    },
    {
      alternativeId: "adaptive",
      demandScale: 1,
      demandVph: 1600,
      vehicleLimitReached: false,
      performance: {
        status: "available",
        values: {
          averageDelay: value(3.19, 0.2, 6.1),
          throughput: value(5.67, 1, 10),
          // A missing indicator must never be shown as 0.
          averageQueueLength: value(null, null, null),
        },
        unavailable: [],
      },
    },
  ],
  comparison: {
    baselineId: "fixed_time",
    vsBaseline: [
      {
        alternativeId: "adaptive",
        baselineId: "fixed_time",
        demandScale: 1,
        metric: "averageDelay",
        baselineMean: 6.96,
        alternativeMean: 3.19,
        delta: -3.77,
        ciLow: -12.94,
        ciHigh: 5.4,
        n: 3,
        reading: "inconclusive",
        verdict: "inconclusive",
      },
      {
        alternativeId: "adaptive",
        baselineId: "fixed_time",
        demandScale: 1,
        metric: "throughput",
        baselineMean: 6.33,
        alternativeMean: 5.67,
        delta: -0.67,
        ciLow: -6.4,
        ciHigh: 5.07,
        n: 3,
        reading: "tie",
        verdict: "tie",
      },
      {
        // No defined test statistic (e.g. zero variance in both groups).
        alternativeId: "adaptive",
        baselineId: "fixed_time",
        demandScale: 1,
        metric: "collisionCount",
        baselineMean: 0,
        alternativeMean: 0,
        delta: 0,
        ciLow: null,
        ciHigh: null,
        n: 3,
        reading: "tie",
        verdict: "tie",
      },
      {
        alternativeId: "adaptive",
        baselineId: "fixed_time",
        demandScale: 1,
        metric: "averageQueueLength",
        n: 0,
        reading: "unavailable",
        verdict: "unavailable",
      },
    ],
  },
  reliability: {
    repetitions: 3,
    seeds: [1, 2, 3],
    confidenceLevel: 0.95,
    sampleAdequacy: "small",
    flags: [
      {
        code: "small_sample",
        severity: "caution",
        message: "3 repetitions: indicative only; 5+ recommended.",
      },
    ],
  },
  findings: [
    {
      id: "F1",
      kind: "delay",
      statement:
        "Adaptive signal showed an inconclusive difference in mean delay compared with Fixed-time signal at x1 demand (3 seeds could not separate them).",
      confidence: "low",
      evidence: [{ path: "comparison.vsBaseline[0]" }],
      caveats: ["Short simulated period."],
    },
  ],
  limitations: [
    "Readings are per metric and per demand scale; there is no overall winner.",
  ],
  validity: {
    fieldCalibration: "not_provided",
    exploratory: true,
    vehicleLimitReached: false,
    caveats: [],
  },
  meta: {
    gitCommit: "4b40cc9aa7cf8880965e983188c9c52a8a0ff1b8",
    scenarioFingerprint: "d6638e5eb9d4bd7c",
    inputFingerprint: "7a5e10fbe2f8af48",
    resultFingerprint: "128d8bd783b1cfba",
    seeds: [1, 2, 3],
    createdAt: "2026-10-12T12:12:41Z",
  },
};

type Handler = (url: URL, init: RequestInit) => Response | Promise<Response>;

function json(
  body: unknown,
  status = 200,
  headers: Record<string, string> = {},
) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

function errorBody(status: number, message: string, errors?: string[]) {
  return json(
    {
      error: {
        code: "X",
        message,
        details: errors ? { errors } : null,
        timestamp: "",
      },
    },
    status,
  );
}

const validResponse = {
  valid: true,
  errors: [],
  warnings: [],
  simulations: 45,
  scenarioFingerprint: "d6638e5eb9d4bd7c",
  alternatives: [],
};

let fetchMock: ReturnType<typeof vi.fn>;
let routes: Partial<Record<string, Handler>>;
const calls: { method: string; path: string; body: unknown }[] = [];

function urlOf(input: RequestInfo | URL): string {
  return input instanceof Request ? input.url : input.toString();
}

function install(overrides: Record<string, Handler> = {}) {
  routes = {
    "POST /api/v1/scenarios/validate": () =>
      json({
        valid: true,
        errors: [],
        warnings: [],
        strategies: ["fixed_time", "adaptive", "roundabout"],
      }),
    "POST /api/v2/planning/validate": () => json(validResponse),
    ...overrides,
  };
  fetchMock = vi.fn((input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = new URL(urlOf(input), "http://localhost");
    const method = (init.method ?? "GET").toUpperCase();
    calls.push({
      method,
      path: url.pathname + url.search,
      body: typeof init.body === "string" ? JSON.parse(init.body) : undefined,
    });
    const handler =
      routes[`${method} ${url.pathname}${url.search}`] ??
      routes[`${method} ${url.pathname}`];
    if (!handler) return Promise.resolve(json({}, 404));
    return Promise.resolve(handler(url, init));
  });
  vi.stubGlobal("fetch", fetchMock);
}

function visit(path: string) {
  window.history.replaceState(null, "", path);
}

beforeEach(() => {
  calls.length = 0;
  visit(VIEW_ROUTES.planner);
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("planner wording rules", () => {
  it("never turns a missing number into 0", () => {
    expect(formatNumber(null)).toBe(NOT_AVAILABLE);
    expect(formatNumber(undefined)).toBe(NOT_AVAILABLE);
    expect(formatNumber(Number.NaN)).toBe(NOT_AVAILABLE);
    expect(formatNumber(0)).toBe("0.00");
    expect(formatInterval(null, 2)).toBe(NOT_AVAILABLE);
    expect(formatInterval(-1, 2)).toBe("-1.00 to 2.00");
  });

  it("reads ties and inconclusive results as such, and never ranks", () => {
    expect(verdictText({ verdict: "tie" })).toMatch(/tie/i);
    expect(verdictText({ verdict: "inconclusive" })).toMatch(/inconclusive/i);
    expect(verdictText({ verdict: "unavailable" })).toBe("Not available");
    for (const v of ["better", "worse", "tie", "inconclusive"] as const) {
      expect(verdictText({ verdict: v })).not.toMatch(/winner|best|recommend/i);
    }
  });

  it("groups per-alternative notes without dropping any", () => {
    const titles = new Map([
      ["fixed_time", "Fixed-time signal"],
      ["adaptive", "Adaptive signal"],
    ]);
    const groups = groupStudyNotes(
      [
        "fixed_time: More than one lane: exploratory.",
        "adaptive: More than one lane: exploratory.",
        "adaptive: Mixed vehicle classes.",
        "unknown_alt: Kept as sent.",
        "No prefix here.",
      ],
      (id) => titles.get(id),
    );
    expect(groups).toEqual([
      {
        message: "More than one lane: exploratory.",
        appliesTo: ["Fixed-time signal", "Adaptive signal"],
      },
      { message: "Mixed vehicle classes.", appliesTo: ["Adaptive signal"] },
      { message: "unknown_alt: Kept as sent.", appliesTo: [] },
      { message: "No prefix here.", appliesTo: [] },
    ]);
  });

  it("shows a caveat shared by several findings once, and keeps the rest", () => {
    const split = splitCaveats([
      { id: "a", caveats: ["Scenario-wide.", "Only a."] },
      { id: "b", caveats: ["Scenario-wide."] },
      { id: "c", caveats: [] },
    ]);
    expect(split.shared).toEqual(["Scenario-wide."]);
    expect(split.own.get("a")).toEqual(["Only a."]);
    expect(split.own.get("b")).toEqual([]);
    expect(split.refs.get("a")).toEqual([0]);
    expect(split.refs.get("c")).toEqual([]);
  });

  it("formats elapsed job time", () => {
    expect(formatElapsed(2)).toBe("0:02");
    expect(formatElapsed(125)).toBe("2:05");
    expect(formatElapsed(3725)).toBe("1:02:05");
    expect(formatElapsed(null)).toBe(NOT_AVAILABLE);
  });

  it("never calls an observed-data comparison calibration", () => {
    expect(fieldCalibrationText("not_provided")).toMatch(
      /not field-calibrated/i,
    );
    const rated = fieldCalibrationText("GOOD");
    expect(rated).toMatch(/still not field-calibrated/i);
    expect(rated).toMatch(/not tuned/i);
  });

  it("builds the request with the baseline first and server-safe ids", () => {
    const req = buildStudyRequest({
      name: "  ",
      scenario: DEFAULT_SCENARIO,
      alternatives: [
        { key: 1, strategy: "adaptive", label: "" },
        { key: 2, strategy: "adaptive", label: " Longer greens " },
        { key: 3, strategy: "roundabout", label: "" },
      ],
      seeds: 4,
      scales: [1.5, 1],
    });
    expect(req.name).toBe("Planning study");
    expect(req.alternatives.map((a) => a.id)).toEqual([
      "adaptive",
      "adaptive-2",
      "roundabout",
    ]);
    expect(req.alternatives[1].label).toBe("Longer greens");
    expect(req.demand.scales).toEqual([1, 1.5]);
    expect(req.repetitions.seeds).toBe(4);
  });

  it("has its own route, mirrored by nginx", () => {
    expect(resolveRoute("/app/planner")).toEqual({
      kind: "view",
      view: "planner",
    });
  });
});

describe("planner setup (PL-1 … PL-4)", () => {
  // axe walks the whole rendered document: about 3 s for the planner form on
  // an idle machine, past the default 5 s when the full suite runs alongside
  // other work. It waits only on rendered output, so the budget hides no race.
  it(
    "has no automatically detectable accessibility violations (axe)",
    { timeout: 15_000 },
    async () => {
      install();
      render(
        <main>
          <PlannerPage />
        </main>,
      );
      await screen.findByText(/45 simulations/, {}, { timeout: 10_000 });
      expect(await axeViolations(document.body)).toEqual([]);
    },
  );

  it("validates the study and shows the simulation count, with no invented time estimate", async () => {
    install();
    render(<PlannerPage />);
    expect(
      await screen.findByText(/45 simulations/, {}, { timeout: 3000 }),
    ).toBeInTheDocument();
    expect(screen.getByText(/no measured estimate/i)).toBeInTheDocument();
    const sent = calls.find((c) => c.path === "/api/v2/planning/validate")
      ?.body as { alternatives: { strategy: string }[] };
    expect(sent.alternatives.map((a) => a.strategy)).toEqual([
      "fixed_time",
      "adaptive",
      "roundabout",
    ]);
    expect(screen.getByRole("button", { name: "Run study" })).toBeEnabled();
  });

  it("shows the server's validation errors and blocks the run", async () => {
    install({
      "POST /api/v2/planning/validate": () =>
        json({
          ...validResponse,
          valid: false,
          errors: [
            "repetitions.seeds: Input should be less than or equal to 30",
          ],
        }),
    });
    render(<PlannerPage />);
    expect(
      await screen.findByText(/cannot run yet/i, {}, { timeout: 3000 }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Repetitions: seeds/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run study" })).toBeDisabled();
  });

  it("lets the user choose the baseline and alternatives", async () => {
    install();
    render(<PlannerPage />);
    await screen.findByText(/45 simulations/, {}, { timeout: 3000 });
    const table = screen.getByRole("table", {
      name: /Alternatives to compare/,
    });
    fireEvent.click(
      within(table).getAllByRole("button", { name: "Make baseline" })[1],
    );
    await waitFor(
      () => {
        const last = [...calls]
          .reverse()
          .find((c) => c.path === "/api/v2/planning/validate")?.body as {
          alternatives: { strategy: string }[];
        };
        expect(last.alternatives[0].strategy).toBe("roundabout");
      },
      { timeout: 3000 },
    );
  });

  it("explains the two-study limit (HTTP 429) instead of swallowing it", async () => {
    install({
      "POST /api/v2/planning/jobs": () =>
        errorBody(429, "2 planning studies are already running"),
    });
    render(<PlannerPage />);
    await screen.findByText(/45 simulations/, {}, { timeout: 3000 });
    fireEvent.click(screen.getByRole("button", { name: "Run study" }));
    const alert = await screen.findByText(/maximum of two planning studies/);
    expect(alert).toHaveTextContent("2 planning studies are already running");
  });

  it("says when the server cannot be reached", async () => {
    install({
      "POST /api/v2/planning/validate": () => {
        throw new TypeError("Failed to fetch");
      },
    });
    fetchMock.mockImplementation((input: RequestInfo | URL) =>
      urlOf(input).includes("/api/v2/")
        ? Promise.reject(new TypeError("Failed to fetch"))
        : Promise.resolve(
            json({ valid: true, errors: [], warnings: [], strategies: [] }),
          ),
    );
    render(<PlannerPage />);
    expect(
      await screen.findByText(/could not be reached/, {}, { timeout: 3000 }),
    ).toBeInTheDocument();
  });

  it("starts the study as a job and follows its progress to the result", async () => {
    let polls = 0;
    install({
      "POST /api/v2/planning/jobs": () =>
        json(
          {
            id: STUDY_ID,
            name: "Planning study",
            status: "queued",
            error: null,
            createdAt: "",
            result: null,
          } satisfies StudyRecord,
          202,
        ),
      [`GET /api/v2/planning/${STUDY_ID}`]: () => {
        polls += 1;
        if (polls === 1) {
          return json({
            id: STUDY_ID,
            name: "Planning study",
            status: "running",
            error: null,
            createdAt: "",
            result: null,
            progress: {
              phase: "simulating",
              total: 45,
              completed: 3,
              fraction: 0.07,
              elapsedSeconds: 2,
            },
          } satisfies StudyRecord);
        }
        return json({
          id: STUDY_ID,
          name: "Planning study",
          status: "completed",
          error: null,
          createdAt: "",
          result: RESULT,
        } satisfies StudyRecord);
      },
    });
    render(<PlannerPage />);
    await screen.findByText(/45 simulations/, {}, { timeout: 3000 });
    fireEvent.click(screen.getByRole("button", { name: "Run study" }));
    await waitFor(() => {
      expect(window.location.search).toBe(`?study=${STUDY_ID}`);
    });
    expect(
      await screen.findByText(/3 of 45 simulations finished/),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole(
        "heading",
        { name: /Evidence: Fixture study/ },
        { timeout: 4000 },
      ),
    ).toBeInTheDocument();
  });

  it("shows a failed job's error", async () => {
    visit(`${VIEW_ROUTES.planner}?study=${STUDY_ID}`);
    install({
      [`GET /api/v2/planning/${STUDY_ID}`]: () =>
        json({
          id: STUDY_ID,
          name: "Broken",
          status: "failed",
          error: "engine exploded",
          createdAt: "",
          result: null,
        } satisfies StudyRecord),
    });
    render(<PlannerPage />);
    expect(await screen.findByText(/engine exploded/)).toBeInTheDocument();
  });
});

describe("planner results (PL-5 … PL-9)", () => {
  function completed() {
    return json({
      id: STUDY_ID,
      name: "Fixture study",
      status: "completed",
      error: null,
      createdAt: "",
      result: RESULT,
    } satisfies StudyRecord);
  }

  async function openStudy(extra: Record<string, Handler> = {}) {
    visit(`${VIEW_ROUTES.planner}?study=${STUDY_ID}`);
    install({ [`GET /api/v2/planning/${STUDY_ID}`]: completed, ...extra });
    render(<PlannerPage />);
    await screen.findByRole("heading", { name: /Evidence: Fixture study/ });
  }

  // axe walks the whole rendered document: about 3 s for the planner form on
  // an idle machine, past the default 5 s when the full suite runs alongside
  // other work. It waits only on rendered output, so the budget hides no race.
  it(
    "has no automatically detectable accessibility violations (axe)",
    { timeout: 15_000 },
    async () => {
      // Inside <main>, as the app mounts it (PageTransition renders <main>).
      visit(`${VIEW_ROUTES.planner}?study=${STUDY_ID}`);
      install({ [`GET /api/v2/planning/${STUDY_ID}`]: completed });
      render(
        <main>
          <PlannerPage />
        </main>,
      );
      await screen.findByRole("heading", { name: /Evidence: Fixture study/ });
      expect(await axeViolations(document.body)).toEqual([]);
    },
  );

  it("re-opens a study from the URL alone (reload / shared link)", async () => {
    await openStudy();
    expect(calls[0]).toMatchObject({
      method: "GET",
      path: `/api/v2/planning/${STUDY_ID}`,
    });
  });

  it("compares with the baseline using honest wording", async () => {
    await openStudy();
    const table = screen.getByRole("table", { name: /Paired difference/ });
    const rows = within(table).getAllByRole("row").slice(1);
    const byMetric = (label: RegExp) => {
      const row = rows.find((r) => label.test(r.textContent));
      if (!row) throw new Error(`no row for ${label.source}`);
      return row;
    };
    expect(byMetric(/Mean delay/)).toHaveTextContent(/Inconclusive/);
    expect(byMetric(/Mean delay/)).toHaveTextContent("-12.94 to 5.40");
    expect(byMetric(/Vehicles served/)).toHaveTextContent(/Tie/);
    // No defined statistic: the interval is "not available", not 0 to 0.
    expect(byMetric(/Simulated collisions/)).toHaveTextContent(NOT_AVAILABLE);
    const queue = byMetric(/Mean queue/);
    expect(queue).toHaveTextContent("Not available");
    expect(queue.textContent).not.toMatch(/\b0\.00\b/);
    // "there is no overall winner" (a limitation) is fine; a ranking is not.
    expect(document.body.textContent).not.toMatch(
      /is the winner|best (option|alternative)|we recommend/i,
    );
  });

  it("shows unavailable indicators as not available, never 0", async () => {
    await openStudy();
    const table = screen.getByRole("table", {
      name: /Indicators per alternative/,
    });
    const adaptive = within(table).getByRole("row", {
      name: /Adaptive signal/,
    });
    expect(adaptive).toHaveTextContent(NOT_AVAILABLE);
    expect(
      screen.getByText(/Minimum time-to-collision: not available/),
    ).toBeInTheDocument();
  });

  it("shows the validity banner, findings with evidence, and caveats", async () => {
    await openStudy();
    const banner = screen.getByRole("note", { name: "Validity" });
    expect(banner).toHaveTextContent(/Not field-calibrated/);
    expect(banner).toHaveTextContent(/does not rank or recommend/);
    expect(screen.getByText("comparison.vsBaseline[0]")).toBeInTheDocument();
    expect(screen.getByText("Short simulated period.")).toBeInTheDocument();
    expect(screen.getByText(/5\+ recommended/)).toBeInTheDocument();
  });

  it("downloads the three report formats from the server", async () => {
    const created: string[] = [];
    // jsdom has no object URLs; downloadText needs both.
    vi.stubGlobal(
      "URL",
      Object.assign(URL, {
        createObjectURL: () => {
          created.push("blob");
          return "blob:x";
        },
        revokeObjectURL: () => undefined,
      }),
    );
    const report = (format: string) => () =>
      new Response(`report-${format}`, {
        headers: {
          "Content-Type": "text/plain",
          "Content-Disposition": `attachment; filename="study.${format}"`,
        },
      });
    await openStudy({
      [`GET /api/v2/planning/${STUDY_ID}/report?format=json`]: report("json"),
      [`GET /api/v2/planning/${STUDY_ID}/report?format=md`]: report("md"),
      [`GET /api/v2/planning/${STUDY_ID}/report?format=csv`]: report("csv"),
    });
    for (const name of ["Download JSON", "Download Markdown", "Download CSV"]) {
      fireEvent.click(screen.getByRole("button", { name }));
    }
    await waitFor(() => {
      expect(created).toHaveLength(3);
    });
    expect(calls.map((c) => c.path)).toEqual(
      expect.arrayContaining([
        `/api/v2/planning/${STUDY_ID}/report?format=json`,
        `/api/v2/planning/${STUDY_ID}/report?format=md`,
        `/api/v2/planning/${STUDY_ID}/report?format=csv`,
      ]),
    );
  });

  it("shows fingerprints, commit and seeds, and the reproduce outcome", async () => {
    await openStudy({
      [`POST /api/v2/planning/${STUDY_ID}/reproduce`]: () =>
        json({
          id: STUDY_ID,
          reproduced: false,
          originalResultFingerprint: "128d8bd783b1cfba",
          rerunResultFingerprint: "ffffffffffffffff",
          gitCommitOriginal: "aaa",
          gitCommitRerun: "bbb",
        }),
    });
    expect(screen.getByText("7a5e10fbe2f8af48")).toBeInTheDocument();
    expect(
      screen.getByText("4b40cc9aa7cf8880965e983188c9c52a8a0ff1b8"),
    ).toBeInTheDocument();
    expect(screen.getByText("1, 2, 3")).toBeInTheDocument();
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Reproduce" }));
      await Promise.resolve();
    });
    expect(await screen.findByText(/Not reproduced/)).toHaveTextContent(
      /different commit/,
    );
  });

  it("explains a study that is not found (another user's, or a bad id)", async () => {
    visit(`${VIEW_ROUTES.planner}?study=${STUDY_ID}`);
    install({
      [`GET /api/v2/planning/${STUDY_ID}`]: () =>
        errorBody(404, "Planning study not found"),
    });
    render(<PlannerPage />);
    expect(await screen.findByText(/study was not found/)).toBeInTheDocument();
  });
});
