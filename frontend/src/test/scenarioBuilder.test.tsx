/**
 * V1.4 custom scenarios on the frontend: the scenario model (presets, local
 * checks, import/export, the bridge to the dashboard config), the dashboard
 * payload carrying a scenario, and the scenario builder.
 */
import { fireEvent, render, screen, within } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  DEFAULT_CONFIG_VALUES,
  dashboardPayload,
  sameConfigValues,
} from "../types/config";
import {
  SCENARIO_PRESETS,
  approachLanes,
  configValuesFromScenario,
  defaultLaneUse,
  describeScenario,
  exportScenarioJson,
  localIssues,
  matchesPreset,
  mixTotal,
  parseScenarioJson,
  scenarioFromConfigValues,
  scenarioFromPreset,
  withLaneCount,
} from "../scenario/scenarioModel";
import type { ScenarioDocument } from "../scenario/scenarioTypes";
import { ScenarioBuilder } from "../components/scenario/ScenarioBuilder";
import type { ValidationState } from "../components/scenario/useScenarioValidation";
import { MixEditor } from "../components/scenario/MixEditor";
import { ApproachResults } from "../components/guided/ApproachResults";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("scenario model", () => {
  it("ships the five required presets plus the calibrated baseline", () => {
    const ids = SCENARIO_PRESETS.map((p) => p.id);
    for (const id of [
      "typical-urban",
      "heavy-commuter",
      "bus-corridor",
      "mixed-urban",
      "motorcycle-heavy",
      "calibrated-baseline",
    ]) {
      expect(ids).toContain(id);
    }
  });

  it("presets are editable copies, and edits are recognised as custom", () => {
    const doc = scenarioFromPreset("typical-urban");
    expect(matchesPreset(doc)).toBe(true);
    doc.approaches.north.vehiclesPerHour += 100;
    expect(matchesPreset(doc)).toBe(false);
    // The preset itself is untouched.
    expect(matchesPreset(scenarioFromPreset("typical-urban"))).toBe(true);
  });

  it("reports a vehicle mix that does not total 100% without rescaling it", () => {
    const doc = scenarioFromPreset("typical-urban");
    doc.vehicles.mix = { car: 0.5, suv: 0.2, bus: 0, truck: 0, motorcycle: 0 };
    const issues = localIssues(doc, ["fixed_time"]);
    expect(issues.some((i) => i.where === "vehicles")).toBe(true);
    expect(mixTotal(doc.vehicles.mix)).toBeCloseTo(0.7, 9);
    expect(doc.vehicles.mix.car).toBe(0.5);
  });

  it("flags crossing arrows and unserved turns for a signal only", () => {
    const doc = scenarioFromPreset("typical-urban");
    doc.approaches.north.laneUse = [["straight"], ["left"]];
    const signal = localIssues(doc, ["fixed_time"]);
    expect(signal.some((i) => /cross/.test(i.message))).toBe(true);
    expect(
      localIssues(doc, ["roundabout"]).some((i) => /cross/.test(i.message)),
    ).toBe(false);
    doc.approaches.north.laneUse = [["straight"], ["straight"]];
    expect(
      localIssues(doc, ["fixed_time"]).some((i) =>
        /no lane allows it/.test(i.message),
      ),
    ).toBe(true);
  });

  it("requires equal opposite approaches at a signal but not at a roundabout", () => {
    const doc = scenarioFromPreset("typical-urban");
    doc.approaches.south = withLaneCount(doc.approaches.south, 3);
    expect(
      localIssues(doc, ["fixed_time"]).some((i) =>
        /same number of lanes/.test(i.message),
      ),
    ).toBe(true);
    expect(localIssues(doc, ["roundabout"])).toEqual([]);
  });

  it("drops lane arrows that no longer fit a new lane count", () => {
    const arm = scenarioFromPreset("heavy-commuter").approaches.north;
    expect(arm.laneUse).toHaveLength(3);
    expect(withLaneCount(arm, 2).laneUse).toBeNull();
    expect(defaultLaneUse(3)).toEqual([
      ["left", "straight"],
      ["straight"],
      ["straight", "right"],
    ]);
  });

  it("exports and imports a scenario losslessly", () => {
    const doc = scenarioFromPreset("bus-corridor");
    const parsed = parseScenarioJson(exportScenarioJson(doc));
    expect("scenario" in parsed && parsed.scenario).toEqual(doc);
  });

  it("rejects files that are not UrbanFlow scenarios, explaining why", () => {
    expect(parseScenarioJson("{nope")).toEqual({
      error: "That file is not valid JSON.",
    });
    const other = parseScenarioJson(JSON.stringify({ format: "other" }));
    expect("error" in other && other.error).toMatch(
      /Not an UrbanFlow scenario/,
    );
    const future = parseScenarioJson(
      JSON.stringify({ ...scenarioFromPreset("bus-corridor"), version: 9 }),
    );
    expect("error" in future && future.error).toMatch(/version 9/);
  });

  it("describes a scenario in plain language", () => {
    const text = describeScenario(scenarioFromPreset("heavy-commuter"));
    expect(text).toMatch(/3-lane north–south road/);
    expect(text).toMatch(/heaviest from the north/);
  });

  it("bridges to the dashboard config and back", () => {
    const doc = scenarioFromPreset("heavy-commuter");
    const config = configValuesFromScenario(doc, DEFAULT_CONFIG_VALUES);
    expect(config.scenario).toEqual(doc);
    expect(config.signalControl).toBe("adaptive");
    expect(config.arrivalRate).toBeCloseTo(2150 / 3600, 9);
    expect(approachLanes(config)).toEqual({
      north: 3,
      south: 3,
      east: 2,
      west: 2,
    });
    expect(scenarioFromConfigValues(config)).toEqual(doc);
    const payload = dashboardPayload(config, "fixed_time_signal");
    expect(payload.scenario).toEqual(doc);
    expect(sameConfigValues(config, { ...config })).toBe(true);
    expect(
      sameConfigValues(config, {
        ...config,
        scenario: { ...doc, name: "Other" },
      }),
    ).toBe(false);
  });

  it("starts the builder from the quick-setup answers", () => {
    const doc = scenarioFromConfigValues({
      ...DEFAULT_CONFIG_VALUES,
      lanes: 2,
      arrivalRate: 0.4,
    });
    expect(doc.approaches.north.lanes).toBe(2);
    expect(doc.approaches.east.vehiclesPerHour).toBe(360);
  });

  it("leaves the dashboard payload exactly as before without a scenario", () => {
    expect(
      "scenario" in dashboardPayload(DEFAULT_CONFIG_VALUES, "roundabout"),
    ).toBe(false);
  });
});

const READY: ValidationState = {
  status: "done",
  result: {
    valid: true,
    errors: [],
    warnings: ["Mixed vehicle classes: exploratory."],
    strategies: ["fixed_time", "roundabout"],
  },
};

function Harness({
  initial,
  validation = READY,
  onChangeSpy,
}: {
  initial: ScenarioDocument;
  validation?: ValidationState;
  onChangeSpy?: (doc: ScenarioDocument) => void;
}) {
  const [doc, setDoc] = useState(initial);
  return (
    <ScenarioBuilder
      value={doc}
      onChange={(next) => {
        onChangeSpy?.(next);
        setDoc(next);
      }}
      strategies={["fixed_time", "roundabout"]}
      validation={validation}
    />
  );
}

describe("scenario builder", () => {
  it("shows the backend's verdict and warnings", () => {
    render(<Harness initial={scenarioFromPreset("typical-urban")} />);
    expect(screen.getByText(/Ready to simulate as/)).toBeInTheDocument();
    expect(
      screen.getByText("Mixed vehicle classes: exploratory."),
    ).toBeInTheDocument();
  });

  it("explains why a configuration cannot be simulated", () => {
    render(
      <Harness
        initial={scenarioFromPreset("typical-urban")}
        validation={{
          status: "done",
          result: {
            valid: false,
            errors: ["Roundabout: 3 circulating lanes are not supported yet"],
            warnings: [],
            strategies: ["roundabout"],
          },
        }}
      />,
    );
    expect(
      screen.getByText(/cannot currently be simulated/),
    ).toBeInTheDocument();
    expect(screen.getByText(/not supported yet/)).toBeInTheDocument();
  });

  it("changes an approach's lane count and its arrows", () => {
    const spy = vi.fn<(doc: ScenarioDocument) => void>();
    render(
      <Harness
        initial={scenarioFromPreset("typical-urban")}
        onChangeSpy={spy}
      />,
    );
    const lanes = screen.getAllByRole("group", { name: "Lanes" })[0];
    fireEvent.click(within(lanes).getByRole("button", { name: /More lanes/ }));
    const last = spy.mock.calls[spy.mock.calls.length - 1][0];
    expect(last.approaches.north.lanes).toBe(3);

    // North's card comes first.
    const toggle = screen.getAllByRole("button", {
      name: "Lane 1: Straight",
    })[0];
    fireEvent.click(toggle);
    const after = spy.mock.calls[spy.mock.calls.length - 1][0];
    expect(after.approaches.north.laneUse?.[0]).toEqual(["left"]);
  });

  it("sets how busy a road is with a level or an exact figure", () => {
    const spy = vi.fn<(doc: ScenarioDocument) => void>();
    render(
      <Harness
        initial={scenarioFromPreset("typical-urban")}
        onChangeSpy={spy}
      />,
    );
    fireEvent.click(screen.getAllByRole("button", { name: "Very busy" })[0]);
    const doc = spy.mock.calls[spy.mock.calls.length - 1][0];
    expect(doc.approaches.north.vehiclesPerHour).toBe(1100);
  });

  it("loads a preset and offers to reset to it after edits", () => {
    render(<Harness initial={scenarioFromPreset("typical-urban")} />);
    fireEvent.change(screen.getByLabelText("Start from a preset"), {
      target: { value: "motorcycle-heavy" },
    });
    expect(
      screen.getByText("Preset: Motorcycle-heavy traffic"),
    ).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole("button", { name: "Quiet" })[0]);
    expect(
      screen.getByRole("button", {
        name: /Reset to “Motorcycle-heavy traffic”/,
      }),
    ).toBeInTheDocument();
  });
});

describe("per-approach results", () => {
  it("splits both junctions' results by the road drivers came from", () => {
    const doc = scenarioFromPreset("heavy-commuter");
    const side = (delay: number) => ({
      north: {
        exited: 40,
        averageDelay: delay,
        active: 3,
        averageQueueLength: 2,
        maxQueueLength: 6,
      },
      east: {
        exited: 0,
        averageDelay: 0,
        active: 1,
        averageQueueLength: 0,
        maxQueueLength: 1,
      },
    });
    render(
      <ApproachResults
        scenario={doc}
        signal={side(31.2)}
        roundabout={side(18.4)}
      />,
    );
    const north = screen.getByRole("row", { name: /North/ });
    expect(within(north).getByText("3 · 1,100 veh/h")).toBeInTheDocument();
    expect(within(north).getAllByText("40")).toHaveLength(2);
    expect(
      within(screen.getByRole("row", { name: /East/ })).getAllByText(
        "none through",
      ),
    ).toHaveLength(2);
  });
});

describe("mix editor", () => {
  it("shows the live total and never rescales", () => {
    const onChange = vi.fn<(mix: Record<string, number> | null) => void>();
    render(
      <MixEditor
        value={{ car: 0.6, suv: 0.2, bus: 0.1, truck: 0.05, motorcycle: 0.05 }}
        onChange={onChange}
      />,
    );
    expect(screen.getByText(/Total 100%/)).toBeInTheDocument();
    const car = screen.getByRole("spinbutton", { name: "Car" });
    fireEvent.change(car, { target: { value: "50" } });
    const next = onChange.mock.calls[onChange.mock.calls.length - 1][0] ?? {};
    expect(next.car).toBe(0.5);
    expect(next.suv).toBe(0.2);
  });

  it("warns when the shares do not add up to 100%", () => {
    render(
      <MixEditor
        value={{ car: 0.5, suv: 0.2, bus: 0, truck: 0, motorcycle: 0 }}
        onChange={() => {}}
      />,
    );
    expect(screen.getByText(/must be 100%/)).toBeInTheDocument();
    expect(screen.getByText(/will not rescale/)).toBeInTheDocument();
  });
});
