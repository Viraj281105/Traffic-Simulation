/**
 * @vitest-environment jsdom
 *
 * V1.3 adaptive signal control on the frontend: the dashboard payload, the
 * guided question, advanced settings, the live status overlay, results
 * wording and the Research Lab three-way study.
 */
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  ADAPTIVE_DEFAULTS,
  DEFAULT_CONFIG_VALUES,
  dashboardPayload,
  sameConfigValues,
} from "../types/config";
import type {
  FixedTimeControllerState,
  LiveSnapshot,
} from "../types/simulation";
import { ScenarioSetup } from "../components/guided/ScenarioSetup";
import { ConfigurationSidebar } from "../components/ConfigurationSidebar";
import { AdaptiveSignalStatus } from "../components/AdaptiveSignalStatus";
import { adaptiveStatusText, phaseApproaches } from "../signals/signalControl";
import { explanations, type SideSummary } from "../metrics/plainLanguage";
import { ControlComparisonStudy } from "../components/ControlComparisonStudy";
import { completedJob } from "./studyJob";

vi.mock("../config", () => ({ API_BASE_URL: "http://localhost:8000" }));

const ADAPTIVE = {
  ...DEFAULT_CONFIG_VALUES,
  signalControl: "adaptive" as const,
};

describe("dashboard payload", () => {
  it("is unchanged for the fixed timetable", () => {
    const body = dashboardPayload(DEFAULT_CONFIG_VALUES, "fixed_time_signal");
    expect(body).not.toHaveProperty("signalControl");
    expect(body).not.toHaveProperty("adaptive");
    expect(
      dashboardPayload(
        { ...DEFAULT_CONFIG_VALUES, signalControl: "fixed_time" },
        "fixed_time_signal",
      ),
    ).toEqual(body);
  });

  it("asks for adaptive control, sending only changed settings", () => {
    expect(dashboardPayload(ADAPTIVE, "fixed_time_signal")).toMatchObject({
      signalControl: "adaptive",
    });
    expect(dashboardPayload(ADAPTIVE, "fixed_time_signal")).not.toHaveProperty(
      "adaptive",
    );
    const tuned = dashboardPayload(
      { ...ADAPTIVE, adaptive: { ...ADAPTIVE_DEFAULTS, maxGreen: 40 } },
      "fixed_time_signal",
    );
    expect(tuned.adaptive).toEqual({ maxGreen: 40 });
  });

  it("compares configs by their effective signal control", () => {
    expect(
      sameConfigValues(DEFAULT_CONFIG_VALUES, {
        ...DEFAULT_CONFIG_VALUES,
        signalControl: "fixed_time",
      }),
    ).toBe(true);
    expect(sameConfigValues(DEFAULT_CONFIG_VALUES, ADAPTIVE)).toBe(false);
    expect(
      sameConfigValues(ADAPTIVE, { ...ADAPTIVE, adaptive: ADAPTIVE_DEFAULTS }),
    ).toBe(true);
    expect(
      sameConfigValues(ADAPTIVE, { ...ADAPTIVE, adaptive: { minGreen: 12 } }),
    ).toBe(false);
  });
});

describe("guided setup", () => {
  it("asks how the signal should respond and runs with the answer", async () => {
    const onRun = vi.fn();
    render(
      <ScenarioSetup
        config={DEFAULT_CONFIG_VALUES}
        onRun={onRun}
        runInProgress={false}
      />,
    );
    expect(
      screen.getByText("How should the signal respond to traffic?"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("radio", { name: /On a fixed timetable/ }),
    ).toBeChecked();
    await userEvent.click(
      screen.getByRole("radio", { name: /Responds to traffic/ }),
    );
    expect(
      screen.getByText(/Each green lasts at least 10 s/),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Traffic signal that responds" }),
    ).toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: /Run the comparison/ }),
    );
    expect(onRun).toHaveBeenCalledWith(
      expect.objectContaining({ signalControl: "adaptive" }),
    );
  });
});

describe("advanced settings", () => {
  it("shows adaptive settings only for a signal that responds", async () => {
    const onApply = vi.fn();
    render(
      <ConfigurationSidebar
        isOpen={true}
        onClose={vi.fn()}
        config={DEFAULT_CONFIG_VALUES}
        onApply={onApply}
        mode="comparative"
      />,
    );
    expect(screen.queryByLabelText(/Minimum green/)).toBeNull();
    await userEvent.click(
      screen.getByRole("radio", { name: /Responds to traffic/ }),
    );
    expect(screen.getByLabelText(/Minimum green/)).toHaveValue("10");
    expect(screen.getByLabelText(/Maximum green/)).toHaveValue("50");
    // Fixed green sliders are replaced; yellow and all-red stay.
    expect(screen.queryByLabelText(/Green \(both corridors\)/)).toBeNull();
    expect(screen.getByLabelText(/^Yellow/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Apply/ }));
    expect(onApply).toHaveBeenCalledWith(
      expect.objectContaining({ signalControl: "adaptive" }),
    );
  });

  it("blocks a maximum green no longer than the minimum", () => {
    render(
      <ConfigurationSidebar
        isOpen={true}
        onClose={vi.fn()}
        config={{ ...ADAPTIVE, adaptive: { minGreen: 40, maxGreen: 30 } }}
        onApply={vi.fn()}
        mode="comparative"
      />,
    );
    expect(
      screen.getByText(/maximum green must be longer than the minimum/),
    ).toBeInTheDocument();
  });

  it("has no signal control on a roundabout", () => {
    render(
      <ConfigurationSidebar
        isOpen={true}
        onClose={vi.fn()}
        config={DEFAULT_CONFIG_VALUES}
        onApply={vi.fn()}
        mode="roundabout"
      />,
    );
    expect(screen.queryByText("Signal control")).toBeNull();
  });
});

function adaptiveController(
  overrides: Partial<NonNullable<FixedTimeControllerState["adaptive"]>> = {},
  phase: FixedTimeControllerState["currentPhase"] = "ns_green",
  remaining = 20,
): FixedTimeControllerState {
  return {
    type: "fixed_time_signal",
    timeInCurrentState: 12,
    currentPhase: phase,
    phaseTimeRemaining: remaining,
    cycleNumber: 1,
    signals: [],
    signalControl: "adaptive",
    adaptive: {
      status: "extending",
      minGreen: 10,
      maxGreen: 50,
      extensionStep: 2.5,
      detectionDistance: 30,
      demandThreshold: 1,
      greenElapsed: 12,
      gapTimer: 0,
      servedDemand: 3,
      phasesWaiting: 1,
      detected: { north: 2, south: 1, east: 4, west: 0 },
      nextPhase: null,
      decisions: {
        greens: 3,
        gapOuts: 2,
        maxOuts: 0,
        greensExtended: 1,
        phasesSkipped: 0,
        restSeconds: 4,
      },
      recentDecisions: [],
      ...overrides,
    },
  };
}

describe("live status", () => {
  it("names the approaches of a phase", () => {
    expect(phaseApproaches("ns_green")).toBe("north–south");
    expect(phaseApproaches("east_straight_right")).toBe("east");
    expect(phaseApproaches(null)).toBe("the next direction");
  });

  it("explains each decision state in plain words", () => {
    expect(adaptiveStatusText(adaptiveController())).toMatch(
      /Holding green for north–south: traffic is still arriving\. Someone is waiting on red, so this green ends within 20 s at most\./,
    );
    expect(
      adaptiveStatusText(adaptiveController({ phasesWaiting: 0 })),
    ).toMatch(/nobody is waiting on red/);
    expect(
      adaptiveStatusText(adaptiveController({ status: "resting" })),
    ).toMatch(/Green stays with north–south/);
    expect(
      adaptiveStatusText(adaptiveController({ status: "min_green" })),
    ).toMatch(/at least 10 s/);
    expect(
      adaptiveStatusText(
        adaptiveController(
          { status: "clearance", nextPhase: "ew_green" },
          "ns_yellow",
        ),
      ),
    ).toMatch(/Changing: east–west has traffic waiting\. Yellow and all-red/);
  });

  it("is absent for a fixed-timetable signal", () => {
    const fixed: FixedTimeControllerState = {
      ...adaptiveController(),
      signalControl: "fixed_time",
      adaptive: undefined,
    };
    expect(adaptiveStatusText(fixed)).toBeNull();
    const { container } = render(
      <AdaptiveSignalStatus
        snapshot={{ controller: fixed } as unknown as LiveSnapshot}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("shows the decision and detector counts on the map", () => {
    render(
      <AdaptiveSignalStatus
        snapshot={
          { controller: adaptiveController() } as unknown as LiveSnapshot
        }
      />,
    );
    const panel = screen.getByLabelText("Signal responding to traffic");
    expect(panel).toHaveTextContent("Responds to traffic");
    expect(panel).toHaveTextContent(/N 2.*S 1.*E 4.*W 0/);
  });
});

describe("results wording", () => {
  const side: SideSummary = {
    delay: 20,
    queuedTime: 12,
    p95Delay: 45,
    stops: 1.2,
    served: 50,
    inNetwork: 6,
    avgQueue: 1.1,
    maxQueue: 5,
    congestedSeconds: 10,
    fairness: 0.95,
    collisions: 0,
    idleGreenPct: 12,
  };
  const facts = {
    lanes: 1,
    arrivalRate: 0.3,
    greenNs: 30,
    greenEw: 30,
    cycleSeconds: 72,
    criticalGap: 4,
  };

  it("describes the adaptive rule instead of the timetable", () => {
    const fixed = explanations(side, side, facts)
      .map((e) => e.body)
      .join(" ");
    expect(fixed).toMatch(/fixed timetable/);
    const adaptive = explanations(side, side, {
      ...facts,
      adaptive: { minGreen: 10, maxGreen: 50, extensionStep: 2.5 },
    });
    const text = adaptive.map((e) => e.body).join(" ");
    expect(text).toMatch(/The signal responds to traffic/);
    expect(text).not.toMatch(/fixed timetable: each direction/);
    expect(adaptive.map((e) => e.title)).toContain(
      "Some green still went unused",
    );
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
  method: {
    design: "Same seeds.",
    interval: "t",
    delayComparison: "Paired per-seed differences.",
  },
  results: [
    {
      level: "light",
      demandVph: 310,
      degreeOfSaturation: 0.25,
      vehicleLimitReached: false,
      controls: {
        fixed_time: { averageDelay: STAT(20), phaseChanges: STAT(8) },
        adaptive: { averageDelay: STAT(11), phaseChanges: STAT(12) },
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
          meanDifference: 5,
          ciLow: 3,
          ciHigh: 7,
          reading: "higher",
        },
        fixed_time_vs_roundabout: {
          meanDifference: 0.4,
          ciLow: -1,
          ciHigh: 2,
          reading: "tie",
        },
      },
    },
  ],
};

describe("Research Lab three-way study", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  it("runs the study and reports every pair with its interval", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(completedJob(STUDY)), { status: 202 }),
    );
    render(<ControlComparisonStudy />);
    await userEvent.click(
      screen.getByRole("button", { name: /Run the three-way study/ }),
    );
    await waitFor(() => {
      expect(screen.getByText(/Mean delay per vehicle/)).toBeInTheDocument();
    });
    expect(vi.mocked(fetch).mock.calls[0][0]).toMatch(
      /\/api\/v1\/study\/control-comparison\/jobs$/,
    );
    expect(
      JSON.parse(vi.mocked(fetch).mock.calls[0][1]?.body as string),
    ).toEqual({
      lanes: 1,
      numSeeds: 5,
      duration: 300,
    });
    const table = screen.getByRole("table", { name: /Mean delay per vehicle/ });
    const row = within(table).getByRole("row", { name: /Light/ });
    expect(row).toHaveTextContent("20.0 ± 1.5");
    expect(row).toHaveTextContent("Adaptive lower (-9.0 s, -11.0 to -7.0)");
    expect(row).toHaveTextContent("Roundabout lower");
    expect(row).toHaveTextContent("About the same");
    expect(
      screen.getByRole("button", { name: "Download CSV" }),
    ).toBeInTheDocument();
  });
});
