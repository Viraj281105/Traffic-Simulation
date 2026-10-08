/**
 * V1.5 real-world junctions on the frontend: the scenario model (arms,
 * bearings, U-turns, stop-line geometry), the scenario builder's arm and
 * geometry controls, the junction preview and the live-map geometry.
 */
import { fireEvent, render, screen, within } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import {
  armOf,
  describeScenario,
  localIssues,
  movementTarget,
  possibleMovements,
  presentApproaches,
  scenarioFromPreset,
  stopLineDistances,
  totalVph,
  turningTotal,
} from "../scenario/scenarioModel";
import type { ScenarioDocument } from "../scenario/scenarioTypes";
import { ScenarioBuilder } from "../components/scenario/ScenarioBuilder";
import { JunctionPreview } from "../components/scenario/JunctionPreview";
import type { ValidationState } from "../components/scenario/useScenarioValidation";
import { armWorldPoint, realWorldArms } from "../components/realWorldMap";

const READY: ValidationState = {
  status: "done",
  result: {
    valid: true,
    errors: [],
    warnings: [],
    strategies: ["fixed_time", "roundabout"],
  },
};

/** A T-junction: east-west main road, south stem, no north arm. */
function tJunction(): ScenarioDocument {
  const doc = scenarioFromPreset("calibrated-baseline");
  doc.approaches.north = null;
  armOf(doc, "south").turning = { left: 0.5, straight: 0, right: 0.5 };
  armOf(doc, "east").turning = { left: 0.3, straight: 0.7, right: 0 };
  armOf(doc, "west").turning = { left: 0, straight: 0.7, right: 0.3 };
  return doc;
}

function Harness({
  initial,
  onChangeSpy,
}: {
  initial: ScenarioDocument;
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
      validation={READY}
    />
  );
}

describe("real-world scenario model", () => {
  it("knows which slot every movement leaves by", () => {
    expect(movementTarget("north", "left")).toBe("east");
    expect(movementTarget("north", "straight")).toBe("south");
    expect(movementTarget("north", "right")).toBe("west");
    expect(movementTarget("south", "left")).toBe("west");
    expect(movementTarget("east", "uturn")).toBe("east");
  });

  it("offers only the movements a three-arm junction allows", () => {
    const doc = tJunction();
    expect(presentApproaches(doc)).toEqual(["east", "south", "west"]);
    expect(possibleMovements(doc, "south")).toEqual(["uturn", "left", "right"]);
    expect(totalVph(doc)).toBe(
      armOf(doc, "east").vehiclesPerHour +
        armOf(doc, "south").vehiclesPerHour +
        armOf(doc, "west").vehiclesPerHour,
    );
    expect(describeScenario(doc)).toMatch(/^Three-arm junction: /);
    expect(localIssues(doc, ["fixed_time", "roundabout"])).toEqual([]);
  });

  it("flags traffic sent into the missing arm without changing it", () => {
    const doc = tJunction();
    armOf(doc, "south").turning = { left: 0.4, straight: 0.2, right: 0.4 };
    const issues = localIssues(doc, ["fixed_time"]);
    expect(
      issues.some(
        (i) => i.where === "south" && /into the north slot/.test(i.message),
      ),
    ).toBe(true);
    expect(armOf(doc, "south").turning.straight).toBe(0.2);
  });

  it("needs at least three arms", () => {
    const doc = tJunction();
    doc.approaches.south = null;
    expect(
      localIssues(doc, ["fixed_time"]).some((i) =>
        /3 or 4 arms/.test(i.message),
      ),
    ).toBe(true);
  });

  it("flags an arm more than 30 degrees from its slot", () => {
    const doc = scenarioFromPreset("calibrated-baseline");
    armOf(doc, "east").bearing = 135;
    expect(
      localIssues(doc, ["fixed_time"]).some(
        (i) => i.where === "east" && /at most 30°/.test(i.message),
      ),
    ).toBe(true);
  });

  it("counts a U-turn share towards the 100%", () => {
    expect(
      turningTotal({ left: 0.2, straight: 0.5, right: 0.2, uturn: 0.1 }),
    ).toBeCloseTo(1, 9);
    expect(turningTotal({ left: 0.2, straight: 0.6, right: 0.2 })).toBeCloseTo(
      1,
      9,
    );
  });

  it("mirrors the backend's stop-line distances", () => {
    const doc = scenarioFromPreset("calibrated-baseline");
    const square = stopLineDistances(doc, false);
    expect(square.north).toBeCloseTo(1 * 3.5 + 3.5, 9);
    // Backend test_skewed_arms_set_their_stop_lines_back_until_clear.
    armOf(doc, "north").bearing = 30;
    const skewed = stopLineDistances(doc, false);
    const expected =
      (3.5 + 3.5 * Math.cos(Math.PI / 3)) / Math.sin(Math.PI / 3) + 3.5;
    expect(skewed.north).toBeCloseTo(expected, 9);
    expect(stopLineDistances(doc, true).north).toBeCloseTo(24, 9);
  });
});

describe("real-world scenario builder", () => {
  it("switches an arm off and back on without losing its settings", () => {
    const docs: ScenarioDocument[] = [];
    const initial = scenarioFromPreset("typical-urban");
    armOf(initial, "north").vehiclesPerHour = 777;
    render(
      <Harness
        initial={initial}
        onChangeSpy={(d) => {
          docs.push(d);
        }}
      />,
    );
    const group = screen.getByRole("group", { name: "Arms of the junction" });
    const north = Array.from(group.querySelectorAll("button")).find(
      (b) => b.textContent === "North",
    );
    expect(north).toBeDefined();
    if (!north) return;
    fireEvent.click(north);
    expect(docs[docs.length - 1]?.approaches.north).toBeNull();
    expect(
      screen.getByText(/A three-arm junction: no north road/),
    ).toBeInTheDocument();
    fireEvent.click(north);
    expect(docs[docs.length - 1]?.approaches.north?.vehiclesPerHour).toBe(777);
  });

  it("marks a U-turn lane only when the user asks", () => {
    const docs: ScenarioDocument[] = [];
    render(
      <Harness
        initial={scenarioFromPreset("calibrated-baseline")}
        onChangeSpy={(d) => {
          docs.push(d);
        }}
      />,
    );
    const northArrows = screen.getByRole("group", {
      name: "north signal lane arrows",
    });
    const toggle = within(northArrows).getByRole("button", {
      name: "Lane 1: U-turn",
    });
    expect(toggle).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(toggle);
    expect(docs[docs.length - 1]?.approaches.north?.laneUse).toEqual([
      ["uturn", "left", "straight", "right"],
    ]);
    // The U-turn share is offered once a lane allows U-turns.
    expect(
      screen.getByLabelText("north: share turning uturn (%)"),
    ).toBeInTheDocument();
  });

  it("keeps bearings and lane widths under Advanced", () => {
    const docs: ScenarioDocument[] = [];
    const { container } = render(
      <Harness
        initial={scenarioFromPreset("calibrated-baseline")}
        onChangeSpy={(d) => {
          docs.push(d);
        }}
      />,
    );
    expect(
      screen.queryByText("Junction geometry (real-world layout)"),
    ).toBeNull();
    const details = container.querySelector("details.sb-advanced");
    expect(details).not.toBeNull();
    if (!details) return;
    (details as HTMLDetailsElement).open = true;
    fireEvent(details, new Event("toggle"));
    expect(
      screen.getByText("Junction geometry (real-world layout)"),
    ).toBeInTheDocument();
    const bearings = screen.getAllByLabelText("Bearing");
    expect(bearings).toHaveLength(4);
    fireEvent.change(bearings[1], { target: { value: "80" } });
    expect(docs[docs.length - 1]?.approaches.east?.bearing).toBe(80);
  });
});

describe("junction preview", () => {
  it("draws only the arms that exist", () => {
    render(<JunctionPreview scenario={tJunction()} view="signal" />);
    const svg = screen.getByRole("img");
    expect(svg.getAttribute("aria-label")).toMatch(
      /3-arm junction as a signal/,
    );
    expect(svg.querySelectorAll(".jp-arm")).toHaveLength(3);
    expect(svg.querySelector("polygon.jp-box")).not.toBeNull();
  });

  it("keeps the square box for the standard junction", () => {
    render(
      <JunctionPreview
        scenario={scenarioFromPreset("calibrated-baseline")}
        view="signal"
      />,
    );
    const svg = screen.getByRole("img");
    expect(svg.querySelector("rect.jp-box")).not.toBeNull();
  });

  it("uses the engine's stop lines once the server has resolved them", () => {
    const doc = tJunction();
    render(
      <JunctionPreview
        scenario={doc}
        view="signal"
        design={{
          laneUse: {},
          geometry: {
            east: {
              bearing: 90,
              lanes: 1,
              laneWidth: 3.5,
              length: 200,
              stopLineDistance: 12,
            },
            south: {
              bearing: 180,
              lanes: 1,
              laneWidth: 3.5,
              length: 200,
              stopLineDistance: 12,
            },
            west: {
              bearing: 270,
              lanes: 1,
              laneWidth: 3.5,
              length: 200,
              stopLineDistance: 12,
            },
          },
        }}
      />,
    );
    const stop = screen.getByRole("img").querySelector(".jp-stop-line");
    expect(stop?.getAttribute("y1")).toBe("12.6");
  });
});

describe("live map geometry", () => {
  it("draws the standard junction with the existing renderer", () => {
    expect(
      realWorldArms([
        { direction: "north", queueLength: 0, laneCount: 1 },
        { direction: "south", queueLength: 0, laneCount: 1 },
      ]),
    ).toBeNull();
  });

  it("reads each arm's laid-out geometry from the snapshot", () => {
    const arms = realWorldArms([
      {
        direction: "north",
        queueLength: 0,
        laneCount: 2,
        bearing: 20,
        laneWidth: 3.2,
        stopLineDistance: 9.5,
      },
    ]);
    expect(arms).toEqual([
      {
        direction: "north",
        bearing: 20,
        laneWidth: 3.2,
        stopLineDistance: 9.5,
        laneCount: 2,
        lanePermittedTurns: undefined,
      },
    ]);
  });

  it("places points exactly as the backend's arm frame", () => {
    // ArmGeometry.point: along * u + lateral * n, u = (sin b, cos b),
    // n = (cos b, -sin b).
    const [x, y] = armWorldPoint(20, 50, -1.75);
    const b = (20 * Math.PI) / 180;
    expect(x).toBeCloseTo(50 * Math.sin(b) - 1.75 * Math.cos(b), 9);
    expect(y).toBeCloseTo(50 * Math.cos(b) + 1.75 * Math.sin(b), 9);
    const [nx, ny] = armWorldPoint(0, 50, -1.75);
    expect(nx).toBeCloseTo(-1.75, 9);
    expect(ny).toBeCloseTo(50, 9);
  });
});
