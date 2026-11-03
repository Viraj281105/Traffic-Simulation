/**
 * @vitest-environment jsdom
 *
 * F-14: SimCanvas's optional frame cap. With maxFps=30 a canvas repaints on
 * at most every other 60 Hz frame, and canvases with the same cap repaint on
 * the same frames (the compare tiles stay in step). Without it, every frame
 * whose clock moved repaints, as before.
 */
import { render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createRef } from "react";

const draws = vi.hoisted(() => [] as { canvas: unknown; t: number }[]);

vi.mock("../landing/scene/render", () => ({
  createGroundLayer: () => ({ canvas: null }),
  drawScene: (
    ctx: { canvas: unknown },
    _w: number,
    _h: number,
    s: { clock: number },
  ) => {
    draws.push({ canvas: ctx.canvas, t: s.clock });
  },
}));
vi.mock("../landing/scene/sceneData", () => ({
  sampleRun: (_run: unknown, _data: unknown, t: number) => ({
    vehicles: [],
    control: null,
    clock: t,
  }),
}));
vi.mock("../landing/scene/clock", () => ({
  useOnScreen: () => ({ current: true }),
}));

import { SimCanvas } from "../landing/scene/SimCanvas";

type Frame = (now: number) => void;
let queue: Frame[] = [];

beforeEach(() => {
  draws.length = 0;
  queue = [];
  vi.stubGlobal("requestAnimationFrame", (cb: Frame) => {
    queue.push(cb);
    return queue.length;
  });
  vi.stubGlobal("cancelAnimationFrame", () => {});
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockImplementation(
    function (this: HTMLCanvasElement) {
      return {
        canvas: this,
        setTransform: () => {},
      } as unknown as CanvasRenderingContext2D;
    },
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

/** Runs 60 Hz frames for one second, advancing the clock every frame. */
function runOneSecond(clock: { current: { t: number } }) {
  for (let i = 1; i <= 60; i++) {
    const now = i * (1000 / 60);
    clock.current.t = i / 60;
    const pending = queue;
    queue = [];
    for (const cb of pending) cb(now);
  }
}

const data = { runs: { roundabout: { geometry: {} } } } as never;
const camera = {
  current: { yaw: 0, elev: 0, zoom: 1, shiftX: 0, shiftY: 0 },
};

describe("SimCanvas frame cap", () => {
  it("repaints every frame the clock moves without a cap", () => {
    const clock = { current: { t: 0 } };
    render(
      <SimCanvas
        data={data}
        strategy={"roundabout"}
        clock={clock as never}
        camera={camera as never}
        label="x"
      />,
    );
    runOneSecond(clock);
    expect(draws.length).toBe(60);
  });

  it("repaints at most 30 times a second with maxFps=30, in step across canvases", () => {
    const clock = { current: { t: 0 } };
    const ref = createRef<HTMLDivElement>();
    render(
      <div ref={ref}>
        <SimCanvas
          data={data}
          strategy={"roundabout"}
          clock={clock as never}
          camera={camera as never}
          label="a"
          maxFps={30}
        />
        <SimCanvas
          data={data}
          strategy={"roundabout"}
          clock={clock as never}
          camera={camera as never}
          label="b"
          maxFps={30}
        />
      </div>,
    );
    runOneSecond(clock);
    const [a, b] = Array.from(ref.current!.querySelectorAll("canvas"));
    const tA = draws.filter((d) => d.canvas === a).map((d) => d.t);
    const tB = draws.filter((d) => d.canvas === b).map((d) => d.t);
    expect(tA.length).toBeGreaterThanOrEqual(29);
    expect(tA.length).toBeLessThanOrEqual(31);
    expect(tB).toEqual(tA);
  });
});
