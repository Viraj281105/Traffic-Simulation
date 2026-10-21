/**
 * @vitest-environment jsdom
 *
 * V3.0 W2 follow-up (UX audit docs/product/ux-audit-v3-w2-followup.md):
 * metered roundabout entry is chosen where the junction is described, is named
 * wherever the roundabout is named, and no text claims a metered roundabout has
 * no signal. Conventional roundabouts must stay exactly as they were.
 */
import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { ScenarioBuilder } from "../components/scenario/ScenarioBuilder";
import { EntryControlChoice } from "../components/scenario/EntryControlChoice";
import type { ValidationState } from "../components/scenario/useScenarioValidation";
import { LiveGuide } from "../components/guided/LiveGuide";
import { buildStudyRequest } from "../components/planner/plannerRequest";
import {
  cloneScenario,
  defaultEntryMetering,
  exportScenarioJson,
  meteringCoverage,
  rebuildEntryMeteringPhases,
  scenarioFromPreset,
  setEntryControl,
} from "../scenario/scenarioModel";
import {
  METERED_ROUNDABOUT_TITLE,
  isMeteredEntry,
  strategyTitle,
  type Strategy,
  type ScenarioDocument,
} from "../scenario/scenarioTypes";
import { explanations, sideSummary } from "../metrics/plainLanguage";
import { axeViolations } from "./axe";

const READY: ValidationState = {
  status: "done",
  result: {
    valid: true,
    errors: [],
    warnings: [],
    strategies: ["fixed_time", "roundabout"],
  },
};

function Harness({
  initial,
  strategies = ["fixed_time", "roundabout"],
  validation = READY,
  spy,
}: {
  initial: ScenarioDocument;
  strategies?: Strategy[];
  validation?: ValidationState;
  spy?: (doc: ScenarioDocument) => void;
}) {
  const [doc, setDoc] = useState(initial);
  return (
    <ScenarioBuilder
      value={doc}
      onChange={(next) => {
        spy?.(next);
        setDoc(next);
      }}
      strategies={strategies}
      validation={validation}
    />
  );
}

const metered = (): ScenarioDocument => {
  const doc = scenarioFromPreset("typical-urban");
  setEntryControl(doc, "metered_entry");
  return doc;
};

describe("entry-control model", () => {
  it("a conventional roundabout never carries metering fields", () => {
    const doc = scenarioFromPreset("typical-urban");
    const before = exportScenarioJson(doc);
    setEntryControl(doc, "metered_entry");
    expect(isMeteredEntry(doc)).toBe(true);
    expect(doc.roundabout.entryMetering?.phases).toHaveLength(2);
    setEntryControl(doc, "conventional");
    expect("entryControl" in doc.roundabout).toBe(false);
    expect("entryMetering" in doc.roundabout).toBe(false);
    expect(exportScenarioJson(doc)).toBe(before);
  });

  it("choosing metered keeps a plan the user already edited", () => {
    const doc = metered();
    const plan = doc.roundabout.entryMetering;
    if (!plan) throw new Error("plan expected");
    plan.phases[0].green = 33;
    setEntryControl(doc, "metered_entry");
    expect(doc.roundabout.entryMetering?.phases[0].green).toBe(33);
  });

  it("names the roads a plan signals, leaves out and no longer has", () => {
    const doc = metered();
    expect(meteringCoverage(doc)).toEqual({
      metered: ["north", "east", "south", "west"],
      unmetered: [],
      missing: [],
    });
    doc.approaches.north = null;
    expect(meteringCoverage(doc).missing).toEqual(["north"]);
    expect(meteringCoverage(doc).metered).toEqual(["east", "south", "west"]);

    const partial = metered();
    partial.roundabout.entryMetering = {
      ...defaultEntryMetering(partial),
      phases: [{ entries: ["north", "south"], green: 20 }],
    };
    expect(meteringCoverage(partial).unmetered).toEqual(["east", "west"]);
  });

  it("rebuilding phases keeps clearances, guard and cap but not greens", () => {
    const doc = metered();
    const plan = doc.roundabout.entryMetering;
    if (!plan) throw new Error("plan expected");
    plan.yellow = 4;
    plan.allRed = 1.5;
    plan.spillbackGuard = { enabled: true, stoppedThreshold: 3, maxHold: 12 };
    plan.phases[0].green = 40;
    doc.approaches.north = null;
    rebuildEntryMeteringPhases(doc);
    const after = doc.roundabout.entryMetering;
    expect(after?.phases.map((p) => p.entries)).toEqual([
      ["south"],
      ["east", "west"],
    ]);
    expect(after?.phases.every((p) => p.green === 20)).toBe(true);
    expect(after?.yellow).toBe(4);
    expect(after?.allRed).toBe(1.5);
    expect(after?.spillbackGuard).toEqual({
      enabled: true,
      stoppedThreshold: 3,
      maxHold: 12,
    });
    expect(meteringCoverage(doc).missing).toEqual([]);
  });

  it("only a metered roundabout is renamed", () => {
    const conventional = scenarioFromPreset("typical-urban");
    expect(strategyTitle("roundabout", conventional)).toBe("Roundabout");
    expect(strategyTitle("roundabout", metered())).toBe(
      METERED_ROUNDABOUT_TITLE,
    );
    expect(strategyTitle("fixed_time", metered())).toBe("Fixed-time signal");
    expect(strategyTitle("adaptive", metered())).toBe("Adaptive signal");
  });
});

describe("step 1 of the scenario builder", () => {
  it("offers the entry control without opening Advanced", () => {
    render(<Harness initial={scenarioFromPreset("typical-urban")} />);
    const group = screen.getByRole("group", {
      name: "How do vehicles enter the roundabout?",
    });
    expect(group).toBeInTheDocument();
    expect(
      screen.getByRole("radio", { name: /Conventional roundabout/ }),
    ).toBeChecked();
    expect(
      screen.getByRole("radio", { name: /Metered entry \(signals\)/ }),
    ).not.toBeChecked();
    expect(
      screen.getByText(/Ready to simulate as Fixed-time signal, Roundabout\./),
    ).toBeInTheDocument();
    // The timing fields stay in the closed Advanced section.
    expect(screen.queryByText("Yellow clearance")).not.toBeInTheDocument();
  });

  it("does not touch the document just by rendering", () => {
    const spy = vi.fn();
    render(<Harness initial={scenarioFromPreset("typical-urban")} spy={spy} />);
    expect(spy).not.toHaveBeenCalled();
  });

  it("switching to metered entry is named in the readiness line", () => {
    const spy = vi.fn<(doc: ScenarioDocument) => void>();
    render(<Harness initial={scenarioFromPreset("typical-urban")} spy={spy} />);
    fireEvent.click(
      screen.getByRole("radio", { name: /Metered entry \(signals\)/ }),
    );
    const next = spy.mock.calls[0][0];
    expect(next.roundabout.entryControl).toBe("metered_entry");
    expect(
      screen.getByText(
        /Ready to simulate as Fixed-time signal, Roundabout \(metered entry\)\./,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/signals on North, East, South, West/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/not calibrated to real sites/),
    ).toBeInTheDocument();
  });

  it("is hidden when no roundabout is being run", () => {
    render(
      <Harness
        initial={scenarioFromPreset("typical-urban")}
        strategies={["fixed_time", "adaptive"]}
      />,
    );
    expect(
      screen.queryByRole("group", {
        name: "How do vehicles enter the roundabout?",
      }),
    ).not.toBeInTheDocument();
  });

  it("returns to conventional and removes the metering fields", () => {
    const spy = vi.fn<(doc: ScenarioDocument) => void>();
    render(<Harness initial={metered()} spy={spy} />);
    fireEvent.click(
      screen.getByRole("radio", { name: /Conventional roundabout/ }),
    );
    const next = spy.mock.calls[0][0];
    expect("entryControl" in next.roundabout).toBe(false);
    expect("entryMetering" in next.roundabout).toBe(false);
  });

  it("explains and repairs phases that name a switched-off road", () => {
    render(
      <Harness
        initial={metered()}
        validation={{
          status: "done",
          result: {
            valid: false,
            errors: [
              "Roundabout: phase 0 entry 'north' is not present at the junction (metering.missing_arm)",
            ],
            warnings: [],
            strategies: ["roundabout"],
          },
        }}
      />,
    );
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "North" }));
    expect(screen.getByRole("alert")).toHaveTextContent(
      /still name North, which this junction no longer has/,
    );
    expect(
      screen.getByText(/choose “Rebuild phases for the current roads”/),
    ).toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", {
        name: "Rebuild phases for the current roads",
      }),
    );
    expect(
      screen.queryByRole("button", {
        name: "Rebuild phases for the current roads",
      }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByText(/signals on East, South, West/),
    ).toBeInTheDocument();
  });

  it("says which roads are not metered, and never rewrites by itself", () => {
    const doc = metered();
    doc.roundabout.entryMetering = {
      ...defaultEntryMetering(doc),
      phases: [{ entries: ["north", "south"], green: 25 }],
    };
    const before = cloneScenario(doc);
    render(<EntryControlChoice value={doc} update={() => {}} />);
    expect(
      screen.getByText(/East, West are not in any phase/),
    ).toBeInTheDocument();
    expect(doc).toEqual(before);
  });

  it("has no accessibility violations, plain or in the repair state", async () => {
    const plain = render(
      <EntryControlChoice
        value={scenarioFromPreset("typical-urban")}
        update={() => {}}
      />,
    );
    expect(await axeViolations(plain.container)).toEqual([]);
    plain.unmount();

    const stale = metered();
    stale.approaches.north = null;
    const repair = render(
      <EntryControlChoice value={stale} update={() => {}} />,
    );
    expect(await axeViolations(repair.container)).toEqual([]);
  });
});

describe("the planner request", () => {
  const rows = [
    { key: 1, strategy: "fixed_time" as const, label: "" },
    { key: 2, strategy: "roundabout" as const, label: "" },
  ];
  it("keeps a conventional roundabout's request exactly as before", () => {
    const req = buildStudyRequest({
      name: "x",
      scenario: scenarioFromPreset("typical-urban"),
      alternatives: rows,
      seeds: 3,
      scales: [1],
    });
    expect(req.alternatives).toEqual([
      { id: "fixed_time", strategy: "fixed_time" },
      { id: "roundabout", strategy: "roundabout" },
    ]);
  });

  it("names a metered roundabout unless the user chose a label", () => {
    const named = buildStudyRequest({
      name: "x",
      scenario: metered(),
      alternatives: rows,
      seeds: 3,
      scales: [1],
    });
    expect(named.alternatives[0]).not.toHaveProperty("label");
    expect(named.alternatives[1].label).toBe(METERED_ROUNDABOUT_TITLE);
    const own = buildStudyRequest({
      name: "x",
      scenario: metered(),
      alternatives: [rows[0], { ...rows[1], label: "Ring signals" }],
      seeds: 3,
      scales: [1],
    });
    expect(own.alternatives[1].label).toBe("Ring signals");
  });
});

describe("text that describes the roundabout", () => {
  const facts = {
    lanes: 1,
    arrivalRate: 0.3,
    greenNs: 25,
    greenEw: 25,
    cycleSeconds: 60,
    criticalGap: 4.5,
  };
  const side = (geometry: "fixed_time_signal" | "roundabout") =>
    sideSummary({ metrics: undefined, geometry, inWarmup: false });
  const roundaboutBody = (extra: { meteredEntry?: boolean }) =>
    explanations(side("fixed_time_signal"), side("roundabout"), {
      ...facts,
      ...extra,
    }).find((e) => e.title === "How the roundabout decides who goes")?.body;

  it("a conventional roundabout is still described as having no red light", () => {
    expect(roundaboutBody({})).toMatch(/^Nobody gets a red light/);
    expect(roundaboutBody({ meteredEntry: false })).toMatch(
      /^Nobody gets a red light/,
    );
  });

  it("a metered roundabout is not, and keeps the gap rule and its limits", () => {
    const body = roundaboutBody({ meteredEntry: true }) ?? "";
    expect(body).not.toMatch(/Nobody gets a red light/);
    expect(body).toMatch(/a green never sends one in/);
    expect(body).toMatch(/gap of at least 4\.5 s/);
    expect(body).toMatch(/Nothing inside the ring is signalled/);
    expect(body).toMatch(/assumption of this simulation/);
  });

  const guide = (meteredEntry?: boolean) =>
    render(
      <LiveGuide
        snapshot={null}
        meteredEntry={meteredEntry}
        durationSeconds={120}
        connectionStatus="connected"
        onSeeResults={() => {}}
        detailedPanel={null}
      />,
    );

  it("the live tip no longer says nobody waits for a light when metered", () => {
    guide(true);
    expect(
      screen.queryByText(/nobody waits for a light/),
    ).not.toBeInTheDocument();
    expect(
      screen.getByText(/a green never forces a driver in/),
    ).toBeInTheDocument();
  });

  it("the live tip is unchanged for a conventional roundabout", () => {
    guide();
    expect(screen.getByText(/nobody waits for a light/)).toBeInTheDocument();
  });
});
