/**
 * @vitest-environment jsdom
 *
 * V3.0 W2 S8: Signalised roundabout frontend integration and UI controls.
 * Covers:
 * - SR-27: Entry-control selector and minimal plan editor in AdvancedSettings
 * - SR-28: Signal states, text labels, hold reasons, and limitations banner
 * - SR-29: Accessibility (axeViolations clean)
 * - Backward compatibility: conventional roundabouts untouched
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AdvancedSettings } from "../components/scenario/AdvancedSettings";
import { MeteredRoundaboutStatus } from "../components/MeteredRoundaboutStatus";
import { meteringHoldReasonText } from "../components/meteredRoundaboutUtils";
import { RoundaboutMap } from "../components/RoundaboutMap";
import { scenarioFromPreset } from "../scenario/scenarioModel";
import type { ScenarioDocument } from "../scenario/scenarioTypes";
import type {
  LiveSnapshot,
  MeteringControllerState,
  RoundaboutControllerState,
  RunningMetrics,
} from "../types/simulation";
import { axeViolations } from "./axe";

beforeEach(() => {
  vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockReturnValue(800);
  vi.spyOn(HTMLElement.prototype, "clientHeight", "get").mockReturnValue(600);
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      disconnect() {}
    },
  );
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

function mockMetrics(overrides: Partial<RunningMetrics> = {}): RunningMetrics {
  return {
    averageDelay: 0,
    medianDelay: 0,
    minDelay: 0,
    maxDelay: 0,
    p95Delay: 0,
    delayStdDev: 0,
    averageWaitTime: 0,
    throughput: 0,
    throughputRate: 0,
    currentQueueLengths: { north: 0, south: 0, east: 0, west: 0 },
    maxQueueLength: 0,
    averageQueueLength: 0,
    activeAverageQueueLength: 0,
    queueStdDev: 0,
    totalStops: 0,
    averageStopsPerVehicle: 0,
    speedVarianceIndex: 0,
    travelTimeReliability: 1,
    idleOpportunityLoss: 0,
    directionalFairnessIndex: 1,
    activeVehicleCount: 0,
    totalVehiclesSpawned: 0,
    averageTravelSpeed: 0,
    queueStabilityIndex: 0,
    congestionRecoveryTime: 0,
    spaceFootprintConsumed: 0,
    intersectionUtilization: 0,
    criticalSaturationVolume: 0,
    collisionCount: 0,
    ...overrides,
  };
}

function makeMeteredSnapshot(
  meteringOverrides?: Partial<MeteringControllerState>,
): LiveSnapshot {
  const defaultMetering: MeteringControllerState = {
    currentPhase: "ns_green",
    color: "green",
    timeRemaining: 14.2,
    cycleNumber: 3,
    cycleProgress: 0.25,
    arms: [
      { direction: "north", metered: true, color: "green", reason: null },
      { direction: "south", metered: true, color: "green", reason: null },
      { direction: "east", metered: true, color: "red", reason: "red" },
      { direction: "west", metered: true, color: "red", reason: "red" },
    ],
    decisions: { red: 12, yellow: 4 },
    recentDecisions: [],
    spillbackGuard: { enabled: false },
    queueCap: { enabled: false },
    ...meteringOverrides,
  };

  return {
    schemaVersion: "1.0.0",
    simulationId: "sim-test",
    configId: "cfg-test",
    timestamp: 45.0,
    frameNumber: 450,
    tick: 450,
    wallClockTime: "2026-10-20T12:00:00Z",
    samplingFrequency: 10,
    deltaTime: 0.1,
    warmupTime: 10,
    simulationStatus: "running",
    vehicles: [],
    intersection: {
      type: "roundabout",
      centerX: 0,
      centerY: 0,
      boundingRadius: 40,
      approaches: [
        { direction: "north", queueLength: 0, laneCount: 1 },
        { direction: "south", queueLength: 0, laneCount: 1 },
        { direction: "east", queueLength: 2, laneCount: 1 },
        { direction: "west", queueLength: 1, laneCount: 1 },
      ],
      stopLineSetback: 3.5,
      circulatingLanes: 1,
    },
    controller: {
      type: "roundabout",
      timeInCurrentState: 5.8,
      innerRadius: 10.0,
      outerRadius: 20.0,
      circulatingCount: 2,
      yieldingCount: 1,
      gapAcceptance: 4.0,
      circulatingLanes: 1,
      entryControl: "metered_entry",
      metering: defaultMetering,
    },
    metrics: mockMetrics({
      throughput: 15,
      throughputRate: 20.0,
      averageDelay: 8.5,
      maxDelay: 15.0,
      averageWaitTime: 4.2,
      averageQueueLength: 1.2,
      maxQueueLength: 3,
      currentQueueLengths: { north: 0, south: 0, east: 2, west: 1 },
      activeVehicleCount: 3,
      totalVehiclesSpawned: 18,
      collisionCount: 0,
      averageTravelSpeed: 5.8,
      averageStopsPerVehicle: 0.4,
      directionalFairnessIndex: 0.95,
      intersectionUtilization: 0.75,
      spaceFootprintConsumed: 1256,
      idleOpportunityLoss: 0.05,
    }),
    vehicleCounts: {
      active: 3,
      approaching: 1,
      waiting: 1,
      crossing: 0,
      inRoundabout: 1,
      exited: 15,
    },
    laneModel: {
      laneChanges: 0,
      laneChangesInProgress: 0,
      missedTurns: 0,
    },
  };
}

function makeConventionalSnapshot(): LiveSnapshot {
  const snap = makeMeteredSnapshot();
  const c = snap.controller;
  if (c.type === "roundabout") {
    delete c.entryControl;
    delete c.metering;
  }
  return snap;
}

describe("SR-27: Roundabout entry control scenario settings", () => {
  it("starts in conventional mode with uncontrolled chip active", () => {
    const doc = scenarioFromPreset("typical-urban");
    const update = vi.fn();
    render(<AdvancedSettings value={doc} update={update} />);

    const conventionalBtn = screen.getByRole("button", {
      name: "Uncontrolled (conventional)",
    });
    const meteredBtn = screen.getByRole("button", {
      name: "Metered entry (signals)",
    });

    expect(conventionalBtn).toHaveAttribute("aria-pressed", "true");
    expect(meteredBtn).toHaveAttribute("aria-pressed", "false");
    expect(
      screen.queryByLabelText(/Yellow clearance/i),
    ).not.toBeInTheDocument();
  });

  it("switches to metered entry and exposes plan editor and timings", async () => {
    const doc: ScenarioDocument = scenarioFromPreset("typical-urban");
    const update = (mutate: (d: ScenarioDocument) => void) => {
      mutate(doc);
    };

    const { rerender } = render(
      <AdvancedSettings value={doc} update={update} />,
    );
    const meteredBtn = screen.getByRole("button", {
      name: "Metered entry (signals)",
    });
    await userEvent.click(meteredBtn);

    expect(doc.roundabout.entryControl).toBe("metered_entry");
    expect(doc.roundabout.entryMetering).toBeDefined();
    expect(doc.roundabout.entryMetering?.phases.length).toBeGreaterThan(0);

    rerender(<AdvancedSettings value={doc} update={update} />);

    expect(
      screen.getByRole("button", { name: "Metered entry (signals)" }),
    ).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByLabelText(/Yellow clearance/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/All-red clearance/i)).toBeInTheDocument();
    expect(
      screen.getByText(
        /Simulation assumption — signal timings are not calibrated to real sites/i,
      ),
    ).toBeInTheDocument();
  });

  it("edits phase green, yellow, and optional spillback/queue cap settings", async () => {
    const doc: ScenarioDocument = scenarioFromPreset("typical-urban");
    const update = (mutate: (d: ScenarioDocument) => void) => {
      mutate(doc);
    };

    doc.roundabout.entryControl = "metered_entry";
    doc.roundabout.entryMetering = {
      phases: [
        { entries: ["north", "south"], green: 20 },
        { entries: ["east", "west"], green: 20 },
      ],
      yellow: 3.0,
      allRed: 2.0,
      spillbackGuard: { enabled: false, stoppedThreshold: 2, maxHold: 10.0 },
      queueCap: { enabled: false, vehicles: 8 },
    };

    const { rerender } = render(
      <AdvancedSettings value={doc} update={update} />,
    );

    // Check spillback guard checkbox
    const guardCheck = screen.getByLabelText(/Downstream spillback guard/i);
    await userEvent.click(guardCheck);
    expect(doc.roundabout.entryMetering.spillbackGuard?.enabled).toBe(true);

    // Re-render with guard enabled
    rerender(<AdvancedSettings value={doc} update={update} />);
    expect(
      screen.getByLabelText(/Spillback stopped threshold/i),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText(/Spillback max hold per cycle/i),
    ).toBeInTheDocument();

    // Check queue cap checkbox
    const queueCapCheck = screen.getByLabelText(/Approach queue cap/i);
    await userEvent.click(queueCapCheck);
    expect(doc.roundabout.entryMetering.queueCap?.enabled).toBe(true);

    rerender(<AdvancedSettings value={doc} update={update} />);
    expect(screen.getByLabelText(/Queue cap vehicles/i)).toBeInTheDocument();
  });

  it("switches back to conventional mode cleanly removing metering fields", async () => {
    const doc: ScenarioDocument = scenarioFromPreset("typical-urban");
    const update = (mutate: (d: ScenarioDocument) => void) => {
      mutate(doc);
    };

    doc.roundabout.entryControl = "metered_entry";
    doc.roundabout.entryMetering = {
      phases: [{ entries: ["north", "south"], green: 25 }],
      yellow: 3.0,
      allRed: 2.0,
    };

    const { rerender } = render(
      <AdvancedSettings value={doc} update={update} />,
    );
    const conventionalBtn = screen.getByRole("button", {
      name: "Uncontrolled (conventional)",
    });
    await userEvent.click(conventionalBtn);

    expect(doc.roundabout.entryControl).toBeUndefined();
    expect(doc.roundabout.entryMetering).toBeUndefined();
    // Preserves unrelated properties
    expect(doc.roundabout.innerRadius).toBe(10);
    expect(doc.roundabout.outerRadius).toBe(20);

    rerender(<AdvancedSettings value={doc} update={update} />);
    expect(
      screen.queryByLabelText(/Yellow clearance/i),
    ).not.toBeInTheDocument();
  });
});

describe("SR-28: MeteredRoundaboutStatus overlay", () => {
  it("renders null for conventional roundabouts", () => {
    const snap = makeConventionalSnapshot();
    const { container } = render(<MeteredRoundaboutStatus snapshot={snap} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders phase, time remaining, cycle count, and arms for metered roundabouts", () => {
    const snap = makeMeteredSnapshot();
    render(<MeteredRoundaboutStatus snapshot={snap} />);

    expect(
      screen.getByText(/Metered entry · Phase ns green/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/14.2s left/i)).toBeInTheDocument();
    expect(
      screen.getAllByText("GREEN", { selector: ".metered-status__arm-color" }),
    ).toHaveLength(2);
    expect(
      screen.getAllByText("RED", { selector: ".metered-status__arm-color" }),
    ).toHaveLength(2);
    expect(
      screen.getByText(
        "Simulation assumption — signal timings are not calibrated to real sites; no claim that signalised roundabouts are better or safer in the real world.",
      ),
    ).toBeInTheDocument();
  });

  it("explains hold reasons in plain language", () => {
    // Normal green
    const normal = makeMeteredSnapshot();
    expect(
      meteringHoldReasonText(
        (normal.controller as RoundaboutControllerState).metering!,
      ),
    ).toBe("Phase running on scheduled green.");

    // Spillback guard hold on East
    const spillback = makeMeteredSnapshot({
      arms: [
        { direction: "north", metered: true, color: "green", reason: null },
        {
          direction: "east",
          metered: true,
          color: "red",
          reason: "ring_spillback_hold",
        },
      ],
    });
    expect(
      meteringHoldReasonText(
        (spillback.controller as RoundaboutControllerState).metering!,
      ),
    ).toContain("Spillback guard active: holding red on E");

    // Queue cap: the controller emits an event, never an arm reason, then runs the
    // normal yellow clearance (events copied from SignalisedRoundaboutController).
    const capped = makeMeteredSnapshot({
      color: "yellow",
      recentDecisions: [
        { time: 10.1, arm: "east", reason: "open", state: "open" },
        { time: 31.4, arm: "south", reason: "queue_cap", state: "triggered" },
        { time: 31.4, arm: "north", reason: "yellow", state: "closed" },
      ],
    });
    expect(
      meteringHoldReasonText(
        (capped.controller as RoundaboutControllerState).metering!,
      ),
    ).toContain("green ended early because the standing queue on S");

    // ...and stops being the explanation once the next green has opened.
    const reopened = makeMeteredSnapshot({
      color: "green",
      recentDecisions: [
        { time: 31.4, arm: "south", reason: "queue_cap", state: "triggered" },
        { time: 36.4, arm: "east", reason: "open", state: "open" },
      ],
    });
    expect(
      meteringHoldReasonText(
        (reopened.controller as RoundaboutControllerState).metering!,
      ),
    ).toBe("Phase running on scheduled green.");

    // A cap from an earlier cycle does not explain a later clearance.
    const stale = makeMeteredSnapshot({
      color: "yellow",
      recentDecisions: [
        { time: 31.4, arm: "south", reason: "queue_cap", state: "triggered" },
        { time: 36.4, arm: "east", reason: "open", state: "open" },
      ],
    });
    expect(
      meteringHoldReasonText(
        (stale.controller as RoundaboutControllerState).metering!,
      ),
    ).toContain("Yellow change interval");

    // Yellow change interval
    const yellow = makeMeteredSnapshot({ color: "yellow" });
    expect(
      meteringHoldReasonText(
        (yellow.controller as RoundaboutControllerState).metering!,
      ),
    ).toContain("Yellow change interval");

    // All-red clearance
    const allRed = makeMeteredSnapshot({ color: "red" });
    expect(
      meteringHoldReasonText(
        (allRed.controller as RoundaboutControllerState).metering!,
      ),
    ).toContain("All-red clearance interval");
  });
});

describe("RoundaboutMap canvas integration", () => {
  it("renders canvas for conventional snapshot without error", () => {
    const snap = makeConventionalSnapshot();
    const { container } = render(
      <RoundaboutMap snapshot={snap} width={800} height={600} />,
    );
    expect(container.querySelector("canvas")).toBeInTheDocument();
  });

  it("renders canvas with signal heads for metered snapshot without error", () => {
    const snap = makeMeteredSnapshot();
    const { container } = render(
      <RoundaboutMap snapshot={snap} width={800} height={600} />,
    );
    expect(container.querySelector("canvas")).toBeInTheDocument();
  });
});

describe("SR-29: Accessibility (axe audit)", () => {
  it("MeteredRoundaboutStatus has no accessibility violations", async () => {
    const snap = makeMeteredSnapshot();
    const { container } = render(<MeteredRoundaboutStatus snapshot={snap} />);
    const violations = await axeViolations(container);
    expect(violations).toEqual([]);
  });

  it("AdvancedSettings in metered mode has no accessibility violations", async () => {
    const doc = scenarioFromPreset("typical-urban");
    doc.roundabout.entryControl = "metered_entry";
    doc.roundabout.entryMetering = {
      phases: [
        { entries: ["north", "south"], green: 20 },
        { entries: ["east", "west"], green: 20 },
      ],
      yellow: 3.0,
      allRed: 2.0,
      spillbackGuard: { enabled: true, stoppedThreshold: 2, maxHold: 10.0 },
      queueCap: { enabled: true, vehicles: 8 },
    };
    const { container } = render(
      <AdvancedSettings value={doc} update={() => {}} />,
    );
    const violations = await axeViolations(container);
    expect(violations).toEqual([]);
  });
});
