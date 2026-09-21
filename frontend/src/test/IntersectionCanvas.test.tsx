/**
 * Tests for IntersectionCanvas — the visualisation itself.
 *
 * jsdom provides no 2D context, so the canvas API is stubbed and the test
 * asserts on the drawing calls. That is enough to pin the behaviour that
 * actually breaks in practice: rendering with no vehicle yet, re-rendering when
 * the vehicle moves, and the world-to-canvas mapping that decides whether
 * anything lands on screen at all. A silent failure here is a blank demo.
 */
import { render } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { IntersectionCanvas } from "../components/IntersectionCanvas";
import type { SingleVehicleResponse } from "../types/simulation";

interface DrawCall {
  op: string;
  args: unknown[];
}

let calls: DrawCall[] = [];

function makeContext(): Record<string, unknown> {
  const record =
    (op: string) =>
    (...args: unknown[]) => {
      calls.push({ op, args });
    };

  return {
    fillRect: record("fillRect"),
    clearRect: record("clearRect"),
    strokeRect: record("strokeRect"),
    beginPath: record("beginPath"),
    closePath: record("closePath"),
    moveTo: record("moveTo"),
    lineTo: record("lineTo"),
    arc: record("arc"),
    fill: record("fill"),
    stroke: record("stroke"),
    save: record("save"),
    restore: record("restore"),
    translate: record("translate"),
    rotate: record("rotate"),
    scale: record("scale"),
    fillText: record("fillText"),
    strokeText: record("strokeText"),
    setLineDash: record("setLineDash"),
    measureText: () => ({ width: 10 }),
    canvas: null,
    fillStyle: "",
    strokeStyle: "",
    lineWidth: 1,
    font: "",
    textAlign: "",
    textBaseline: "",
    globalAlpha: 1,
    lineCap: "",
    lineJoin: "",
    shadowBlur: 0,
    shadowColor: "",
  };
}

function aVehicle(
  overrides: Partial<SingleVehicleResponse> = {},
): SingleVehicleResponse {
  return {
    vehicle_id: "vehicle_1",
    position: 10,
    speed: 12,
    acceleration: 0,
    x: 0,
    y: -70,
    heading: 0,
    state: "approaching",
    lane_id: "s_in_0",
    wait_time: 0,
    stop_count: 0,
    sim_time: 1,
    tick: 10,
    simulation_status: "running",
    ...overrides,
  };
}

beforeEach(() => {
  calls = [];
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockImplementation(
    () => makeContext() as unknown as CanvasRenderingContext2D,
  );
});

describe("IntersectionCanvas", () => {
  it("renders a canvas element at the requested size", () => {
    const { container } = render(
      <IntersectionCanvas vehicle={null} width={800} height={600} />,
    );

    const canvas = container.querySelector("canvas");
    expect(canvas).not.toBeNull();
    expect(canvas?.width).toBe(800);
    expect(canvas?.height).toBe(600);
  });

  it("draws the scene even before any vehicle has arrived", () => {
    render(<IntersectionCanvas vehicle={null} width={800} height={600} />);

    // The background fill plus the road/intersection furniture must be drawn,
    // otherwise the demo opens on an empty box.
    expect(calls.length).toBeGreaterThan(0);
    expect(calls.some((c) => c.op === "fillRect")).toBe(true);
  });

  it("paints a background covering the whole canvas", () => {
    render(<IntersectionCanvas vehicle={null} width={800} height={600} />);

    const background = calls.find(
      (c) =>
        c.op === "fillRect" &&
        c.args[0] === 0 &&
        c.args[1] === 0 &&
        c.args[2] === 800 &&
        c.args[3] === 600,
    );
    expect(background).toBeDefined();
  });

  it("draws more when a vehicle is present than when it is not", () => {
    render(<IntersectionCanvas vehicle={null} width={800} height={600} />);
    const withoutVehicle = calls.length;

    calls = [];
    render(
      <IntersectionCanvas vehicle={aVehicle()} width={800} height={600} />,
    );

    expect(calls.length).toBeGreaterThan(withoutVehicle);
  });

  it("redraws when the vehicle moves", () => {
    const { rerender } = render(
      <IntersectionCanvas
        vehicle={aVehicle({ y: -70 })}
        width={800}
        height={600}
      />,
    );
    const initial = calls.length;

    calls = [];
    rerender(
      <IntersectionCanvas
        vehicle={aVehicle({ y: -20 })}
        width={800}
        height={600}
      />,
    );

    expect(calls.length).toBeGreaterThan(0);
    expect(calls.length).toBeCloseTo(initial, -2);
  });

  it("redraws when the canvas is resized", () => {
    const { rerender } = render(
      <IntersectionCanvas vehicle={null} width={800} height={600} />,
    );

    calls = [];
    rerender(<IntersectionCanvas vehicle={null} width={400} height={300} />);

    const background = calls.find(
      (c) => c.op === "fillRect" && c.args[2] === 400 && c.args[3] === 300,
    );
    expect(background).toBeDefined();
  });

  it("maps the world origin to the centre of the canvas", () => {
    // The vehicle at world (0, 0) must be drawn at the canvas centre. If the
    // world-to-canvas mapping regresses, vehicles silently render off-screen.
    render(
      <IntersectionCanvas
        vehicle={aVehicle({ x: 0, y: 0 })}
        width={800}
        height={600}
      />,
    );

    const translate = calls.find(
      (c) => c.op === "translate" && c.args[0] === 400 && c.args[1] === 300,
    );
    expect(translate).toBeDefined();
  });

  it("does not throw when the 2D context is unavailable", () => {
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null);

    expect(() =>
      render(
        <IntersectionCanvas vehicle={aVehicle()} width={800} height={600} />,
      ),
    ).not.toThrow();
  });
});
