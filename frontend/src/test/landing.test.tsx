import { render, screen, waitFor } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";

import scene from "../landing/data/scene.json";
import evidence from "../landing/data/evidence.json";
import {
  STRATEGY_IDS,
  formatClock,
  sampleRun,
  seriesAt,
  windowLength,
  type SceneData,
} from "../landing/scene/sceneData";
import {
  createGroundLayer,
  drawScene,
  type Camera,
  type GroundLayer,
  type SceneTheme,
} from "../landing/scene/render";
import { Evidence } from "../landing/sections/Evidence";
import App from "../landing/App";

const data = scene as unknown as SceneData;

// jsdom has no IntersectionObserver; report every element as on screen so
// the scroll-triggered pieces render their final state.
beforeAll(() => {
  class InView {
    constructor(private readonly cb: IntersectionObserverCallback) {}
    observe(target: Element) {
      this.cb(
        [
          {
            isIntersecting: true,
            intersectionRatio: 1,
            target,
          } as IntersectionObserverEntry,
        ],
        this as unknown as IntersectionObserver,
      );
    }
    unobserve() {}
    disconnect() {}
    takeRecords() {
      return [];
    }
  }
  vi.stubGlobal("IntersectionObserver", InView);
});

describe("recorded landing scene", () => {
  it("holds one run per control strategy, recorded from one seed and one demand", () => {
    expect(Object.keys(data.runs).sort()).toEqual([...STRATEGY_IDS].sort());
    expect(data.provenance.gitCommit).toMatch(/^[0-9a-f]{40}$/);
    expect(data.provenance.seed).toBe(5);
    const lengths = new Set(
      STRATEGY_IDS.map((id) => data.runs[id].frames.length),
    );
    expect(lengths.size).toBe(1);
    for (const id of STRATEGY_IDS) {
      const run = data.runs[id];
      expect(run.series.length).toBeGreaterThan(100);
      expect(run.metrics.totalVehiclesSpawned).toBe(
        data.runs.fixed_time.metrics.totalVehiclesSpawned,
      );
    }
  });

  it("replays the same arrivals under every control", () => {
    // The seed fixes who arrives when, so vehicle ids present early in the
    // window overlap heavily between strategies.
    const first = (id: (typeof STRATEGY_IDS)[number]) =>
      new Set(data.runs[id].frames[0]?.v.map((v) => v[0]));
    const a = first("fixed_time");
    const b = first("roundabout");
    const shared = [...a].filter((v) => b.has(v)).length;
    expect(shared / Math.max(a.size, b.size)).toBeGreaterThan(0.5);
  });

  it("blends frames and loops without inventing vehicles", () => {
    const run = data.runs.fixed_time;
    const step = data.provenance.frameSeconds;
    const at = sampleRun(run, data, 10);
    const next = sampleRun(run, data, 10 + step / 2);
    const ids = new Set(run.frames.flatMap((f) => f.v.map((v) => v[0])));
    for (const v of next.vehicles) expect(ids.has(v.id)).toBe(true);
    const moved = next.vehicles.find((v) =>
      at.vehicles.some((w) => w.id === v.id),
    );
    expect(moved).toBeDefined();
    // Looping: one full window later is the same moment.
    const len = windowLength(data);
    expect(sampleRun(run, data, 10 + len).vehicles.length).toBe(
      at.vehicles.length,
    );
    // The seam fades the scene out.
    expect(sampleRun(run, data, 0).vehicles.every((v) => v.alpha < 0.05)).toBe(
      true,
    );
  });

  it("reads queue and departures from the per-second series, clamped to the run", () => {
    const run = data.runs.adaptive;
    expect(seriesAt(run, -5)).toEqual(seriesAt(run, 0));
    const end = seriesAt(run, 10_000);
    expect(end.departed).toBe(run.series[run.series.length - 1]?.[2]);
    expect(formatClock(75)).toBe("01:15");
  });
});

/** The fill colours a theme paints, in order, from a recording context. */
function fillsFor(theme: SceneTheme): string[] {
  const fills: string[] = [];
  const noop = () => undefined;
  const ctx = new Proxy(
    {},
    {
      get: (_t, prop) =>
        prop === "createRadialGradient" ? () => ({ addColorStop: noop }) : noop,
      set: (_t, prop, value) => {
        if (prop === "fillStyle" && typeof value === "string")
          fills.push(value);
        return true;
      },
    },
  ) as unknown as CanvasRenderingContext2D;
  const run = data.runs.fixed_time;
  const s = sampleRun(run, data, 20);
  drawScene(ctx, 800, 500, {
    strategy: "fixed_time",
    vehicles: s.vehicles,
    control: s.control,
    camera: { yaw: -30, elev: 40, zoom: 1, shiftX: 0, shiftY: 0 },
    innerRadius: 10,
    outerRadius: 20,
    clock: s.clock,
    theme,
  });
  return fills;
}

describe("scene themes", () => {
  it("paints a pale daylight ground in light mode and the night ground in dark mode", () => {
    expect(fillsFor("light")[0]).toBe("#edf1f7");
    expect(fillsFor("dark")[0]).toBe("#0a1626");
  });

  it("draws the two themes with different palettes and still draws vehicles", () => {
    const light = fillsFor("light");
    expect(light).not.toEqual(fillsFor("dark"));
    // Vehicle faces are the translucent rgba() fills.
    expect(light.some((f) => f.startsWith("rgba("))).toBe(true);
  });
});

/** A recording 2D context: fill colours and drawImage calls, in order. */
function recorder() {
  const fills: string[] = [];
  const images: unknown[] = [];
  const noop = () => undefined;
  const ctx = new Proxy(
    {},
    {
      get: (_t, prop) => {
        if (prop === "canvas") return { width: 800, height: 500 };
        if (prop === "getTransform") return () => ({});
        if (prop === "drawImage")
          return (img: unknown) => {
            images.push(img);
          };
        if (prop === "createRadialGradient")
          return () => ({ addColorStop: noop });
        return noop;
      },
      set: (_t, prop, value) => {
        if (prop === "fillStyle" && typeof value === "string")
          fills.push(value);
        return true;
      },
    },
  ) as unknown as CanvasRenderingContext2D;
  return { ctx, fills, images };
}

function draw(
  ctx: CanvasRenderingContext2D,
  camera: Camera,
  ground?: GroundLayer,
): void {
  const s = sampleRun(data.runs.fixed_time, data, 20);
  drawScene(ctx, 800, 500, {
    strategy: "fixed_time",
    vehicles: s.vehicles,
    control: s.control,
    camera,
    innerRadius: 10,
    outerRadius: 20,
    clock: s.clock,
    theme: "dark",
    ground,
  });
}

const STILL: Camera = { yaw: -30, elev: 40, zoom: 1, shiftX: 0, shiftY: 0 };

describe("scene renderer work", () => {
  it("caches the ground once a view repeats and blits it afterwards", () => {
    const layerCtx = recorder();
    const spy = vi
      .spyOn(HTMLCanvasElement.prototype, "getContext")
      .mockImplementation(() => layerCtx.ctx);
    try {
      const ground = createGroundLayer();
      const page = recorder();
      draw(page.ctx, STILL, ground); // first sight of this view: drawn directly
      draw(page.ctx, STILL, ground); // repeated: cached, then blitted
      draw(page.ctx, STILL, ground); // still repeated: blitted, no redraw
      expect(page.images).toHaveLength(2);
      // The ground fill went to the page once and to the cache once.
      expect(page.fills.filter((f) => f === "#0a1626")).toHaveLength(1);
      expect(layerCtx.fills.filter((f) => f === "#0a1626")).toHaveLength(1);
      // A moving camera never uses the cache.
      const moving = recorder();
      const fresh = createGroundLayer();
      draw(moving.ctx, STILL, fresh);
      draw(moving.ctx, { ...STILL, yaw: STILL.yaw + 1 }, fresh);
      expect(moving.images).toHaveLength(0);
    } finally {
      spy.mockRestore();
    }
  });

  it("skips vehicles and buildings that project entirely off the canvas", () => {
    const on = recorder();
    draw(on.ctx, STILL);
    const off = recorder();
    draw(off.ctx, { ...STILL, shiftX: 50 }); // scene centre far to the right
    // Vehicle faces are rgba() with a three-decimal alpha and buildings are
    // rgb(); palette colours (dashes, stop lines) are neither.
    const boxFills = (f: string[]) =>
      f.filter((c) => /^rgb\(|^rgba\(\d+,\d+,\d+,\d\.\d{3}\)$/.test(c)).length;
    expect(boxFills(on.fills)).toBeGreaterThan(50);
    expect(boxFills(off.fills)).toBe(0);
  });
});

describe("evidence section", () => {
  it("reports the study's own verdicts and counts", () => {
    render(<Evidence />);
    expect(
      screen.getByRole("heading", { name: /you do not know/i }),
    ).toBeInTheDocument();
    const inconclusive = evidence.deltas.filter(
      (d) => d.verdict === "inconclusive",
    ).length;
    expect(screen.getAllByText("inconclusive")).toHaveLength(inconclusive);
    expect(screen.getAllByText(/indicative only/i).length).toBeGreaterThan(0);
  });
});

describe("landing page", () => {
  it("opens with the application entry points and the story", async () => {
    render(<App />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      /Signal or/,
    );
    expect(screen.getByTestId("link-explore-simulation")).toHaveAttribute(
      "href",
      "/app/comparative",
    );
    expect(screen.getByTestId("link-run-another-scenario")).toHaveAttribute(
      "href",
      "/app/comparative",
    );
    expect(screen.getByTestId("link-plan-study")).toHaveAttribute(
      "href",
      "/app/planner",
    );
    // "Login" is the dashboard's real (Cognito) sign-in, opened on arrival;
    // the landing page no longer carries a placeholder form (F-18).
    expect(screen.getByRole("link", { name: "Login" })).toHaveAttribute(
      "href",
      "/app/comparative?signin=1",
    );
    expect(document.querySelector('input[type="password"]')).toBeNull();
    // The chapter navigation is there for keyboard users of the pinned story.
    expect(
      screen.getByRole("navigation", { name: "Story chapters" }),
    ).toBeInTheDocument();
    await waitFor(() => {
      expect(
        screen.getAllByRole("img", { name: /replayed|recorded/i }).length,
      ).toBeGreaterThan(0);
    });
  });
});
